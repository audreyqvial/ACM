"""Scénario C — Nouvelle version de prompt (§24.3).

Situation initiale :
    A1 validated with P1 revision R1
    Evidence E1 covers A1 + P1@R1

Changement :
    P1 revision R2 replaces R1
    A1 revision R2 uses P1@R2

Résultat attendu — pour la NOUVELLE révision de A1 (§19.1) :
    lifecycle_state   = draft
    quality_state     = unknown
    assurance_state   = unassessed
    impact_state      = current      (non affectée par un changement EXTERNE ;
                                       bloquée car draft/unassessed, pas impactée)
    eligibility_state = blocked
    -> E1 reste historiquement valide pour A1@R1 mais N'EST PAS applicable à R2.

Résultat attendu — pour une ANCIENNE config utilisant encore P1@R1 (déprécié) :
    impact_state peut devenir impacted
    eligibility_state peut devenir warning

Deux fixtures distinctes : `build_new_revision()` et `build_old_config()`.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    DeclaredStatus,
    Evidence,
    Relation,
)
from acm.models.aci import AssurancePolicy
from acm.models.enums import (
    AssuranceState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)
from acm.state_machines.revisions import new_revision

DIMS = ["functional", "robustness"]

R1 = "01JR1"
R2 = "01JR2"


def _prompt(revision_id: str, lifecycle: LifecycleState) -> ACIRevision:
    return ACIRevision(
        ref=ACIRef(
            id="aci:prompt:planner-system",
            revision_id=revision_id,
            digest=f"sha256:planner-system:{revision_id}",
        ),
        aci_type="prompt",
        declared=DeclaredStatus(
            lifecycle_state=lifecycle,
            quality_state=QualityState.OK if lifecycle != LifecycleState.DRAFT else QualityState.UNKNOWN,
            assurance_state=AssuranceState.ASSESSED if lifecycle != LifecycleState.DRAFT else AssuranceState.UNASSESSED,
        ),
        content_frozen=lifecycle != LifecycleState.DRAFT,
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(DIMS)),
    )


def _agent(revision_id: str, lifecycle: LifecycleState) -> ACIRevision:
    return ACIRevision(
        ref=ACIRef(
            id="aci:agent:planner",
            revision_id=revision_id,
            digest=f"sha256:planner:{revision_id}",
        ),
        aci_type="agent",
        declared=DeclaredStatus(
            lifecycle_state=lifecycle,
            quality_state=QualityState.OK if lifecycle == LifecycleState.VALIDATED else QualityState.UNKNOWN,
            assurance_state=AssuranceState.ASSESSED if lifecycle == LifecycleState.VALIDATED else AssuranceState.UNASSESSED,
        ),
        content_frozen=lifecycle != LifecycleState.DRAFT,
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(DIMS)),
    )


def _evidence_for(target: ACIRef) -> Evidence:
    """E1 — preuve bloquante ciblant une révision exacte."""
    return Evidence(
        evidence_id=f"evidence:eval:{target.id}:{target.revision_id}",
        evidence_type="evaluation",
        target=target,
        scope_environment="local",
        scope_dimensions=list(DIMS),
        result="pass",
        blocking=True,
        produced_at=datetime(2026, 7, 27, 10, 0, 0),
        dependency_snapshot=[
            ACIRef(id="aci:prompt:planner-system", revision_id=target.revision_id),
        ],
    )


def build_new_revision() -> Tuple[ConfigurationGraph, List[Evidence]]:
    """Nouvelle révision A1@R2 utilisant P1@R2, avec E1 ciblant les R1.

    E1 (ciblant A1@R1 et P1@R1) est fournie mais NON applicable à R2.
    """
    p1_r1 = _prompt(R1, LifecycleState.VALIDATED)
    a1_r1 = _agent(R1, LifecycleState.VALIDATED)

    # Nouvelle révision de P1 (contenu modifié -> R2)
    p1_r2 = new_revision(p1_r1, R2, f"sha256:planner-system:{R2}")
    # Nouvelle révision de A1 (utilise désormais P1@R2)
    a1_r2 = new_revision(a1_r1, R2, f"sha256:planner:{R2}")

    revisions = [p1_r2, a1_r2]

    relations = [
        Relation(
            relation_id="rel:a1r2:uses-prompt:p1r2",
            source=a1_r2.ref,
            target=p1_r2.ref,
            relation_type=RelationType.USES_PROMPT,
            required=True,
            propagation_policy=PropagationPolicy.BLOCKING,
        ),
    ]

    # E1 cible les anciennes révisions R1 -> non applicable à R2
    evidence = [
        _evidence_for(a1_r1.ref),
        _evidence_for(p1_r1.ref),
    ]

    return ConfigurationGraph.build(revisions, relations), evidence


def build_old_config() -> Tuple[ConfigurationGraph, List[Evidence]]:
    """Ancienne config : A1@R1 utilise toujours P1@R1, désormais déprécié."""
    p1_r1 = _prompt(R1, LifecycleState.DEPRECATED)
    a1_r1 = _agent(R1, LifecycleState.VALIDATED)

    revisions = [p1_r1, a1_r1]

    relations = [
        Relation(
            relation_id="rel:a1r1:uses-prompt:p1r1",
            source=a1_r1.ref,
            target=p1_r1.ref,
            relation_type=RelationType.USES_PROMPT,
            required=True,
            propagation_policy=PropagationPolicy.BLOCKING,
        ),
    ]

    evidence = [_evidence_for(a1_r1.ref), _evidence_for(p1_r1.ref)]
    return ConfigurationGraph.build(revisions, relations), evidence
