"""Politique de propagation et contexte de calcul (§12.3, §26)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EligibilityContext(str, Enum):
    """§12.3 — L'éligibilité dépend de l'opération évaluée."""

    VALIDATION = "validation"
    BASELINE_RELEASE = "baseline_release"
    RUNTIME = "runtime"
    PROMOTION = "promotion"


class PropagationContext(BaseModel):
    """Contexte passé au moteur de propagation."""

    eligibility_context: EligibilityContext = EligibilityContext.VALIDATION
    now: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Environnement d'évaluation courant (§10.3). Une preuve dont le scope cible
    # un autre environnement n'est pas applicable. None = pas de contrainte.
    environment: Optional[str] = None


class ReleaseRules(BaseModel):
    """§26 — Règles de release d'une politique."""

    require_validated: bool = True
    require_assessed: bool = True
    allow_to_improve: bool = True
    allow_deprecated: bool = False
    allow_warning: bool = False


class Policy(BaseModel):
    """Politique de propagation locale (§26).

    ACM Core v0.1 ne nécessite pas un langage de règles plus général.
    """

    policy_id: str = "policy:propagation:default-v0.1"
    version: str = "0.1.0"
    release_rules: ReleaseRules = Field(default_factory=ReleaseRules)
    # Une politique de projet PEUT exiger effective_quality = ok (§5.4)
    require_ok_for_validation: bool = False


DEFAULT_POLICY = Policy()
