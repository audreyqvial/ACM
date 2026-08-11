# Emplacement : tests/test_scenarios_group_b.py
"""Tests dédiés du groupe B (S07, S08, S10, S11) pour les cas multi-configs.

Les fixtures YAML testent l'état représentatif de chaque scénario ; ces tests
couvrent les variations que le format mono-configuration ne peut pas exprimer :
  - S08 : états intermédiaires de couverture (E1 seul, E1+E2) et retrait de E2 ;
  - S10 : les 4 modes de composition (direct_only, aggregate_only, hybrid,
          anti-vacuité) ;
  - S11 : distinction null vs policy vide, visible dans le rapport ;
  - S07 : staleness par snapshot divergent (même révision d'agent).
"""
from __future__ import annotations

from datetime import datetime, timezone

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
    CompositionAssuranceMode,
    EvidenceResult,
    LifecycleState,
    QualityState,
    RelationType,
)


def _rev(aci_id, aci_type, *, lc=LifecycleState.VALIDATED, q=QualityState.OK,
         a=AssuranceState.ASSESSED, dims=("functional",), mode=CompositionAssuranceMode.HYBRID,
         policy=True, allow_vac=False):
    ap = None
    if policy:
        ap = AssurancePolicy(
            required_assurance_dimensions=list(dims),
            composition_mode=mode,
            allow_vacuous_assessment=allow_vac,
        )
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id="R1", digest=f"sha256:{aci_id}"),
        aci_type=aci_type,
        declared=DeclaredStatus(lifecycle_state=lc, quality_state=q, assurance_state=a),
        assurance_policy=ap,
    )


def _assurance(graph, evidence):
    r = propagate(graph, evidence, PropagationContext())
    return next(iter(r.items.values())).computed.effective_assurance


# ------------------------------------------------------------------ S08

def _s08_agent():
    return _rev("aci:agent:planner", ACIType.AGENT,
                dims=("functional", "security", "robustness"),
                mode=CompositionAssuranceMode.DIRECT_ONLY)


def _s08_ev(dim):
    return Evidence(
        evidence_id=f"e:{dim}",
        target=ACIRef(id="aci:agent:planner", revision_id="R1", digest="sha256:aci:agent:planner"),
        scope_dimensions=[dim], result=EvidenceResult.PASS, blocking=True,
    )


def test_s08_e1_only_is_partial():
    graph = ConfigurationGraph.build([_s08_agent()], [])
    assert _assurance(graph, [_s08_ev("functional")]) == AssuranceState.PARTIALLY_ASSESSED


def test_s08_e1_e2_still_partial():
    graph = ConfigurationGraph.build([_s08_agent()], [])
    ev = [_s08_ev("functional"), _s08_ev("security")]
    assert _assurance(graph, ev) == AssuranceState.PARTIALLY_ASSESSED


def test_s08_all_three_assessed():
    graph = ConfigurationGraph.build([_s08_agent()], [])
    ev = [_s08_ev("functional"), _s08_ev("security"), _s08_ev("robustness")]
    assert _assurance(graph, ev) == AssuranceState.ASSESSED


def test_s08_removing_e2_returns_to_partial():
    """Le retrait de E2 (security) ramène assessed → partially_assessed."""
    graph = ConfigurationGraph.build([_s08_agent()], [])
    full = [_s08_ev("functional"), _s08_ev("security"), _s08_ev("robustness")]
    assert _assurance(graph, full) == AssuranceState.ASSESSED
    reduced = [_s08_ev("functional"), _s08_ev("robustness")]  # E2 retirée
    assert _assurance(graph, reduced) == AssuranceState.PARTIALLY_ASSESSED


# ------------------------------------------------------------------ S10

def _s10_workflow(mode, dims=("functional",), allow_vac=False):
    return _rev("aci:workflow:w", ACIType.WORKFLOW, mode=mode, dims=dims, allow_vac=allow_vac)


def _s10_dep(*, assessed=True):
    if assessed:
        return _rev("aci:agent:d", ACIType.AGENT)
    return _rev("aci:agent:d", ACIType.AGENT, lc=LifecycleState.DRAFT,
                q=QualityState.UNKNOWN, a=AssuranceState.UNASSESSED, policy=False)


def _s10_run(w, deps, evidence):
    rels = [
        Relation(relation_id=f"r{i}", source=w.ref, target=d.ref,
                 relation_type=RelationType.CONTAINS)
        for i, d in enumerate(deps)
    ]
    graph = ConfigurationGraph.build([w] + deps, rels)
    r = propagate(graph, evidence, PropagationContext())
    return next(i for i in r.items.values() if i.ref.id == "aci:workflow:w").computed.effective_assurance


def _direct_ev():
    return Evidence(evidence_id="ew", target=ACIRef(id="aci:workflow:w", revision_id="R1", digest="sha256:aci:workflow:w"),
                    scope_dimensions=["functional"], result=EvidenceResult.PASS, blocking=True)


def _dep_ev():
    return Evidence(evidence_id="ed", target=ACIRef(id="aci:agent:d", revision_id="R1", digest="sha256:aci:agent:d"),
                    scope_dimensions=["functional"], result=EvidenceResult.PASS, blocking=True)


def test_s10_case_a_direct_only_assessed():
    """direct_only : preuve directe complète suffit, dépendances ignorées."""
    w = _s10_workflow(CompositionAssuranceMode.DIRECT_ONLY)
    assert _s10_run(w, [_s10_dep()], [_direct_ev(), _dep_ev()]) == AssuranceState.ASSESSED


def test_s10_case_b_aggregate_only_assessed():
    """aggregate_only : dépendances assessed suffisent, sans preuve directe."""
    w = _s10_workflow(CompositionAssuranceMode.AGGREGATE_ONLY, dims=())
    assert _s10_run(w, [_s10_dep()], [_dep_ev()]) == AssuranceState.ASSESSED


def test_s10_case_c_hybrid_with_unassessed_dep_not_assessed():
    """hybrid : preuve directe complète NE SUFFIT PAS si une dep non assessed."""
    w = _s10_workflow(CompositionAssuranceMode.HYBRID)
    result = _s10_run(w, [_s10_dep(assessed=False)], [_direct_ev()])
    assert result != AssuranceState.ASSESSED
    assert result == AssuranceState.PARTIALLY_ASSESSED


def test_s10_case_d_vacuity_guard_unassessed():
    """aggregate_only sans AUCUNE dépendance → unassessed (anti-vacuité)."""
    w = _s10_workflow(CompositionAssuranceMode.AGGREGATE_ONLY, dims=())
    assert _s10_run(w, [], []) == AssuranceState.UNASSESSED


def test_s10_case_d_vacuity_can_be_overridden():
    """allow_vacuous_assessment=True autorise l'assessment vide explicitement."""
    w = _s10_workflow(CompositionAssuranceMode.AGGREGATE_ONLY, dims=(), allow_vac=True)
    assert _s10_run(w, [], []) == AssuranceState.ASSESSED


# ------------------------------------------------------------------ S11

def test_s11_null_policy_is_unassessed():
    rev = _rev("aci:x", ACIType.AGENT, policy=False)
    graph = ConfigurationGraph.build([rev], [])
    assert _assurance(graph, []) == AssuranceState.UNASSESSED


def test_s11_null_vs_empty_are_distinguishable():
    """La policy absente et la policy vide restent distinguables dans le modèle."""
    rev_null = _rev("aci:null", ACIType.AGENT, policy=False)
    rev_empty = _rev("aci:empty", ACIType.AGENT, dims=())
    # Distinction visible au niveau du modèle : l'un a une policy, l'autre non.
    assert rev_null.assurance_policy is None
    assert rev_empty.assurance_policy is not None


# ------------------------------------------------------------------ S07

def test_s07_stale_via_divergent_snapshot():
    """Même révision d'agent, mais snapshot de dépendance divergent → stale."""
    from acm import evidence_applicability, EvidenceApplicability

    prompt = _rev("aci:prompt:p", ACIType.PROMPT)
    # dépendance courante model @ 02J
    model = ACIRevision(
        ref=ACIRef(id="aci:model:m", revision_id="02J", digest="sha256:m2"),
        aci_type=ACIType.MODEL,
        declared=DeclaredStatus(lifecycle_state=LifecycleState.VALIDATED,
                                quality_state=QualityState.OK, assurance_state=AssuranceState.ASSESSED),
    )
    graph = ConfigurationGraph.build([prompt, model], [])
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="R1", digest="sha256:aci:prompt:p"),
        scope_dimensions=["functional"], blocking=True,
        dependency_snapshot=[ACIRef(id="aci:model:m", revision_id="01J", digest="sha256:m1")],
    )
    state = evidence_applicability(ev, prompt, PropagationContext(), graph)
    assert state == EvidenceApplicability.STALE


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
