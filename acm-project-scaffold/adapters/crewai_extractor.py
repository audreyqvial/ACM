# Emplacement : adapters/crewai_extractor.py
"""Extracteur CrewAI : Crew / Flow natif → WorkflowIR canonique (E:F→A).

CrewAI distribue sa configuration entre objets Python (Agent, Task, Crew, Flow)
et éventuellement des fichiers YAML (agents.yaml, tasks.yaml). Contrairement à
LangGraph, la topologie n'est pas un graphe explicite : elle se déduit des
Task.context (dépendances de contexte) et des routes du Flow. L'extracteur
documente donc soigneusement ce qui est `extracted` vs `declared_by_adapter`.

À EXÉCUTER dans un environnement où crewai est installé
(`pip install -e '.[crewai]'`). L'introspection s'appuie sur les attributs des
objets CrewAI ; ils varient selon la version, d'où la robustesse défensive.

Deux voies d'entrée :
  - extract_crew(crew, ...)  : un objet Crew (agents + tasks + process) ;
  - extract_flow(flow, ...)  : un objet Flow (routing steps + crews).
Le mapping agent→ACI (agent_ref, prompt_ref, model_ref) n'est pas déductible du
rôle seul : il est fourni par `agent_metadata` explicite (declared_by_adapter).
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


def extract_crew(
    crew: Any,
    *,
    workflow_id: str = "wf:extracted-crewai",
    agent_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    flow: Any = None,
) -> WorkflowIR:
    """Extrait un WorkflowIR d'un Crew CrewAI (et optionnellement de son Flow).

    Args:
        crew: objet `Crew` (porte agents, tasks, process).
        agent_metadata: mapping role → {agent_ref, prompt_ref, model_ref,
            tool_refs}. Non introspectable depuis le rôle : declared_by_adapter.
        flow: objet `Flow` optionnel pour extraire routing steps et branches.
    """
    agent_metadata = agent_metadata or {}
    ir = WorkflowIR(workflow_id=workflow_id, framework="crewai")

    _merge_crew_into(ir, crew, agent_metadata)

    # --- Flow : routing steps + branches (si fourni) -------------------------
    if flow is not None:
        _extract_flow_into(ir, flow, {}, flow_metadata=None)

    # --- entrée / sorties ----------------------------------------------------
    # Sans Flow explicite, l'entrée est la première tâche sans dépendance
    # entrante, la sortie la dernière sans dépendance sortante.
    if not ir.entry_nodes:
        ir.entry_nodes = _infer_entry_nodes(ir)
    if not ir.terminal_nodes:
        ir.terminal_nodes = _infer_terminal_nodes(ir)

    ir.state_schema_keys = _get_flow_state_keys(flow) if flow is not None else []
    return ir


def _reclassify_terminals(ir: WorkflowIR) -> None:
    """Reclasse en TERMINAL les nœuds génériques (OTHER) sans arête sortante.

    Appelé APRÈS que toutes les arêtes sont posées. Un listener de Flow qui
    n'émet vers rien est une terminaison (ex. finish_from_research). On ne touche
    ni aux agents, ni aux routers, ni aux tâches.
    """
    has_outgoing = {e.source for e in ir.edges}
    for n in ir.nodes:
        if n.kind == NodeKind.OTHER and n.node_id not in has_outgoing:
            n.kind = NodeKind.TERMINAL


def _apply_declared_edges(ir: WorkflowIR, flow_edges: List[Dict[str, Any]]) -> None:
    """Applique des arêtes DÉCLARÉES (declared_by_adapter) au IR d'un Flow.

    Utilisé quand la topologie du Flow n'est pas introspectable statiquement.
    ANTI-SILENCE : chaque arête déclarée est marquée declared_by_adapter, et on
    enregistre dans unresolved_elements que la topologie du Flow a dû être
    déclarée faute d'introspection.
    """
    for spec in flow_edges:
        kind_str = str(spec.get("kind", "direct")).lower()
        kind = EdgeKind.CONDITIONAL if kind_str == "conditional" else EdgeKind.DIRECT
        ir.edges.append(WorkflowEdge(
            source=str(spec["source"]),
            target=str(spec["target"]),
            kind=kind,
            status=ExtractionStatus.DECLARED_BY_ADAPTER,
            condition_label=spec.get("condition_label"),
            condition_semantics="opaque" if kind == EdgeKind.CONDITIONAL else "n/a",
            possible_targets=list(spec.get("possible_targets", [])),
        ))
    ir.unresolved_elements.append({
        "kind": "flow_topology",
        "representation": "flow_edges",
        "semantics": "declared",
        "reason": "les arêtes du Flow ne sont pas introspectables statiquement "
                  "dans cette version de CrewAI (topologie résolue à l'exécution) ; "
                  "elles ont été fournies par métadonnées (declared_by_adapter)",
        "declared_edge_count": len(flow_edges),
    })


def _merge_crew_into(ir: WorkflowIR, crew: Any,
                     agent_metadata: Dict[str, Dict[str, Any]]) -> None:
    """Fusionne les tâches d'un Crew et leurs dépendances de contexte dans l'IR.

    Une Task = un nœud (kind=task). Task.context = dépendances de contexte
    (arêtes context). Partagé entre extract_crew (Crew-only) et extract_flow
    (Flow+Crew).
    """
    tasks = _get_tasks(crew)
    task_ids: Dict[int, str] = {}

    for i, task in enumerate(tasks):
        node_id = _task_id(task, i)
        task_ids[id(task)] = node_id
        role = _agent_role(_task_agent(task))
        meta = agent_metadata.get(role, {})
        status = (ExtractionStatus.DECLARED_BY_ADAPTER if meta
                  else ExtractionStatus.EXTRACTED)
        ir.nodes.append(WorkflowNode(
            node_id=node_id, kind=NodeKind.TASK, status=status,
            agent_ref=meta.get("agent_ref"),
            prompt_ref=meta.get("prompt_ref"),
            model_ref=meta.get("model_ref"),
            tool_refs=list(meta.get("tool_refs", [])),
            meta={"role": role, "expected_output": _expected_output(task)},
        ))

    for task in tasks:
        target_id = task_ids.get(id(task))
        for ctx in _task_context(task):
            source_id = task_ids.get(id(ctx))
            if source_id and target_id:
                ir.edges.append(WorkflowEdge(
                    source=source_id, target=target_id,
                    kind=EdgeKind.CONTEXT_DEPENDENCY,
                    status=ExtractionStatus.EXTRACTED,
                ))


def extract_flow(
    flow: Any,
    *,
    workflow_id: str = "wf:extracted-crewai-flow",
    flow_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    flow_edges: Optional[List[Dict[str, Any]]] = None,
    agent_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    include_crew: bool = True,
) -> WorkflowIR:
    """Extrait un WorkflowIR d'un CrewAI Flow (topologie @start/@router/@listen).

    Le Flow est traité comme objet de PREMIER ORDRE. Les NŒUDS et leur rôle
    (start/router/listen) sont extraits directement de `flow._methods`. Les
    ARÊTES (qui écoute qui, labels du router) ne sont PAS toujours introspectables
    statiquement : selon la version de CrewAI, la topologie est résolue à
    l'exécution et n'est stockée nulle part sur les wrappers/méthodes. Dans ce
    cas, les arêtes doivent être fournies par `flow_edges` (declared_by_adapter),
    conformément au principe : ne pas inventer, ne pas omettre, DÉCLARER.

    Args:
        flow_metadata: mapping méthode_de_flow → refs ACM (declared_by_adapter).
        flow_edges: arêtes déclarées quand l'introspection ne les fournit pas.
            Chaque entrée : {"source", "target", "kind", "condition_label"?,
            "possible_targets"?}. kind ∈ {"direct","conditional"}.
        agent_metadata: mapping role → refs ACM, pour le Crew éventuel.
        include_crew: si False, extraction Flow-only (topologie seule).
    """
    flow_metadata = flow_metadata or {}
    agent_metadata = agent_metadata or {}

    ir = WorkflowIR(workflow_id=workflow_id, framework="crewai")

    # 1. Topologie du Flow (nœuds + arêtes introspectables si disponibles).
    _extract_flow_into(ir, flow, {}, flow_metadata=flow_metadata)

    # 1b. Arêtes déclarées : appliquées si l'introspection n'en a pas produit.
    #     ANTI-SILENCE : on enregistre que ces arêtes sont déclarées, pas extraites.
    if flow_edges and not any(e for e in ir.edges):
        _apply_declared_edges(ir, flow_edges)

    # 2. Crew référencé par le Flow (optionnel — cas Flow+Crew).
    if include_crew:
        crew = _first_crew_of_flow(flow)
        if crew is not None:
            _merge_crew_into(ir, crew, agent_metadata)

    if not ir.entry_nodes:
        ir.entry_nodes = _infer_entry_nodes(ir)
    # Reclasser en TERMINAL les nœuds génériques (OTHER) sans arête sortante,
    # MAINTENANT que toutes les arêtes (extraites ou déclarées) sont posées.
    _reclassify_terminals(ir)
    # Recalcule les terminaux MAINTENANT que les arêtes (extraites ou déclarées)
    # sont posées, pour ne pas classer terminaux des nœuds qui ont une sortie.
    ir.terminal_nodes = _infer_terminal_nodes(ir)
    ir.state_schema_keys = _get_flow_state_keys(flow)
    return ir


# --------------------------------------------------------------------------
# Introspection défensive CrewAI.
# --------------------------------------------------------------------------

def _get_agents(crew: Any) -> List[Any]:
    return list(getattr(crew, "agents", None) or [])


def _get_tasks(crew: Any) -> List[Any]:
    return list(getattr(crew, "tasks", None) or [])


def _task_id(task: Any, index: int) -> str:
    name = getattr(task, "name", None)
    if name:
        return f"task_{name}"
    desc = getattr(task, "description", None)
    if desc:
        slug = "".join(c if c.isalnum() else "_" for c in str(desc)[:24]).strip("_")
        return f"task_{slug}".lower()
    return f"task_{index}"


def _task_agent(task: Any) -> Any:
    return getattr(task, "agent", None)


def _agent_role(agent: Any) -> str:
    if agent is None:
        return ""
    return str(getattr(agent, "role", "") or "")


def _expected_output(task: Any) -> str:
    return str(getattr(task, "expected_output", "") or "")


def _task_context(task: Any) -> List[Any]:
    """Task.context = liste de tâches dont celle-ci dépend (dépendance amont).

    CrewAI n'utilise PAS None quand context est absent : il pose un objet
    sentinelle (_NotSpecified) qui est truthy mais non itérable. On ne retient
    donc que les vraies listes/tuples.
    """
    ctx = getattr(task, "context", None)
    if isinstance(ctx, (list, tuple)):
        return list(ctx)
    return []


def _extract_flow_into(ir: WorkflowIR, flow: Any, task_ids: Dict[int, str],
                       flow_metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    """Ajoute au IR la topologie d'un CrewAI Flow (@start / @router / @listen).

    CrewAI expose la structure du Flow via des attributs internes :
      - flow._start_methods   : noms des méthodes @start ;
      - flow._routers         : noms des méthodes @router ;
      - flow._listeners       : {method: (condition_type, [triggers])} ;
      - flow._router_paths    : {router: [labels possibles]} (selon version).

    Principe ANTI-SILENCE : tout élément détecté mais non pleinement
    reconstructible est ENREGISTRÉ (nœud + unresolved_elements avec raison),
    jamais omis. La logique de routage elle-même est opaque par nature.
    """
    flow_metadata = flow_metadata or {}

    start_methods = _flow_start_methods(flow)
    routers = _flow_routers(flow)
    listeners = _flow_listeners(flow)  # {method: (condition_type, [triggers])}

    known_nodes: set[str] = set()

    # --- @start → nœud d'entrée ---------------------------------------------
    for m in start_methods:
        node_id = f"flow_{m}"
        ir.nodes.append(WorkflowNode(node_id, NodeKind.ENTRY,
                                     status=ExtractionStatus.EXTRACTED,
                                     meta={"flow_method": m}))
        ir.entry_nodes.append(node_id)
        known_nodes.add(node_id)

    # --- @router → nœud de branchement --------------------------------------
    for m in routers:
        node_id = f"flow_{m}"
        ir.nodes.append(WorkflowNode(node_id, NodeKind.ROUTER,
                                     status=ExtractionStatus.EXTRACTED,
                                     meta={"flow_method": m}))
        known_nodes.add(node_id)

    # --- @listen → nœuds de branche + arêtes --------------------------------
    # Chaque listener écoute un ou plusieurs triggers (méthode amont ou label).
    for method, (cond_type, triggers) in listeners.items():
        node_id = f"flow_{method}"
        meta = flow_metadata.get(method, {})
        # Un listener avec réf ACM est un nœud agent ; sinon c'est un nœud de
        # flow générique (OTHER), PAS une tâche de crew — les tâches (kind=TASK)
        # ne viennent que d'un Crew fusionné, ce qui garde Flow-only et Crew-only
        # distincts.
        kind = NodeKind.AGENT if meta.get("agent_ref") else NodeKind.OTHER
        status = (ExtractionStatus.DECLARED_BY_ADAPTER if meta
                  else ExtractionStatus.EXTRACTED)
        if node_id not in known_nodes:
            ir.nodes.append(WorkflowNode(
                node_id, kind, status=status,
                agent_ref=meta.get("agent_ref"),
                prompt_ref=meta.get("prompt_ref"),
                model_ref=meta.get("model_ref"),
                tool_refs=list(meta.get("tool_refs", [])),
                meta={"flow_method": method, "condition_type": cond_type},
            ))
            known_nodes.add(node_id)

        for trig in triggers:
            src_id = f"flow_{trig}"
            # Si le trigger est un LABEL de router (pas une méthode), l'arête
            # part du router qui émet ce label.
            emitting_router = _router_emitting_label(flow, trig)
            if emitting_router:
                src_id = f"flow_{emitting_router}"
                ir.edges.append(WorkflowEdge(
                    source=src_id, target=node_id, kind=EdgeKind.CONDITIONAL,
                    status=ExtractionStatus.EXTRACTED,
                    condition_label=str(trig),
                    condition_semantics="opaque",
                    possible_targets=_router_labels(flow, emitting_router),
                ))
            else:
                # Trigger = méthode amont : arête directe (ou conditionnelle si
                # cond_type l'indique, ex. "or"/"and" restent des flux directs).
                ir.edges.append(WorkflowEdge(
                    source=src_id, target=node_id, kind=EdgeKind.DIRECT,
                    status=ExtractionStatus.EXTRACTED,
                ))

    # --- routers : enregistrer branches + opacité (ANTI-SILENCE) ------------
    for m in routers:
        node_id = f"flow_{m}"
        labels = _router_labels(flow, m)
        if labels:
            ir.unresolved_elements.append({
                "kind": "flow_router",
                "at_node": node_id,
                "representation": f"route_{m}",
                "semantics": "opaque",
                "reason": "la logique de routage est une fonction Python non "
                          "introspectable ; seuls les labels de sortie sont extraits",
                "possible_targets": sorted(labels),
            })
        else:
            # Router détecté mais labels non extractibles : NE PAS omettre.
            ir.unresolved_elements.append({
                "kind": "flow_router",
                "at_node": node_id,
                "representation": f"route_{m}",
                "semantics": "opaque",
                "reason": "router détecté mais labels de sortie non introspectables "
                          "dans cette version de CrewAI",
                "possible_targets": [],
            })

    # --- terminaisons : nœuds sans arête sortante ---------------------------
    if not ir.terminal_nodes:
        has_outgoing = {e.source for e in ir.edges}
        terminals = sorted(
            n.node_id for n in ir.nodes
            if n.node_id not in has_outgoing and n.kind != NodeKind.ENTRY
        )
        ir.terminal_nodes = terminals


# --------------------------------------------------------------------------
# Introspection Flow — attributs internes CrewAI, avec fallbacks défensifs.
#
# CrewAI (versions récentes) expose la structure via un dict unique
# `flow._methods = {name: <wrapper>}` où le wrapper est une instance de
# StartMethod / RouterMethod / ListenMethod. Le rôle se lit sur le NOM DE CLASSE
# du wrapper. Les triggers d'un ListenMethod et les paths d'un RouterMethod sont
# lus défensivement (les noms d'attributs varient selon la version).
# --------------------------------------------------------------------------

def _flow_method_wrappers(flow: Any) -> Dict[str, Any]:
    """Retourne {method_name: wrapper} depuis flow._methods (ou {})."""
    methods = getattr(flow, "_methods", None)
    if isinstance(methods, dict):
        return dict(methods)
    return {}


def _wrapper_kind(wrapper: Any) -> str:
    """Rôle d'un wrapper via son nom de classe : start / router / listen / other."""
    cls = type(wrapper).__name__.lower()
    if "start" in cls:
        return "start"
    if "router" in cls:
        return "router"
    if "listen" in cls:
        return "listen"
    return "other"


def _wrapper_attr(wrapper: Any, *names: str) -> Any:
    """Premier attribut non nul trouvé parmi `names` sur le wrapper."""
    for n in names:
        val = getattr(wrapper, n, None)
        if val is not None:
            return val
    return None


def _flow_methods(flow: Any) -> List[str]:
    """Noms des méthodes publiques et callables du Flow (fallback générique)."""
    try:
        return [n for n in dir(flow) if not n.startswith("_")
                and callable(getattr(flow, n, None))]
    except Exception:
        return []


def _flow_start_methods(flow: Any) -> List[str]:
    wrappers = _flow_method_wrappers(flow)
    if wrappers:
        return [name for name, w in wrappers.items() if _wrapper_kind(w) == "start"]
    # Anciennes versions : attribut dédié, puis marqueurs de méthode.
    val = getattr(flow, "_start_methods", None)
    if val:
        return [str(m) for m in val]
    return [n for n in _flow_methods(flow)
            if _method_has_attr(flow, n, "__is_start_method__")]


def _flow_routers(flow: Any) -> List[str]:
    wrappers = _flow_method_wrappers(flow)
    if wrappers:
        return [name for name, w in wrappers.items() if _wrapper_kind(w) == "router"]
    val = getattr(flow, "_routers", None)
    if val:
        if isinstance(val, dict):
            return [str(k) for k in val.keys()]
        return [str(m) for m in val]
    return [n for n in _flow_methods(flow)
            if _method_has_attr(flow, n, "__is_router__")]


def _scan_for_string_list(wrapper: Any) -> List[str]:
    """Cherche une liste de labels/triggers dans un wrapper de Flow CrewAI.

    Les ListenMethod/RouterMethod n'exposent souvent QUE ._instance, ._meth et
    .unwrap() ; les triggers/paths sont attachés par les décorateurs @listen/
    @router à la MÉTHODE sous-jacente (._meth, sa __func__, ou le résultat de
    unwrap()), pas au wrapper. On explore tous ces objets, robuste aux noms.
    """
    candidates: List[Any] = [wrapper]

    # Fonction décorée / méthode sous-jacente sous divers noms.
    for fn_attr in ("__wrapped__", "func", "method", "fn", "_func", "_meth",
                    "_method", "callback", "_callback", "_original", "original"):
        fn = getattr(wrapper, fn_attr, None)
        if fn is not None:
            candidates.append(fn)
            # __func__ d'une méthode liée porte les attributs du décorateur.
            inner = getattr(fn, "__func__", None)
            if inner is not None:
                candidates.append(inner)

    # Résultat de unwrap() s'il existe (méthode non liée d'origine).
    unwrap = getattr(wrapper, "unwrap", None)
    if callable(unwrap):
        try:
            u = unwrap()
            if u is not None:
                candidates.append(u)
                inner = getattr(u, "__func__", None)
                if inner is not None:
                    candidates.append(inner)
        except Exception:
            pass

    _EXCLUDE = {"instance", "_instance", "state", "_state", "flow", "_flow", "self"}
    _ALLOW_DUNDER_HINTS = ("trigger", "listen", "path", "router", "condition", "method")
    best: List[str] = []
    seen_ids: set[int] = set()
    for obj in candidates:
        if id(obj) in seen_ids:
            continue
        seen_ids.add(id(obj))
        for attr in dir(obj):
            if attr in _EXCLUDE:
                continue
            if attr.startswith("__"):
                low = attr.lower()
                if not any(h in low for h in _ALLOW_DUNDER_HINTS):
                    continue
            try:
                val = getattr(obj, attr)
            except Exception:
                continue
            if callable(val):
                continue
            items: List[Any] = []
            if isinstance(val, (list, tuple, set)):
                items = list(val)
            elif isinstance(val, dict):
                items = list(val.keys())
            else:
                continue
            if not items:
                continue
            names = [_trigger_name(x) for x in items
                     if isinstance(x, str) or callable(x) or hasattr(x, "__name__")]
            if names and len(names) == len(items) and len(names) > len(best):
                best = names
    return best


def _flow_listeners(flow: Any) -> Dict[str, tuple]:
    """Retourne {method_name: (condition_type, [triggers])}.

    Depuis flow._methods : chaque ListenMethod porte ses triggers. On tente
    d'abord des noms connus, puis un BALAYAGE générique des attributs pour
    rester robuste aux variations de version.
    """
    wrappers = _flow_method_wrappers(flow)
    if wrappers:
        result: Dict[str, tuple] = {}
        for name, w in wrappers.items():
            if _wrapper_kind(w) != "listen":
                continue
            triggers = _wrapper_attr(
                w, "trigger_methods", "triggers", "listen_to", "conditions",
                "__trigger_methods__", "methods",
            )
            trig_list: List[str] = []
            if isinstance(triggers, (list, tuple, set)):
                trig_list = [_trigger_name(t) for t in triggers]
            elif triggers is not None:
                trig_list = [_trigger_name(triggers)]
            # Fallback robuste : balayage générique si rien trouvé par nom.
            if not trig_list:
                trig_list = _scan_for_string_list(w)
            cond = _wrapper_attr(w, "condition_type", "condition", "__condition_type__") or "or"
            result[name] = (str(cond), trig_list)
        return result
    # Anciennes versions.
    val = getattr(flow, "_listeners", None)
    if isinstance(val, dict):
        out: Dict[str, tuple] = {}
        for method, spec in val.items():
            if isinstance(spec, tuple) and len(spec) == 2:
                cond_type, triggers = spec
                out[str(method)] = (str(cond_type), [str(t) for t in triggers])
            elif isinstance(spec, (list, tuple, set)):
                out[str(method)] = ("or", [str(t) for t in spec])
            else:
                out[str(method)] = ("or", [str(spec)])
        return out
    return {}


def _trigger_name(trigger: Any) -> str:
    """Nom d'un trigger : une méthode (→ son __name__), une string (→ label)."""
    if isinstance(trigger, str):
        return trigger
    name = getattr(trigger, "__name__", None)
    if name:
        return str(name)
    return str(trigger)


def _router_labels(flow: Any, router_method: str) -> List[str]:
    """Labels de sortie possibles d'un router.

    Depuis flow._methods : le RouterMethod porte ses paths/labels. On tente des
    noms connus, puis un BALAYAGE générique.
    """
    wrappers = _flow_method_wrappers(flow)
    w = wrappers.get(router_method)
    if w is not None:
        paths = _wrapper_attr(w, "paths", "router_paths", "labels", "possible_paths",
                              "__router_paths__")
        if isinstance(paths, (list, tuple, set)):
            return [str(x) for x in paths]
        if isinstance(paths, dict):
            return [str(x) for x in paths.keys()]
        # Fallback robuste : balayage générique.
        scanned = _scan_for_string_list(w)
        if scanned:
            return scanned
    # Anciennes versions.
    paths = getattr(flow, "_router_paths", None)
    if isinstance(paths, dict) and router_method in paths:
        return [str(x) for x in paths[router_method]]
    return []


def _router_emitting_label(flow: Any, label: str) -> Optional[str]:
    """Retourne le router qui émet `label`, si `label` est bien un label."""
    for r in _flow_routers(flow):
        if label in _router_labels(flow, r):
            return r
    return None


def _method_has_attr(flow: Any, method_name: str, attr: str) -> bool:
    method = getattr(flow, method_name, None)
    return method is not None and getattr(method, attr, None) is not None
    try:
        return [n for n in dir(flow) if not n.startswith("_")
                and callable(getattr(flow, n, None))]
    except Exception:
        return []


def _get_flow_state_keys(flow: Any) -> List[str]:
    state = getattr(flow, "state", None)
    if state is None:
        return []
    annotations = getattr(type(state), "__annotations__", None)
    if isinstance(annotations, dict):
        return sorted(annotations.keys())
    if isinstance(state, dict):
        return sorted(state.keys())
    return []


def _first_crew_of_flow(flow: Any) -> Any:
    for name in dir(flow):
        try:
            val = getattr(flow, name)
        except Exception:
            continue
        if val.__class__.__name__ == "Crew":
            return val
    return None


def _infer_entry_nodes(ir: WorkflowIR) -> List[str]:
    has_incoming = {e.target for e in ir.edges}
    entries = [n.node_id for n in ir.nodes
               if n.node_id not in has_incoming and n.kind != NodeKind.TERMINAL]
    return sorted(entries) if entries else []


def _infer_terminal_nodes(ir: WorkflowIR) -> List[str]:
    has_outgoing = {e.source for e in ir.edges}
    terminals = [n.node_id for n in ir.nodes
                 if n.node_id not in has_outgoing and n.kind != NodeKind.ENTRY]
    return sorted(terminals) if terminals else []
