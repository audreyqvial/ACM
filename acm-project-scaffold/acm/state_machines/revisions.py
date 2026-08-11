"""Héritage d'état lors de la création d'une nouvelle révision (§19.1).

Toute modification du contenu canonique d'un ACI produit une nouvelle révision
avec des états intrinsèques réinitialisés. C'est l'invariant I1 (ACM-LIFE-001).

    new revision_id
    new digest
    lifecycle_state   = draft
    quality_state     = unknown
    assurance_state   = unassessed
    impact_state      = current      (calculé — non affecté par un changement
                                       EXTERNE connu ; ne signifie PAS validé)
    eligibility_state = blocked      (calculé — draft/unassessed => bloqué)

Une preuve d'une révision précédente NE DOIT PAS être automatiquement attachée
à la nouvelle révision (§19.2). Elle reste valide historiquement pour l'ancienne.
"""
from __future__ import annotations

from ..models.aci import ACIRevision, AssurancePolicy, DeclaredStatus
from ..models.enums import AssuranceState, LifecycleState, QualityState
from ..models.refs import ACIRef


def new_revision(
    previous: ACIRevision,
    new_revision_id: str,
    new_digest: str,
    *,
    inherit_assurance_policy: bool = True,
) -> ACIRevision:
    """Crée une nouvelle révision à partir d'une précédente (§19.1).

    Les états intrinsèques sont réinitialisés (draft / unknown / unassessed).
    La politique d'assurance (exigences de dimensions, mode de composition) est
    une propriété structurelle de l'objet, pas un état : on la conserve par
    défaut, car les exigences d'évaluation ne changent pas du seul fait d'une
    nouvelle révision (§19.3 : la classification peut influencer les évaluations
    à relancer, pas les exigences elles-mêmes).

    Aucune preuve n'est attachée : la nouvelle révision part sans couverture.
    """
    new_ref = ACIRef(
        id=previous.ref.id,
        revision_id=new_revision_id,
        digest=new_digest,
    )
    assurance_policy = None
    if inherit_assurance_policy and previous.assurance_policy is not None:
        assurance_policy = previous.assurance_policy.model_copy(deep=True)
    return ACIRevision(
        ref=new_ref,
        aci_type=previous.aci_type,
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.DRAFT,
            quality_state=QualityState.UNKNOWN,
            assurance_state=AssuranceState.UNASSESSED,
        ),
        schema_valid=previous.schema_valid,
        digest_valid=True,
        content_frozen=False,
        assurance_policy=assurance_policy,
    )
