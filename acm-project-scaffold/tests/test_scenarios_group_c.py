# Emplacement : tests/test_scenarios_group_c.py
"""Tests du groupe C — runtime, replay et drift (§ plan ACM-S12/S14/S15/S16).

Ces scénarios portent sur le monde runtime (RuntimeSignal, évaluation, drift) et
non sur propagate() : ils sont implémentés comme tests dédiés.

Séparation retenue (cf. conception) :
  - drift_state          : jugement normatif discret du moteur (none /
                           undeclared_instance), INCHANGÉ ;
  - classification_detail : explication fine dérivée (declared_extension,
                           untraceable_instance) — harness/runtime_conformity ;
  - configuration_conformity : conforme / mismatch entre digest runtime et
                           baseline, résultat SÉPARÉ du drift (S16).
"""
from __future__ import annotations

from acm import evaluate_runtime_instance
from acm.models.enums import EligibilityState
from acm.models.refs import ACIRef
from acm.runtime.governance import digest_of_resolved_config
from acm.runtime.instance import DriftClassification, PermissionDrift
from acm.runtime.signal import RuntimeSignal, RuntimeTerminalState
from harness.runtime_conformity import (
    ClassificationDetail,
    ConfigurationConformity,
    classification_detail,
    configuration_conformity,
)
from scenarios import scenario_de


# ============================================================ S12 — replay

def test_s12_replay_is_deterministic():
    """Même signal rejoué → même verdict et même digest (record/replay)."""
    sig = scenario_de.signal_d_conforming()
    record = sig.to_record()
    replayed = RuntimeSignal.from_record(record)

    v1 = evaluate_runtime_instance(sig).model_dump(exclude={"instance_id"})
    v2 = evaluate_runtime_instance(replayed).model_dump(exclude={"instance_id"})
    assert v1 == v2


def test_s12_replay_twice_gives_identical_digests():
    """Deux replays successifs produisent des digests de config identiques."""
    sig = scenario_de.signal_d_conforming()
    r1 = RuntimeSignal.from_record(sig.to_record())
    r2 = RuntimeSignal.from_record(sig.to_record())
    d1 = digest_of_resolved_config(r1.resolved_config)
    d2 = digest_of_resolved_config(r2.resolved_config)
    assert d1 == d2


def test_s12_no_drift_on_nominal_replay():
    """Le replay nominal ne fabrique pas de drift : drift_state = none."""
    sig = scenario_de.signal_d_conforming()
    v = evaluate_runtime_instance(sig)
    assert v.drift_classification == DriftClassification.NONE


# ============================================================ S14 — mutation autorisée

def _spec_conforming_with_authorized_override() -> RuntimeSignal:
    """Instance conforme AVEC override autorisé (provenance complète).

    On part du signal conforme et on marque un override de prompt autorisé,
    template et factory tracés : c'est une extension DÉCLARÉE, pas un drift.
    """
    base = scenario_de.signal_d_conforming()
    resolved = base.resolved_config.model_copy(update={"prompt_overridden": True})
    return base.model_copy(update={"resolved_config": resolved})


def test_s14_authorized_mutation_is_not_drift():
    """Une mutation autorisée et tracée ne produit PAS de drift_state."""
    sig = _spec_conforming_with_authorized_override()
    v = evaluate_runtime_instance(sig)
    assert v.drift_classification == DriftClassification.NONE


def test_s14_classification_detail_is_declared_extension():
    """classification_detail = declared_extension (override tracé, pas un drift)."""
    sig = _spec_conforming_with_authorized_override()
    v = evaluate_runtime_instance(sig)
    detail = classification_detail(sig, v)
    assert detail == ClassificationDetail.DECLARED_EXTENSION


def test_s14_instance_remains_reconstructible():
    """L'instance reste reconstructible par record/replay (baseline intacte)."""
    sig = _spec_conforming_with_authorized_override()
    replayed = RuntimeSignal.from_record(sig.to_record())
    assert evaluate_runtime_instance(replayed).eligibility_state == \
        evaluate_runtime_instance(sig).eligibility_state


# ============================================================ S15 — non traçable

def test_s15_untraceable_instance_drift_state():
    """Instance sans provenance → drift_state = undeclared_instance."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert v.drift_classification == DriftClassification.UNDECLARED_INSTANCE


def test_s15_classification_detail_is_untraceable():
    """classification_detail = untraceable_instance (provenance insuffisante)."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert classification_detail(sig, v) == ClassificationDetail.UNTRACEABLE_INSTANCE


def test_s15_severity_critical_and_blocked():
    """§24.5 — permission_drift critical, eligibility blocked."""
    sig = scenario_de.signal_e_unauthorized()
    v = evaluate_runtime_instance(sig)
    assert v.permission_drift == PermissionDrift.CRITICAL
    assert v.eligibility_state == EligibilityState.BLOCKED


def test_s15_replay_preserves_but_flags():
    """Le replay conserve techniquement l'événement, mais le verdict reste blocked."""
    sig = scenario_de.signal_e_unauthorized()
    replayed = RuntimeSignal.from_record(sig.to_record())
    assert evaluate_runtime_instance(replayed).eligibility_state == EligibilityState.BLOCKED


# ============================================================ S16 — config drift

def test_s16_config_mismatch_is_separate_from_drift():
    """Instance TRAÇABLE (drift=none) mais digest config ≠ baseline → mismatch.

    Cœur de S16 : le mismatch de configuration est orthogonal au drift_state.
    Une instance connue avec un prompt différent n'est PAS une instance non
    déclarée — c'est un problème de conformité de configuration.
    """
    sig = scenario_de.signal_d_conforming()
    v = evaluate_runtime_instance(sig)
    # L'instance est traçable : pas de drift de provenance.
    assert v.drift_classification == DriftClassification.NONE
    # Mais sa config ne correspond pas au digest de baseline attendu.
    baseline_digest = "sha256:P1_R1_baseline_digest_D1"
    conf = configuration_conformity(sig, baseline_digest)
    assert conf == ConfigurationConformity.MISMATCH


def test_s16_conformant_when_digests_match():
    """Si le digest runtime == digest baseline → conformant."""
    sig = scenario_de.signal_d_conforming()
    runtime_digest = digest_of_resolved_config(sig.resolved_config)
    assert configuration_conformity(sig, runtime_digest) == ConfigurationConformity.CONFORMANT


def test_s16_execution_remains_observable():
    """L'exécution reste observable malgré le mismatch (verdict produit)."""
    sig = scenario_de.signal_d_conforming()
    v = evaluate_runtime_instance(sig)
    assert v is not None
    assert v.eligibility_state is not None


def test_s16_mismatch_means_release_not_conformant():
    """Un mismatch de config implique une non-conformité de release."""
    sig = scenario_de.signal_d_conforming()
    baseline_digest = "sha256:different_from_runtime"
    conf = configuration_conformity(sig, baseline_digest)
    release_conformant = conf == ConfigurationConformity.CONFORMANT
    assert release_conformant is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
