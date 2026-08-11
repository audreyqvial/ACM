"""Calcul et propagation de l'éligibilité (§17).

L'éligibilité dépend du CONTEXTE de l'opération (§12.3) :
  - validation d'une révision candidate (§17.1)
  - inclusion dans une baseline released (§17.2)

Agrégation (§17.3) : eligible < warning < blocked ; on prend le plus sévère
en tenant compte de la politique portée par chaque relation.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..models.aci import ConfigurationGraph
from ..models.enums import (
    AssuranceState,
    EligibilityState,
    ImpactState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    worst_eligibility,
)
from ..models.refs import ACIRef, Reason
from ..models.status import ItemStatus
from ..policy import EligibilityContext, Policy, PropagationContext


def _self_eligibility_validation(
    item: ItemStatus, policy: Policy
) -> Tuple[EligibilityState, List[Reason]]:
    """§17.1 — Éligibilité propre d'une révision candidate à la validation."""
    reasons: List[Reason] = []
    c = item.computed

    # --- blocked ---
    if c.effective_quality == QualityState.NOK:
        reasons.append(Reason(
            code="ACM-ELIG-VAL-QUALITY-NOK",
            message="Effective quality is NOK.",
            observed_state="nok", rule="§17.1", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    if c.effective_assurance == AssuranceState.UNASSESSED:
        reasons.append(Reason(
            code="ACM-ELIG-VAL-UNASSESSED",
            message="Effective assurance is unassessed for final validation.",
            observed_state="unassessed", rule="§17.1", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    # --- warning ---
    if c.effective_quality == QualityState.TO_IMPROVE:
        reasons.append(Reason(
            code="ACM-ELIG-VAL-TO-IMPROVE",
            message="Effective quality is to_improve.",
            observed_state="to_improve", rule="§17.1", severity="warning",
        ))
        return EligibilityState.WARNING, reasons

    if policy.require_ok_for_validation and c.effective_quality != QualityState.OK:
        reasons.append(Reason(
            code="ACM-ELIG-VAL-POLICY-OK-REQUIRED",
            message="Policy requires effective_quality = ok.",
            rule="§5.4", severity="warning",
        ))
        return EligibilityState.WARNING, reasons

    return EligibilityState.ELIGIBLE, reasons


def _self_eligibility_release(
    item: ItemStatus, policy: Policy
) -> Tuple[EligibilityState, List[Reason]]:
    """§17.2 — Éligibilité propre à une baseline released."""
    reasons: List[Reason] = []
    c = item.computed

    # --- blocked ---
    # Cas particulier : un ACI déprécié. Le §24.6 / §6.4 autorise une
    # dérogation (allow_deprecated) qui transforme le blocage en warning.
    # Sans dérogation, deprecated bloque comme tout lifecycle != validated.
    if item.lifecycle_state == LifecycleState.DEPRECATED:
        if policy.release_rules.allow_deprecated:
            reasons.append(Reason(
                code="ACM-ELIG-REL-DEPRECATED-WAIVED",
                message="Deprecated ACI included under an explicit waiver.",
                observed_state="deprecated", rule="§6.4", severity="warning",
            ))
            return EligibilityState.WARNING, reasons
        reasons.append(Reason(
            code="ACM-ELIG-REL-DEPRECATED",
            message="Deprecated ACI cannot enter a new released baseline.",
            observed_state="deprecated", rule="§6.4", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    if item.lifecycle_state != LifecycleState.VALIDATED and policy.release_rules.require_validated:
        reasons.append(Reason(
            code="ACM-ELIG-REL-NOT-VALIDATED",
            message="Lifecycle state is not validated.",
            observed_state=item.lifecycle_state.value, rule="§17.2", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    if c.effective_quality == QualityState.NOK:
        reasons.append(Reason(
            code="ACM-ELIG-REL-QUALITY-NOK",
            message="Effective quality is NOK.",
            observed_state="nok", rule="§17.2", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    if c.effective_assurance != AssuranceState.ASSESSED and policy.release_rules.require_assessed:
        reasons.append(Reason(
            code="ACM-ELIG-REL-NOT-ASSESSED",
            message="Effective assurance is not assessed.",
            observed_state=c.effective_assurance.value, rule="§17.2", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    if c.impact_state == ImpactState.STALE:
        reasons.append(Reason(
            code="ACM-ELIG-REL-STALE",
            message="Impact state is stale.",
            observed_state="stale", rule="§17.2", severity="blocking",
        ))
        return EligibilityState.BLOCKED, reasons

    # --- warning ---
    if c.effective_quality == QualityState.TO_IMPROVE and policy.release_rules.allow_to_improve:
        reasons.append(Reason(
            code="ACM-ELIG-REL-TO-IMPROVE",
            message="Effective quality is to_improve.",
            observed_state="to_improve", rule="§17.2", severity="warning",
        ))
        return EligibilityState.WARNING, reasons

    if c.impact_state == ImpactState.IMPACTED:
        reasons.append(Reason(
            code="ACM-ELIG-REL-IMPACTED",
            message="Impact state is impacted.",
            observed_state="impacted", rule="§17.2", severity="warning",
        ))
        return EligibilityState.WARNING, reasons

    return EligibilityState.ELIGIBLE, reasons


def _propagated_from_deps(
    graph: ConfigurationGraph,
    ref: ACIRef,
    status: Dict[str, ItemStatus],
    policy: Policy,
    ctx: PropagationContext,
) -> Tuple[EligibilityState, List[Reason]]:
    """Propagation de l'éligibilité des enfants selon la politique de relation.

    §17.3 : la propagation d'un enfant ne s'applique que selon la politique
    portée par la relation (blocking / warning / informational / none).
    """
    agg = EligibilityState.ELIGIBLE
    reasons: List[Reason] = []

    for rel in graph.dependencies_of(ref):
        dep = status.get(rel.target.key())
        if dep is None:
            # §S02 — Référence requise non résolue (target absente du graphe).
            # La validité structurelle et l'éligibilité restent des concepts
            # distincts, mais elles sont RELIÉES quand l'erreur structurelle est
            # directement attribuable à cet ACI : une dépendance REQUISE pointant
            # vers une révision absente rend la source non éligible.
            if rel.required:
                reasons.append(Reason(
                    code="ACM-REF-UNRESOLVED",
                    message="A required dependency reference is unresolved (target missing).",
                    source_ref=rel.target,
                    relation_type=rel.relation_type.value,
                    observed_state="unresolved",
                    rule="§S02", severity="blocking",
                ))
                agg = worst_eligibility(agg, EligibilityState.BLOCKED)
            continue
        dep_elig = dep.computed.eligibility_state
        dep_quality = dep.computed.effective_quality
        dep_deprecated = dep.lifecycle_state == LifecycleState.DEPRECATED

        # --- Dépendance dépréciée (§6.4, §17.1, §24.3, §24.6) ---
        # En release : blocked par défaut, dégradable en warning par politique.
        # En validation : warning.
        if dep_deprecated and rel.required:
            if ctx.eligibility_context == EligibilityContext.BASELINE_RELEASE:
                if policy.release_rules.allow_deprecated:
                    reasons.append(Reason(
                        code="ACM-PROP-DEPRECATED-WARN",
                        message="A required dependency is deprecated (waived to warning).",
                        source_ref=rel.target,
                        relation_type=rel.relation_type.value,
                        observed_state="deprecated",
                        rule="§6.4", severity="warning",
                    ))
                    agg = worst_eligibility(agg, EligibilityState.WARNING)
                else:
                    reasons.append(Reason(
                        code="ACM-PROP-DEPRECATED-BLOCK",
                        message="A required dependency is deprecated.",
                        source_ref=rel.target,
                        relation_type=rel.relation_type.value,
                        observed_state="deprecated",
                        rule="§6.4", severity="blocking",
                    ))
                    agg = worst_eligibility(agg, EligibilityState.BLOCKED)
            else:
                reasons.append(Reason(
                    code="ACM-PROP-DEPRECATED-WARN",
                    message="A required dependency is deprecated.",
                    source_ref=rel.target,
                    relation_type=rel.relation_type.value,
                    observed_state="deprecated",
                    rule="§17.1", severity="warning",
                ))
                agg = worst_eligibility(agg, EligibilityState.WARNING)

        if rel.propagation_policy == PropagationPolicy.BLOCKING and rel.required:
            # §I9 : dépendance blocking requise NOK -> source blocked
            if dep_quality == QualityState.NOK or dep_elig == EligibilityState.BLOCKED:
                reasons.append(Reason(
                    code="ACM-PROP-001",
                    message="A required blocking dependency is NOK/blocked.",
                    source_ref=rel.target,
                    relation_type=rel.relation_type.value,
                    observed_state=dep_quality.value,
                    rule="§I9", severity="blocking",
                ))
                agg = worst_eligibility(agg, EligibilityState.BLOCKED)
            elif dep_elig == EligibilityState.WARNING:
                agg = worst_eligibility(agg, EligibilityState.WARNING)

        elif rel.propagation_policy == PropagationPolicy.WARNING:
            # §15.4 : une dépendance warning avec qualité nok -> warning
            if dep_quality == QualityState.NOK or dep_elig in (
                EligibilityState.WARNING, EligibilityState.BLOCKED
            ):
                reasons.append(Reason(
                    code="ACM-PROP-WARN",
                    message="A warning dependency is problematic.",
                    source_ref=rel.target,
                    relation_type=rel.relation_type.value,
                    observed_state=dep_quality.value,
                    rule="§15.4", severity="warning",
                ))
                agg = worst_eligibility(agg, EligibilityState.WARNING)
        # informational / none : pas d'effet sur l'éligibilité

    return agg, reasons


def compute_eligibility(
    graph: ConfigurationGraph,
    ref: ACIRef,
    status: Dict[str, ItemStatus],
    policy: Policy,
    ctx: PropagationContext,
) -> Tuple[EligibilityState, List[Reason]]:
    """Éligibilité = worst(self, propagation des dépendances) (§17.3)."""
    item = status[ref.key()]

    if ctx.eligibility_context == EligibilityContext.BASELINE_RELEASE:
        self_elig, self_reasons = _self_eligibility_release(item, policy)
    else:
        self_elig, self_reasons = _self_eligibility_validation(item, policy)

    dep_elig, dep_reasons = _propagated_from_deps(graph, ref, status, policy, ctx)

    final = worst_eligibility(self_elig, dep_elig)
    return final, self_reasons + dep_reasons
