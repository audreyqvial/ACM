# Emplacement : tests/test_scenarios_group_e.py
"""Tests du groupe E — portabilité et robustesse (§ plan ACM-S22..S27).

Deux thèmes :
  - Portabilité inter-framework (S22, S23, S24) : LangGraph et CrewAI projettent
    un même système logique vers la même sémantique ACM. S'appuie sur
    l'équivalence déjà validée dans test_crewai_adapter / test_langgraph_adapter.
  - Robustesse (S25 invariance à l'ordre, S26 cycles autorisés, S27 échelle).

Les tests de portabilité utilisent pytest.importorskip pour rester exécutables
sans les extras langgraph/crewai installés.
"""
from __future__ import annotations

import time

import pytest

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    Evidence,
    PropagationContext,
    Relation,
    propagate,
)
from acm.models.aci import AssurancePolicy, DeclaredStatus
from acm.models.enums import (
    ACIType,
    AssuranceState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)


def _rev(aci_id, aci_type=ACIType.AGENT, *, q=QualityState.OK, a=AssuranceState.ASSESSED,
         lc=LifecycleState.VALIDATED, dims=("functional",)):
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id="R1", digest=f"sha256:{aci_id}"),
        aci_type=aci_type,
        declared=DeclaredStatus(lifecycle_state=lc, quality_state=q, assurance_state=a),
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(dims)),
    )


# ============================================================ S22 — portabilité

def _common_spec():
    from acm.runtime.spec import AgentSpec
    return AgentSpec(
        instance_id="rt:router-001",
        template_ref=ACIRef(id="aci:template:router", revision_id="01JT1"),
        factory_ref=ACIRef(id="aci:factory:f1", revision_id="01JF1"),
        creation_event_id="evt:001",
        prompt_ref=ACIRef(id="aci:prompt:router", revision_id="01JR1"),
        model_ref=ACIRef(id="aci:model:gpt-5.4", revision_id="01JM1"),
        tool_refs=[ACIRef(id="aci:tool:web-search", revision_id="01JR1")],
        tool_names=["web_search"], model_name="gpt-5.4", authorized_tools=["web_search"],
    )


def test_s22_langgraph_crewai_same_digest():
    """Même système logique → même resolved_config_digest via les 2 frameworks."""
    pytest.importorskip("crewai")
    pytest.importorskip("langgraph")
    from adapters.crewai_adapter import CrewAIAdapter
    from adapters.langgraph_adapter import LangGraphAdapter

    spec = _common_spec()
    lg = LangGraphAdapter().create_instance({"spec": spec})
    cw = CrewAIAdapter().create_instance({"spec": spec})
    assert lg.resolved_config_digest == cw.resolved_config_digest


def test_s22_langgraph_crewai_same_verdict():
    """Même système logique → mêmes décisions d'éligibilité (rapports ACM)."""
    pytest.importorskip("crewai")
    pytest.importorskip("langgraph")
    from acm import evaluate_runtime_instance
    from adapters.crewai_adapter import CrewAIAdapter
    from adapters.langgraph_adapter import LangGraphAdapter

    spec = _common_spec()
    lg = evaluate_runtime_instance(LangGraphAdapter().create_instance({"spec": spec}))
    cw = evaluate_runtime_instance(CrewAIAdapter().create_instance({"spec": spec}))
    assert lg.model_dump(exclude={"instance_id"}) == cw.model_dump(exclude={"instance_id"})


# ============================================================ S23 — topologie / import

def test_s23_adapter_reports_extraction_transparency():
    """L'adaptateur produit un signal traçable dont on peut lister la provenance.

    S23 exige transparence sur ce qui est extrait automatiquement vs annoté.
    Ici on vérifie qu'un signal porte les références résolues (extraction auto)
    et une traçabilité inspectable — la base d'un rapport d'import transparent.
    """
    pytest.importorskip("langgraph")
    from adapters.langgraph_adapter import LangGraphAdapter

    sig = LangGraphAdapter().create_instance({"spec": _common_spec()})
    # Éléments extraits automatiquement, inspectables dans le signal.
    assert sig.resolved_config.prompt_ref is not None
    assert sig.resolved_config.model_ref is not None
    assert sig.traceability.is_traceable()


# ============================================================ S24 — événements runtime

def test_s24_runtime_vocabulary_is_framework_neutral():
    """Le vocabulaire runtime ACM (RuntimeEventType) est commun aux frameworks.

    S24 : des événements natifs différents se projettent vers un vocabulaire
    commun. On vérifie que le vocabulaire ACM existe et couvre les événements
    recherchés, indépendamment de tout framework.
    """
    from acm.state_machines import RuntimeEventType

    values = {e.value for e in RuntimeEventType}
    # Les événements clés du plan sont représentables.
    assert "node.instantiated" in values
    assert "state.changed" in values
    assert "node.terminated" in values


def test_s24_journal_replays_deterministically():
    """Un journal runtime valide se rejoue (base de l'interopérabilité)."""
    from scenarios import scenario_de
    from acm import evaluate_runtime_instance
    from acm.runtime.signal import RuntimeSignal

    sig = scenario_de.signal_d_conforming()
    replayed = RuntimeSignal.from_record(sig.to_record())
    assert evaluate_runtime_instance(replayed).eligibility_state == \
        evaluate_runtime_instance(sig).eligibility_state


# ============================================================ S25 — invariance à l'ordre

def _sample_graph():
    p = _rev("aci:prompt:p", ACIType.PROMPT)
    t = _rev("aci:tool:t", ACIType.TOOL)
    a = _rev("aci:agent:a", ACIType.AGENT)
    rels = [
        Relation(relation_id="r1", source=a.ref, target=p.ref, relation_type=RelationType.USES_PROMPT),
        Relation(relation_id="r2", source=a.ref, target=t.ref, relation_type=RelationType.USES_TOOL),
    ]
    ev = [
        Evidence(evidence_id=f"e:{r.ref.id}", target=r.ref,
                 scope_dimensions=["functional"], blocking=True)
        for r in (p, t, a)
    ]
    return [p, t, a], rels, ev


def test_s25_order_invariance_computed_status():
    """Permuter révisions/relations/preuves ne change pas les états calculés."""
    revs, rels, ev = _sample_graph()
    g1 = ConfigurationGraph.build(revs, rels)
    g2 = ConfigurationGraph.build(list(reversed(revs)), list(reversed(rels)))
    r1 = propagate(g1, ev, PropagationContext())
    r2 = propagate(g2, list(reversed(ev)), PropagationContext())
    for key in r1.items:
        c1, c2 = r1.items[key].computed, r2.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


def test_s25_order_invariance_digest():
    """Le configuration_digest est invariant à l'ordre d'insertion."""
    from harness import configuration_digest
    revs, rels, _ = _sample_graph()
    g1 = ConfigurationGraph.build(revs, rels)
    g2 = ConfigurationGraph.build(list(reversed(revs)), list(reversed(rels)))
    assert configuration_digest(g1) == configuration_digest(g2)


def test_s25_order_invariance_convergence():
    """La convergence est identique quel que soit l'ordre."""
    revs, rels, ev = _sample_graph()
    g1 = ConfigurationGraph.build(revs, rels)
    g2 = ConfigurationGraph.build(list(reversed(revs)), list(reversed(rels)))
    r1 = propagate(g1, ev, PropagationContext())
    r2 = propagate(g2, list(reversed(ev)), PropagationContext())
    assert r1.converged == r2.converged


# ============================================================ S26 — cycles

def _cycle_graph(qa=QualityState.OK):
    a = _rev("aci:a", q=qa)
    b = _rev("aci:b")
    rels = [
        Relation(relation_id="r1", source=a.ref, target=b.ref,
                 relation_type=RelationType.EVALUATED_UNDER, required=False,
                 propagation_policy=PropagationPolicy.WARNING),
        Relation(relation_id="r2", source=b.ref, target=a.ref,
                 relation_type=RelationType.EVALUATED_UNDER, required=False,
                 propagation_policy=PropagationPolicy.WARNING),
    ]
    return ConfigurationGraph.build([a, b], rels)


def test_s26_allowed_cycle_converges_all_ok():
    """Cas 1 — cycle autorisé, tous ok : convergence sans problème."""
    r = propagate(_cycle_graph(QualityState.OK), [], PropagationContext())
    assert r.converged is True
    assert r.graph_problems == []


def test_s26_allowed_cycle_converges_with_nok():
    """Cas 3 — cycle autorisé, un élément nok : converge quand même."""
    r = propagate(_cycle_graph(QualityState.NOK), [], PropagationContext())
    assert r.converged is True


def test_s26_iterations_recorded():
    """Le nombre d'itérations est enregistré (pas de boucle infinie)."""
    r = propagate(_cycle_graph(), [], PropagationContext())
    assert r.iterations >= 1
    assert r.iterations < 100  # borne : pas de boucle infinie


def test_s26_forbidden_cycle_is_rejected():
    """Un cycle interdit (contains) est détecté comme problème de graphe."""
    a = _rev("aci:a", ACIType.WORKFLOW)
    b = _rev("aci:b", ACIType.AGENT)
    rels = [
        Relation(relation_id="r1", source=a.ref, target=b.ref, relation_type=RelationType.CONTAINS),
        Relation(relation_id="r2", source=b.ref, target=a.ref, relation_type=RelationType.CONTAINS),
    ]
    graph = ConfigurationGraph.build([a, b], rels)
    problems = graph.validate_integrity()
    assert any("ycle" in p for p in problems)


def test_s26_non_convergence_flagged_with_low_max_iterations():
    """Non-convergence artificielle (plafond bas) → signalée explicitement."""
    revs = [_rev(f"aci:{n}", ACIType.AGENT) for n in "abcde"]
    e = revs[-1]
    revs[-1] = e.model_copy(update={
        "declared": e.declared.model_copy(update={"quality_state": QualityState.NOK})
    })
    rels = [
        Relation(relation_id=f"r{i}", source=revs[i].ref, target=revs[i + 1].ref,
                 relation_type=RelationType.CONTAINS)
        for i in range(len(revs) - 1)
    ]
    graph = ConfigurationGraph.build(revs, rels)
    r = propagate(graph, [], PropagationContext(), max_iterations=1)
    assert r.converged is False
    assert r.valid is False


# ============================================================ S27 — échelle

def _scale_graph(n_aci: int, n_rel: int):
    revs = [_rev(f"aci:n{i}", ACIType.AGENT) for i in range(n_aci)]
    rels = []
    for i in range(n_rel):
        src = revs[i % n_aci]
        tgt = revs[(i * 7 + 1) % n_aci]
        if src.ref.id != tgt.ref.id:
            rels.append(Relation(
                relation_id=f"r{i}", source=src.ref, target=tgt.ref,
                relation_type=RelationType.EVALUATED_UNDER, required=False,
                propagation_policy=PropagationPolicy.WARNING,
            ))
    return ConfigurationGraph.build(revs, rels)


def test_s27_scale_100_aci_converges_quickly():
    """100 ACI / ~300 relations : converge en un temps raisonnable sur CPU."""
    graph = _scale_graph(100, 300)
    t0 = time.perf_counter()
    r = propagate(graph, [], PropagationContext())
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.converged is True
    assert elapsed_ms < 5000  # borne large : reproductible sur CPU standard


def test_s27_scale_reports_iterations():
    """Le rapport à l'échelle enregistre les itérations (auditabilité)."""
    graph = _scale_graph(100, 300)
    r = propagate(graph, [], PropagationContext())
    assert r.iterations >= 1
    assert len(r.items) == 100


def test_s27_scale_is_deterministic():
    """Deux propagations du même grand graphe donnent le même résultat."""
    graph = _scale_graph(100, 300)
    r1 = propagate(graph, [], PropagationContext())
    r2 = propagate(graph, [], PropagationContext())
    assert r1.converged == r2.converged
    assert r1.iterations == r2.iterations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
