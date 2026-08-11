"""Tests P0 issus de la revue technique.

Couvre les 10 points P0 :
  1. digest incorrect (identité des preuves)
  2. changement de dependency snapshot (staleness)
  3. environnement incompatible
  4. politique absente
  5. qualité NOK après preuve bloquante
  6. référence obligatoire manquante (intégrité graphe)
  7. immutabilité (frozen)
  8. extra="forbid"
  9. validation I4/I5 (conservée sur le déclaré — cf. note requirements)
 10. exécution du cœur sans extras (voir test_core_no_extras.py)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    Evidence,
    EvidenceApplicability,
    PropagationContext,
    Relation,
    classify_evidence,
    evidence_applicability,
    propagate,
    quality_from_evidence,
)
from acm.models.aci import AssurancePolicy, DeclaredStatus
from acm.models.enums import (
    ACIType,
    AssuranceState,
    EvidenceResult,
    ImpactState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)


def _rev(aci_id, rid="01J", digest="sha256:x", aci_type=ACIType.PROMPT,
         lifecycle=LifecycleState.VALIDATED, dims=("functional",)):
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


# --- P0-1 : identité des preuves (digest) ---

def test_p0_1_same_revision_id_different_digest_is_inapplicable():
    """Même revision_id mais digest différent -> preuve NON applicable."""
    rev = _rev("aci:prompt:p", rid="01J", digest="sha256:AAA")
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:BBB"),
        scope_dimensions=["functional"], blocking=True,
    )
    state = evidence_applicability(ev, rev, PropagationContext())
    assert state == EvidenceApplicability.INAPPLICABLE


def test_p0_1_same_digest_different_revision_is_inapplicable():
    """Même digest mais revision différente -> non applicable."""
    rev = _rev("aci:prompt:p", rid="01J", digest="sha256:X")
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="02J", digest="sha256:X"),
        scope_dimensions=["functional"], blocking=True,
    )
    assert evidence_applicability(ev, rev, PropagationContext()) == EvidenceApplicability.INAPPLICABLE


def test_p0_1_matching_revision_and_digest_is_applicable():
    rev = _rev("aci:prompt:p", rid="01J", digest="sha256:X")
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:X"),
        scope_dimensions=["functional"], blocking=True,
    )
    assert evidence_applicability(ev, rev, PropagationContext()) == EvidenceApplicability.APPLICABLE


# --- P0-2 : staleness par dependency_snapshot ---

def test_p0_2_changed_dependency_snapshot_is_stale():
    """Une preuve dont une dépendance snapshotée a changé -> stale."""
    prompt = _rev("aci:prompt:p", rid="01J", digest="sha256:p")
    # dépendance courante : model @ 02J
    model = _rev("aci:model:m", rid="02J", digest="sha256:m2", aci_type=ACIType.MODEL)
    graph = ConfigurationGraph.build([prompt, model], [])

    # preuve visant le prompt, mais snapshot du model à l'ancienne révision 01J
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:p"),
        scope_dimensions=["functional"], blocking=True,
        dependency_snapshot=[ACIRef(id="aci:model:m", revision_id="01J", digest="sha256:m1")],
    )
    state = evidence_applicability(ev, prompt, PropagationContext(), graph)
    assert state == EvidenceApplicability.STALE


def test_p0_2_stale_evidence_propagates_stale_impact():
    """Une preuve stale rend la révision impactée en `stale`."""
    prompt = _rev("aci:prompt:p", rid="01J", digest="sha256:p")
    model = _rev("aci:model:m", rid="02J", digest="sha256:m2", aci_type=ACIType.MODEL)
    graph = ConfigurationGraph.build([prompt, model], [])
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:p"),
        scope_dimensions=["functional"], blocking=True,
        dependency_snapshot=[ACIRef(id="aci:model:m", revision_id="01J", digest="sha256:m1")],
    )
    report = propagate(graph, [ev], PropagationContext())
    p = next(i for i in report.items.values() if i.ref.id == "aci:prompt:p")
    assert p.computed.impact_state == ImpactState.STALE
    assert "e1" in p.stale_evidence_ids


# --- P0-3 : environnement incompatible ---

def test_p0_3_environment_mismatch_is_inapplicable():
    rev = _rev("aci:prompt:p", rid="01J", digest="sha256:p")
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:p"),
        scope_environment="staging", scope_dimensions=["functional"], blocking=True,
    )
    ctx = PropagationContext(environment="production")
    assert evidence_applicability(ev, rev, ctx) == EvidenceApplicability.INAPPLICABLE


def test_p0_3_environment_match_is_applicable():
    rev = _rev("aci:prompt:p", rid="01J", digest="sha256:p")
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:prompt:p", revision_id="01J", digest="sha256:p"),
        scope_environment="production", scope_dimensions=["functional"], blocking=True,
    )
    ctx = PropagationContext(environment="production")
    assert evidence_applicability(ev, rev, ctx) == EvidenceApplicability.APPLICABLE


# --- P0-4 : politique absente vs vide ---

def test_p0_4_absent_policy_is_distinguishable_from_empty():
    rev_absent = ACIRevision(
        ref=ACIRef(id="aci:x", revision_id="01J", digest="sha256:x"),
        aci_type=ACIType.AGENT,
    )
    rev_empty = ACIRevision(
        ref=ACIRef(id="aci:y", revision_id="01J", digest="sha256:y"),
        aci_type=ACIType.AGENT,
        assurance_policy=AssurancePolicy(),
    )
    assert rev_absent.assurance_policy is None
    assert rev_empty.assurance_policy is not None
    # La politique effective est identique (vide) mais la distinction est visible
    assert rev_absent.effective_assurance_policy().composition_mode == \
        rev_empty.effective_assurance_policy().composition_mode


# --- P0-5 : qualité NOK après preuve bloquante ---

def test_p0_5_blocking_fail_evidence_yields_nok():
    applicable = [
        Evidence(evidence_id="e1", target=ACIRef(id="a", revision_id="01J", digest="d"),
                 result=EvidenceResult.FAIL, blocking=True),
    ]
    assert quality_from_evidence(applicable) == QualityState.NOK


def test_p0_5_nonblocking_fail_yields_to_improve():
    applicable = [
        Evidence(evidence_id="e1", target=ACIRef(id="a", revision_id="01J", digest="d"),
                 result=EvidenceResult.FAIL, blocking=False),
    ]
    assert quality_from_evidence(applicable) == QualityState.TO_IMPROVE


def test_p0_5_inconclusive_yields_unknown():
    applicable = [
        Evidence(evidence_id="e1", target=ACIRef(id="a", revision_id="01J", digest="d"),
                 result=EvidenceResult.INCONCLUSIVE, blocking=True),
    ]
    assert quality_from_evidence(applicable) == QualityState.UNKNOWN


def test_p0_5_blocking_fail_propagates_to_effective_quality():
    """Une preuve bloquante fail sur un ACI validé -> effective_quality nok."""
    rev = _rev("aci:tool:t", rid="01J", digest="sha256:t", aci_type=ACIType.TOOL)
    graph = ConfigurationGraph.build([rev], [])
    ev = Evidence(
        evidence_id="e1",
        target=ACIRef(id="aci:tool:t", revision_id="01J", digest="sha256:t"),
        scope_dimensions=["functional"], result=EvidenceResult.FAIL, blocking=True,
    )
    report = propagate(graph, [ev], PropagationContext())
    t = next(iter(report.items.values()))
    assert t.computed.effective_quality == QualityState.NOK


# --- P0-6 : référence obligatoire manquante ---

def test_p0_6_missing_reference_detected():
    a1 = _rev("aci:agent:a", rid="01J", digest="sha256:a", aci_type=ACIType.AGENT)
    # relation vers un prompt ABSENT du graphe
    rel = Relation(
        relation_id="r1",
        source=a1.ref,
        target=ACIRef(id="aci:prompt:missing", revision_id="01J", digest="sha256:m"),
        relation_type=RelationType.USES_PROMPT,
    )
    graph = ConfigurationGraph.build([a1], [rel])
    problems = graph.validate_integrity()
    assert any("manquante" in p for p in problems)


def test_p0_6_duplicate_relation_detected():
    a1 = _rev("aci:agent:a", rid="01J", digest="sha256:a", aci_type=ACIType.AGENT)
    p1 = _rev("aci:prompt:p", rid="01J", digest="sha256:p")
    rel = Relation(relation_id="r1", source=a1.ref, target=p1.ref,
                   relation_type=RelationType.USES_PROMPT)
    rel_dup = Relation(relation_id="r1", source=a1.ref, target=p1.ref,
                       relation_type=RelationType.USES_PROMPT)
    graph = ConfigurationGraph.build([a1, p1], [rel, rel_dup])
    problems = graph.validate_integrity()
    assert any("dupliquée" in p.lower() for p in problems)


def test_p0_6_strict_raises_on_missing_reference():
    a1 = _rev("aci:agent:a", rid="01J", digest="sha256:a", aci_type=ACIType.AGENT)
    rel = Relation(relation_id="r1", source=a1.ref,
                   target=ACIRef(id="aci:missing", revision_id="01J", digest="d"),
                   relation_type=RelationType.USES_PROMPT)
    graph = ConfigurationGraph.build([a1], [rel])
    with pytest.raises(ValueError):
        propagate(graph, [], PropagationContext(), strict=True)


# --- P0-7 : immutabilité (frozen) ---

def test_p0_7_revision_is_frozen():
    rev = _rev("aci:x")
    with pytest.raises(ValidationError):
        rev.declared = DeclaredStatus()


def test_p0_7_declared_status_is_frozen():
    rev = _rev("aci:x")
    with pytest.raises(ValidationError):
        rev.declared.quality_state = QualityState.NOK


def test_p0_7_evidence_is_frozen():
    ev = Evidence(evidence_id="e1", target=ACIRef(id="a", revision_id="01J", digest="d"))
    with pytest.raises(ValidationError):
        ev.result = EvidenceResult.FAIL


# --- P0-8 : extra="forbid" ---

def test_p0_8_extra_field_forbidden_on_revision():
    with pytest.raises(ValidationError):
        ACIRevision(
            ref=ACIRef(id="a", revision_id="01J", digest="d"),
            aci_type=ACIType.AGENT,
            unknown_field="boom",
        )


def test_p0_8_extra_field_forbidden_on_ref():
    with pytest.raises(ValidationError):
        ACIRef(id="a", revision_id="01J", digest="d", typo_field=123)


# --- P0 : rapport enrichi ---

def test_report_carries_diagnostics():
    rev = _rev("aci:x", rid="01J", digest="sha256:x")
    graph = ConfigurationGraph.build([rev], [])
    report = propagate(graph, [], PropagationContext())
    assert report.iterations >= 1
    assert report.converged is True
    assert isinstance(report.graph_problems, list)
    item = next(iter(report.items.values()))
    assert item.assurance_mode is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
