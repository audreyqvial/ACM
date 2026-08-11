"""Stratégies Hypothesis pour générer des graphes de configuration ACM valides.

Génère des graphes acycliques (sur les types structurels), avec révisions,
relations et preuves cohérentes. Utilisé par les tests property-based P2.

Le graphe généré est un DAG en couches : les modèles/prompts/tools (feuilles),
puis les agents (qui en dépendent), puis les workflows (qui contiennent des
agents). Cette structure garantit l'absence de cycle interdit tout en couvrant
les relations principales.
"""
from __future__ import annotations

from typing import List, Tuple

from hypothesis import strategies as st

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
    CompositionAssuranceMode,
    EvidenceResult,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)

DIMENSIONS = ["functional", "security", "robustness"]

# Stratégies élémentaires
lifecycle_st = st.sampled_from(list(LifecycleState))
quality_st = st.sampled_from(list(QualityState))
assurance_st = st.sampled_from(list(AssuranceState))
result_st = st.sampled_from(list(EvidenceResult))
mode_st = st.sampled_from(list(CompositionAssuranceMode))
dims_st = st.lists(st.sampled_from(DIMENSIONS), unique=True, max_size=3)


@st.composite
def declared_status(draw) -> DeclaredStatus:
    return DeclaredStatus(
        lifecycle_state=draw(lifecycle_st),
        quality_state=draw(quality_st),
        assurance_state=draw(assurance_st),
    )


@st.composite
def leaf_revision(draw, aci_id: str, aci_type: ACIType) -> ACIRevision:
    """Une révision feuille (prompt/tool/model) sans dépendance."""
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id="01J", digest=f"sha256:{aci_id}"),
        aci_type=aci_type,
        declared=draw(declared_status()),
        assurance_policy=AssurancePolicy(
            required_assurance_dimensions=draw(dims_st),
            composition_mode=draw(mode_st),
        ),
    )


@st.composite
def acm_graph(draw) -> Tuple[ConfigurationGraph, List[Evidence]]:
    """Génère un DAG ACM valide : feuilles -> agents -> workflow, + preuves.

    Structure garantissant l'acyclicité sur les types structurels :
      - 1 model, 1 prompt, 1 tool (feuilles) ;
      - 1..3 agents, chacun uses_prompt/uses_tool/uses_model ;
      - 1 workflow contains les agents.
    """
    model = draw(leaf_revision("aci:model:m", ACIType.MODEL))
    prompt = draw(leaf_revision("aci:prompt:p", ACIType.PROMPT))
    tool = draw(leaf_revision("aci:tool:t", ACIType.TOOL))

    n_agents = draw(st.integers(min_value=1, max_value=3))
    agents = []
    relations = []
    for i in range(n_agents):
        agent = draw(leaf_revision(f"aci:agent:a{i}", ACIType.AGENT))
        agents.append(agent)
        relations.append(Relation(
            relation_id=f"r:a{i}:prompt", source=agent.ref, target=prompt.ref,
            relation_type=RelationType.USES_PROMPT,
            required=draw(st.booleans()),
            propagation_policy=draw(st.sampled_from(list(PropagationPolicy))),
        ))
        relations.append(Relation(
            relation_id=f"r:a{i}:tool", source=agent.ref, target=tool.ref,
            relation_type=RelationType.USES_TOOL,
            required=draw(st.booleans()),
            propagation_policy=draw(st.sampled_from(list(PropagationPolicy))),
        ))
        relations.append(Relation(
            relation_id=f"r:a{i}:model", source=agent.ref, target=model.ref,
            relation_type=RelationType.USES_MODEL,
            required=draw(st.booleans()),
            propagation_policy=draw(st.sampled_from(list(PropagationPolicy))),
        ))

    workflow = draw(leaf_revision("aci:workflow:w", ACIType.WORKFLOW))
    for i, agent in enumerate(agents):
        relations.append(Relation(
            relation_id=f"r:w:contains:a{i}", source=workflow.ref, target=agent.ref,
            relation_type=RelationType.CONTAINS,
            required=draw(st.booleans()),
            propagation_policy=draw(st.sampled_from(list(PropagationPolicy))),
        ))

    all_revs = [model, prompt, tool] + agents + [workflow]

    # Preuves : 0..1 par révision, avec dimensions et résultat aléatoires.
    evidence = []
    for rev in all_revs:
        if draw(st.booleans()):
            evidence.append(Evidence(
                evidence_id=f"e:{rev.ref.id}",
                target=rev.ref,
                scope_dimensions=draw(dims_st),
                result=draw(result_st),
                blocking=draw(st.booleans()),
            ))

    graph = ConfigurationGraph.build(all_revs, relations)
    return graph, evidence
