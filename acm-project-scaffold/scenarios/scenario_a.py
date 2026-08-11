"""Scénario A — Promotion nominale (§24.1).

Use case : pipeline de génération de rapports.

    Prompt P1   = validated, ok, assessed
    Prompt P2   = validated, ok, assessed
    Tool  T1    = validated, ok, assessed
    Model M1    = validated, ok, assessed
    Agent A1 (planner) uses P1, T1, M1
    Agent A2 (writer)  uses P2, M1
    Workflow W1 contains A1, A2

Résultat attendu :
    A1/A2/W1 : effective_quality = ok, effective_assurance = assessed,
               impact_state = current, eligibility_state = eligible.
    Une baseline candidate contenant ces objets peut devenir released.
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
    CompositionAssuranceMode,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)

REV = "01JREV"  # revision_id fictif stable pour le scénario

# Dimensions d'assurance requises pour chaque ACI du pipeline.
REQUIRED_DIMENSIONS = ["functional", "robustness"]


def _validated_ok_assessed(
    aci_id: str,
    aci_type: str,
    mode: CompositionAssuranceMode = CompositionAssuranceMode.HYBRID,
) -> ACIRevision:
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id=REV, digest=f"sha256:{aci_id}"),
        aci_type=aci_type,
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.VALIDATED,
            quality_state=QualityState.OK,
            assurance_state=AssuranceState.ASSESSED,
        ),
        content_frozen=True,
        assurance_policy=AssurancePolicy(
            required_assurance_dimensions=list(REQUIRED_DIMENSIONS),
            composition_mode=mode,
        ),
    )


def _blocking_evidence(target: ACIRef) -> Evidence:
    """Preuve bloquante couvrant les dimensions requises -> couverture complète."""
    return Evidence(
        evidence_id=f"evidence:eval:{target.id}:001",
        evidence_type="evaluation",
        target=target,
        scope_environment="local",
        scope_dimensions=list(REQUIRED_DIMENSIONS),
        result="pass",
        blocking=True,
        produced_at=datetime(2026, 7, 27, 10, 0, 0),
        valid_until=None,
    )


def build() -> Tuple[ConfigurationGraph, List[Evidence]]:
    """Construit la configuration + les preuves du scénario A."""
    p1 = _validated_ok_assessed("aci:prompt:planner-system", "prompt")
    p2 = _validated_ok_assessed("aci:prompt:writer-system", "prompt")
    t1 = _validated_ok_assessed("aci:tool:web-search", "tool")
    m1 = _validated_ok_assessed("aci:model:default-llm", "model")
    a1 = _validated_ok_assessed("aci:agent:planner", "agent")
    a2 = _validated_ok_assessed("aci:agent:writer", "agent")
    w1 = _validated_ok_assessed("aci:workflow:report-pipeline", "workflow")

    revisions = [p1, p2, t1, m1, a1, a2, w1]

    def rel(rid, src, tgt, rtype, policy=PropagationPolicy.BLOCKING, required=True):
        return Relation(
            relation_id=rid,
            source=src.ref,
            target=tgt.ref,
            relation_type=rtype,
            required=required,
            propagation_policy=policy,
        )

    relations = [
        rel("rel:a1:uses-prompt:p1", a1, p1, RelationType.USES_PROMPT),
        rel("rel:a1:uses-tool:t1", a1, t1, RelationType.USES_TOOL),
        rel("rel:a1:uses-model:m1", a1, m1, RelationType.USES_MODEL),
        rel("rel:a2:uses-prompt:p2", a2, p2, RelationType.USES_PROMPT),
        rel("rel:a2:uses-model:m1", a2, m1, RelationType.USES_MODEL),
        rel("rel:w1:contains:a1", w1, a1, RelationType.CONTAINS),
        rel("rel:w1:contains:a2", w1, a2, RelationType.CONTAINS),
    ]

    # Preuve bloquante directe pour chaque révision -> couverture directe complète
    evidence = [_blocking_evidence(r.ref) for r in revisions]

    return ConfigurationGraph.build(revisions, relations), evidence
