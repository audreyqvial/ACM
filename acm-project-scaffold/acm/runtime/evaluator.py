"""Évaluation de gouvernance d'une instance dynamique (§20).

Transforme un RuntimeSignal (produit par un adaptateur quelconque) en états
de gouvernance déterministes. Cœur pur : aucune dépendance framework.

Ordre de décision :
  1. Traçabilité (§I11) — non traçable => bloquant.
  2. Permissions (§I13) — escalade => bloquant + permission_drift=critical.
  3. Factory/outils autorisés (§20.4) — non autorisé => bloquant.
  4. Override comportemental (§20.3) — unknown / unassessed.
  5. Instance conforme (§20.2) — partially_assessed / warning ;
     jamais assessed automatiquement.
  6. Contrôles runtime réussis (§24.4) — élève au scope d'exécution.
"""
from __future__ import annotations

from ..models.enums import (
    AssuranceState,
    EligibilityState,
    PromotionState,
    QualityState,
    RuntimeState,
)
from ..models.refs import Reason
from .instance import (
    DriftClassification,
    PermissionDrift,
    RuntimeInstanceStatus,
)
from .signal import RuntimeSignal, RuntimeTerminalState


def _terminal_to_runtime_state(ts: RuntimeTerminalState) -> RuntimeState:
    return {
        RuntimeTerminalState.CREATED: RuntimeState.CREATED,
        RuntimeTerminalState.COMPLETED: RuntimeState.COMPLETED,
        RuntimeTerminalState.FAILED: RuntimeState.FAILED,
        RuntimeTerminalState.CANCELLED: RuntimeState.CANCELLED,
    }[ts]


def evaluate_runtime_instance(signal: RuntimeSignal) -> RuntimeInstanceStatus:
    """§20 — évalue une instance dynamique à partir de son RuntimeSignal."""
    status = RuntimeInstanceStatus(
        instance_id=signal.instance_id,
        definition_ref=signal.definition_ref,
        runtime_state=_terminal_to_runtime_state(signal.terminal_state),
        promotion_state=PromotionState.EPHEMERAL,
        quality_state=QualityState.UNKNOWN,
        effective_assurance=AssuranceState.UNASSESSED,
        eligibility_state=EligibilityState.ELIGIBLE,
    )

    blocking = False

    # --- 1. Traçabilité (§I11 / ACM-DYNAMIC-001) ---
    if not signal.traceability.is_traceable():
        status.drift_classification = DriftClassification.UNDECLARED_INSTANCE
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-001",
            message="Dynamic instance is not fully traceable "
                    "(missing factory/template/creation event).",
            observed_state="undeclared_instance",
            rule="§I11", severity="blocking",
        ))
        blocking = True

    # --- 2. Permissions (§I13 / ACM-PERM-001) ---
    if signal.permissions.has_escalation():
        status.permission_drift = PermissionDrift.CRITICAL
        status.reasons.append(Reason(
            code="ACM-PERM-001",
            message="Permission escalation beyond creator/factory/environment ceiling.",
            observed_state="permission_drift=critical",
            rule="§I13", severity="blocking",
        ))
        blocking = True

    # --- 3. Factory / outils autorisés (§20.4) ---
    if not signal.traceability.created_by_valid_factory:
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-FACTORY",
            message="Instance not created by a valid factory.",
            rule="§20.4", severity="blocking",
        ))
        blocking = True
    if not signal.permissions.uses_authorized_tools_only:
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-TOOL",
            message="Instance uses an unauthorized tool/definition.",
            rule="§20.4", severity="blocking",
        ))
        blocking = True

    if blocking:
        # §24.5 — instance non autorisée : nok / unassessed / blocked.
        status.quality_state = QualityState.NOK
        status.effective_assurance = AssuranceState.UNASSESSED
        status.eligibility_state = EligibilityState.BLOCKED
        return status

    cfg = signal.resolved_config

    # --- 4a. Override d'un champ INTERDIT (§S20) ---
    # Un override de champs non surchargeables (outils, identité de modèle,
    # politiques, permissions, sources mémoire/récupération) est un blocage dur,
    # pas un simple avertissement : l'instance modifie un aspect qu'elle ne peut
    # légitimement pas modifier. Traité AVANT l'override tolérable du §20.3.
    if cfg.has_forbidden_override():
        status.quality_state = QualityState.NOK
        status.effective_assurance = AssuranceState.UNASSESSED
        status.eligibility_state = EligibilityState.BLOCKED
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-FORBIDDEN-OVERRIDE",
            message="Instance overrides a non-overridable field "
                    "(tool set, model identity, policy, permissions, or memory/"
                    "retrieval source); this is not eligible.",
            observed_state="forbidden_override",
            rule="§S20", severity="blocking",
        ))
        return status

    # --- 4b. Override comportemental toléré (§20.3) ---
    if cfg.has_behavioral_override():
        status.quality_state = QualityState.UNKNOWN
        status.effective_assurance = AssuranceState.UNASSESSED
        status.eligibility_state = EligibilityState.WARNING
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-OVERRIDE",
            message="Behavioral override present; runtime checks required "
                    "before any assurance can be granted.",
            observed_state="unassessed",
            rule="§20.3", severity="warning",
        ))
        # Les contrôles runtime peuvent élever cette instance (§24.4).
        if signal.runtime_checks_completed and signal.runtime_checks_passed:
            status.quality_state = QualityState.OK
            status.effective_assurance = AssuranceState.ASSESSED
            status.eligibility_state = EligibilityState.ELIGIBLE
        return status

    # --- 5. Instance conforme sans override (§20.2) ---
    # partially_assessed au mieux : les preuves du template ne couvrent pas
    # nécessairement le contexte runtime. JAMAIS assessed automatiquement.
    status.quality_state = QualityState.UNKNOWN
    status.effective_assurance = AssuranceState.PARTIALLY_ASSESSED
    status.eligibility_state = EligibilityState.WARNING
    status.reasons.append(Reason(
        code="ACM-DYNAMIC-CONFORMING",
        message="Conforming dynamic instance; template evidence does not "
                "necessarily cover the runtime context.",
        observed_state="partially_assessed",
        rule="§20.2", severity="warning",
    ))

    # --- 6. Contrôles runtime réussis (§24.4) ---
    # Élèvent l'instance au scope d'exécution, sans en faire un ACI permanent.
    if signal.runtime_checks_completed and signal.runtime_checks_passed:
        status.quality_state = QualityState.OK
        status.effective_assurance = AssuranceState.ASSESSED
        status.eligibility_state = EligibilityState.ELIGIBLE
        status.reasons.append(Reason(
            code="ACM-DYNAMIC-RUNTIME-OK",
            message="Runtime checks passed for execution scope "
                    "(does not make the instance a permanent ACI).",
            observed_state="assessed",
            rule="§24.4", severity="info",
        ))

    return status
