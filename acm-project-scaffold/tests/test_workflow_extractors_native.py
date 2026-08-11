# Emplacement : tests/test_workflow_extractors_native.py
"""Tests des extracteurs natifs — À EXÉCUTER AVEC LES FRAMEWORKS INSTALLÉS.

Ces tests construisent de VRAIS workflows LangGraph/CrewAI non triviaux (branche
conditionnelle, dépendances de tâches) puis valident l'extraction contre le
golden oracle et mesurent la perte d'information. Ils sont SKIPPÉS automatiquement
si langgraph/crewai ne sont pas installés (comme dans l'environnement de
développement de la strate mesurable).

Dans un environnement avec `pip install -e '.[langgraph,crewai]'`, ces tests
produisent les chiffres de fidélité d'extraction pour l'article.
"""
import pytest

from harness.extraction_oracle import evaluate_extraction
from harness.information_loss import LossStatus, measure_information_loss
from scenarios.workflow_golden import golden_crewai, golden_langgraph

# Constructeurs de workflows natifs et métadonnées partagés avec le générateur de
# rapport (scenarios/native_workflows.py). Voir ce module pour la note sur
# WorkflowState / get_type_hints.
from scenarios.native_workflows import (
    CREWAI_METADATA as _CREWAI_METADATA,
    LANGGRAPH_METADATA as _LANGGRAPH_METADATA,
    LANGGRAPH_STATE_KEYS,
    build_native_crewai as _build_native_crewai,
    build_native_langgraph as _build_native_langgraph,
)


# ============================================================ LangGraph

def test_langgraph_extraction_preserves_topology():
    pytest.importorskip("langgraph")
    from adapters.langgraph_extractor import extract_langgraph

    native = _build_native_langgraph()
    extracted = extract_langgraph(
        native, workflow_id="wf:research-pipeline",
        node_metadata=_LANGGRAPH_METADATA,
        state_schema_keys=LANGGRAPH_STATE_KEYS,
    )
    golden = golden_langgraph()
    metrics = evaluate_extraction(golden, extracted)

    assert metrics.entry_preserved, metrics.to_dict()
    assert metrics.terminal_preserved, metrics.to_dict()
    assert set(extracted.agent_ids()) == set(golden.agent_ids())


def test_langgraph_extraction_reports_opaque_conditions():
    pytest.importorskip("langgraph")
    from adapters.langgraph_extractor import extract_langgraph

    native = _build_native_langgraph()
    extracted = extract_langgraph(native, node_metadata=_LANGGRAPH_METADATA)
    assert extracted.unresolved_elements, "les conditions opaques doivent être signalées"
    assert all(u["semantics"] == "opaque" for u in extracted.unresolved_elements)


# ============================================================ CrewAI

def test_crewai_extraction_captures_context_dependencies():
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_crew

    native = _build_native_crewai()
    extracted = extract_crew(native, workflow_id="wf:research-pipeline",
                             agent_metadata=_CREWAI_METADATA)
    # Les dépendances de contexte entre tâches doivent être extraites.
    from harness.workflow_ir import EdgeKind
    context_edges = [e for e in extracted.edges if e.kind == EdgeKind.CONTEXT_DEPENDENCY]
    assert len(context_edges) >= 2, "research→review et review→finalize attendues"


def test_crewai_extraction_covers_agent_set():
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_crew

    native = _build_native_crewai()
    extracted = extract_crew(native, agent_metadata=_CREWAI_METADATA)
    # Les trois agents du crew doivent être présents.
    for agent_ref in ["aci:agent:researcher", "aci:agent:reviewer", "aci:agent:finalizer"]:
        assert agent_ref in extracted.agent_ids()


# ============================================================ CrewAI Flow (non trivial)

def test_crewai_flow_extraction_topology():
    """Extraction d'un vrai Flow non trivial : nœuds, entrée, sorties, routes."""
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    ir = extract_flow(flow, workflow_id="wf:research-flow",
                      flow_metadata=CREWAI_FLOW_METADATA,
                      flow_edges=CREWAI_FLOW_EDGES, include_crew=False)

    # Entrée : la méthode @start.
    assert any("begin" in e for e in ir.entry_nodes), ir.entry_nodes
    # Router présent.
    from harness.workflow_ir import NodeKind
    routers = [n for n in ir.nodes if n.kind == NodeKind.ROUTER]
    assert routers, "le @router doit être extrait comme nœud router"
    # Branches conditionnelles (recherche / directe).
    assert len(ir.conditional_edges()) >= 2, "les deux branches doivent être extraites"
    # Terminaisons identifiables.
    assert ir.terminal_nodes, "au moins une terminaison doit être identifiée"


def test_crewai_flow_reports_opaque_router():
    """ANTI-SILENCE : le router opaque est enregistré avec une raison."""
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    ir = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                      flow_edges=CREWAI_FLOW_EDGES, include_crew=False)

    routers = [u for u in ir.unresolved_elements if u.get("kind") == "flow_router"]
    assert routers, "le router doit apparaître dans unresolved_elements"
    for r in routers:
        assert r["semantics"] == "opaque"
        assert "reason" in r and r["reason"], "chaque élément opaque porte une raison"


def test_crewai_flow_agent_refs_declared():
    """Les références agent/prompt/outil des branches sont déclarées (metadata)."""
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    ir = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                      flow_edges=CREWAI_FLOW_EDGES, include_crew=False)
    # researcher et direct doivent être présents via les métadonnées.
    assert "aci:agent:researcher" in ir.agent_ids()
    assert "aci:agent:direct" in ir.agent_ids()


# ============================================================ trois sémantiques distinctes

def test_three_extraction_semantics_are_distinct():
    """Crew-only, Flow-only et Flow+Crew produisent des IR distincts et cohérents.

    - Crew-only : tâches + dépendances de contexte, PAS de router ;
    - Flow-only : topologie de flow (router, branches), PAS de tâches de crew ;
    - Flow+Crew : les deux fusionnés.
    """
    pytest.importorskip("crewai")
    from harness.workflow_ir import EdgeKind, NodeKind
    from adapters.crewai_extractor import extract_crew, extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, CREWAI_METADATA,
        build_native_crewai, build_native_crewai_flow,
    )

    crew = build_native_crewai()
    flow = build_native_crewai_flow()

    crew_only = extract_crew(crew, agent_metadata=CREWAI_METADATA)
    flow_only = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                             flow_edges=CREWAI_FLOW_EDGES, include_crew=False)
    flow_plus = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                             flow_edges=CREWAI_FLOW_EDGES,
                             agent_metadata=CREWAI_METADATA, include_crew=True)

    # Crew-only : des dépendances de contexte, aucun router.
    crew_ctx = [e for e in crew_only.edges if e.kind == EdgeKind.CONTEXT_DEPENDENCY]
    crew_routers = [n for n in crew_only.nodes if n.kind == NodeKind.ROUTER]
    assert crew_ctx, "Crew-only doit avoir des dépendances de contexte"
    assert not crew_routers, "Crew-only ne doit PAS avoir de router"

    # Flow-only : un router, aucune tâche de crew (kind=task).
    flow_routers = [n for n in flow_only.nodes if n.kind == NodeKind.ROUTER]
    flow_tasks = [n for n in flow_only.nodes if n.kind == NodeKind.TASK]
    assert flow_routers, "Flow-only doit avoir un router"
    assert not flow_tasks, "Flow-only ne doit PAS contenir les tâches du crew"

    # Flow+Crew : router ET tâches présents.
    fp_routers = [n for n in flow_plus.nodes if n.kind == NodeKind.ROUTER]
    fp_tasks = [n for n in flow_plus.nodes if n.kind == NodeKind.TASK]
    assert fp_routers, "Flow+Crew doit avoir un router"
    assert fp_tasks, "Flow+Crew doit contenir les tâches du crew fusionné"


def test_crewai_flow_digest_stable():
    """Le digest de l'extraction Flow est stable sur extraction répétée."""
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_flow
    from scenarios.native_workflows import (
        CREWAI_FLOW_EDGES, CREWAI_FLOW_METADATA, build_native_crewai_flow,
    )

    flow = build_native_crewai_flow()
    d1 = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                      flow_edges=CREWAI_FLOW_EDGES, include_crew=False).digest()
    d2 = extract_flow(flow, flow_metadata=CREWAI_FLOW_METADATA,
                      flow_edges=CREWAI_FLOW_EDGES, include_crew=False).digest()
    assert d1 == d2


# ============================================================ portabilité croisée

def test_cross_framework_agent_equivalence():
    """Les deux extractions natives projettent le même ensemble d'agents ACM.

    C'est la revendication de portabilité au niveau EXTRACTION (plus forte que
    l'instanciabilité) : deux applications natives indépendantes normalisées vers
    le même ensemble d'agents ACM.
    """
    pytest.importorskip("langgraph")
    pytest.importorskip("crewai")
    from adapters.crewai_extractor import extract_crew
    from adapters.langgraph_extractor import extract_langgraph

    lg = extract_langgraph(_build_native_langgraph(), node_metadata=_LANGGRAPH_METADATA)
    cw = extract_crew(_build_native_crewai(), agent_metadata=_CREWAI_METADATA)
    # Intersection non triviale des agents (researcher, reviewer, finalizer).
    common = set(lg.agent_ids()) & set(cw.agent_ids())
    assert {"aci:agent:researcher", "aci:agent:reviewer", "aci:agent:finalizer"} <= common


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
