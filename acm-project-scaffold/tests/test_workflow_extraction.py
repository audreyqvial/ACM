# Emplacement : tests/test_workflow_extraction.py
"""Tests de la strate mesurable des workflows non triviaux (vague 1.b).

Ces tests s'exécutent SANS les frameworks : ils valident la couche de mesure
(WorkflowIR canonique, taxonomie de perte, oracle) sur des structures
représentatives et sur des extractions simulées (golden dégradé). Les extracteurs
natifs (langgraph_extractor, crewai_extractor) sont testés séparément dans un
environnement avec frameworks — voir tests/test_workflow_extractors_native.py.

Principe de simulation : on part du golden et on le DÉGRADE de façons ciblées pour
vérifier que measure_information_loss classe correctement :
  - suppression d'un outil       → tool_set/agent_tool_refs non préservés ;
  - perte du schéma d'état        → state_schema unsupported ;
  - perte des branches            → conditional_branches non préservé.
"""
from __future__ import annotations

import copy

from harness.extraction_oracle import evaluate_extraction
from harness.information_loss import (
    LossStatus,
    NORMATIVE_SCOPE,
    measure_information_loss,
)
from harness.workflow_ir import EdgeKind, ExtractionStatus, NodeKind, WorkflowIR
from scenarios.workflow_golden import (
    golden_crewai,
    golden_crewai_flow,
    golden_langgraph,
    golden_openai_agent,
    golden_openai_agent_graph,
)


# ---------------------------------------------------------------- golden sain

def test_langgraph_golden_self_is_lossless_except_opaque():
    """Golden vs lui-même : tout preserved sauf les branches (approx par nature)."""
    g = golden_langgraph()
    report = measure_information_loss(g, g)
    unsupported = report.by_status(LossStatus.UNSUPPORTED)
    assert unsupported == [], "aucune propriété ne doit être unsupported sur le golden"
    approx = {r.name for r in report.by_status(LossStatus.APPROXIMATED)}
    # Seules les branches conditionnelles sont approximées par nature.
    assert approx == {"conditional_branches"}


def test_crewai_golden_self_is_lossless_except_opaque():
    g = golden_crewai()
    report = measure_information_loss(g, g)
    assert report.by_status(LossStatus.UNSUPPORTED) == []
    approx = {r.name for r in report.by_status(LossStatus.APPROXIMATED)}
    assert approx == {"conditional_branches"}


def test_openai_agent_golden_self_is_lossless_except_opaque():
    """Golden Agent seul vs lui-même : rien d'unsupported, seules les branches
    (vides ici) sont approximées par nature."""
    g = golden_openai_agent()
    report = measure_information_loss(g, g)
    assert report.by_status(LossStatus.UNSUPPORTED) == []
    approx = {r.name for r in report.by_status(LossStatus.APPROXIMATED)}
    assert approx == {"conditional_branches"}


def test_openai_agent_graph_golden_self_is_lossless_except_opaque():
    """Golden graphe de handoffs vs lui-même : idem, la topologie de handoffs
    est en arêtes directes, donc aucune perte hors branches (vides)."""
    g = golden_openai_agent_graph()
    report = measure_information_loss(g, g)
    assert report.by_status(LossStatus.UNSUPPORTED) == []
    approx = {r.name for r in report.by_status(LossStatus.APPROXIMATED)}
    assert approx == {"conditional_branches"}


def test_normative_scope_is_complete():
    """Le périmètre normatif couvre les propriétés clés des notes de conception."""
    names = {p.name for p in NORMATIVE_SCOPE}
    for required in ["agent_set", "tool_set", "entry_nodes", "terminal_nodes",
                     "conditional_branches", "context_dependencies",
                     "agent_prompt_refs", "agent_tool_refs", "state_schema"]:
        assert required in names


# ---------------------------------------------------------------- dégradations

def _degrade_remove_tool(g: WorkflowIR) -> WorkflowIR:
    """Simule une extraction qui rate l'outil d'un agent."""
    d = copy.deepcopy(g)
    for n in d.nodes:
        n.tool_refs = []
    return d


def _degrade_lose_state(g: WorkflowIR) -> WorkflowIR:
    """Simule une extraction qui ne récupère pas le schéma d'état."""
    d = copy.deepcopy(g)
    d.state_schema_keys = []
    return d


def _degrade_lose_branches(g: WorkflowIR) -> WorkflowIR:
    """Simule une extraction qui aplatit les branches conditionnelles."""
    d = copy.deepcopy(g)
    for e in d.edges:
        if e.kind == EdgeKind.CONDITIONAL:
            e.kind = EdgeKind.DIRECT
            e.possible_targets = []
    return d


def test_missing_tool_is_detected_as_loss():
    g = golden_langgraph()
    degraded = _degrade_remove_tool(g)
    report = measure_information_loss(g, degraded)
    statuses = {r.name: r.status for r in report.results}
    # tool_set devient unsupported (plus aucun outil extrait), agent_tool_refs aussi.
    assert statuses["tool_set"] == LossStatus.UNSUPPORTED
    assert statuses["agent_tool_refs"] == LossStatus.UNSUPPORTED
    assert not report.is_lossless


def test_lost_state_schema_is_unsupported():
    g = golden_langgraph()
    degraded = _degrade_lose_state(g)
    report = measure_information_loss(g, degraded)
    statuses = {r.name: r.status for r in report.results}
    assert statuses["state_schema"] == LossStatus.UNSUPPORTED


def test_flattened_branches_are_approximated_or_lost():
    g = golden_langgraph()
    degraded = _degrade_lose_branches(g)
    report = measure_information_loss(g, degraded)
    statuses = {r.name: r.status for r in report.results}
    # Les branches conditionnelles ne sont plus présentes → unsupported.
    assert statuses["conditional_branches"] == LossStatus.UNSUPPORTED


# ---------------------------------------------------------------- oracle

def test_extraction_metrics_perfect_on_golden():
    g = golden_langgraph()
    metrics = evaluate_extraction(g, g)
    assert metrics.node_coverage == 1.0
    assert metrics.relation_coverage == 1.0
    assert metrics.entry_preserved is True
    assert metrics.terminal_preserved is True
    assert metrics.branch_coverage == 1.0
    assert metrics.agent_prompt_ref_coverage == 1.0


def test_extraction_metrics_degraded_tool():
    g = golden_langgraph()
    degraded = _degrade_remove_tool(g)
    metrics = evaluate_extraction(g, degraded)
    # La couverture des références outil chute (l'agent researcher perd son outil).
    assert metrics.agent_tool_ref_coverage < 1.0
    # Mais entry/terminal restent préservés.
    assert metrics.entry_preserved is True
    assert metrics.terminal_preserved is True


# ---------------------------------------------------------------- digest stable

def test_digest_is_stable_across_rebuilds():
    """Deux constructions du même golden donnent le même digest (canonicité)."""
    assert golden_langgraph().digest() == golden_langgraph().digest()
    assert golden_crewai().digest() == golden_crewai().digest()


def test_digest_independent_of_node_order():
    """Le digest est invariant à l'ordre d'insertion des nœuds/arêtes."""
    g1 = golden_langgraph()
    g2 = golden_langgraph()
    g2.nodes.reverse()
    g2.edges.reverse()
    assert g1.digest() == g2.digest()


def test_langgraph_and_crewai_share_agent_set():
    """LangGraph et le Flow CrewAI, d'intention équivalente, partagent leurs agents.

    C'est la démonstration de portabilité au niveau extraction : deux expressions
    natives BRANCHÉES (LangGraph conditionnel / CrewAI Flow) projettent des agents
    ACM cohérents. La comparaison se fait avec le Flow — et non le Crew séquentiel,
    qui n'a pas la même structure de branchement. Les agents du Flow sont un
    sous-ensemble de ceux du LangGraph (reviewer/finalizer vivent dans le Research
    Crew, pas dans les nœuds du Flow), et les outils coïncident.
    """
    lg = golden_langgraph()
    flow = golden_crewai_flow()
    # Les agents portés par les nœuds du Flow sont tous présents côté LangGraph.
    assert set(flow.agent_ids()) <= set(lg.agent_ids())
    # Agents-clés partagés par les deux expressions branchées.
    assert {"aci:agent:researcher", "aci:agent:direct"} <= set(lg.agent_ids())
    assert {"aci:agent:researcher", "aci:agent:direct"} <= set(flow.agent_ids())
    # Les outils coïncident exactement.
    assert lg.tool_ids() == flow.tool_ids()


# ---------------------------------------------------------------- anti-silence

class _MockFlow:
    """Faux Flow minimal : un start, un router SANS labels introspectables.

    Sert à vérifier le principe ANTI-SILENCE sans dépendre de crewai : même
    quand les labels de sortie du router ne sont pas extractibles, le router
    doit être enregistré dans unresolved_elements avec une raison — jamais omis.
    """
    _start_methods = ["begin"]
    _routers = ["route_request"]
    _listeners = {}          # aucun listener introspectable
    _router_paths = {}       # labels NON extractibles

    def begin(self): return None
    def route_request(self): return None


def test_anti_silence_router_without_labels_is_recorded():
    """Un router dont les labels ne sont pas extractibles est classé, pas omis."""
    from adapters.crewai_extractor import extract_flow

    ir = extract_flow(_MockFlow(), workflow_id="wf:mock", include_crew=False)

    routers = [u for u in ir.unresolved_elements if u.get("kind") == "flow_router"]
    assert routers, "le router doit être enregistré même sans labels"
    for r in routers:
        assert r["semantics"] == "opaque"
        assert r["reason"], "chaque élément non extractible porte une raison"
        # Le nœud router lui-même doit exister dans l'IR (pas d'omission).
    from harness.workflow_ir import NodeKind
    assert any(n.kind == NodeKind.ROUTER for n in ir.nodes)


def test_anti_silence_router_node_present_even_when_opaque():
    """Le nœud router est matérialisé dans l'IR même si sa logique est opaque."""
    from adapters.crewai_extractor import extract_flow
    from harness.workflow_ir import NodeKind

    ir = extract_flow(_MockFlow(), include_crew=False)
    router_nodes = [n for n in ir.nodes if n.kind == NodeKind.ROUTER]
    assert len(router_nodes) == 1
    assert router_nodes[0].node_id == "flow_route_request"


# ------------------------------------------------- extracteur openai-agents (sans SDK)

class _FakeTool:
    """Faux outil du SDK OpenAI : porte simplement un `name` (comme FunctionTool)."""

    def __init__(self, name: str):
        self.name = name


class _FakeAgent:
    """Faux `agents.Agent` minimal : attributs directs name/model/tools/handoffs.

    Le SDK OpenAI expose sa structure par attributs directs (contrairement au
    Flow CrewAI, non introspectable) ; l'extracteur openai-agents peut donc être
    testé SANS installer le SDK, avec un double pur-Python — dans l'esprit du
    _MockFlow ci-dessus pour l'anti-silence CrewAI.
    """

    def __init__(self, name, tools=None, handoffs=None):
        self.name = name
        self.instructions = ""
        self.model = "gpt-5.4"
        self.tools = tools or []
        self.handoffs = handoffs or []


def _fake_single_agent():
    """Un researcher isolé portant un outil (miroir de build_native_openai_agent)."""
    return _FakeAgent("researcher", tools=[_FakeTool("web_search")])


def _fake_agent_graph():
    """triage → {researcher → reviewer → finalizer | direct} (miroir du graphe natif)."""
    finalizer = _FakeAgent("finalizer")
    reviewer = _FakeAgent("reviewer", handoffs=[finalizer])
    researcher = _FakeAgent("researcher", tools=[_FakeTool("web_search")],
                            handoffs=[reviewer])
    direct = _FakeAgent("direct")
    return _FakeAgent("triage", handoffs=[researcher, direct])


_OPENAI_METADATA = {
    "triage": {"agent_ref": "aci:agent:triage", "prompt_ref": "aci:prompt:triage",
               "model_ref": "aci:model:shared-llm"},
    "researcher": {"agent_ref": "aci:agent:researcher", "prompt_ref": "aci:prompt:research",
                   "model_ref": "aci:model:shared-llm", "tool_refs": ["aci:tool:web-search"]},
    "reviewer": {"agent_ref": "aci:agent:reviewer", "prompt_ref": "aci:prompt:review",
                 "model_ref": "aci:model:shared-llm"},
    "finalizer": {"agent_ref": "aci:agent:finalizer", "prompt_ref": "aci:prompt:finalize",
                  "model_ref": "aci:model:shared-llm"},
    "direct": {"agent_ref": "aci:agent:direct", "prompt_ref": "aci:prompt:direct",
               "model_ref": "aci:model:shared-llm"},
}


def test_openai_extract_agent_matches_golden_without_sdk():
    """extract_agent sur un double pur-Python reproduit le golden Agent seul."""
    from adapters.openai_agents_extractor import extract_agent

    ir = extract_agent(_fake_single_agent(), workflow_id="wf:research-agent",
                       agent_metadata=_OPENAI_METADATA)
    metrics = evaluate_extraction(golden_openai_agent(), ir)
    assert metrics.node_coverage == 1.0
    assert metrics.relation_coverage == 1.0
    assert metrics.entry_preserved is True
    assert metrics.terminal_preserved is True
    assert set(ir.agent_ids()) == set(golden_openai_agent().agent_ids())
    assert "aci:tool:web-search" in ir.tool_ids()
    # Un agent seul n'a pas d'arête.
    assert ir.edges == []


def test_openai_extract_graph_matches_golden_without_sdk():
    """extract_agent_graph sur un double pur-Python reproduit le golden graphe."""
    from adapters.openai_agents_extractor import extract_agent_graph

    ir = extract_agent_graph(_fake_agent_graph(),
                             workflow_id="wf:research-agent-graph",
                             agent_metadata=_OPENAI_METADATA)
    metrics = evaluate_extraction(golden_openai_agent_graph(), ir)
    assert metrics.node_coverage == 1.0
    assert metrics.relation_coverage == 1.0
    assert metrics.entry_preserved is True
    assert metrics.terminal_preserved is True
    assert set(ir.agent_ids()) == set(golden_openai_agent_graph().agent_ids())


def test_openai_handoff_edges_are_extracted_not_declared():
    """Différence de conception vs CrewAI Flow : les arêtes de handoff sont
    EXTRAITES (topologie introspectable), jamais declared_by_adapter, et aucune
    topologie ne reste unresolved."""
    from adapters.openai_agents_extractor import extract_agent_graph

    ir = extract_agent_graph(_fake_agent_graph(), agent_metadata=_OPENAI_METADATA)
    assert ir.edges, "le graphe doit produire des arêtes de handoff"
    assert all(e.status == ExtractionStatus.EXTRACTED for e in ir.edges)
    topo_unresolved = [u for u in ir.unresolved_elements
                       if "topology" in str(u.get("kind", ""))]
    assert not topo_unresolved, "aucune topologie non résolue pour le SDK OpenAI"


def test_openai_agent_graph_handles_cycles():
    """La fermeture transitive des handoffs tolère les cycles (A↔B) sans boucler."""
    from adapters.openai_agents_extractor import extract_agent_graph

    a = _FakeAgent("a")
    b = _FakeAgent("b", handoffs=[a])
    a.handoffs = [b]
    ir = extract_agent_graph(a)
    assert len(ir.nodes) == 2, "chaque agent visité une seule fois malgré le cycle"
    assert {("agent_a", "agent_b"), ("agent_b", "agent_a")} == {
        (e.source, e.target) for e in ir.edges
    }


def test_openai_two_semantics_are_distinct_without_sdk():
    """Agent seul et graphe produisent des IR distincts (digests différents)."""
    from adapters.openai_agents_extractor import extract_agent, extract_agent_graph

    single = extract_agent(_fake_single_agent(), agent_metadata=_OPENAI_METADATA)
    graph = extract_agent_graph(_fake_agent_graph(), agent_metadata=_OPENAI_METADATA)
    assert len(single.nodes) == 1 and not single.edges
    assert len(graph.nodes) > 1 and graph.edges
    assert single.digest() != graph.digest()


def test_openai_missing_tool_is_detected_as_loss():
    """Un researcher extrait sans son outil dégrade tool_set/agent_tool_refs."""
    from adapters.openai_agents_extractor import extract_agent

    # Métadonnées SANS tool_refs pour le researcher → l'outil ACM est perdu.
    meta_no_tool = dict(_OPENAI_METADATA)
    meta_no_tool["researcher"] = {k: v for k, v in _OPENAI_METADATA["researcher"].items()
                                  if k != "tool_refs"}
    ir = extract_agent(_fake_single_agent(), agent_metadata=meta_no_tool)
    report = measure_information_loss(golden_openai_agent(), ir)
    statuses = {r.name: r.status for r in report.results}
    assert statuses["tool_set"] == LossStatus.UNSUPPORTED
    assert statuses["agent_tool_refs"] == LossStatus.UNSUPPORTED
    assert not report.is_lossless


# ------------------------------------------------- portabilité (trois goldens)

def test_three_goldens_share_agent_core():
    """LangGraph, CrewAI Flow et le graphe OpenAI partagent le noyau d'agents ACM.

    Version « golden » (sans framework) de la portabilité croisée à trois : les
    trois représentations d'intention équivalente projettent le même noyau
    researcher/reviewer/finalizer sur le périmètre normatif ACM.
    """
    lg = set(golden_langgraph().agent_ids())
    oa = set(golden_openai_agent_graph().agent_ids())
    # Le Flow CrewAI ne porte que researcher/direct sur ses nœuds (reviewer et
    # finalizer vivent dans le Research Crew) ; on compare donc au niveau LangGraph
    # et OpenAI, qui matérialisent le pipeline complet en nœuds.
    core = {"aci:agent:researcher", "aci:agent:reviewer", "aci:agent:finalizer"}
    assert core <= lg
    assert core <= oa
    assert core <= (lg & oa)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
