"""Adaptateur CrewAI — implémentation du port `RuntimeAdapter`.

Symétrique de l'adaptateur LangGraph : mêmes deux couches, mêmes helpers de
gouvernance du cœur, même contrat `RuntimeSignal` en sortie. C'est ce qui
garantit l'équivalence inter-adaptateurs — un même AgentSpec produit le même
verdict et le même digest via LangGraph OU CrewAI.

  1. construire + inspecter (create_instance) : construit un vrai Agent/Crew
     CrewAI à partir d'un AgentSpec pour prouver l'instanciabilité, puis produit
     un RuntimeSignal SANS exécuter de LLM.
  2. exécuter (execute) : lance réellement le Crew avec gpt-5.4, capture le
     résultat terminal, enrichit le signal (mode record possible).

Frontière étanche : aucun objet CrewAI ne fuit dans le RuntimeSignal.
Le contenu métier (sortie du crew) ne traverse jamais la frontière.
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


class CrewAIBuildError(Exception):
    """La construction de l'agent/crew CrewAI a échoué (config non instanciable)."""


class CrewAIAdapter(RuntimeAdapter):
    """Adaptateur CrewAI.

    `llm_factory` et `tool_factory` permettent d'injecter des constructeurs
    réels (couche 2) ou des mocks (tests). En couche 1, l'agent est construit
    mais jamais exécuté.
    """

    name = "crewai"

    def __init__(
        self,
        *,
        build_agent: bool = True,
        llm_factory: Optional[Callable[[str], Any]] = None,
        tool_factory: Optional[Callable[[str], Any]] = None,
    ):
        self._build_agent = build_agent
        self._llm_factory = llm_factory
        self._tool_factory = tool_factory

    # -- Couche 1 : construire + inspecter ---------------------------------

    def create_instance(self, request: Dict[str, Any]) -> RuntimeSignal:
        """Construit (optionnellement) et inspecte une instance CrewAI.

        `request["spec"]` : un AgentSpec (ou dict équivalent).
        N'exécute AUCUN LLM. Produit un RuntimeSignal à l'état `created`.
        """
        spec = request["spec"]
        if not isinstance(spec, AgentSpec):
            spec = AgentSpec.model_validate(spec)

        build_ok = True
        build_error: Optional[str] = None
        if self._build_agent:
            try:
                self._construct_agent(spec)
            except Exception as exc:  # noqa: BLE001
                build_ok = False
                build_error = f"{type(exc).__name__}: {exc}"

        signal = self._signal_from_spec(
            spec, terminal_state=RuntimeTerminalState.CREATED
        )
        if not build_ok:
            signal.adapter_name = f"{self.name} (build_failed: {build_error})"
        return signal

    def _construct_agent(self, spec: AgentSpec) -> Any:
        """Construit un Agent CrewAI à partir de la spec.

        Mapping des dimensions ACM sur CrewAI :
            llm        <- uses_model (spec.model_name)
            tools      <- uses_tool  (spec.tool_names)
            role/goal/ <- uses_prompt / config comportementale
              backstory
        On n'exécute pas : la seule construction prouve l'instanciabilité.
        """
        from crewai import Agent

        llm = self._resolve_llm(spec, executable=False)
        tools = self._resolve_tools(spec, executable=False)

        agent = Agent(
            role=f"instance:{spec.instance_id}",
            goal=spec.prompt_text or "Execute the assigned task.",
            backstory=spec.prompt_text or "A governed dynamic instance.",
            llm=llm,
            tools=tools,
            allow_delegation=spec.delegation_policy_overridden,
            verbose=False,
        )
        return agent

    # -- Couche 2 : exécution réelle (gpt-5.4) + record ---------------------

    def execute(
        self,
        request: Dict[str, Any],
        *,
        task_description: str = "Execute the assigned task.",
        expected_output: str = "A concise result.",
        record_path: Optional[str] = None,
    ) -> RuntimeSignal:
        """Construit ET exécute réellement un Crew mono-agent, puis produit un
        signal enrichi de l'état terminal.

        Nécessite un llm_factory (ou le défaut gpt-5.4) et une clé API. Le
        contenu métier (sortie du crew) ne remonte PAS dans le signal : seule
        la gouvernance traverse la frontière. `record_path` fige le signal en
        JSON pour rejeu déterministe.
        """
        spec = request["spec"]
        if not isinstance(spec, AgentSpec):
            spec = AgentSpec.model_validate(spec)

        terminal = RuntimeTerminalState.COMPLETED
        checks_completed = False
        checks_passed = False
        try:
            self._run_crew(spec, task_description, expected_output)
            checks_completed = True
            checks_passed = True
        except Exception:  # noqa: BLE001
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

    def _run_crew(
        self, spec: AgentSpec, task_description: str, expected_output: str
    ) -> Any:
        """Construit un Crew mono-agent réel et l'exécute une fois.

        Le LLM est résolu via llm_factory, ou par défaut CrewAI utilise le
        modèle nommé (ex. gpt-5.4). La clé API est lue depuis l'environnement
        et ne transite jamais par le RuntimeSignal.
        """
        from crewai import Agent, Crew, Process, Task

        llm = self._resolve_llm(spec, executable=True)
        tools = self._resolve_tools(spec, executable=True)

        agent = Agent(
            role=f"instance:{spec.instance_id}",
            goal=spec.prompt_text or "Execute the assigned task.",
            backstory=spec.prompt_text or "A governed dynamic instance.",
            llm=llm,
            tools=tools,
            allow_delegation=spec.delegation_policy_overridden,
            verbose=False,
        )
        task = Task(
            description=task_description,
            expected_output=expected_output,
            agent=agent,
        )
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        return crew.kickoff()

    # -- Résolution des dépendances ----------------------------------------

    def _resolve_llm(self, spec: AgentSpec, *, executable: bool) -> Any:
        if self._llm_factory is not None:
            return self._llm_factory(spec.model_name or "")
        # CrewAI accepte un identifiant de modèle sous forme de chaîne, aussi
        # bien pour la construction que pour l'exécution (il crée le client).
        # La clé API est lue depuis l'environnement par CrewAI/litellm.
        return spec.model_name or "gpt-5.4"

    def _resolve_tools(self, spec: AgentSpec, *, executable: bool) -> List[Any]:
        if self._tool_factory is not None:
            return [self._tool_factory(name) for name in spec.tool_names]
        # En l'absence de fabrique d'outils, on construit sans outils : les
        # noms d'outils restent portés par la gouvernance (spec.tool_names ->
        # permission_check), indépendamment de l'instanciation CrewAI.
        return []

    # -- Signal ------------------------------------------------------------

    def _signal_from_spec(
        self,
        spec: AgentSpec,
        *,
        terminal_state: RuntimeTerminalState,
        runtime_checks_completed: bool = False,
        runtime_checks_passed: bool = False,
    ) -> RuntimeSignal:
        """Assemble le RuntimeSignal via les helpers de gouvernance du cœur.

        Identique à l'adaptateur LangGraph : c'est le partage de ces helpers
        qui garantit l'équivalence inter-adaptateurs (même verdict, même digest).
        """
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
