"""Calcul de l'assurance (§10, §16).

L'assurance est fondée sur la COUVERTURE des preuves, non sur leur réussite.
`assessed` NE SIGNIFIE PAS `passed` (§9.3).

Non-transitivité (§10.5) : une composition n'hérite PAS de l'assurance de ses
enfants. Le silence (absence d'exigence déclarée) ne vaut pas preuve. C'est
le mode de composition (§16.2) qui décide si les dépendances participent.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Set

from ..models.aci import ACIRevision, ConfigurationGraph, Evidence
from ..models.enums import AssuranceState, CompositionAssuranceMode
from ..policy import PropagationContext


class EvidenceApplicability(str, Enum):
    """État d'applicabilité d'une preuve vis-à-vis d'une révision (§10.3, §18).

        applicable    la preuve couvre la révision courante et son contexte ;
        stale         la preuve visait bien la révision mais une dépendance
                      snapshotée a changé, ou une contrainte n'est plus tenue
                      (la preuve doit être renouvelée) ;
        inapplicable  la preuve ne concerne pas cette révision (cible/digest
                      différents), ou est révoquée/expirée.
    """

    APPLICABLE = "applicable"
    STALE = "stale"
    INAPPLICABLE = "inapplicable"


def _snapshot_is_current(
    ev: Evidence, graph: Optional[ConfigurationGraph]
) -> bool:
    """§18.1 — le dependency_snapshot de la preuve correspond-il aux révisions
    de dépendances courantes dans le graphe ?

    Pour chaque dépendance snapshotée, on cherche dans le graphe une révision
    de même id ; si sa révision courante diffère de celle du snapshot, la
    preuve est stale (I10 / ACM-EVIDENCE-002).
    """
    if graph is None or not ev.dependency_snapshot:
        return True
    for snap in ev.dependency_snapshot:
        # Révision courante de cette dépendance dans le graphe (par id logique).
        current = None
        for key, rev in graph.revisions.items():
            if rev.ref.id == snap.id:
                current = rev.ref
                break
        if current is None:
            # La dépendance snapshotée n'est plus dans le graphe -> stale.
            return False
        if not snap.matches_revision(current):
            return False
    return True


def evidence_applicability(
    ev: Evidence,
    revision: ACIRevision,
    ctx: PropagationContext,
    graph: Optional[ConfigurationGraph] = None,
) -> EvidenceApplicability:
    """§10.3 — état d'applicabilité d'une preuve pour une révision exacte.

    Conditions vérifiées :
      - révocation / expiration -> inapplicable ;
      - cible (id + revision_id + digest) -> inapplicable si divergence ;
      - environnement de scope vs contexte -> inapplicable si divergence ;
      - dependency_snapshot vs révisions courantes -> stale si divergence.
    """
    if ev.revoked:
        return EvidenceApplicability.INAPPLICABLE
    if ev.valid_until is not None and ctx.now > ev.valid_until:
        return EvidenceApplicability.INAPPLICABLE
    if not ev.targets_revision(revision.ref):
        return EvidenceApplicability.INAPPLICABLE

    # Contrainte d'environnement (§10.3) : si la preuve déclare un environnement
    # et que le contexte en impose un autre, elle n'est pas applicable.
    if (
        ctx.environment is not None
        and ev.scope_environment is not None
        and ev.scope_environment != ctx.environment
    ):
        return EvidenceApplicability.INAPPLICABLE

    # Staleness par snapshot de dépendances (§18.1).
    if not _snapshot_is_current(ev, graph):
        return EvidenceApplicability.STALE

    return EvidenceApplicability.APPLICABLE


def evidence_is_applicable(
    ev: Evidence,
    revision: ACIRevision,
    ctx: PropagationContext,
    graph: Optional[ConfigurationGraph] = None,
) -> bool:
    """Compat : True uniquement si strictement `applicable` (ni stale ni inapplicable)."""
    return evidence_applicability(ev, revision, ctx, graph) == EvidenceApplicability.APPLICABLE


def applicable_evidence(
    revision: ACIRevision,
    evidence: List[Evidence],
    ctx: PropagationContext,
    graph: Optional[ConfigurationGraph] = None,
) -> List[Evidence]:
    """Sous-ensemble des preuves strictement applicables à cette révision."""
    return [
        ev for ev in evidence
        if evidence_applicability(ev, revision, ctx, graph)
        == EvidenceApplicability.APPLICABLE
    ]


def classify_evidence(
    revision: ACIRevision,
    evidence: List[Evidence],
    ctx: PropagationContext,
    graph: Optional[ConfigurationGraph] = None,
) -> Dict[str, List[Evidence]]:
    """Classe les preuves d'une révision par état d'applicabilité (pour le rapport)."""
    buckets: Dict[str, List[Evidence]] = {
        "applicable": [], "stale": [], "inapplicable": [],
    }
    for ev in evidence:
        state = evidence_applicability(ev, revision, ctx, graph)
        buckets[state.value].append(ev)
    return buckets


def covered_dimensions(
    revision: ACIRevision, applicable: List[Evidence]
) -> Set[str]:
    """E_d(x) — dimensions requises effectivement couvertes.

    Plusieurs preuves peuvent CONJOINTEMENT couvrir R_d(x) :
        proof_1 -> functional
        proof_2 -> security
    couvrent ensemble ["functional", "security"].

    Une dimension n'est comptée que si elle est requise ET couverte par au
    moins une preuve applicable.
    """
    required = set(revision.effective_assurance_policy().required_assurance_dimensions)
    covered: Set[str] = set()
    for ev in applicable:
        covered |= (set(ev.scope_dimensions) & required)
    return covered


def direct_assurance_from_coverage(
    revision: ACIRevision, applicable: List[Evidence]
) -> AssuranceState:
    """Assurance DIRECTE dérivée de la couverture des exigences directes (§10.2).

        coverage = |E_d(x)| / |R_d(x)|
        unassessed        si couverture nulle
        partially_assessed si 0 < couverture < 1
        assessed          si couverture = 1

    Cas particulier : R_d(x) vide. On NE renvoie PAS assessed par défaut —
    l'absence d'exigence directe est neutre, pas positive. Le mode de
    composition décidera si les dépendances suffisent.
    """
    required = set(revision.effective_assurance_policy().required_assurance_dimensions)
    if not required:
        # Aucune exigence directe déclarée : couverture directe "neutre".
        # direct_complete sera True (rien à couvrir) mais sans progres propre.
        return AssuranceState.UNASSESSED
    covered = covered_dimensions(revision, applicable)
    if len(covered) == 0:
        return AssuranceState.UNASSESSED
    if covered == required:
        return AssuranceState.ASSESSED
    return AssuranceState.PARTIALLY_ASSESSED


def compute_effective_assurance(
    revision: ACIRevision,
    direct_required: Set[str],
    direct_covered: Set[str],
    dependency_states: List[AssuranceState],
) -> AssuranceState:
    """§16.2 — Règle des trois cas (hybrid / aggregate_only / direct_only).

    Remplace l'ancien worst(direct, deps). Distingue explicitement :
      - exigences directes complètes ;
      - dépendances requises assessed ;
      - absence d'exigence (neutre) vs exigence non couverte (dégradant).
    """
    policy = revision.effective_assurance_policy()
    mode = policy.composition_mode

    direct_total = len(direct_required)
    direct_done = len(direct_required & direct_covered)
    direct_complete = direct_done == direct_total  # vrai si direct_total == 0
    direct_has_progress = direct_done > 0

    deps_total = len(dependency_states)
    deps_complete = all(s == AssuranceState.ASSESSED for s in dependency_states)
    deps_have_progress = any(
        s != AssuranceState.UNASSESSED for s in dependency_states
    )

    if mode == CompositionAssuranceMode.HYBRID:
        complete = direct_complete and deps_complete
        progress = direct_has_progress or deps_have_progress
        # Éléments effectivement pris en compte par ce mode :
        considered_count = direct_total + deps_total

    elif mode == CompositionAssuranceMode.AGGREGATE_ONLY:
        complete = deps_complete
        progress = deps_have_progress
        considered_count = deps_total

    elif mode == CompositionAssuranceMode.DIRECT_ONLY:
        complete = direct_complete
        progress = direct_has_progress
        considered_count = direct_total

    else:  # pragma: no cover
        raise ValueError(f"Unsupported assurance mode: {mode}")

    # Garde-fou anti-vacuité (§16.2) : si le mode ne considère AUCUN élément
    # (aucune exigence directe et/ou dépendance selon le mode), `complete` est
    # vrai par vacuité. On refuse assessed sauf autorisation explicite.
    if considered_count == 0:
        if policy.allow_vacuous_assessment:
            return AssuranceState.ASSESSED
        return AssuranceState.UNASSESSED

    if complete:
        return AssuranceState.ASSESSED
    if progress:
        return AssuranceState.PARTIALLY_ASSESSED
    return AssuranceState.UNASSESSED
