"""Énumérations normatives ACM v0.1.

Chaque enum reprend EXACTEMENT les états définis dans la spécification.
Les noms d'états sont en anglais technique (langue normative des objets),
les commentaires en français (langue des explications).
"""
from __future__ import annotations

from enum import Enum


class LifecycleState(str, Enum):
    """§5.1 — Lifecycle d'une révision d'ACI."""

    DRAFT = "draft"
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class QualityState(str, Enum):
    """§9.1 — Quality state.

    Ordre de sévérité (§15.3) : ok < unknown < to_improve < nok
    """

    OK = "ok"
    TO_IMPROVE = "to_improve"
    NOK = "nok"
    UNKNOWN = "unknown"


class AssuranceState(str, Enum):
    """§10.1 — Assurance state (fondée sur la couverture des preuves)."""

    UNASSESSED = "unassessed"
    PARTIALLY_ASSESSED = "partially_assessed"
    ASSESSED = "assessed"


class ImpactState(str, Enum):
    """§11.1 — Impact state.

    Ordre de sévérité (§11.3) : current < impacted < stale
    """

    CURRENT = "current"
    IMPACTED = "impacted"
    STALE = "stale"


class EligibilityState(str, Enum):
    """§12.1 — Eligibility state.

    Ordre de sévérité (§17.3) : eligible < warning < blocked
    """

    ELIGIBLE = "eligible"
    WARNING = "warning"
    BLOCKED = "blocked"


class BaselineState(str, Enum):
    """§6.1 — Machine à états des baselines."""

    CANDIDATE = "candidate"
    RELEASED = "released"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class RuntimeState(str, Enum):
    """§7.1 — Machine à états des instances runtime."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TERMINATED = "terminated"


class PromotionState(str, Enum):
    """§8.2 — Machine de promotion des objets créés au runtime."""

    EPHEMERAL = "ephemeral"
    RETAINED = "retained"
    CANDIDATE = "candidate"
    REGISTERED = "registered"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CompositionAssuranceMode(str, Enum):
    """§16.2 — Mode de calcul de l'assurance d'une composition.

    Détermine si l'assurance `assessed` exige une preuve directe, les
    dépendances, ou les deux. Vit sur la politique de l'ACI composite,
    JAMAIS sur une preuve (une preuve absente ne peut pas justifier son
    absence — argument de circularité).

        hybrid          exigences directes + dépendances (défaut comportemental)
        aggregate_only  dépendances seules (composition purement agrégative)
        direct_only     exigences directes seules
    """

    HYBRID = "hybrid"
    AGGREGATE_ONLY = "aggregate_only"
    DIRECT_ONLY = "direct_only"


class PropagationPolicy(str, Enum):
    """§13.4 — Politique de propagation portée par une relation."""

    BLOCKING = "blocking"
    WARNING = "warning"
    INFORMATIONAL = "informational"
    NONE = "none"


class RelationType(str, Enum):
    """§13.1 — Relations du ConfigurationGraph concernées par la propagation."""

    CONTAINS = "contains"
    USES_PROMPT = "uses_prompt"
    USES_TOOL = "uses_tool"
    USES_MODEL = "uses_model"
    GOVERNED_BY = "governed_by"
    EVALUATED_UNDER = "evaluated_under"
    CAN_INSTANTIATE = "can_instantiate"
    TEMPLATES = "templates"


class ACIType(str, Enum):
    """Types d'ACI reconnus (§) — normalise aci_type."""

    PROMPT = "prompt"
    TOOL = "tool"
    MODEL = "model"
    AGENT = "agent"
    WORKFLOW = "workflow"
    TEMPLATE = "template"
    FACTORY = "factory"
    POLICY = "policy"
    OTHER = "other"


class EvidenceResult(str, Enum):
    """§10.4 — résultat d'une preuve (distinct de sa couverture)."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class ActorType(str, Enum):
    """§5.5 — Types d'acteurs autorisés pour une transition."""

    USER = "user"
    REVIEWER = "reviewer"
    MAINTAINER = "maintainer"
    PIPELINE = "pipeline"
    ACM_ENGINE = "acm_engine"
    EXTERNAL_SYSTEM = "external_system"
    AGENT = "agent"


# --- Ordres de sévérité normatifs (utilisés par l'agrégation "worst-state") ---

QUALITY_SEVERITY = {
    QualityState.OK: 0,
    QualityState.UNKNOWN: 1,
    QualityState.TO_IMPROVE: 2,
    QualityState.NOK: 3,
}

IMPACT_SEVERITY = {
    ImpactState.CURRENT: 0,
    ImpactState.IMPACTED: 1,
    ImpactState.STALE: 2,
}

ELIGIBILITY_SEVERITY = {
    EligibilityState.ELIGIBLE: 0,
    EligibilityState.WARNING: 1,
    EligibilityState.BLOCKED: 2,
}

ASSURANCE_SEVERITY = {
    AssuranceState.ASSESSED: 0,
    AssuranceState.PARTIALLY_ASSESSED: 1,
    AssuranceState.UNASSESSED: 2,
}


def worst_quality(*states: QualityState) -> QualityState:
    """Retourne l'état de qualité le plus sévère (§15.3)."""
    return max(states, key=lambda s: QUALITY_SEVERITY[s])


def worst_impact(*states: ImpactState) -> ImpactState:
    """Retourne l'état d'impact le plus sévère (§11.3)."""
    return max(states, key=lambda s: IMPACT_SEVERITY[s])


def worst_eligibility(*states: EligibilityState) -> EligibilityState:
    """Retourne l'état d'éligibilité le plus sévère (§17.3)."""
    return max(states, key=lambda s: ELIGIBILITY_SEVERITY[s])


def worst_assurance(*states: AssuranceState) -> AssuranceState:
    """Retourne l'état d'assurance le plus sévère (couverture la plus faible)."""
    return max(states, key=lambda s: ASSURANCE_SEVERITY[s])
