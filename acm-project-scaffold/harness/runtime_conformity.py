# Emplacement : harness/runtime_conformity.py
"""Conformité runtime pour le groupe C — additif, sans toucher au moteur.

Le moteur porte un drift_state DISCRET et stable (DriftClassification :
none / undeclared_instance). Le plan d'évaluation demande une granularité plus
fine (declared_extension, untraceable_instance, configuration_mismatch). Plutôt
que d'enrichir l'enum du moteur, on dérive ici un `classification_detail`
explicatif à partir du signal et du verdict, et un résultat de conformité de
configuration SÉPARÉ (orthogonal au drift_state).

Séparation retenue (cf. conception) :
  - drift_state          : jugement normatif discret (moteur, inchangé) ;
  - classification_detail : explication fine (dérivée ici) ;
  - configuration_conformity : conforme / mismatch entre digest runtime et
    digest de baseline — indépendant du drift_state (une instance traçable peut
    exécuter une config non conforme).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from acm.runtime.instance import DriftClassification
from acm.runtime.signal import RuntimeSignal


class ClassificationDetail(str, Enum):
    """Explication fine du drift, plus riche que le drift_state du moteur."""

    NONE = "none"
    DECLARED_EXTENSION = "declared_extension"       # S14 : mutation autorisée, tracée
    UNTRACEABLE_INSTANCE = "untraceable_instance"   # S15 : provenance insuffisante
    CONFIGURATION_MISMATCH = "configuration_mismatch"  # S16 : config ≠ baseline


class ConfigurationConformity(str, Enum):
    """Résultat de conformité config runtime vs baseline (orthogonal au drift)."""

    CONFORMANT = "conformant"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"       # pas de baseline de référence fournie


def classification_detail(signal: RuntimeSignal, verdict) -> ClassificationDetail:
    """Dérive l'explication fine à partir du signal et du verdict du moteur.

    - drift_state == undeclared_instance  -> untraceable_instance (S15) ;
    - drift_state == none ET instance traçable avec override autorisé
      -> declared_extension (S14) ;
    - drift_state == none sans override    -> none.
    Ne surcharge JAMAIS undeclared_instance pour un simple mismatch de config
    (S16), qui relève de configuration_conformity, pas du drift.
    """
    if verdict.drift_classification == DriftClassification.UNDECLARED_INSTANCE:
        return ClassificationDetail.UNTRACEABLE_INSTANCE

    # drift_state == none : distinguer extension déclarée d'une instance neutre.
    traceable = signal.traceability.is_traceable()
    has_override = signal.resolved_config.has_behavioral_override()
    if traceable and has_override:
        return ClassificationDetail.DECLARED_EXTENSION
    return ClassificationDetail.NONE


def _runtime_digest(signal: RuntimeSignal) -> Optional[str]:
    """Digest de config runtime : pré-rempli sur le signal, sinon recalculé."""
    if signal.resolved_config_digest is not None:
        return signal.resolved_config_digest
    from acm.runtime.governance import digest_of_resolved_config

    return digest_of_resolved_config(signal.resolved_config)


def configuration_conformity(
    signal: RuntimeSignal, baseline_config_digest: Optional[str]
) -> ConfigurationConformity:
    """Compare le digest de config runtime au digest attendu par la baseline (S16).

    Résultat SÉPARÉ du drift_state : une instance parfaitement traçable
    (drift=none) peut exécuter une configuration dont le digest ne correspond pas
    à la baseline -> mismatch. C'est le cœur de S16.
    """
    if baseline_config_digest is None:
        return ConfigurationConformity.UNKNOWN
    if _runtime_digest(signal) == baseline_config_digest:
        return ConfigurationConformity.CONFORMANT
    return ConfigurationConformity.MISMATCH
