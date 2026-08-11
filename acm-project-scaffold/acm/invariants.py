"""Invariants normatifs I1 à I14 (§23).

Chaque invariant est une assertion réutilisable retournant une liste de
`InvariantViolation`. Une implémentation conforme (§28) doit vérifier I1..I14.

Trois familles :
  - STRUCTURELS : vérifiables sur un graphe + rapport de propagation
    (I1, I4, I5, I9, I10). Appelés par `check_report_invariants()`.
  - TRANSITION : vérifiables lors d'un changement d'état
    (I2, I3, I6, I12). Fonctions dédiées.
  - RUNTIME / BASELINE / META : I7, I11, I13, I14. Fonctions dédiées.

`check_report_invariants()` est appelable en fin de `propagate()` en mode
strict pour garantir les invariants structurels à chaque calcul.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from pydantic import BaseModel

from .models.aci import ConfigurationGraph, Relation
from .models.enums import (
    AssuranceState,
    BaselineState,
    EligibilityState,
    ImpactState,
    LifecycleState,
    PromotionState,
    PropagationPolicy,
    QualityState,
)
from .models.refs import ACIRef
from .models.status import ItemStatus, PropagationReport


class InvariantViolation(BaseModel):
    """Violation d'un invariant normatif."""

    code: str          # ex. ACM-QUALITY-001
    invariant: str     # ex. I5
    message: str
    item_ref: Optional[ACIRef] = None


# ---------------------------------------------------------------------------
# STRUCTURELS — vérifiables sur (graphe, rapport)
# ---------------------------------------------------------------------------

def i1_new_revision_is_draft(revision) -> List[InvariantViolation]:
    """I1 (ACM-LIFE-001) — toute nouvelle révision commence en draft.

    Vérifié à la création (state_machines.revisions.new_revision garantit
    déjà draft). Ici sous forme d'assertion ponctuelle sur une révision.
    """
    v: List[InvariantViolation] = []
    if revision.declared.lifecycle_state != LifecycleState.DRAFT:
        v.append(InvariantViolation(
            code="ACM-LIFE-001", invariant="I1",
            message="A newly created revision must start in draft.",
            item_ref=revision.ref,
        ))
    return v


def i4_validated_implies_assessed(item: ItemStatus) -> List[InvariantViolation]:
    """I4 (ACM-ASSURANCE-001) — validated ⇒ assurance intrinsèque assessed.

    Vérifie la COHÉRENCE INTRINSÈQUE : une révision déclarée validated ne peut
    pas avoir été déclarée avec une assurance intrinsèque < assessed. Ceci porte
    sur l'état DÉCLARÉ, pas sur l'assurance effective : une dépendance peut
    dégrader l'assurance effective d'un composite validé sans contredire I4
    (c'est la propagation restrictive du §3.4, pas une incohérence de promotion).

    Choix documenté : voir docs/requirements_update_I4_I5.md (la spec §23 énonce
    l'effectif ; on retient le déclaré et on propose de reformuler la spec).
    """
    v: List[InvariantViolation] = []
    if (
        item.lifecycle_state == LifecycleState.VALIDATED
        and item.declared_assurance != AssuranceState.ASSESSED
    ):
        v.append(InvariantViolation(
            code="ACM-ASSURANCE-001", invariant="I4",
            message="A validated revision must be declared with assurance = assessed.",
            item_ref=item.ref,
        ))
    return v


def i5_validated_excludes_nok(item: ItemStatus) -> List[InvariantViolation]:
    """I5 (ACM-QUALITY-001) — validated ⇒ qualité intrinsèque ≠ nok.

    Porte sur l'état DÉCLARÉ. Une révision ne peut pas être déclarée validated
    tout en étant déclarée nok (incohérence de promotion). En revanche, un
    composite validé dont la qualité EFFECTIVE devient nok par propagation
    d'une dépendance NE viole PAS I5 : c'est le mécanisme restrictif du §3.4
    (l'éligibilité est bloquée, le jugement intrinsèque est préservé).
    """
    v: List[InvariantViolation] = []
    if (
        item.lifecycle_state == LifecycleState.VALIDATED
        and item.declared_quality == QualityState.NOK
    ):
        v.append(InvariantViolation(
            code="ACM-QUALITY-001", invariant="I5",
            message="A validated revision cannot be declared with quality = nok.",
            item_ref=item.ref,
        ))
    return v


def i9_blocking_dep_nok(
    graph: ConfigurationGraph, item: ItemStatus, status: Dict[str, ItemStatus]
) -> List[InvariantViolation]:
    """I9 (ACM-PROP-001) — dépendance requise+blocking avec Qe=nok
    ⇒ source blocked."""
    v: List[InvariantViolation] = []
    for rel in graph.dependencies_of(item.ref):
        if not (rel.required and rel.propagation_policy == PropagationPolicy.BLOCKING):
            continue
        dep = status.get(rel.target.key())
        if dep is None:
            continue
        if (
            dep.computed.effective_quality == QualityState.NOK
            and item.computed.eligibility_state != EligibilityState.BLOCKED
        ):
            v.append(InvariantViolation(
                code="ACM-PROP-001", invariant="I9",
                message="Required blocking dependency is NOK but source is not blocked.",
                item_ref=item.ref,
            ))
    return v


def i10_dependency_change_staleness(
    graph: ConfigurationGraph, item: ItemStatus, status: Dict[str, ItemStatus]
) -> List[InvariantViolation]:
    """I10 (ACM-EVIDENCE-002) — si une preuve référence une révision de
    dépendance différente de la révision courante, son applicabilité est stale.

    Vérification structurelle : si une dépendance requise a un impact `stale`
    et que la source possède une couverture qui en dépend, la source ne doit
    pas rester `current`.
    """
    v: List[InvariantViolation] = []
    for rel in graph.dependencies_of(item.ref):
        if not rel.impact_dependency:
            continue
        dep = status.get(rel.target.key())
        if dep is None:
            continue
        if (
            dep.computed.impact_state == ImpactState.STALE
            and item.computed.impact_state == ImpactState.CURRENT
        ):
            v.append(InvariantViolation(
                code="ACM-EVIDENCE-002", invariant="I10",
                message="Dependency is stale but dependent remains current.",
                item_ref=item.ref,
            ))
    return v


def check_report_invariants(
    graph: ConfigurationGraph, report: PropagationReport
) -> List[InvariantViolation]:
    """Vérifie tous les invariants STRUCTURELS sur un rapport de propagation.

    Couvre I4, I5, I9, I10. Appelable en fin de propagate() en mode strict.
    """
    violations: List[InvariantViolation] = []
    for item in report.items.values():
        violations += i4_validated_implies_assessed(item)
        violations += i5_validated_excludes_nok(item)
        violations += i9_blocking_dep_nok(graph, item, report.items)
        violations += i10_dependency_change_staleness(graph, item, report.items)
    return violations


# ---------------------------------------------------------------------------
# TRANSITION — vérifiables lors d'un changement d'état
# ---------------------------------------------------------------------------

def i2_validation_targets_exact_revision(
    target_ref: ACIRef,
) -> List[InvariantViolation]:
    """I2 (ACM-LIFE-002) — toute preuve de validation référence un
    revision_id ET un digest (l'identité logique seule est insuffisante)."""
    v: List[InvariantViolation] = []
    if target_ref.revision_id is None or target_ref.digest is None:
        v.append(InvariantViolation(
            code="ACM-LIFE-002", invariant="I2",
            message="Validation must target an exact revision_id and digest.",
            item_ref=target_ref,
        ))
    return v


# Matrice de transitions du lifecycle des ACI (§5.3)
_ACI_TRANSITIONS = {
    (LifecycleState.DRAFT, LifecycleState.CANDIDATE),
    (LifecycleState.DRAFT, LifecycleState.ARCHIVED),
    (LifecycleState.CANDIDATE, LifecycleState.DRAFT),
    (LifecycleState.CANDIDATE, LifecycleState.VALIDATED),
    (LifecycleState.CANDIDATE, LifecycleState.ARCHIVED),
    (LifecycleState.VALIDATED, LifecycleState.DEPRECATED),
    (LifecycleState.DEPRECATED, LifecycleState.ARCHIVED),
}


def i3_transition_in_matrix(
    current: LifecycleState, target: LifecycleState
) -> List[InvariantViolation]:
    """I3 (ACM-LIFE-003) — toute transition doit figurer dans la matrice §5.3."""
    v: List[InvariantViolation] = []
    if (current, target) not in _ACI_TRANSITIONS:
        v.append(InvariantViolation(
            code="ACM-LIFE-003", invariant="I3",
            message=f"Illegal lifecycle transition {current.value} -> {target.value}.",
        ))
    return v


def i6_archived_not_reactivable(
    current: LifecycleState, target: LifecycleState
) -> List[InvariantViolation]:
    """I6 (ACM-LIFE-004) — archived ne peut transiter vers aucun autre état."""
    v: List[InvariantViolation] = []
    if current == LifecycleState.ARCHIVED and target != LifecycleState.ARCHIVED:
        v.append(InvariantViolation(
            code="ACM-LIFE-004", invariant="I6",
            message="An archived revision cannot be reactivated; create a new revision.",
        ))
    return v


def i12_no_direct_promotion(
    current: PromotionState, target: PromotionState
) -> List[InvariantViolation]:
    """I12 (ACM-DYNAMIC-002) — une instance ephemeral ne peut pas devenir
    directement un ACI validated/registered."""
    v: List[InvariantViolation] = []
    forbidden = {
        (PromotionState.EPHEMERAL, PromotionState.REGISTERED),
        (PromotionState.REJECTED, PromotionState.REGISTERED),
        (PromotionState.EXPIRED, PromotionState.REGISTERED),
    }
    if (current, target) in forbidden:
        v.append(InvariantViolation(
            code="ACM-DYNAMIC-002", invariant="I12",
            message=f"Illegal promotion {current.value} -> {target.value}.",
        ))
    return v


# ---------------------------------------------------------------------------
# BASELINE / RUNTIME
# ---------------------------------------------------------------------------

def i7_release_without_block(
    baseline_state: BaselineState,
    required_items: List[ItemStatus],
) -> List[InvariantViolation]:
    """I7 (ACM-BASELINE-002) — baseline released ⇒ tous les items requis
    sont eligible (jamais blocked ; une dérogation peut autoriser warning)."""
    v: List[InvariantViolation] = []
    if baseline_state != BaselineState.RELEASED:
        return v
    for item in required_items:
        if item.computed.eligibility_state == EligibilityState.BLOCKED:
            v.append(InvariantViolation(
                code="ACM-BASELINE-002", invariant="I7",
                message="A released baseline cannot contain a blocked required item.",
                item_ref=item.ref,
            ))
    return v


def i11_dynamic_instance_traceable(signal) -> List[InvariantViolation]:
    """I11 (ACM-DYNAMIC-001) — toute instance dynamique doit référencer
    factory, template, événement de création, config et permissions résolues."""
    v: List[InvariantViolation] = []
    if not signal.traceability.is_traceable():
        v.append(InvariantViolation(
            code="ACM-DYNAMIC-001", invariant="I11",
            message="Dynamic instance must be fully traceable.",
            item_ref=signal.definition_ref,
        ))
    return v


def i13_no_permission_escalation(signal) -> List[InvariantViolation]:
    """I13 (ACM-PERM-001) — P_instance ⊆ P_creator ∩ P_factory ∩ P_environment."""
    v: List[InvariantViolation] = []
    if signal.permissions.has_escalation():
        v.append(InvariantViolation(
            code="ACM-PERM-001", invariant="I13",
            message="Permission escalation beyond allowed ceiling.",
            item_ref=signal.definition_ref,
        ))
    return v


# ---------------------------------------------------------------------------
# META
# ---------------------------------------------------------------------------

def i14_deterministic(
    compute: Callable[[], PropagationReport],
    runs: int = 2,
) -> List[InvariantViolation]:
    """I14 (ACM-PROP-002) — mêmes entrées ⇒ mêmes états effectifs.

    Exécute `compute` plusieurs fois et compare les états calculés item par
    item (on ignore report_id / timestamps, non déterministes par nature).
    """
    v: List[InvariantViolation] = []
    reports = [compute() for _ in range(runs)]
    ref = reports[0]
    for other in reports[1:]:
        for key, item in ref.items.items():
            o = other.items.get(key)
            if o is None:
                v.append(InvariantViolation(
                    code="ACM-PROP-002", invariant="I14",
                    message=f"Item {key} missing across deterministic runs.",
                ))
                continue
            c1, c2 = item.computed, o.computed
            if (
                c1.effective_quality != c2.effective_quality
                or c1.effective_assurance != c2.effective_assurance
                or c1.impact_state != c2.impact_state
                or c1.eligibility_state != c2.eligibility_state
            ):
                v.append(InvariantViolation(
                    code="ACM-PROP-002", invariant="I14",
                    message=f"Non-deterministic computed status for {key}.",
                    item_ref=item.ref,
                ))
    return v


# ---------------------------------------------------------------------------
# Exception de mode strict
# ---------------------------------------------------------------------------

class InvariantViolationError(Exception):
    """Levée en mode strict lorsqu'un invariant structurel est violé."""

    def __init__(self, violations: List[InvariantViolation]):
        self.violations = violations
        codes = ", ".join(f"{v.invariant}:{v.code}" for v in violations)
        super().__init__(f"Invariant violations: {codes}")
