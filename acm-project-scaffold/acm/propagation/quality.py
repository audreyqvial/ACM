"""Calcul de la qualité effective (§15).

effective_quality = worst(declared_quality, computed_from_dependencies)

Règle clé (§3.4) : une dépendance blocking NOK bloque l'ÉLIGIBILITÉ du parent
et rend sa qualité effective NOK, mais NE MODIFIE PAS sa quality_state
intrinsèque. La provenance du jugement est préservée.
"""
from __future__ import annotations

from typing import Dict, List

from ..models.aci import ACIRevision, ConfigurationGraph, Evidence, Relation
from ..models.enums import (
    EvidenceResult,
    PropagationPolicy,
    QualityState,
    worst_quality,
)
from ..models.refs import ACIRef
from ..models.status import ItemStatus
from ..policy import PropagationContext


def quality_from_evidence(applicable: List[Evidence]) -> QualityState:
    """§9.2/§9.3 — contribution des RÉSULTATS de preuve à la qualité.

    Distinct de la couverture (assurance). Le résultat des preuves applicables
    alimente directement la qualité :

        nok         s'il existe une preuve BLOQUANTE avec result = fail ;
        to_improve  sinon s'il existe une preuve non bloquante avec fail ;
        unknown     sinon s'il existe une preuve inconclusive ;
        ok          s'il existe au moins une preuve pass et aucun problème ;
        ok          (neutre) s'il n'y a aucune preuve — la qualité vient alors
                    du déclaré/dépendances, pas des preuves.

    Ne renvoie jamais un état qui *améliore* la qualité déclarée : c'est
    `worst()` en aval qui combine. Ici on produit la contribution des preuves.
    """
    if not applicable:
        return QualityState.OK  # neutre pour worst()

    has_blocking_fail = any(
        ev.result == EvidenceResult.FAIL and ev.blocking for ev in applicable
    )
    if has_blocking_fail:
        return QualityState.NOK

    has_nonblocking_fail = any(
        ev.result == EvidenceResult.FAIL and not ev.blocking for ev in applicable
    )
    if has_nonblocking_fail:
        return QualityState.TO_IMPROVE

    has_inconclusive = any(
        ev.result == EvidenceResult.INCONCLUSIVE for ev in applicable
    )
    if has_inconclusive:
        return QualityState.UNKNOWN

    return QualityState.OK


def blocking_required_deps(graph: ConfigurationGraph, ref: ACIRef) -> List[Relation]:
    """Req(x) : dépendances requises avec politique blocking (§15.2)."""
    return [
        rel
        for rel in graph.dependencies_of(ref)
        if rel.required and rel.propagation_policy == PropagationPolicy.BLOCKING
    ]


def computed_quality_from_deps(
    graph: ConfigurationGraph,
    ref: ACIRef,
    status: Dict[str, ItemStatus],
) -> QualityState:
    """§15.2 — Qualité calculée depuis les dépendances requises/blocking.

        nok         s'il existe d blocking requis avec Qe(d) = nok
        to_improve  sinon s'il existe d avec Qe(d) = to_improve
        unknown     sinon s'il existe d avec Qe(d) = unknown
        ok          sinon
    """
    req = blocking_required_deps(graph, ref)
    dep_qualities: List[QualityState] = []
    for rel in req:
        dep_status = status.get(rel.target.key())
        if dep_status is None:
            continue
        dep_qualities.append(dep_status.computed.effective_quality)

    if not dep_qualities:
        return QualityState.OK
    if QualityState.NOK in dep_qualities:
        return QualityState.NOK
    if QualityState.TO_IMPROVE in dep_qualities:
        return QualityState.TO_IMPROVE
    if QualityState.UNKNOWN in dep_qualities:
        return QualityState.UNKNOWN
    return QualityState.OK


def compute_effective_quality(
    graph: ConfigurationGraph,
    ref: ACIRef,
    status: Dict[str, ItemStatus],
) -> QualityState:
    """§15.3 — effective_quality = worst(declared, evidence, computed_from_deps).

    Combine trois contributions par sévérité croissante :
      - la qualité DÉCLARÉE (intrinsèque) ;
      - la contribution des RÉSULTATS de preuve applicables (§9.2/§9.3) ;
      - la qualité calculée depuis les dépendances blocking (§15.2).
    """
    item = status[ref.key()]
    declared = item.declared_quality
    from_evidence = item.evidence_quality
    from_deps = computed_quality_from_deps(graph, ref, status)
    return worst_quality(declared, from_evidence, from_deps)
