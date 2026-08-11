# Emplacement : adapters/openai_agents_extractor.py
"""Extracteur OpenAI Agents SDK : Agent natif → WorkflowIR canonique (E:F→A).

Troisième extracteur illustratif, symétrique de LangGraph et CrewAI. L'OpenAI
Agents SDK représente un système multi-agents comme un `Agent` racine portant
des `handoffs` (délégations vers d'autres agents) et des `tools`. Contrairement
au CrewAI Flow — dont la topologie @router/@listen n'est pas introspectable
statiquement et doit être DÉCLARÉE — la structure du SDK est directement lisible
sur les objets :

    agent.name          -> identité du nœud
    agent.instructions  -> prompt (contenu, pas ref ACM)
    agent.model         -> modèle
    agent.tools         -> outils attachés
    agent.handoffs      -> agents-cibles de délégation (arêtes)

Les arêtes de handoff sont donc `extracted` (pas `declared_by_adapter`) : c'est
la différence de conception centrale avec l'extracteur CrewAI Flow, et un point
d'intérêt pour l'article (introspectabilité variable selon le framework, à
périmètre normatif ACM constant).

Comme pour LangGraph, le mapping node→ACI (agent_ref, prompt_ref, model_ref,
tool_refs) n'est PAS déductible du seul objet SDK (le SDK ne connaît que des
chaînes de modèle et des fonctions-outils Python). Ces références sont fournies
par un `agent_metadata` explicite (statut declared_by_adapter), conformément au
principe : ne pas inventer, ne pas omettre, DÉCLARER.

Deux voies d'entrée (deux sémantiques distinctes, goldens distincts) :
  - extract_agent(agent, ...)          : un Agent seul (mono-nœud, symétrique
                                         extract_crew mono) ;
  - extract_agent_graph(agent, ...)    : l'Agent racine + fermeture transitive
                                         de ses handoffs (topologie, symétrique
                                         extract_flow(include_crew=True)).

À EXÉCUTER dans un environnement où openai-agents est installé
(`pip install -e '.[openai_agents]'`). L'introspection reste défensive (getattr,
fallbacks) car les attributs internes peuvent varier selon la version du SDK.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from harness.workflow_ir import (
    EdgeKind,
    ExtractionStatus,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
)


# --------------------------------------------------------------------------
# Sémantique 1 : Agent seul (mono-nœud). Symétrique extract_crew mono-agent.
# --------------------------------------------------------------------------

def extract_agent(
    agent: Any,
    *,
    workflow_id: str = "wf:extracted-openai-agent",
    agent_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    state_schema_keys: Optional[List[str]] = None,
) -> WorkflowIR:
    """Extrait un WorkflowIR d'un `agents.Agent` isolé (sans ses handoffs).

    Un agent seul n'a PAS de topologie : ni entrée/sortie de graphe, ni router,
    ni arête. Il projette un unique nœud AGENT, dont les outils sont extraits
    directement de `agent.tools` et dont les références ACM (agent/prompt/model)
    sont déclarées via `agent_metadata` (non introspectable depuis le SDK).

    Args:
        agent: objet `Agent` du SDK.
        agent_metadata: mapping agent.name → {agent_ref, prompt_ref, model_ref,
            tool_refs}. Non introspectable : declared_by_adapter.
        state_schema_keys: clés d'un éventuel schéma d'état/contexte, si connues.
    """
    agent_metadata = agent_metadata or {}
    ir = WorkflowIR(workflow_id=workflow_id, framework="openai_agents")

    node = _node_from_agent(agent, agent_metadata)
    ir.nodes.append(node)

    # Un agent seul est à la fois entrée et terminaison de son mini-workflow.
    ir.entry_nodes = [node.node_id]
    ir.terminal_nodes = [node.node_id]
    ir.state_schema_keys = list(state_schema_keys) if state_schema_keys else []
    return ir


# --------------------------------------------------------------------------
# Sémantique 2 : Agent + handoffs (graphe). Symétrique extract_flow(+crew).
# --------------------------------------------------------------------------

def extract_agent_graph(
    root_agent: Any,
    *,
    workflow_id: str = "wf:extracted-openai-agent-graph",
    agent_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    state_schema_keys: Optional[List[str]] = None,
) -> WorkflowIR:
    """Extrait un WorkflowIR de l'Agent racine et de la fermeture transitive de
    ses handoffs (le graphe de délégation complet).

    Chaque agent atteignable → un nœud AGENT. Chaque handoff A→B → une arête
    DIRECT `extracted` (le SDK stocke la relation explicitement, elle n'a pas à
    être déclarée — c'est la différence avec CrewAI Flow). Les outils de chaque
    agent sont extraits de `agent.tools`.

    L'entrée est l'agent racine ; les terminaisons sont les agents sans handoff
    sortant (feuilles du graphe de délégation).

    Args:
        root_agent: l'`Agent` de départ (celui passé à Runner.run).
        agent_metadata: mapping agent.name → refs ACM (declared_by_adapter).
        state_schema_keys: clés d'un éventuel schéma de contexte partagé.
    """
    agent_metadata = agent_metadata or {}
    ir = WorkflowIR(workflow_id=workflow_id, framework="openai_agents")

    # Parcours en largeur de la fermeture transitive des handoffs. On indexe par
    # id(objet) pour tolérer des cycles (A délègue à B qui peut re-déléguer à A).
    visited: Dict[int, str] = {}
    order: List[Any] = []
    queue: List[Any] = [root_agent]
    while queue:
        current = queue.pop(0)
        if id(current) in visited:
            continue
        node_id = _agent_node_id(current)
        visited[id(current)] = node_id
        order.append(current)
        for target in _agent_handoffs(current):
            if id(target) not in visited:
                queue.append(target)

    # Nœuds (ordre de découverte, stable pour un même graphe).
    for agent in order:
        ir.nodes.append(_node_from_agent(agent, agent_metadata))

    # Arêtes de handoff : extracted (topologie lisible sur les objets).
    for agent in order:
        src_id = _agent_node_id(agent)
        for target in _agent_handoffs(agent):
            ir.edges.append(WorkflowEdge(
                source=src_id,
                target=_agent_node_id(target),
                kind=EdgeKind.DIRECT,
                status=ExtractionStatus.EXTRACTED,
            ))

    # Entrée = racine ; terminaisons = agents sans handoff sortant.
    ir.entry_nodes = [_agent_node_id(root_agent)]
    has_outgoing = {e.source for e in ir.edges}
    ir.terminal_nodes = sorted(
        n.node_id for n in ir.nodes if n.node_id not in has_outgoing
    )
    ir.state_schema_keys = list(state_schema_keys) if state_schema_keys else []
    return ir


# --------------------------------------------------------------------------
# Construction d'un nœud à partir d'un Agent (partagé par les deux sémantiques).
# --------------------------------------------------------------------------

def _node_from_agent(
    agent: Any, agent_metadata: Dict[str, Dict[str, Any]]
) -> WorkflowNode:
    """Projette un `Agent` du SDK sur un WorkflowNode canonique.

    Les outils sont extraits (`agent.tools` → noms), mais leur MAPPING vers des
    refs ACM (`aci:tool:...`) provient des métadonnées : le SDK ne connaît que
    des fonctions-outils, pas des identités ACM. On applique donc la même règle
    de statut que LangGraph : nœud extrait, refs déclarées si metadata fournie.
    """
    name = _agent_name(agent)
    meta = agent_metadata.get(name, {})
    status = (ExtractionStatus.DECLARED_BY_ADAPTER if meta
              else ExtractionStatus.EXTRACTED)

    # Outils réellement présents sur l'objet (noms introspectés), à titre de
    # diagnostic. Les tool_refs ACM restent ceux des métadonnées.
    native_tool_names = _agent_tool_names(agent)

    return WorkflowNode(
        node_id=_agent_node_id(agent),
        kind=NodeKind.AGENT,
        status=status,
        agent_ref=meta.get("agent_ref"),
        prompt_ref=meta.get("prompt_ref"),
        model_ref=meta.get("model_ref"),
        tool_refs=list(meta.get("tool_refs", [])),
        meta={
            "native_agent": name,
            "native_model": _agent_model(agent),
            "native_tool_names": native_tool_names,
            "handoff_names": [_agent_name(h) for h in _agent_handoffs(agent)],
        },
    )


# --------------------------------------------------------------------------
# Introspection défensive du SDK (attributs susceptibles de varier par version).
# --------------------------------------------------------------------------

def _agent_name(agent: Any) -> str:
    return str(getattr(agent, "name", "") or "agent")


def _agent_node_id(agent: Any) -> str:
    """Identifiant de nœud canonique dérivé du nom de l'agent.

    Préfixé `agent_` pour rester lisible et cohérent avec les conventions des
    autres extracteurs (`task_...`, `flow_...`). Le nom natif reste porté par
    `meta.native_agent`.
    """
    name = _agent_name(agent)
    slug = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()
    return f"agent_{slug}" if slug else "agent"


def _agent_model(agent: Any) -> str:
    """Modèle de l'agent : le SDK accepte une chaîne ou un objet Model.

    On retourne une représentation stable (chaîne si c'est une chaîne, sinon le
    nom de classe / attribut `model` de l'objet).
    """
    model = getattr(agent, "model", None)
    if model is None:
        return ""
    if isinstance(model, str):
        return model
    # Objet Model : tenter un attribut nominal, sinon le nom de classe.
    for attr in ("model", "name", "model_name"):
        val = getattr(model, attr, None)
        if isinstance(val, str) and val:
            return val
    return type(model).__name__


def _agent_tool_names(agent: Any) -> List[str]:
    """Noms des outils attachés à l'agent (`agent.tools`).

    Chaque outil du SDK (FunctionTool, hosted tool…) porte généralement un
    attribut `name` ; sinon on retombe sur le nom de la fonction sous-jacente.
    """
    tools = getattr(agent, "tools", None) or []
    names: List[str] = []
    for t in tools:
        name = getattr(t, "name", None)
        if not name:
            fn = getattr(t, "on_invoke_tool", None) or getattr(t, "func", None)
            name = getattr(fn, "__name__", None)
        names.append(str(name) if name else type(t).__name__)
    return sorted(names)


def _agent_handoffs(agent: Any) -> List[Any]:
    """Agents-cibles de délégation (`agent.handoffs`).

    Le SDK autorise soit un `Agent` directement, soit un objet `Handoff` qui
    encapsule l'agent cible (attribut `agent`). On normalise vers l'agent cible
    pour reconstruire le graphe de délégation ; les entrées non résolubles sont
    ignorées (topologie extractible seulement).
    """
    handoffs = getattr(agent, "handoffs", None) or []
    targets: List[Any] = []
    for h in handoffs:
        # Handoff(agent=...) ou Agent directement.
        target = getattr(h, "agent", None)
        if target is None and getattr(h, "name", None) is not None:
            target = h  # c'est déjà un Agent
        if target is not None:
            targets.append(target)
    return targets
