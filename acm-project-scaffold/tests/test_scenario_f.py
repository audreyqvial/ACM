"""Test du scénario F — Dépendance dépréciée (§24.6)."""
from __future__ import annotations

from acm import PropagationContext, propagate
from acm.models.enums import (
    BaselineState,
    EligibilityState,
    ImpactState,
)
from acm.policy import EligibilityContext, Policy, ReleaseRules
from acm.state_machines.baselines import (
    OperationalStatus,
    baseline_transition_allowed,
)
from scenarios import scenario_f


def _a1(report):
    return next(i for i in report.items.values() if i.ref.id == "aci:agent:planner")


# --- Nouvelle baseline ---

def test_new_baseline_default_blocks():
    """Par défaut : A1 impacted + blocked."""
    graph, evidence = scenario_f.build()
    ctx = PropagationContext(eligibility_context=EligibilityContext.BASELINE_RELEASE)
    report = propagate(graph, evidence, ctx)

    a1 = _a1(report)
    assert a1.computed.impact_state == ImpactState.IMPACTED
    assert a1.computed.eligibility_state == EligibilityState.BLOCKED
    assert report.valid is False


def test_new_baseline_waiver_downgrades_to_warning():
    """Avec dérogation allow_deprecated : A1 warning (au lieu de blocked)."""
    graph, evidence = scenario_f.build()
    ctx = PropagationContext(eligibility_context=EligibilityContext.BASELINE_RELEASE)
    policy = Policy(release_rules=ReleaseRules(allow_deprecated=True))
    report = propagate(graph, evidence, ctx, policy)

    a1 = _a1(report)
    assert a1.computed.eligibility_state == EligibilityState.WARNING


def test_impact_is_impacted_not_stale():
    """La dépréciation rend impacted, pas stale (pas de preuve périmée ici)."""
    graph, evidence = scenario_f.build()
    report = propagate(graph, evidence, PropagationContext())
    a1 = _a1(report)
    assert a1.computed.impact_state == ImpactState.IMPACTED


def test_reason_points_to_deprecation():
    graph, evidence = scenario_f.build()
    report = propagate(graph, evidence, PropagationContext())
    a1 = _a1(report)
    codes = {r.code for r in a1.computed.reasons}
    assert "ACM-PROP-DEPRECATED-WARN" in codes


# --- Baseline historique (§6.5) ---

def test_historical_baseline_state_unchanged():
    """§6.5 — une baseline released ne change PAS d'état automatiquement
    quand un de ses ACI devient déprécié."""
    b = scenario_f.historical_baseline()
    assert b.state == BaselineState.RELEASED

    # La dépréciation d'un ACI est un fait EXTERNE : elle n'altère pas le
    # lifecycle de la baseline. On peut seulement lui poser un statut opérationnel.
    b.flag_operational(OperationalStatus.REASSESSMENT_REQUIRED)

    assert b.state == BaselineState.RELEASED  # inchangé
    assert b.operational_status == OperationalStatus.REASSESSMENT_REQUIRED


def test_historical_operational_status_is_separate_registry():
    """Le statut opérationnel est distinct du lifecycle (registre séparé)."""
    b = scenario_f.historical_baseline()
    b.flag_operational(OperationalStatus.WITHDRAWAL_RECOMMENDED)
    # Recommandation de retrait != retrait effectif
    assert b.state == BaselineState.RELEASED
    assert b.operational_status == OperationalStatus.WITHDRAWAL_RECOMMENDED


def test_baseline_transition_matrix():
    """§6.3 — la matrice de transitions autorisées est respectée."""
    assert baseline_transition_allowed(BaselineState.RELEASED, BaselineState.SUPERSEDED)
    assert baseline_transition_allowed(BaselineState.RELEASED, BaselineState.WITHDRAWN)
    # interdites
    assert not baseline_transition_allowed(BaselineState.WITHDRAWN, BaselineState.RELEASED)
    assert not baseline_transition_allowed(BaselineState.SUPERSEDED, BaselineState.RELEASED)


def test_baseline_explicit_transition_only():
    """La baseline ne change d'état que par transition explicite valide."""
    b = scenario_f.historical_baseline()
    b.transition(BaselineState.SUPERSEDED)
    assert b.state == BaselineState.SUPERSEDED

    # une transition interdite lève une erreur
    import pytest
    with pytest.raises(ValueError):
        b.transition(BaselineState.RELEASED)


if __name__ == "__main__":
    import pytest as _p
    _p.main([__file__, "-v"])
