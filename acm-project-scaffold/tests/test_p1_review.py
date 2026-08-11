"""Tests P1 issus de la revue technique.

Couvre : preuves multiples couvrant R(x), preuves expirées, duplicats, cycles
(interdits/autorisés), indépendance de l'ordre, convergence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    Evidence,
    EvidenceApplicability,
    PropagationContext,
    Relation,
    classify_evidence,
    covered_dimensions,
    evidence_applicability,
    propagate,
)
from acm.models.aci import AssurancePolicy, DeclaredStatus
from acm.models.enums import (
    ACIType,
    AssuranceState,
    EligibilityState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)
from acm.propagation.assurance import applicable_evidence


def _rev(aci_id, rid="01J", digest=None, aci_type=ACIType.PROMPT,
         lifecycle=LifecycleState.VALIDATED, dims=("functional", "security")):
    digest = digest or f"sha256:{aci_id}"
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id=rid, digest=digest),
        aci_type=aci_type,
        declared=DeclaredStatus(
            lifecycle_state=lifecycle,
            quality_state=QualityState.OK if lifecycle == LifecycleState.VALIDATED else QualityState.UNKNOWN,
            assurance_state=AssuranceState.ASSESSED if lifecycle == LifecycleState.VALIDATED else AssuranceState.UNASSESSED,
        ),
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(dims)),
    )


# --- P1 : preuves multiples couvrant conjointement R(x) ---

def test_p1_multiple_evidence_jointly_cover_requirements():
    """proof_1 -> functional, proof_2 -> security couvrent ['functional','security']."""
    rev = _rev("aci:agent:a", dims=("functional", "security"))
    ev1 = Evidence(evidence_id="e1", target=rev.ref,
                   scope_dimensions=["functional"], blocking=True)
    ev2 = Evidence(evidence_id="e2", target=rev.ref,
                   scope_dimensions=["security"], blocking=True)

    covered = covered_dimensions(rev, [ev1, ev2])
    assert covered == {"functional", "security"}


def test_p1_multiple_evidence_yield_assessed():
    """Deux preuves couvrant conjointement toutes les dimensions -> assessed."""
    rev = _rev("aci:agent:a", dims=("functional", "security"))
    graph = ConfigurationGraph.build([rev], [])
    ev1 = Evidence(evidence_id="e1", target=rev.ref,
                   scope_dimensions=["functional"], blocking=True)
    ev2 = Evidence(evidence_id="e2", target=rev.ref,
                   scope_dimensions=["security"], blocking=True)
    report = propagate(graph, [ev1, ev2], PropagationContext())
    item = next(iter(report.items.values()))
    assert item.computed.effective_assurance == AssuranceState.ASSESSED


def test_p1_partial_multiple_evidence_is_partial():
    """Deux preuves ne couvrant qu'une partie de R(x) -> partially_assessed."""
    rev = _rev("aci:agent:a", dims=("functional", "security", "robustness"))
    graph = ConfigurationGraph.build([rev], [])
    ev1 = Evidence(evidence_id="e1", target=rev.ref,
                   scope_dimensions=["functional"], blocking=True)
    ev2 = Evidence(evidence_id="e2", target=rev.ref,
                   scope_dimensions=["security"], blocking=True)
    report = propagate(graph, [ev1, ev2], PropagationContext())
    item = next(iter(report.items.values()))
    assert item.computed.effective_assurance == AssuranceState.PARTIALLY_ASSESSED


# --- P1 : preuves expirées ---

def test_p1_expired_evidence_is_inapplicable():
    rev = _rev("aci:agent:a")
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ev = Evidence(evidence_id="e1", target=rev.ref, scope_dimensions=["functional"],
                  blocking=True, valid_until=past)
    ctx = PropagationContext(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert evidence_applicability(ev, rev, ctx) == EvidenceApplicability.INAPPLICABLE


def test_p1_not_yet_expired_evidence_is_applicable():
    rev = _rev("aci:agent:a", dims=("functional",))
    future = datetime(2030, 1, 1, tzinfo=timezone.utc)
    ev = Evidence(evidence_id="e1", target=rev.ref, scope_dimensions=["functional"],
                  blocking=True, valid_until=future)
    ctx = PropagationContext(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert evidence_applicability(ev, rev, ctx) == EvidenceApplicability.APPLICABLE


def test_p1_expired_evidence_drops_coverage():
    """Une preuve expirée ne compte pas dans la couverture -> unassessed."""
    rev = _rev("aci:agent:a", dims=("functional",))
    graph = ConfigurationGraph.build([rev], [])
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ev = Evidence(evidence_id="e1", target=rev.ref, scope_dimensions=["functional"],
                  blocking=True, valid_until=past)
    ctx = PropagationContext(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    report = propagate(graph, [ev], ctx)
    item = next(iter(report.items.values()))
    assert item.computed.effective_assurance == AssuranceState.UNASSESSED


# --- P1 : duplicats ---

def test_p1_duplicate_relation_id_detected():
    a = _rev("aci:a", aci_type=ACIType.AGENT)
    p = _rev("aci:p")
    r1 = Relation(relation_id="dup", source=a.ref, target=p.ref,
                  relation_type=RelationType.USES_PROMPT)
    r2 = Relation(relation_id="dup", source=a.ref, target=p.ref,
                  relation_type=RelationType.USES_PROMPT)
    graph = ConfigurationGraph.build([a, p], [r1, r2])
    problems = graph.validate_integrity()
    assert any("dupliquée" in x.lower() for x in problems)


def test_p1_duplicate_evidence_ids_both_counted_in_buckets():
    """Deux preuves distinctes visant la même révision sont toutes deux classées."""
    rev = _rev("aci:a", dims=("functional",))
    ev1 = Evidence(evidence_id="e1", target=rev.ref, scope_dimensions=["functional"], blocking=True)
    ev2 = Evidence(evidence_id="e2", target=rev.ref, scope_dimensions=["functional"], blocking=True)
    buckets = classify_evidence(rev, [ev1, ev2], PropagationContext())
    assert len(buckets["applicable"]) == 2


# --- P1 : cycles ---

def test_p1_forbidden_cycle_on_contains_detected():
    a = _rev("aci:a", aci_type=ACIType.WORKFLOW)
    b = _rev("aci:b", aci_type=ACIType.AGENT)
    rels = [
        Relation(relation_id="r1", source=a.ref, target=b.ref, relation_type=RelationType.CONTAINS),
        Relation(relation_id="r2", source=b.ref, target=a.ref, relation_type=RelationType.CONTAINS),
    ]
    graph = ConfigurationGraph.build([a, b], rels)
    problems = graph.validate_integrity()
    assert any("Cycle interdit" in x for x in problems)


def test_p1_forbidden_cycle_raises_in_strict():
    a = _rev("aci:a", aci_type=ACIType.WORKFLOW)
    b = _rev("aci:b", aci_type=ACIType.AGENT)
    rels = [
        Relation(relation_id="r1", source=a.ref, target=b.ref, relation_type=RelationType.CONTAINS),
        Relation(relation_id="r2", source=b.ref, target=a.ref, relation_type=RelationType.CONTAINS),
    ]
    graph = ConfigurationGraph.build([a, b], rels)
    with pytest.raises(ValueError):
        propagate(graph, [], PropagationContext(), strict=True)


def test_p1_allowed_cycle_converges():
    """Un cycle sur un type autorisé (evaluated_under) ne bloque pas et converge."""
    a = _rev("aci:a", aci_type=ACIType.AGENT)
    b = _rev("aci:b", aci_type=ACIType.AGENT)
    rels = [
        Relation(relation_id="r1", source=a.ref, target=b.ref,
                 relation_type=RelationType.EVALUATED_UNDER, required=False,
                 propagation_policy=PropagationPolicy.WARNING),
        Relation(relation_id="r2", source=b.ref, target=a.ref,
                 relation_type=RelationType.EVALUATED_UNDER, required=False,
                 propagation_policy=PropagationPolicy.WARNING),
    ]
    graph = ConfigurationGraph.build([a, b], rels)
    # pas de cycle interdit
    assert graph.validate_integrity() == []
    report = propagate(graph, [], PropagationContext())
    assert report.converged is True


# --- P1 : indépendance de l'ordre ---

def test_p1_order_independence_revisions():
    """L'ordre d'insertion des révisions ne change pas le résultat."""
    p = _rev("aci:prompt:p", dims=("functional",))
    t = _rev("aci:tool:t", aci_type=ACIType.TOOL, dims=("functional",))
    a = _rev("aci:agent:a", aci_type=ACIType.AGENT, dims=("functional",))
    rels = [
        Relation(relation_id="r1", source=a.ref, target=p.ref, relation_type=RelationType.USES_PROMPT),
        Relation(relation_id="r2", source=a.ref, target=t.ref, relation_type=RelationType.USES_TOOL),
    ]
    ev = [Evidence(evidence_id=f"e:{r.ref.id}", target=r.ref,
                   scope_dimensions=["functional"], blocking=True) for r in (p, t, a)]

    g1 = ConfigurationGraph.build([p, t, a], rels)
    g2 = ConfigurationGraph.build([a, t, p], list(reversed(rels)))
    r1 = propagate(g1, ev, PropagationContext())
    r2 = propagate(g2, list(reversed(ev)), PropagationContext())

    for key in r1.items:
        c1, c2 = r1.items[key].computed, r2.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


def test_p1_order_independence_evidence_coverage():
    """L'ordre des preuves ne change pas la couverture calculée."""
    rev = _rev("aci:a", dims=("functional", "security"))
    ev1 = Evidence(evidence_id="e1", target=rev.ref, scope_dimensions=["functional"], blocking=True)
    ev2 = Evidence(evidence_id="e2", target=rev.ref, scope_dimensions=["security"], blocking=True)
    assert covered_dimensions(rev, [ev1, ev2]) == covered_dimensions(rev, [ev2, ev1])


# --- P1 : convergence ---

def test_p1_convergence_reported():
    p = _rev("aci:prompt:p", dims=("functional",))
    a = _rev("aci:agent:a", aci_type=ACIType.AGENT, dims=("functional",))
    rels = [Relation(relation_id="r1", source=a.ref, target=p.ref,
                     relation_type=RelationType.USES_PROMPT)]
    graph = ConfigurationGraph.build([p, a], rels)
    report = propagate(graph, [], PropagationContext())
    assert report.converged is True
    assert report.iterations >= 1


def test_p1_non_convergence_flagged_with_low_max_iterations():
    """Avec un plafond d'itérations trop bas sur une chaîne profonde, la
    non-convergence est signalée (converged=False, valid=False)."""
    # Chaîne A->B->C->D->E de dépendances blocking, avec E nok pour forcer
    # plusieurs vagues de propagation.
    revs = []
    for name in ["a", "b", "c", "d", "e"]:
        lc = LifecycleState.VALIDATED
        revs.append(_rev(f"aci:{name}", aci_type=ACIType.AGENT, dims=("functional",)))
    # rendre E nok
    e = revs[-1]
    revs[-1] = e.model_copy(update={
        "declared": e.declared.model_copy(update={"quality_state": QualityState.NOK})
    })
    rels = []
    for i in range(len(revs) - 1):
        rels.append(Relation(
            relation_id=f"r{i}", source=revs[i].ref, target=revs[i + 1].ref,
            relation_type=RelationType.CONTAINS,
        ))
    graph = ConfigurationGraph.build(revs, rels)
    # max_iterations=1 : une seule passe ne suffit pas à propager sur 5 niveaux.
    report = propagate(graph, [], PropagationContext(), max_iterations=1)
    assert report.converged is False
    assert report.valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
