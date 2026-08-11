# Emplacement : adapters/langgraph_extractor.py
"""Extracteur LangGraph : StateGraph natif → WorkflowIR canonique (E:F→A).

Lit un objet LangGraph compilé (ou son builder) et produit la représentation ACM
canonique. LangGraph expose sa topologie de façon introspectable : nœuds, arêtes,
arêtes conditionnelles, point d'entrée. Cet extracteur privilégie l'extraction
directe et marque explicitement ce qui reste opaque.

À EXÉCUTER dans un environnement où langgraph est installé
(`pip install -e '.[langgraph]'`). L'introspection s'appuie sur les attributs
internes du graphe compilé ; ils peuvent varier selon la version de LangGraph —
d'où la robustesse défensive (getattr, fallbacks) et le marquage `unresolved`
quand un élément n'est pas atteignable.

Le mapping node→ACI (agent_ref, prompt_ref…) n'est PAS introspectable depuis le
graphe seul : LangGraph ne connaît que des fonctions Python. Ces références sont
donc fournies par un `node_metadata` explicite (statut declared_by_adapter),
conformément aux notes de conception (« documenter ce qui nécessite des
métadonnées explicites »).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from harness.workflow_ir import (
    EdgeKind,
    ExtractionStatus,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
)

# Noms des sentinelles LangGraph.
_START = "__start__"
_END = "__end__"


def extract_langgraph(
    compiled_or_builder: Any,
    *,
    workflow_id: str = "wf:extracted-langgraph",
    node_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    state_schema_keys: Optional[list[str]] = None,
) -> WorkflowIR:
    """Extrait un WorkflowIR d'un StateGraph LangGraph.

    Args:
        compiled_or_builder: un `CompiledStateGraph` (résultat de `.compile()`)
            ou un `StateGraph` builder. On tente d'accéder au graphe sous-jacent.
        node_metadata: mapping node_name → {agent_ref, prompt_ref, model_ref,
            tool_refs}. Ces liens ne sont pas introspectables et sont donc
            `declared_by_adapter`.
        state_schema_keys: clés du schéma d'état, si connues.
    """
    node_metadata = node_metadata or {}
    graph = _resolve_graph(compiled_or_builder)

    ir = WorkflowIR(workflow_id=workflow_id, framework="langgraph")

    # --- nœuds ---------------------------------------------------------------
    raw_nodes = _get_nodes(graph)
    for name in raw_nodes:
        if name in (_START, _END):
            continue
        meta = node_metadata.get(name, {})
        # Statut : si des métadonnées ACM sont fournies, le lien est déclaré ;
        # le nœud lui-même est extrait.
        status = (ExtractionStatus.DECLARED_BY_ADAPTER if meta
                  else ExtractionStatus.EXTRACTED)
        kind = _infer_kind(name, meta)
        ir.nodes.append(WorkflowNode(
            node_id=name, kind=kind, status=status,
            agent_ref=meta.get("agent_ref"),
            prompt_ref=meta.get("prompt_ref"),
            model_ref=meta.get("model_ref"),
            tool_refs=list(meta.get("tool_refs", [])),
            meta={"native_node": name},
        ))

    # entry/terminal sentinelles matérialisées comme nœuds ACM.
    ir.nodes.append(WorkflowNode("entry", NodeKind.ENTRY))
    ir.nodes.append(WorkflowNode("end", NodeKind.TERMINAL))

    # --- arêtes directes -----------------------------------------------------
    for src, dst in _get_edges(graph):
        s = "entry" if src == _START else src
        d = "end" if dst == _END else dst
        ir.edges.append(WorkflowEdge(s, d, EdgeKind.DIRECT))

    # --- arêtes conditionnelles (branches) -----------------------------------
    for src, targets, label in _get_conditional_edges(graph):
        s = "entry" if src == _START else src
        mapped_targets = ["end" if t == _END else t for t in targets]
        # La condition elle-même est une fonction Python : sémantique OPAQUE.
        for t in mapped_targets:
            ir.edges.append(WorkflowEdge(
                source=s, target=t, kind=EdgeKind.CONDITIONAL,
                status=ExtractionStatus.EXTRACTED,
                condition_label=label,
                condition_semantics="opaque",
                possible_targets=mapped_targets,
            ))
        if label:
            ir.unresolved_elements.append({
                "kind": "conditional_function",
                "at_node": s,
                "representation": label,
                "semantics": "opaque",
                "possible_targets": mapped_targets,
            })

    # --- entrée / sorties ----------------------------------------------------
    ir.entry_nodes = ["entry"]
    ir.terminal_nodes = ["end"]
    if state_schema_keys:
        ir.state_schema_keys = list(state_schema_keys)
    else:
        ir.state_schema_keys = _infer_state_keys(graph)

    return ir


# --------------------------------------------------------------------------
# Introspection défensive (les attributs internes varient selon la version).
# --------------------------------------------------------------------------

def _resolve_graph(obj: Any) -> Any:
    """Retourne l'objet portant nodes/edges (builder ou graphe compilé)."""
    for attr in ("graph", "builder", "get_graph"):
        candidate = getattr(obj, attr, None)
        if callable(candidate):
            try:
                return candidate()
            except Exception:
                continue
        if candidate is not None:
            return candidate
    return obj


def _get_nodes(graph: Any) -> list[str]:
    nodes = getattr(graph, "nodes", None)
    if nodes is None:
        return []
    try:
        return list(nodes.keys()) if hasattr(nodes, "keys") else [
            getattr(n, "id", str(n)) for n in nodes
        ]
    except Exception:
        return []


def _get_edges(graph: Any) -> list[tuple[str, str]]:
    edges = getattr(graph, "edges", None) or []
    result: list[tuple[str, str]] = []
    for e in edges:
        # set d'arêtes (tuples) ou objets Edge.
        if isinstance(e, tuple) and len(e) >= 2:
            result.append((str(e[0]), str(e[1])))
        else:
            src = getattr(e, "source", None)
            dst = getattr(e, "target", None)
            if src is not None and dst is not None and not getattr(e, "conditional", False):
                result.append((str(src), str(dst)))
    return result


def _get_conditional_edges(graph: Any) -> list[tuple[str, list[str], Optional[str]]]:
    """Extrait (source, cibles_possibles, label) des arêtes conditionnelles."""
    result: list[tuple[str, list[str], Optional[str]]] = []
    # LangGraph stocke souvent les branches dans `branches[node][name]`.
    branches = getattr(graph, "branches", None)
    if isinstance(branches, dict):
        for node, by_name in branches.items():
            try:
                for name, branch in by_name.items():
                    ends = getattr(branch, "ends", None) or {}
                    targets = list(ends.values()) if isinstance(ends, dict) else list(ends or [])
                    result.append((str(node), [str(t) for t in targets], str(name)))
            except Exception:
                continue
    # Fallback : arêtes marquées conditional=True.
    for e in getattr(graph, "edges", []) or []:
        if getattr(e, "conditional", False):
            src = getattr(e, "source", None)
            dst = getattr(e, "target", None)
            if src is not None and dst is not None:
                result.append((str(src), [str(dst)], None))
    return result


def _infer_kind(name: str, meta: Dict[str, Any]) -> NodeKind:
    if meta.get("agent_ref"):
        return NodeKind.AGENT
    lowered = name.lower()
    if "rout" in lowered or "branch" in lowered:
        return NodeKind.ROUTER
    return NodeKind.OTHER


def _infer_state_keys(graph: Any) -> list[str]:
    schema = getattr(graph, "schema", None) or getattr(graph, "state_schema", None)
    if schema is None:
        return []
    annotations = getattr(schema, "__annotations__", None)
    if isinstance(annotations, dict):
        return sorted(annotations.keys())
    return []
