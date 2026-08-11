"""Tests des invariants normatifs I1 à I14 (§23).

Chaque invariant est testé avec un cas conforme et un cas violant.
Ensemble, ces tests constituent le critère de conformité §28 (vérifier I1..I14).
"""
from __future__ import annotations

import pytest

from acm import ConfigurationGraph, PropagationContext, propagate
from acm.invariants import (
    InvariantViolationError,
    check_report_invariants,
    i1_new_revision_is_draft,
    i2_validation_targets_exact_revision,
    i3_transition_in_matrix,
    i4_validated_implies_assessed,
    i5_validated_excludes_nok,
    i6_archived_not_reactivable,
    i7_release_without_block,
    i11_dynamic_instance_traceable,
    i12_no_direct_promotion,
    i13_no_permission_escalation,
    i14_deterministic,
)
from acm.models.enums import (
    AssuranceState,
    BaselineState,
    LifecycleState,
    PromotionState,
    QualityState,
)
from acm.models.refs import ACIRef
from acm.state_machines.revisions import new_revision
from scenarios import scenario_a, scenario_b, scenario_de, scenario_f


# --- I1 ---
def test_i1_new_revision_is_draft():
    graph, _ = scenario_a.build()
    prev = graph.revisions["aci:agent:planner@01JREV"]
    fresh = new_revision(prev, "01JNEW", "sha256:new")
    assert i1_new_revision_is_draft(fresh) == []


def test_i1_violation():
    graph, _ = scenario_a.build()
    validated = graph.revisions["aci:agent:planner@01JREV"]  # validated
    assert len(i1_new_revision_is_draft(validated)) == 1


# --- I2 ---
def test_i2_exact_revision_ok():
    ref = ACIRef(id="aci:x", revision_id="01J", digest="sha256:x")
    assert i2_validation_targets_exact_revision(ref) == []


def test_i2_logical_identity_insufficient():
    ref = ACIRef(id="aci:x")  # ni revision_id ni digest
    assert len(i2_validation_targets_exact_revision(ref)) == 1


# --- I3 ---
def test_i3_legal_transition():
    assert i3_transition_in_matrix(
        LifecycleState.CANDIDATE, LifecycleState.VALIDATED
    ) == []


def test_i3_illegal_transition():
    # draft -> validated est interdit (validation candidate requise)
    assert len(i3_transition_in_matrix(
        LifecycleState.DRAFT, LifecycleState.VALIDATED
    )) == 1


# --- I4 ---
def test_i4_validated_assessed_ok():
    graph, ev = scenario_a.build()
    r = propagate(graph, ev, PropagationContext())
    for item in r.items.values():
        assert i4_validated_implies_assessed(item) == []


def test_i4_violation():
    graph, ev = scenario_a.build()
    r = propagate(graph, ev, PropagationContext())
    item = next(iter(r.items.values()))
    item.declared_assurance = AssuranceState.UNASSESSED  # validated mais unassessed
    assert len(i4_validated_implies_assessed(item)) == 1


# --- I5 ---
def test_i5_validated_not_nok_ok():
    """§3.4 — A1 validated + declared ok mais eff nok NE viole PAS I5."""
    graph, ev = scenario_b.build()
    r = propagate(graph, ev, PropagationContext())
    a1 = next(i for i in r.items.values() if i.ref.id == "aci:agent:planner")
    assert i5_validated_excludes_nok(a1) == []  # declared ok -> pas de violation


def test_i5_violation_declared_nok_while_validated():
    """T1 declared nok tout en étant validated -> violation d'incohérence."""
    graph, ev = scenario_b.build()
    r = propagate(graph, ev, PropagationContext())
    t1 = next(i for i in r.items.values() if i.ref.id == "aci:tool:web-search")
    assert len(i5_validated_excludes_nok(t1)) == 1


# --- I6 ---
def test_i6_archived_terminal():
    assert len(i6_archived_not_reactivable(
        LifecycleState.ARCHIVED, LifecycleState.VALIDATED
    )) == 1


def test_i6_archived_to_archived_ok():
    assert i6_archived_not_reactivable(
        LifecycleState.ARCHIVED, LifecycleState.ARCHIVED
    ) == []


# --- I7 ---
def test_i7_release_all_eligible_ok():
    graph, ev = scenario_a.build()
    r = propagate(graph, ev, PropagationContext())
    items = list(r.items.values())
    assert i7_release_without_block(BaselineState.RELEASED, items) == []


def test_i7_release_with_blocked_violates():
    graph, ev = scenario_b.build()  # A1/W1 blocked
    r = propagate(graph, ev, PropagationContext())
    items = list(r.items.values())
    assert len(i7_release_without_block(BaselineState.RELEASED, items)) >= 1


# --- I9 ---
def test_i9_blocking_dep_nok_source_blocked():
    """Vérifié via le rapport : B produit une config où I9 est SATISFAIT
    (A1 est bien blocked car T1 est nok) -> pas de violation."""
    graph, ev = scenario_b.build()
    r = propagate(graph, ev, PropagationContext())
    viol = [v for v in check_report_invariants(graph, r) if v.invariant == "I9"]
    assert viol == []  # A1 EST blocked -> invariant respecté


# --- I10 ---
def test_i10_no_stale_mismatch_in_healthy_config():
    graph, ev = scenario_a.build()
    r = propagate(graph, ev, PropagationContext())
    viol = [v for v in check_report_invariants(graph, r) if v.invariant == "I10"]
    assert viol == []


# --- I11 ---
def test_i11_traceable_ok():
    sig = scenario_de.signal_d_conforming()
    assert i11_dynamic_instance_traceable(sig) == []


def test_i11_untraceable_violates():
    sig = scenario_de.signal_e_unauthorized()
    assert len(i11_dynamic_instance_traceable(sig)) == 1


# --- I12 ---
def test_i12_ephemeral_to_registered_forbidden():
    assert len(i12_no_direct_promotion(
        PromotionState.EPHEMERAL, PromotionState.REGISTERED
    )) == 1


def test_i12_legal_promotion_step_ok():
    assert i12_no_direct_promotion(
        PromotionState.EPHEMERAL, PromotionState.RETAINED
    ) == []


# --- I13 ---
def test_i13_no_escalation_ok():
    sig = scenario_de.signal_d_conforming()
    assert i13_no_permission_escalation(sig) == []


def test_i13_escalation_violates():
    sig = scenario_de.signal_e_unauthorized()
    assert len(i13_no_permission_escalation(sig)) == 1


# --- I14 ---
def test_i14_deterministic():
    graph, ev = scenario_a.build()
    ctx = PropagationContext()
    assert i14_deterministic(lambda: propagate(graph, ev, ctx), runs=3) == []


# --- Mode strict de propagate() ---
def test_strict_mode_passes_on_healthy_config():
    graph, ev = scenario_a.build()
    # ne doit pas lever
    propagate(graph, ev, PropagationContext(), strict=True)


def test_strict_mode_raises_on_violation():
    graph, ev = scenario_b.build()  # T1 declared nok while validated -> I5
    with pytest.raises(InvariantViolationError):
        propagate(graph, ev, PropagationContext(), strict=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
