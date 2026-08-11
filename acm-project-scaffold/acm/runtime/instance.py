"""Instance runtime dynamique et sa classification (§7, §8, §20)."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ..models.enums import (
    AssuranceState,
    EligibilityState,
    PromotionState,
    QualityState,
    RuntimeState,
)
from ..models.refs import ACIRef, Reason


class DriftClassification(str, Enum):
    """Classification de dérive d'une instance dynamique (§24.5)."""

    NONE = "none"
    UNDECLARED_INSTANCE = "undeclared_instance"


class PermissionDrift(str, Enum):
    """Sévérité de dérive de permissions (§24.5)."""

    NONE = "none"
    CRITICAL = "critical"


class RuntimeInstanceStatus(BaseModel):
    """État complet d'une instance dynamique après évaluation §20.

    Combine états runtime/promotion (intrinsèques) et états de gouvernance
    (calculés) — comme un ACI, mais dans le monde runtime.
    """

    instance_id: str
    definition_ref: ACIRef

    runtime_state: RuntimeState = RuntimeState.CREATED
    promotion_state: PromotionState = PromotionState.EPHEMERAL

    quality_state: QualityState = QualityState.UNKNOWN
    effective_assurance: AssuranceState = AssuranceState.UNASSESSED
    eligibility_state: EligibilityState = EligibilityState.ELIGIBLE

    drift_classification: DriftClassification = DriftClassification.NONE
    permission_drift: PermissionDrift = PermissionDrift.NONE

    reasons: List[Reason] = Field(default_factory=list)
