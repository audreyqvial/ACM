"""Adaptateur LangGraph — implémentation du port `RuntimeAdapter`.

Deux couches :
  1. construire + inspecter (create_instance) : construit un vrai graphe
     LangGraph à partir d'un AgentSpec pour vérifier que la config est
     instanciable, puis produit un RuntimeSignal SANS exécuter de LLM.
  2. exécuter (execute) : lance réellement le graphe avec un modèle (gpt-5.4),
     capture le résultat terminal et enrichit le signal (mode record possible).

Frontière étanche : aucun objet LangGraph ne fuit dans le RuntimeSignal.
Le cœur ne voit qu'un RuntimeSignal sérialisable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ports.runtime_adapter import RuntimeAdapter

from acm.runtime.governance import (
    digest_of_resolved_config,
    permission_check_from_spec,
    resolved_config_from_spec,
    traceability_from_spec,
)
from acm.runtime.signal import RuntimeSignal, RuntimeTerminalState
from acm.runtime.spec import AgentSpec


class LangGraphBuildError(Exception):
    """La construction du graphe LangGraph a échoué (config non instanciable)."""


class LangGraphAdapter(RuntimeAdapter):
    """Adaptateur LangGraph.

    En couche 1, `create_instance` construit un node/graphe et inspecte sa
    config sans exécuter. `tool_factory` et `model_factory` permettent
    d'injecter des constructeurs réels (couche 2) ou des mocks (tests).
    """

    name = "langgraph"

    def __init__(
        self,
        *,
        build_graph: bool = True,
        model_factory: Optional[Callable[[str], Any]] = None,
        tool_factory: Optional[Callable[[str], Any]] = None,
    ):
        # build_graph=False permet de produire le signal sans même construire
        # le graphe (utile si langgraph n'est pas installé dans un contexte donné).
        self._build_graph = build_graph
        self._model_factory = model_factory
        self._tool_factory = tool_factory

    # -- Couche 1 : construire + inspecter ---------------------------------

    def create_instance(self, request: Dict[str, Any]) -> RuntimeSignal:
        """Construit (optionnellement) et inspecte une instance.

        `request["spec"]` : un AgentSpec (ou dict équivalent).
        Ne exécute AUCUN LLM. Produit un RuntimeSignal à l'état terminal
        `created`.
        """
        spec = request["spec"]
        if not isinstance(spec, AgentSpec):
            spec = AgentSpec.model_validate(spec)

        # Construction réelle du graphe pour prouver l'instanciabilité.
        # Toute erreur de construction est un signal de config invalide, mais
        # ne doit pas masquer la gouvernance : on la capture.
        build_ok = True
        build_error: Optional[str] = None
        if self._build_graph:
            try:
                self._construct_graph(spec)
            except Exception as exc:  # noqa: BLE001 - on veut tout capturer
                build_ok = False
                build_error = f"{type(exc).__name__}: {exc}"

        signal = self._signal_from_spec(
            spec, terminal_state=RuntimeTerminalState.CREATED
        )
        # Une construction échouée n'invente pas de verdict de gouvernance ;
        # elle est reportée comme note d'adaptateur. Le cœur reste seul juge.
        if not build_ok:
            signal.adapter_name = f"{self.name} (build_failed: {build_error})"
        return signal

    def _construct_graph(self, spec: AgentSpec) -> Any:
        """Construit un graphe LangGraph minimal à partir de la spec.

        On utilise l'API stable StateGraph plutôt que le prebuilt
        create_react_agent (déprécié en LangGraph v1). L'objectif de la
        couche 1 est de PROUVER que la config résolue se câble en un graphe
        exécutable, pas de l'exécuter : on construit un node par agent, on
        y attache la config résolue, et on compile.

        Un modèle et des outils sont résolus (réels via factories, ou inertes)
        pour vérifier qu'ils sont bien fournis et cohérents avec la spec.
        """
        from langgraph.graph import END, START, StateGraph

        model = self._resolve_model(spec, executable=False)
        tools = self._resolve_tools(spec, executable=False)
        prompt = spec.prompt_text or ""

        # État minimal : liste de messages (convention LangGraph).
        def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            # Node inerte en couche 1 : ne s'exécute pas réellement.
            # Sa seule raison d'être est de prouver l'instanciabilité.
            _ = (model, tools, prompt)  # capture la config résolue
            return state

        builder: StateGraph = StateGraph(dict)
        node_name = _safe_node_name(spec.instance_id)
        builder.add_node(node_name, agent_node)
        builder.add_edge(START, node_name)
        builder.add_edge(node_name, END)

        compiled = builder.compile()
        return compiled

    # -- Couche 2 : exécution réelle (gpt-5.4) + record ---------------------

    def execute(
        self,
        request: Dict[str, Any],
        *,
        inputs: Optional[Dict[str, Any]] = None,
        record_path: Optional[str] = None,
    ) -> RuntimeSignal:
        """Construit ET exécute réellement le graphe, puis produit un signal
        enrichi de l'état terminal.

        Nécessite un model_factory (ou le défaut OpenAI) et une clé API. Le
        résultat terminal (completed/failed) est reporté dans le signal. Si
        `record_path` est fourni, le signal est figé en JSON (mode record) pour
        rejeu déterministe ultérieur.

        Le contenu métier de l'exécution (réponses LLM) ne remonte PAS dans le
        signal : seule la gouvernance (config, traçabilité, permissions, état
        terminal) traverse la frontière.
        """
        spec = request["spec"]
        if not isinstance(spec, AgentSpec):
            spec = AgentSpec.model_validate(spec)

        terminal = RuntimeTerminalState.COMPLETED
        checks_completed = False
        checks_passed = False
        try:
            self._run_graph(spec, inputs or {"messages": []})
            checks_completed = True
            checks_passed = True
        except Exception:  # noqa: BLE001 - un échec d'exécution -> failed
            terminal = RuntimeTerminalState.FAILED

        signal = self._signal_from_spec(
            spec,
            terminal_state=terminal,
            runtime_checks_completed=checks_completed,
            runtime_checks_passed=checks_passed,
        )

        if record_path is not None:
            import json
            with open(record_path, "w", encoding="utf-8") as fh:
                json.dump(signal.to_record(), fh, indent=2, ensure_ascii=False)

        return signal

    def _run_graph(self, spec: AgentSpec, inputs: Dict[str, Any]) -> Any:
        """Construit un graphe exécutable réel et l'invoque une fois.

        Le modèle est résolu via model_factory, ou par défaut via
        langchain-openai avec spec.model_name (ex. gpt-5.4). La clé API est
        lue par le client OpenAI depuis l'environnement — elle ne transite
        jamais par le RuntimeSignal.
        """
        from langgraph.graph import END, START, StateGraph
        from langchain_core.messages import SystemMessage

        model = self._resolve_model(spec, executable=True)
        node_name = _safe_node_name(spec.instance_id)
        system_prompt = spec.prompt_text or ""

        def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            messages = state.get("messages", [])
            full = ([SystemMessage(content=system_prompt)] if system_prompt else []) + list(messages)
            response = model.invoke(full)
            return {"messages": list(messages) + [response]}

        builder: StateGraph = StateGraph(dict)
        builder.add_node(node_name, agent_node)
        builder.add_edge(START, node_name)
        builder.add_edge(node_name, END)
        compiled = builder.compile()

        return compiled.invoke(inputs)

    # -- Construction des dépendances (mock en couche 1) -------------------

    def _resolve_model(self, spec: AgentSpec, *, executable: bool) -> Any:
        if self._model_factory is not None:
            return self._model_factory(spec.model_name or "")
        if not executable:
            # Modèle inerte pour l'inspection (couche 1) : porte une identité.
            return _InertModel(spec.model_name or "inert-model")
        # Couche 2 : vrai modèle OpenAI (ex. gpt-5.4). La clé API est lue par
        # le client depuis l'environnement (OPENAI_API_KEY) et ne transite
        # jamais par le RuntimeSignal.
        from langchain_openai import ChatOpenAI

        model_name = spec.model_name or "gpt-5.4"
        return ChatOpenAI(model=model_name)

    def _resolve_tools(self, spec: AgentSpec, *, executable: bool) -> List[Any]:
        if self._tool_factory is not None:
            return [self._tool_factory(name) for name in spec.tool_names]
        if not executable:
            return [_inert_tool(name) for name in spec.tool_names]
        raise LangGraphBuildError(
            "Aucun tool_factory fourni pour une exécution réelle."
        )

    # -- Signal ------------------------------------------------------------

    def _signal_from_spec(
        self,
        spec: AgentSpec,
        *,
        terminal_state: RuntimeTerminalState,
        runtime_checks_completed: bool = False,
        runtime_checks_passed: bool = False,
    ) -> RuntimeSignal:
        """Assemble le RuntimeSignal via les helpers de gouvernance du cœur."""
        resolved = resolved_config_from_spec(spec)
        return RuntimeSignal(
            instance_id=spec.instance_id,
            definition_ref=spec.template_ref,
            resolved_config=resolved,
            resolved_config_digest=digest_of_resolved_config(resolved),
            traceability=traceability_from_spec(spec),
            permissions=permission_check_from_spec(spec),
            terminal_state=terminal_state,
            runtime_checks_completed=runtime_checks_completed,
            runtime_checks_passed=runtime_checks_passed,
            adapter_name=self.name,
            produced_at=datetime.now(timezone.utc),
        )


# --- Stubs inertes pour la couche 1 (aucune exécution) ---------------------

class _InertModel:
    """Modèle factice : porte une identité, n'exécute rien.

    En couche 1 (StateGraph inerte), il suffit qu'il porte un nom : le node
    ne l'invoque pas. En couche 2, un vrai modèle est injecté via model_factory.
    """

    def __init__(self, name: str):
        self.name = name

    def invoke(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("InertModel ne s'exécute pas (couche 1).")


def _inert_tool(name: str):
    """Outil factice minimal : un simple objet nommé (non exécuté en couche 1)."""
    return {"name": name, "inert": True}


def _safe_node_name(instance_id: str) -> str:
    """LangGraph réserve certains caractères (':', ...) dans les noms de node.

    On dérive un nom de node sûr pour la construction interne ; l'instance_id
    original reste porté tel quel par le RuntimeSignal.
    """
    safe = instance_id.replace(":", "_").replace("/", "_").replace("@", "_")
    return safe or "instance"
