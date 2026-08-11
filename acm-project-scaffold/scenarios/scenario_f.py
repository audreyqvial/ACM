"""Scénario F — Dépendance dépréciée (§24.6).

    Prompt P1.lifecycle_state = deprecated
    Agent A1 uses P1

Nouvelle baseline (par défaut) :
    A1.impact_state = impacted
    A1.eligibility_state = blocked
Avec dérogation (allow_deprecated) :
    A1.eligibility_state = warning (justification obligatoire)

Baseline historique (§6.5) :
    ne change pas automatiquement d'état ;
    peut recevoir reassessment_required dans un registre opérationnel distinct.
"""
from __future__ import annotations

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
    BaselineState,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)
from acm.state_machines.baselines import Baseline

DIMS = ["functional", "robustness"]
REV = "01JR1"


def build() -> Tuple[ConfigurationGraph, List[Evidence]]:
    """P1 déprécié, A1 (validated) uses_prompt P1."""
    p1 = ACIRevision(
        ref=ACIRef(id="aci:prompt:planner-system", revision_id=REV,
                   digest=f"sha256:p1:{REV}"),
        aci_type="prompt",
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.DEPRECATED,
            quality_state=QualityState.OK,
            assurance_state=AssuranceState.ASSESSED,
        ),
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(DIMS)),
    )
    a1 = ACIRevision(
        ref=ACIRef(id="aci:agent:planner", revision_id=REV,
                   digest=f"sha256:a1:{REV}"),
        aci_type="agent",
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.VALIDATED,
            quality_state=QualityState.OK,
            assurance_state=AssuranceState.ASSESSED,
        ),
        assurance_policy=AssurancePolicy(required_assurance_dimensions=list(DIMS)),
    )

    relations = [
        Relation(
            relation_id="rel:a1:uses-prompt:p1",
            source=a1.ref, target=p1.ref,
            relation_type=RelationType.USES_PROMPT,
            required=True, propagation_policy=PropagationPolicy.BLOCKING,
        ),
    ]

    def ev(target):
        return Evidence(
            evidence_id=f"evidence:eval:{target.id}:{REV}",
            target=target, scope_dimensions=list(DIMS),
            result="pass", blocking=True,
        )

    evidence = [ev(p1.ref), ev(a1.ref)]
    return ConfigurationGraph.build([p1, a1], relations), evidence


def historical_baseline() -> Baseline:
    """Une baseline déjà released contenant A1 et P1 (avant dépréciation)."""
    b = Baseline(
        baseline_id="baseline:report-pipeline:v1",
        state=BaselineState.RELEASED,
        digest="sha256:baseline:v1",
        required_items=[
            ACIRef(id="aci:agent:planner", revision_id=REV),
            ACIRef(id="aci:prompt:planner-system", revision_id=REV),
        ],
    )
    return b
