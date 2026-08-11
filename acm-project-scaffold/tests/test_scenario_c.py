"""Test du scénario C — Nouvelle version de prompt (§24.3)."""
from __future__ import annotations

from acm import PropagationContext, propagate
from acm.models.enums import (
    AssuranceState,
    EligibilityState,
    ImpactState,
    LifecycleState,
    QualityState,
)
from acm.propagation.assurance import evidence_is_applicable
from scenarios import scenario_c


def _status(report, aci_id, revision_id):
    for item in report.items.values():
        if item.ref.id == aci_id and item.ref.revision_id == revision_id:
            return item
    raise KeyError(f"{aci_id}@{revision_id}")


# --- Partie 1 : nouvelle révision A1@R2 (§19.1) ---

def test_new_revision_inherits_fresh_state():
    """A1@R2 : draft / unknown / unassessed (§19.1)."""
    graph, evidence = scenario_c.build_new_revision()
    report = propagate(graph, evidence, PropagationContext())

    a1r2 = _status(report, "aci:agent:planner", scenario_c.R2)
    assert a1r2.lifecycle_state == LifecycleState.DRAFT
    assert a1r2.declared_quality == QualityState.UNKNOWN
    assert a1r2.computed.effective_assurance == AssuranceState.UNASSESSED


def test_new_revision_impact_current_but_blocked():
    """NUANCE §19.1 : impact = current (pas de changement EXTERNE), mais
    eligibility = blocked (car draft/unassessed). Bloquée n'est pas impactée."""
    graph, evidence = scenario_c.build_new_revision()
    report = propagate(graph, evidence, PropagationContext())

    a1r2 = _status(report, "aci:agent:planner", scenario_c.R2)
    assert a1r2.computed.impact_state == ImpactState.CURRENT
    assert a1r2.computed.eligibility_state == EligibilityState.BLOCKED


def test_old_evidence_not_applicable_to_new_revision():
    """E1 ciblant R1 n'est PAS applicable à R2 (§10.3), mais reste valide
    historiquement pour R1."""
    graph, evidence = scenario_c.build_new_revision()

    a1r2 = graph.revisions[f"aci:agent:planner@{scenario_c.R2}"]
    ctx = PropagationContext()

    # Aucune preuve de la liste ne doit être applicable à A1@R2
    applicable_to_r2 = [
        e for e in evidence if evidence_is_applicable(e, a1r2, ctx)
    ]
    assert applicable_to_r2 == []

    # E1 (ciblant A1@R1) existe toujours dans le jeu de preuves (historique)
    assert any(e.target.revision_id == scenario_c.R1 for e in evidence)


# --- Partie 2 : ancienne config, P1@R1 déprécié (§24.3, §24.6) ---

def test_old_config_becomes_impacted_and_warning():
    """A1@R1 utilisant P1@R1 déprécié : impact=impacted, eligibility=warning."""
    graph, evidence = scenario_c.build_old_config()
    report = propagate(graph, evidence, PropagationContext())

    a1r1 = _status(report, "aci:agent:planner", scenario_c.R1)
    assert a1r1.computed.impact_state == ImpactState.IMPACTED
    assert a1r1.computed.eligibility_state == EligibilityState.WARNING


def test_deprecated_prompt_itself_not_invalid():
    """§3.1 — un ACI déprécié n'est pas invalide : P1@R1 reste ok/eligible."""
    graph, evidence = scenario_c.build_old_config()
    report = propagate(graph, evidence, PropagationContext())

    p1r1 = _status(report, "aci:prompt:planner-system", scenario_c.R1)
    assert p1r1.lifecycle_state == LifecycleState.DEPRECATED
    assert p1r1.computed.effective_quality == QualityState.OK
    # Le prompt lui-même n'a pas de dépendance problématique -> eligible
    assert p1r1.computed.eligibility_state == EligibilityState.ELIGIBLE


def test_old_config_reason_points_to_deprecation():
    """La raison du warning doit référencer la dépréciation de la dépendance."""
    graph, evidence = scenario_c.build_old_config()
    report = propagate(graph, evidence, PropagationContext())

    a1r1 = _status(report, "aci:agent:planner", scenario_c.R1)
    codes = {r.code for r in a1r1.computed.reasons}
    assert "ACM-PROP-DEPRECATED-WARN" in codes


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("scenario C: all assertions passed")
