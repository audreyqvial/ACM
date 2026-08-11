"""Test du scénario B — Dépendance NOK (§24.2)."""
from __future__ import annotations

from acm import PropagationContext, propagate
from acm.models.enums import (
    EligibilityState,
    LifecycleState,
    QualityState,
)
from acm.policy import EligibilityContext
from scenarios import scenario_b


def _status(report, aci_id):
    for item in report.items.values():
        if item.ref.id == aci_id:
            return item
    raise KeyError(aci_id)


def test_scenario_b_tool_nok():
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    t1 = _status(report, "aci:tool:web-search")
    assert t1.computed.effective_quality == QualityState.NOK
    assert t1.computed.eligibility_state == EligibilityState.BLOCKED


def test_scenario_b_intrinsic_quality_preserved():
    """§3.4 — LE POINT CLÉ : la qualité intrinsèque de A1 et W1 ne change PAS.

    Une dépendance NOK bloque l'éligibilité mais ne réécrit pas le jugement
    intrinsèque porté sur le composite. La provenance est préservée.
    """
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    a1 = _status(report, "aci:agent:planner")
    w1 = _status(report, "aci:workflow:report-pipeline")

    # quality_state intrinsèque déclaré = toujours ok
    assert a1.declared_quality == QualityState.OK
    assert w1.declared_quality == QualityState.OK
    # lifecycle intrinsèque inchangé
    assert a1.lifecycle_state == LifecycleState.VALIDATED
    assert w1.lifecycle_state == LifecycleState.VALIDATED


def test_scenario_b_effective_quality_propagates():
    """A1 et W1 : effective_quality = nok (propagation via blocking)."""
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    a1 = _status(report, "aci:agent:planner")
    w1 = _status(report, "aci:workflow:report-pipeline")
    assert a1.computed.effective_quality == QualityState.NOK
    assert w1.computed.effective_quality == QualityState.NOK


def test_scenario_b_eligibility_blocked():
    """A1 et W1 : eligibility_state = blocked."""
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    a1 = _status(report, "aci:agent:planner")
    w1 = _status(report, "aci:workflow:report-pipeline")
    assert a1.computed.eligibility_state == EligibilityState.BLOCKED
    assert w1.computed.eligibility_state == EligibilityState.BLOCKED


def test_scenario_b_writer_unaffected():
    """A2 (writer) n'utilise pas T1 : la propagation est ciblée, pas globale."""
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    a2 = _status(report, "aci:agent:writer")
    assert a2.computed.effective_quality == QualityState.OK
    assert a2.computed.eligibility_state == EligibilityState.ELIGIBLE


def test_scenario_b_release_forbidden():
    """baseline release = forbidden (au moins un item bloqué)."""
    graph, evidence = scenario_b.build()
    ctx = PropagationContext(eligibility_context=EligibilityContext.BASELINE_RELEASE)
    report = propagate(graph, evidence, ctx)

    assert report.valid is False
    assert report.summary["blocked"] >= 1
    w1 = _status(report, "aci:workflow:report-pipeline")
    assert w1.computed.eligibility_state == EligibilityState.BLOCKED


def test_scenario_b_reasons_present():
    """§4.2 — chaque état bloqué DOIT être accompagné d'au moins une raison."""
    graph, evidence = scenario_b.build()
    report = propagate(graph, evidence, PropagationContext())

    a1 = _status(report, "aci:agent:planner")
    assert len(a1.computed.reasons) >= 1
    # une raison doit pointer la dépendance blocking NOK (code ACM-PROP-001)
    codes = {r.code for r in a1.computed.reasons}
    assert "ACM-PROP-001" in codes


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("scenario B: all assertions passed")
