# Emplacement : tests/test_openai_agents_extraction.py
"""Tests de l'extracteur OpenAI Agents SDK — AVEC LE FRAMEWORK INSTALLÉ.

Symétriques de tests/test_workflow_extractors_native.py. Construisent de VRAIS
objets `agents.Agent` (agent seul, puis graphe de handoffs non trivial), valident
l'extraction contre les goldens et mesurent la fidélité/perte d'information.
SKIPPÉS automatiquement si openai-agents n'est pas installé.

Point de conception vérifié ici : contrairement au CrewAI Flow, la topologie de
handoffs du SDK est INTROSPECTABLE — les arêtes sont `extracted`, jamais
`declared_by_adapter`, et aucun `unresolved_elements` de topologie n'est produit.
"""
import pytest

from harness.extraction_oracle import evaluate_extraction
from harness.information_loss import LossStatus, measure_information_loss
from harness.workflow_ir import EdgeKind, ExtractionStatus, NodeKind
from scenarios.workflow_golden import (
    golden_openai_agent,
    golden_openai_agent_graph,
)
from scenarios.native_workflows import (
    OPENAI_AGENTS_METADATA,
    build_native_openai_agent,
    build_native_openai_agent_graph,
)


# ============================================================ Agent seul (sémantique 1)

def test_openai_agent_single_is_mononode():
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent

    native = build_native_openai_agent()
    ir = extract_agent(native, workflow_id="wf:research-agent",
                       agent_metadata=OPENAI_AGENTS_METADATA)

    agents_nodes = [n for n in ir.nodes if n.kind == NodeKind.AGENT]
    assert len(agents_nodes) == 1, "un agent seul -> un unique nœud"
    assert not ir.edges, "un agent seul n'a pas d'arête"
    # Entrée == terminaison == le nœud lui-même.
    assert ir.entry_nodes == ir.terminal_nodes == ["agent_researcher"]


def test_openai_agent_single_matches_golden():
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent

    native = build_native_openai_agent()
    extracted = extract_agent(native, workflow_id="wf:research-agent",
                              agent_metadata=OPENAI_AGENTS_METADATA)
    golden = golden_openai_agent()
    metrics = evaluate_extraction(golden, extracted)

    assert metrics.entry_preserved, metrics.to_dict()
    assert metrics.terminal_preserved, metrics.to_dict()
    assert set(extracted.agent_ids()) == set(golden.agent_ids())
    # L'outil déclaré du researcher doit être projeté (agent_tool_refs).
    assert "aci:tool:web-search" in extracted.tool_ids()


# ============================================================ Graphe de handoffs (sémantique 2)

def test_openai_agent_graph_extracts_handoff_edges():
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent_graph

    native = build_native_openai_agent_graph()
    ir = extract_agent_graph(native, workflow_id="wf:research-agent-graph",
                             agent_metadata=OPENAI_AGENTS_METADATA)

    # Cinq agents atteignables via la fermeture transitive des handoffs.
    agent_nodes = [n for n in ir.nodes if n.kind == NodeKind.AGENT]
    assert len(agent_nodes) == 5, [n.node_id for n in agent_nodes]

    # Les arêtes de handoff sont EXTRAITES (topologie lisible), pas déclarées.
    direct = [e for e in ir.edges if e.kind == EdgeKind.DIRECT]
    assert len(direct) == 4, [(e.source, e.target) for e in direct]
    assert all(e.status == ExtractionStatus.EXTRACTED for e in direct)


def test_openai_agent_graph_no_declared_topology():
    """Différence-clé vs CrewAI Flow : aucune arête declared_by_adapter, aucun
    unresolved_elements de topologie — le SDK est statiquement introspectable."""
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent_graph

    native = build_native_openai_agent_graph()
    ir = extract_agent_graph(native, agent_metadata=OPENAI_AGENTS_METADATA)

    declared = [e for e in ir.edges
                if e.status == ExtractionStatus.DECLARED_BY_ADAPTER]
    assert not declared, "les handoffs sont extraits, pas déclarés"
    topo_unresolved = [u for u in ir.unresolved_elements
                       if "topology" in str(u.get("kind", ""))]
    assert not topo_unresolved, "aucune topologie non résolue attendue"


def test_openai_agent_graph_matches_golden():
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent_graph

    native = build_native_openai_agent_graph()
    extracted = extract_agent_graph(native, workflow_id="wf:research-agent-graph",
                                    agent_metadata=OPENAI_AGENTS_METADATA)
    golden = golden_openai_agent_graph()
    metrics = evaluate_extraction(golden, extracted)

    assert metrics.entry_preserved, metrics.to_dict()
    assert metrics.terminal_preserved, metrics.to_dict()
    assert metrics.node_coverage == 1.0, metrics.to_dict()
    assert metrics.relation_coverage == 1.0, metrics.to_dict()
    assert set(extracted.agent_ids()) == set(golden.agent_ids())


def test_openai_agent_graph_lossless_on_topology():
    """Sur le périmètre topologique, l'extraction du graphe est sans perte
    (agent_set, entry, terminal, node_identities, direct_edges préservés)."""
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent_graph

    native = build_native_openai_agent_graph()
    extracted = extract_agent_graph(native, agent_metadata=OPENAI_AGENTS_METADATA)
    golden = golden_openai_agent_graph()
    report = measure_information_loss(golden, extracted)

    unsupported = report.by_status(LossStatus.UNSUPPORTED)
    assert not unsupported, [r.to_dict() for r in unsupported]


# ============================================================ deux sémantiques distinctes

def test_two_openai_semantics_are_distinct():
    """Agent-seul et Agent-graphe produisent des IR distincts et cohérents.

    - Agent seul : un nœud, aucune arête ;
    - Agent + handoffs : plusieurs nœuds reliés par des arêtes de handoff.
    """
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent, extract_agent_graph

    single = extract_agent(build_native_openai_agent(),
                           agent_metadata=OPENAI_AGENTS_METADATA)
    graph = extract_agent_graph(build_native_openai_agent_graph(),
                                agent_metadata=OPENAI_AGENTS_METADATA)

    assert len(single.nodes) == 1 and not single.edges
    assert len(graph.nodes) > 1 and graph.edges
    assert single.digest() != graph.digest()


def test_openai_agent_graph_digest_stable():
    """Le digest de l'extraction du graphe est stable sur extraction répétée."""
    pytest.importorskip("agents")
    from adapters.openai_agents_extractor import extract_agent_graph

    native = build_native_openai_agent_graph()
    d1 = extract_agent_graph(native, agent_metadata=OPENAI_AGENTS_METADATA).digest()
    d2 = extract_agent_graph(native, agent_metadata=OPENAI_AGENTS_METADATA).digest()
    assert d1 == d2


# ============================================================ portabilité croisée

def test_cross_framework_agent_equivalence_three_frameworks():
    """Les trois extractions natives projettent le même noyau d'agents ACM.

    Revendication de portabilité au niveau EXTRACTION étendue à openai-agents :
    LangGraph, CrewAI et le SDK OpenAI normalisent vers le même ensemble
    d'agents ACM (researcher, reviewer, finalizer).
    """
    pytest.importorskip("langgraph")
    pytest.importorskip("crewai")
    pytest.importorskip("agents")
    from adapters.crewai_extractor import extract_crew
    from adapters.langgraph_extractor import extract_langgraph
    from adapters.openai_agents_extractor import extract_agent_graph
    from scenarios.native_workflows import (
        CREWAI_METADATA, LANGGRAPH_METADATA,
        build_native_crewai, build_native_langgraph,
    )

    lg = extract_langgraph(build_native_langgraph(), node_metadata=LANGGRAPH_METADATA)
    cw = extract_crew(build_native_crewai(), agent_metadata=CREWAI_METADATA)
    oa = extract_agent_graph(build_native_openai_agent_graph(),
                             agent_metadata=OPENAI_AGENTS_METADATA)

    common = set(lg.agent_ids()) & set(cw.agent_ids()) & set(oa.agent_ids())
    assert {"aci:agent:researcher", "aci:agent:reviewer",
            "aci:agent:finalizer"} <= common


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
