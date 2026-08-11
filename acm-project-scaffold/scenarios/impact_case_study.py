# Emplacement : scenarios/impact_case_study.py
"""Cas d'étude d'analyse d'impact — changement d'un composant partagé (vague 1.a).

Construit un système agentique réaliste à plusieurs niveaux et modélise la
question de gouvernance : « je dois mettre à jour le modèle LLM partagé — qu'est-ce
qui est affecté ? ».

Topologie (les flèches vont du dépendant vers la dépendance) :

    workflows ── contains ──▶ agents ── uses_prompt ──▶ prompts
                                 │
                                 └───── uses_model ────▶ modèle partagé  ← CHANGÉ

Le modèle partagé est en bas : beaucoup d'ACI en dépendent, directement
(les agents) et indirectement (les workflows qui contiennent ces agents). C'est
le cas où l'investigation manuelle naïve échoue le plus nettement.
"""
from __future__ import annotations

from typing import List, Tuple

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    Evidence,
    Relation,
)
from acm.models.aci import AssurancePolicy, DeclaredStatus
from acm.models.enums import (
    ACIType,
    AssuranceState,
    LifecycleState,
    QualityState,
    RelationType,
)

SHARED_MODEL_ID = "aci:model:shared-llm"


def _rev(aci_id: str, aci_type: ACIType, quality: QualityState = QualityState.OK) -> ACIRevision:
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id="R1", digest=f"sha256:{aci_id}"),
        aci_type=aci_type,
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.VALIDATED,
            quality_state=quality,
            assurance_state=AssuranceState.ASSESSED,
        ),
        assurance_policy=AssurancePolicy(required_assurance_dimensions=["functional"]),
    )


def build(
    *, model_quality: QualityState = QualityState.OK,
    n_prompts: int = 3, n_agents: int = 6, n_workflows: int = 3,
) -> Tuple[ConfigurationGraph, List[Evidence], ACIRef]:
    """Construit le graphe du cas d'étude.

    Retourne (graphe, preuves, référence du modèle partagé). Passer
    model_quality=NOK simule la dégradation du modèle pour la propagation ACM.
    """
    model = _rev(SHARED_MODEL_ID, ACIType.MODEL, quality=model_quality)
    prompts = [_rev(f"aci:prompt:p{i}", ACIType.PROMPT) for i in range(n_prompts)]
    agents = [_rev(f"aci:agent:a{i}", ACIType.AGENT) for i in range(n_agents)]
    workflows = [_rev(f"aci:workflow:w{i}", ACIType.WORKFLOW) for i in range(n_workflows)]

    revisions = [model] + prompts + agents + workflows
    relations: List[Relation] = []

    # Chaque agent utilise le modèle partagé.
    for a in agents:
        relations.append(Relation(
            relation_id=f"r-{a.ref.id}-model",
            source=a.ref, target=model.ref,
            relation_type=RelationType.USES_MODEL,
            required=True,
        ))
    # Chaque agent utilise un prompt (réparti en tourniquet).
    for i, a in enumerate(agents):
        p = prompts[i % n_prompts]
        relations.append(Relation(
            relation_id=f"r-{a.ref.id}-{p.ref.id}",
            source=a.ref, target=p.ref,
            relation_type=RelationType.USES_PROMPT,
            required=True,
        ))
    # Chaque workflow contient des agents (répartis en tourniquet).
    for i, a in enumerate(agents):
        w = workflows[i % n_workflows]
        relations.append(Relation(
            relation_id=f"r-{w.ref.id}-{a.ref.id}",
            source=w.ref, target=a.ref,
            relation_type=RelationType.CONTAINS,
            required=True,
        ))

    graph = ConfigurationGraph.build(revisions, relations)
    evidence = [
        Evidence(
            evidence_id=f"e-{r.ref.id}", target=r.ref,
            scope_dimensions=["functional"], blocking=True,
        )
        for r in revisions
    ]
    return graph, evidence, model.ref
