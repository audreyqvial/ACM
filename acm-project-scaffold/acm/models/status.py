"""États calculés et rapport de propagation (§4.1, §22)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .enums import (
    AssuranceState,
    EligibilityState,
    ImpactState,
    LifecycleState,
    QualityState,
)
from .refs import ACIRef, Reason


class ComputedStatus(BaseModel):
    """États dérivés du graphe, des dépendances et des preuves (§3.2, §4.1).

    DOIT pouvoir être recalculé sans modifier le contenu intrinsèque de l'ACI.
    """

    impact_state: ImpactState = ImpactState.CURRENT
    eligibility_state: EligibilityState = EligibilityState.ELIGIBLE
    effective_quality: QualityState = QualityState.UNKNOWN
    effective_assurance: AssuranceState = AssuranceState.UNASSESSED
    reasons: List[Reason] = Field(default_factory=list)


class ItemStatus(BaseModel):
    """Statut complet d'un item : déclaré (intrinsèque) + calculé."""

    ref: ACIRef
    lifecycle_state: LifecycleState
    declared_quality: QualityState
    declared_assurance: AssuranceState
    computed: ComputedStatus = Field(default_factory=ComputedStatus)

    # Champs de travail intermédiaires (§21.2 ordre de calcul)
    direct_assurance: AssuranceState = AssuranceState.UNASSESSED
    local_impact: ImpactState = ImpactState.CURRENT
    # Dimensions d'assurance requises / couvertes (E_d(x), R_d(x)) — §16.2
    required_dimensions: List[str] = Field(default_factory=list)
    covered_dimensions: List[str] = Field(default_factory=list)
    # Contribution des résultats de preuve à la qualité (§9.2/§9.3)
    evidence_quality: QualityState = QualityState.OK
    # Diagnostics de preuve (§22 rapport enrichi)
    assurance_mode: Optional[str] = None
    applicable_evidence_ids: List[str] = Field(default_factory=list)
    stale_evidence_ids: List[str] = Field(default_factory=list)
    inapplicable_evidence_ids: List[str] = Field(default_factory=list)


class PropagationReport(BaseModel):
    """Rapport de propagation déterministe (§22)."""

    report_id: str
    configuration_digest: Optional[str] = None
    evidence_digest: Optional[str] = None
    context: str = "validation"
    policy_id: Optional[str] = None
    engine_version: str = "0.1.0"
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    valid: bool = True
    summary: Dict[str, int] = Field(default_factory=dict)
    items: Dict[str, ItemStatus] = Field(default_factory=dict)
    # Diagnostics de calcul (§22.2 reproductibilité)
    iterations: int = 0
    converged: bool = True
    graph_problems: List[str] = Field(default_factory=list)

    def build_summary(self) -> None:
        """Agrège les compteurs par état (§22.1)."""
        counts = {
            "eligible": 0, "warning": 0, "blocked": 0,
            "current": 0, "impacted": 0, "stale": 0,
        }
        for item in self.items.values():
            counts[item.computed.eligibility_state.value] += 1
            counts[item.computed.impact_state.value] += 1
        self.summary = counts
        # valid = aucun item bloqué dans le contexte évalué ET convergence
        self.valid = counts["blocked"] == 0 and self.converged
