"""Test des scénarios D et E — Agents dynamiques (§24.4, §24.5).

Inclut le test de record/replay : un RuntimeSignal figé en JSON puis rejoué
produit exactement le même verdict de gouvernance (frontière étanche).
"""
from __future__ import annotations

from acm import (
    AssuranceState,
    EligibilityState,
    PromotionState,
    QualityState,
    RuntimeSignal,
    evaluate_runtime_instance,
)
from acm.runtime.instance import DriftClassification, PermissionDrift
from adapters.deterministic_stub import DeterministicStubAdapter
from scenarios import scenario_de


def _adapter():
    return DeterministicStubAdapter()


# --- Scénario D — instance conforme (§24.4) ---

def test_d_conforming_is_partially_assessed():
    """§24.4 — ephemeral / unknown / partially_assessed / warning."""
    sig = _adapter().create_instance({"signal": scenario_de.signal_d_conforming()})
    st = evaluate_runtime_instance(sig)

    assert st.promotion_state == PromotionState.EPHEMERAL
    assert st.quality_state == QualityState.UNKNOWN
    assert st.effective_assurance == AssuranceState.PARTIALLY_ASSESSED
    assert st.eligibility_state == EligibilityState.WARNING


def test_d_never_assessed_automatically():
    """§20.2 — une instance conforme n'est JAMAIS assessed automatiquement."""
    sig = _adapter().create_instance({"signal": scenario_de.signal_d_conforming()})
    st = evaluate_runtime_instance(sig)
    assert st.effective_assurance != AssuranceState.ASSESSED


def test_d_runtime_checks_elevate_to_execution_scope():
    """§24.4 — après contrôles runtime réussis : ok / assessed / eligible."""
    sig = _adapter().create_instance(
        {"signal": scenario_de.signal_d_conforming(runtime_checks_passed=True)}
    )
    st = evaluate_runtime_instance(sig)
    assert st.quality_state == QualityState.OK
    assert st.effective_assurance == AssuranceState.ASSESSED
    assert st.eligibility_state == EligibilityState.ELIGIBLE
    # Reste éphémère : pas un ACI permanent (§24.4 dernière phrase).
    assert st.promotion_state == PromotionState.EPHEMERAL


# --- Scénario E — instance non autorisée (§24.5) ---

def test_e_unauthorized_is_blocked():
    """§24.5 — nok / unassessed / blocked."""
    sig = _adapter().create_instance({"signal": scenario_de.signal_e_unauthorized()})
    st = evaluate_runtime_instance(sig)
    assert st.quality_state == QualityState.NOK
    assert st.effective_assurance == AssuranceState.UNASSESSED
    assert st.eligibility_state == EligibilityState.BLOCKED


def test_e_drift_classification():
    """§24.5 — drift = undeclared_instance, permission_drift = critical."""
    sig = _adapter().create_instance({"signal": scenario_de.signal_e_unauthorized()})
    st = evaluate_runtime_instance(sig)
    assert st.drift_classification == DriftClassification.UNDECLARED_INSTANCE
    assert st.permission_drift == PermissionDrift.CRITICAL


def test_e_reasons_cover_all_violations():
    """Les quatre violations doivent être tracées."""
    sig = _adapter().create_instance({"signal": scenario_de.signal_e_unauthorized()})
    st = evaluate_runtime_instance(sig)
    codes = {r.code for r in st.reasons}
    assert "ACM-DYNAMIC-001" in codes   # traçabilité
    assert "ACM-PERM-001" in codes      # escalade permissions
    assert "ACM-DYNAMIC-FACTORY" in codes
    assert "ACM-DYNAMIC-TOOL" in codes


# --- Record / replay (frontière étanche) ---

def test_record_replay_roundtrip_is_identical():
    """Un signal figé en JSON puis rejoué produit le MÊME verdict.

    C'est la garantie que la frontière absorbe la non-détermination : le cœur
    traite un signal rejoué exactement comme un signal frais.
    """
    original = scenario_de.signal_d_conforming()

    # record -> JSON dict
    record = original.to_record()
    # replay -> RuntimeSignal reconstruit
    replayed = RuntimeSignal.from_record(record)

    verdict_original = evaluate_runtime_instance(original)
    verdict_replayed = evaluate_runtime_instance(replayed)

    assert verdict_original.quality_state == verdict_replayed.quality_state
    assert verdict_original.effective_assurance == verdict_replayed.effective_assurance
    assert verdict_original.eligibility_state == verdict_replayed.eligibility_state
    assert verdict_original.drift_classification == verdict_replayed.drift_classification


def test_record_replay_via_adapter():
    """L'adaptateur sait rejouer un record (mode replay du port)."""
    adapter = _adapter()
    record = scenario_de.signal_e_unauthorized().to_record()

    replayed = adapter.replay(record)
    st = evaluate_runtime_instance(replayed)
    assert st.eligibility_state == EligibilityState.BLOCKED


def test_determinism_same_signal_same_verdict():
    """§I14 — même signal -> même verdict, à chaque évaluation."""
    sig = scenario_de.signal_d_conforming()
    v1 = evaluate_runtime_instance(sig)
    v2 = evaluate_runtime_instance(sig)
    assert v1.model_dump() == v2.model_dump()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("scenarios D & E: all assertions passed")
