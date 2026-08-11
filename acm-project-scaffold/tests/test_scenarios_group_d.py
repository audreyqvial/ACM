# Emplacement : tests/test_scenarios_group_d.py
"""Tests du groupe D — agents dynamiques et permissions (§ plan ACM-S18..S21).

Ces scénarios portent sur le monde runtime (RuntimeSignal, évaluateur, machine
de promotion) et non sur propagate() : ils sont implémentés comme tests dédiés,
en réutilisant les signaux des scénarios D/E (scenario_de) et la matrice de
promotion du module state_machines.

Écart normatif documenté (S20) : le plan attend eligibility=blocked pour un
override comportemental interdit ; le moteur actuel produit `warning` (avec
assurance unassessed et un code de raison dédié). On teste le comportement RÉEL
et on documente l'écart, sans le masquer — cf. test_s20_* ci-dessous.
"""
from __future__ import annotations

from acm import evaluate_runtime_instance
from acm.invariants import i12_no_direct_promotion
from acm.models.enums import (
    AssuranceState,
    EligibilityState,
    PromotionState,
    QualityState,
)
from acm.state_machines import InvalidTransitionError, validate_promotion
from acm.state_machines.machines import PROMOTION_MACHINE
from acm.runtime.instance import DriftClassification, PermissionDrift
from acm.runtime.signal import RuntimeSignal
from scenarios import scenario_de


# ============================================================ S18 — conforme

def test_s18_dynamic_instance_is_ephemeral():
    """À la création, une instance dynamique conforme est ephemeral."""
    sig = scenario_de.signal_d_conforming()
    v = evaluate_runtime_instance(sig)
    assert v.promotion_state == PromotionState.EPHEMERAL


def test_s18_provenance_present():
    """Source factory et template présentes (provenance générative)."""
    sig = scenario_de.signal_d_conforming()
    assert sig.traceability.is_traceable()


def test_s18_partially_assessed_and_not_auto_assessed():
    """§20.2 — assurance partially_assessed, jamais assessed automatiquement."""
    sig = scenario_de.signal_d_conforming()
    v = evaluate_runtime_instance(sig)
    assert v.effective_assurance == AssuranceState.PARTIALLY_ASSESSED
    assert v.effective_assurance != AssuranceState.ASSESSED


def test_s18_runtime_checks_elevate_scope():
    """Après contrôles runtime réussis : quality ok, assurance assessed."""
    sig = scenario_de.signal_d_conforming(runtime_checks_passed=True)
    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.OK
    assert v.effective_assurance == AssuranceState.ASSESSED
    assert v.eligibility_state == EligibilityState.ELIGIBLE


def test_s18_never_becomes_permanent_aci_automatically():
    """L'instance reste ephemeral même après contrôles (pas d'ACI permanent)."""
    sig = scenario_de.signal_d_conforming(runtime_checks_passed=True)
    v = evaluate_runtime_instance(sig)
    assert v.promotion_state == PromotionState.EPHEMERAL


# ============================================================ S19 — escalade

def test_s19_permission_escalation_is_critical():
    """Demande d'une capacité hors plafond → permission_drift critical."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert v.permission_drift == PermissionDrift.CRITICAL


def test_s19_escalation_blocks_eligibility():
    """Escalade → eligibility_state blocked (I13)."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert v.eligibility_state == EligibilityState.BLOCKED


def test_s19_escalation_reason_recorded():
    """La tentative et la décision sont conservées (raison ACM-PERM-001)."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert "ACM-PERM-001" in {r.code for r in v.reasons}


def test_s19_replay_preserves_escalation_decision():
    """Le runtime event conserve la tentative : replay → même verdict blocked."""
    sig = scenario_de.signal_e_unauthorized()
    replayed = RuntimeSignal.from_record(sig.to_record())
    assert evaluate_runtime_instance(replayed).eligibility_state == EligibilityState.BLOCKED


# ============================================================ S20 — override interdit

def _signal_forbidden_override() -> RuntimeSignal:
    """Instance conforme mais modifiant des champs comportementaux interdits
    (tool_set, model_identity) — override non autorisé."""
    base = scenario_de.signal_d_conforming()
    resolved = base.resolved_config.model_copy(update={
        "tool_set_overridden": True,
        "model_identity_overridden": True,
    })
    return base.model_copy(update={"resolved_config": resolved})


def test_s20_forbidden_override_is_detected():
    """Un override comportemental interdit est détecté (has_behavioral_override)."""
    sig = _signal_forbidden_override()
    assert sig.resolved_config.has_behavioral_override()


def test_s20_forbidden_override_assurance_unassessed():
    """§ plan S20 — override interdit → assurance unassessed."""
    sig = _signal_forbidden_override()
    v = evaluate_runtime_instance(sig)
    assert v.effective_assurance == AssuranceState.UNASSESSED


def test_s20_forbidden_override_reason_recorded():
    """Une raison dédiée référence l'override interdit (ACM-DYNAMIC-FORBIDDEN-OVERRIDE)."""
    sig = _signal_forbidden_override()
    v = evaluate_runtime_instance(sig)
    assert "ACM-DYNAMIC-FORBIDDEN-OVERRIDE" in {r.code for r in v.reasons}


def test_s20_forbidden_override_is_blocked():
    """CORRECTIF S20 : un override de champ interdit rend l'instance blocked.

    Un override d'un champ non surchargeable (tool set, identité de modèle,
    politiques, permissions, sources mémoire/récupération) est un blocage dur,
    pas un simple avertissement.
    """
    sig = _signal_forbidden_override()
    v = evaluate_runtime_instance(sig)
    assert v.eligibility_state == EligibilityState.BLOCKED
    assert v.effective_assurance == AssuranceState.UNASSESSED


def test_s20_tolerated_override_stays_warning():
    """Un override TOLÉRÉ (prompt seul, autorisé par la factory) reste warning.

    La distinction fine par type de champ : le prompt est réévaluable, pas un
    champ interdit — il ne doit donc pas déclencher le blocage dur du correctif.
    """
    base = scenario_de.signal_d_conforming()
    resolved = base.resolved_config.model_copy(update={"prompt_overridden": True})
    sig = base.model_copy(update={"resolved_config": resolved})
    v = evaluate_runtime_instance(sig)
    assert v.eligibility_state == EligibilityState.WARNING
    assert "ACM-DYNAMIC-OVERRIDE" in {r.code for r in v.reasons}


# ============================================================ S21 — promotion

def test_s21_direct_promotion_ephemeral_to_registered_refused():
    """ephemeral → registered (raccourci) est refusé par la matrice."""
    assert not validate_promotion(
        PromotionState.EPHEMERAL, PromotionState.REGISTERED, strict=False
    ).allowed


def test_s21_direct_promotion_raises_in_strict():
    """En mode strict, la promotion directe lève InvalidTransitionError."""
    import pytest
    with pytest.raises(InvalidTransitionError):
        validate_promotion(PromotionState.EPHEMERAL, PromotionState.REGISTERED, strict=True)


def test_s21_invariant_i12_flags_direct_promotion():
    """I12 signale la promotion directe comme violation."""
    assert len(i12_no_direct_promotion(
        PromotionState.EPHEMERAL, PromotionState.REGISTERED
    )) == 1


def test_s21_progressive_trajectory_is_allowed():
    """La trajectoire correcte ephemeral→retained→candidate→registered passe."""
    steps = [
        (PromotionState.EPHEMERAL, PromotionState.RETAINED),
        (PromotionState.RETAINED, PromotionState.CANDIDATE),
        (PromotionState.CANDIDATE, PromotionState.REGISTERED),
    ]
    for current, target in steps:
        assert PROMOTION_MACHINE.check(current, target).allowed, (current, target)


def test_s21_each_step_is_individually_valid():
    """Chaque étape de la trajectoire est validée sans lever (mode strict)."""
    validate_promotion(PromotionState.EPHEMERAL, PromotionState.RETAINED, strict=True)
    validate_promotion(PromotionState.RETAINED, PromotionState.CANDIDATE, strict=True)
    validate_promotion(PromotionState.CANDIDATE, PromotionState.REGISTERED, strict=True)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
