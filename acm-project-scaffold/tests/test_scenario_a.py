"""Test du scénario A — Promotion nominale (§24.1)."""
from __future__ import annotations

from acm import PropagationContext, propagate
from acm.models.enums import (
    AssuranceState,
    EligibilityState,
    ImpactState,
    QualityState,
)
from acm.policy import EligibilityContext
from scenarios import scenario_a


def _status(report, aci_id):
    for item in report.items.values():
        if item.ref.id == aci_id:
            return item
    raise KeyError(aci_id)


def test_scenario_a_nominal_promotion():
    graph, evidence = scenario_a.build()
    ctx = PropagationContext(eligibility_context=EligibilityContext.VALIDATION)

    report = propagate(graph, evidence, ctx)

    for aci_id in [
        "aci:agent:planner",
        "aci:agent:writer",
        "aci:workflow:report-pipeline",
    ]:
        item = _status(report, aci_id)
        c = item.computed
        assert c.effective_quality == QualityState.OK, aci_id
        assert c.effective_assurance == AssuranceState.ASSESSED, aci_id
        assert c.impact_state == ImpactState.CURRENT, aci_id
        assert c.eligibility_state == EligibilityState.ELIGIBLE, aci_id


def test_scenario_a_release_context_eligible():
    """Une baseline candidate contenant ces objets peut devenir released."""
    graph, evidence = scenario_a.build()
    ctx = PropagationContext(eligibility_context=EligibilityContext.BASELINE_RELEASE)

    report = propagate(graph, evidence, ctx)

    w1 = _status(report, "aci:workflow:report-pipeline")
    assert w1.computed.eligibility_state == EligibilityState.ELIGIBLE
    assert report.valid is True
    assert report.summary["blocked"] == 0


def test_scenario_a_determinism():
    """§I14 — mêmes entrées -> même rapport (états identiques)."""
    graph, evidence = scenario_a.build()
    ctx = PropagationContext()

    r1 = propagate(graph, evidence, ctx)
    r2 = propagate(graph, evidence, ctx)

    for key in r1.items:
        c1 = r1.items[key].computed
        c2 = r2.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


if __name__ == "__main__":
    test_scenario_a_nominal_promotion()
    test_scenario_a_release_context_eligible()
    test_scenario_a_determinism()
    print("scenario A: all assertions passed")
