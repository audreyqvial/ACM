"""Machine à états des baselines (§6) et statut opérationnel historique (§6.5).

Une baseline released est immuable et ne change d'état que par événement
explicite (§6.5). Lorsqu'un de ses ACI est ultérieurement déprécié, elle ne
devient PAS automatiquement invalide : elle peut recevoir un statut
opérationnel EXTERNE, dans un registre distinct de son lifecycle.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ..models.enums import BaselineState
from ..models.refs import ACIRef


class OperationalStatus(str, Enum):
    """§6.5 — statut opérationnel externe d'une baseline historique.

    Distinct du lifecycle de la baseline : n'en modifie pas l'état normatif.
    """

    NONE = "none"
    ATTENTION_REQUIRED = "attention_required"
    REASSESSMENT_REQUIRED = "reassessment_required"
    WITHDRAWAL_RECOMMENDED = "withdrawal_recommended"


# Transitions autorisées de la machine à états des baselines (§6.3)
_ALLOWED_BASELINE_TRANSITIONS = {
    (BaselineState.CANDIDATE, BaselineState.RELEASED),
    (BaselineState.CANDIDATE, BaselineState.WITHDRAWN),
    (BaselineState.RELEASED, BaselineState.SUPERSEDED),
    (BaselineState.RELEASED, BaselineState.WITHDRAWN),
    (BaselineState.SUPERSEDED, BaselineState.WITHDRAWN),
}


def baseline_transition_allowed(current: BaselineState, target: BaselineState) -> bool:
    """§6.3 — la transition figure-t-elle dans la matrice autorisée ?"""
    return (current, target) in _ALLOWED_BASELINE_TRANSITIONS


class Baseline(BaseModel):
    """Snapshot exact de révisions (§6)."""

    baseline_id: str
    state: BaselineState = BaselineState.CANDIDATE
    digest: Optional[str] = None
    required_items: List[ACIRef] = Field(default_factory=list)

    # Statut opérationnel externe — vit dans un "registre" séparé (§6.5).
    # N'affecte pas `state`.
    operational_status: OperationalStatus = OperationalStatus.NONE

    def flag_operational(self, status: OperationalStatus) -> None:
        """Attribue un statut opérationnel SANS changer le lifecycle (§6.5)."""
        self.operational_status = status

    def transition(self, target: BaselineState) -> None:
        """Transition explicite de lifecycle, validée contre la matrice §6.3."""
        if not baseline_transition_allowed(self.state, target):
            raise ValueError(
                f"Transition baseline interdite : {self.state.value} -> {target.value}"
            )
        self.state = target
