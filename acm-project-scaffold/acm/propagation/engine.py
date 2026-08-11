"""Moteur de propagation — point d'entrée `propagate()` (§21).

Ordre de calcul (§21.2) :
  1. validité structurelle
  2. applicabilité des preuves
  3. assurance intrinsèque (couverture directe)
  4. impact local
  5. qualité calculée / effective
  6. assurance effective (règle des trois cas §16.2)
  7. impact propagé
  8. éligibilité locale + propagée

Recalcul itératif jusqu'au point fixe (§21.3). États finis + opérateurs
monotones => point fixe atteint. Déterministe (§I14).
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Set

from ..models.aci import ConfigurationGraph, Evidence
from ..models.enums import AssuranceState, ImpactState
from ..models.status import ItemStatus, PropagationReport
from ..policy import DEFAULT_POLICY, Policy, PropagationContext
from .assurance import (
    EvidenceApplicability,
    applicable_evidence,
    classify_evidence,
    covered_dimensions,
    direct_assurance_from_coverage,
    evidence_applicability,
)
from .assurance import compute_effective_assurance as _effective_assurance
from .eligibility import compute_eligibility
from .impact import compute_effective_impact, compute_local_impact
from .quality import compute_effective_quality, quality_from_evidence


def _initialize_status(
    graph: ConfigurationGraph,
    evidence: List[Evidence],
    ctx: PropagationContext,
) -> Dict[str, ItemStatus]:
    """Étapes 1-4 : validité, applicabilité, couverture directe, impact local."""
    status: Dict[str, ItemStatus] = {}

    for key, rev in graph.revisions.items():
        applicable = applicable_evidence(rev, evidence, ctx, graph)
        direct = direct_assurance_from_coverage(rev, applicable)
        covered = covered_dimensions(rev, applicable)
        ev_quality = quality_from_evidence(applicable)

        # Impact local structurel (§11.4 : dépendance dépréciée...).
        local = compute_local_impact(graph, rev.ref)

        # Staleness par preuve (§18.1, I10) : si une preuve VISANT cette révision
        # est devenue stale (dépendance snapshotée changée / contrainte rompue),
        # la révision devient au minimum stale.
        buckets = classify_evidence(rev, evidence, ctx, graph)
        if buckets["stale"]:
            local = ImpactState.STALE

        status[key] = ItemStatus(
            ref=rev.ref,
            lifecycle_state=rev.declared.lifecycle_state,
            declared_quality=rev.declared.quality_state,
            declared_assurance=rev.declared.assurance_state,
            direct_assurance=direct,
            required_dimensions=list(
                rev.effective_assurance_policy().required_assurance_dimensions
            ),
            covered_dimensions=sorted(covered),
            local_impact=local,
            evidence_quality=ev_quality,
            assurance_mode=rev.effective_assurance_policy().composition_mode.value,
            applicable_evidence_ids=[e.evidence_id for e in buckets["applicable"]],
            stale_evidence_ids=[e.evidence_id for e in buckets["stale"]],
            inapplicable_evidence_ids=[e.evidence_id for e in buckets["inapplicable"]],
        )

    return status


def _effective_assurance_for(
    graph: ConfigurationGraph,
    key: str,
    status: Dict[str, ItemStatus],
) -> AssuranceState:
    """Assemble R_d, E_d et les états de dépendances, puis applique §16.2."""
    item = status[key]
    rev = graph.revisions[key]

    direct_required: Set[str] = set(item.required_dimensions)
    direct_covered: Set[str] = set(item.covered_dimensions)

    # Dépendances participant à l'assurance (assurance_dependency = true)
    dependency_states: List[AssuranceState] = []
    for rel in graph.dependencies_of(item.ref):
        if not rel.assurance_dependency:
            continue
        dep = status.get(rel.target.key())
        if dep is None:
            continue
        dependency_states.append(dep.computed.effective_assurance)

    return _effective_assurance(
        revision=rev,
        direct_required=direct_required,
        direct_covered=direct_covered,
        dependency_states=dependency_states,
    )


def propagate(
    configuration: ConfigurationGraph,
    evidence: List[Evidence],
    context: PropagationContext,
    policy: Policy = DEFAULT_POLICY,
    max_iterations: int = 100,
    strict: bool = False,
    validate_graph: bool = True,
) -> PropagationReport:
    """Calcule les états effectifs de tous les items du graphe (§21.3).

    Si `validate_graph=True`, valide l'intégrité structurelle du graphe (§21.1)
    et reporte les problèmes dans le rapport (et lève en mode strict).
    Si `strict=True`, valide aussi les invariants structurels (I4, I5, I9, I10)
    en fin de calcul et lève `InvariantViolationError` en cas de violation.
    La non-convergence (point fixe non atteint en `max_iterations`) est
    détectée explicitement et rend le rapport invalide (§21.5).
    """
    graph_problems: List[str] = []
    if validate_graph:
        graph_problems = configuration.validate_integrity(strict=strict)

    status = _initialize_status(configuration, evidence, context)

    changed = True
    iterations = 0
    while changed and iterations < max_iterations:
        changed = False
        iterations += 1

        for key in sorted(status.keys()):
            item = status[key]
            ref = item.ref

            new_quality = compute_effective_quality(configuration, ref, status)
            new_impact = compute_effective_impact(configuration, ref, status)
            new_assurance = _effective_assurance_for(configuration, key, status)

            c = item.computed
            if (
                c.effective_quality != new_quality
                or c.impact_state != new_impact
                or c.effective_assurance != new_assurance
            ):
                changed = True
            c.effective_quality = new_quality
            c.impact_state = new_impact
            c.effective_assurance = new_assurance

            new_elig, reasons = compute_eligibility(
                configuration, ref, status, policy, context
            )
            if c.eligibility_state != new_elig:
                changed = True
            c.eligibility_state = new_elig
            c.reasons = reasons

    # Convergence : si `changed` est encore vrai, le point fixe n'a pas été
    # atteint dans la limite d'itérations (§21.5).
    converged = not changed

    report = PropagationReport(
        report_id=f"propagation:{uuid.uuid4().hex[:12]}",
        context=context.eligibility_context.value,
        policy_id=policy.policy_id,
        items=status,
        iterations=iterations,
        converged=converged,
        graph_problems=graph_problems,
    )
    report.build_summary()

    if strict:
        from ..invariants import InvariantViolationError, check_report_invariants
        violations = check_report_invariants(configuration, report)
        if violations:
            raise InvariantViolationError(violations)

    return report
