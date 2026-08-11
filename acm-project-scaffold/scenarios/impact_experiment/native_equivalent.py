# Emplacement : scenarios/impact_experiment/native_equivalent.py
"""Trois systèmes natifs-équivalents dédiés à l'expérience quantitative d'impact.

Objectif : CONTRÔLER la variable « framework » en figeant exactement le même
périmètre gouvernable dans les trois cas, tout en conservant des implémentations
natives INDÉPENDANTES (extraites séparément, jamais générées depuis une spec ACM
commune). Ces variantes sont proches des systèmes existants (validés par le
rapport de préservation) mais :
  - éliminent la boucle spécifique LangGraph (reviewer -> researcher), pour un
    périmètre identique entre frameworks ;
  - figent le même inventaire d'ACI et les mêmes révisions r1.

Topologie commune (intention abstraite, SANS boucle) :

        Triage / Router
              |
        +-----+-----+
        |           |
     Research     Direct
        |
     Reviewer
        |
     Finalizer

Périmètre gouvernable (identique aux trois frameworks) :
  Agents  : researcher, reviewer, finalizer, direct
  Prompts : research, review, finalize, direct
  Model   : shared-llm         (partagé par les 4 agents)
  Tool    : web-search         (utilisé par researcher)
  Workflow: main               (contient les 4 agents)

IMPORTANT — chaîne réelle de l'expérience :
    système natif -> extracteur existant -> ConfigurationGraph -> moteur -> P_f(c)
Ici on construit directement le ConfigurationGraph (ce que l'extracteur PRODUIT)
au même périmètre, avec les PREUVES portant `dependency_snapshot` qui rendent la
perturbation détectable par le moteur (staleness §18.1). Les objets natifs réels
(LangGraph/CrewAI/OpenAI) restent construits par les builders existants et
extraits par les extracteurs existants ; cette fixture fige le graphe cible
commun contre lequel l'expérience mesure.

Les trois `build_impact_*` renvoient (ConfigurationGraph, evidence, baseline).
La seule différence inter-framework tolérée est la présence/annotation de la
relation de topologie du workflow, PAS le périmètre gouvernable ACM.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from acm.models.aci import (
    ACIRevision,
    AssurancePolicy,
    ConfigurationGraph,
    DeclaredStatus,
    Evidence,
    Relation,
)
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
from acm.models.refs import ACIRef
from acm.state_machines.baselines import Baseline, BaselineState

R1 = "r1"
REQUIRED_DIMENSIONS = ["functional", "robustness"]

# --------------------------------------------------------------------------
# Inventaire canonique (ids logiques) — IDENTIQUE aux trois frameworks
# --------------------------------------------------------------------------
AGENTS = {
    "researcher": "aci:agent:researcher",
    "reviewer": "aci:agent:reviewer",
    "finalizer": "aci:agent:finalizer",
    "direct": "aci:agent:direct",
}
PROMPTS = {
    "research": "aci:prompt:research",
    "review": "aci:prompt:review",
    "finalize": "aci:prompt:finalize",
    "direct": "aci:prompt:direct",
}
MODEL = "aci:model:shared-llm"
TOOL = "aci:tool:web-search"
WORKFLOW = "aci:workflow:main"
BASELINE = "baseline:release-B"


def _rev(aci_id: str, aci_type: ACIType, rev: str = R1) -> ACIRevision:
    return ACIRevision(
        ref=ACIRef(id=aci_id, revision_id=rev, digest=f"sha256:{aci_id}@{rev}"),
        aci_type=aci_type,
        declared=DeclaredStatus(
            lifecycle_state=LifecycleState.VALIDATED,
            quality_state=QualityState.OK,
            assurance_state=AssuranceState.ASSESSED,
        ),
        content_frozen=True,
        assurance_policy=AssurancePolicy(
            required_assurance_dimensions=list(REQUIRED_DIMENSIONS),
            composition_mode=CompositionAssuranceMode.HYBRID,
        ),
    )


def _rel(
    rid: str,
    source_id: str,
    target_id: str,
    rtype: RelationType,
    *,
    source_rev: str = R1,
    target_rev: str = R1,
    required: bool = True,
) -> Relation:
    return Relation(
        relation_id=rid,
        source=ACIRef(id=source_id, revision_id=source_rev),
        target=ACIRef(id=target_id, revision_id=target_rev),
        relation_type=rtype,
        required=required,
        propagation_policy=PropagationPolicy.BLOCKING,
    )


def _evidence_for(
    agent_id: str,
    *,
    snapshot: List[ACIRef],
) -> Evidence:
    """Preuve bloquante d'un agent, snapshotant ses dépendances à r1.

    Le `dependency_snapshot` est ce qui rend la perturbation détectable : quand
    une dépendance snapshotée passe r1->r2, la preuve devient stale (§18.1) et
    l'agent devient stale, ce qui propage §14.1.
    """
    return Evidence(
        evidence_id=f"evidence:eval:{agent_id}:001",
        evidence_type="evaluation",
        target=ACIRef(id=agent_id, revision_id=R1),
        scope_environment="local",
        scope_dimensions=list(REQUIRED_DIMENSIONS),
        result=EvidenceResult.PASS,
        blocking=True,
        produced_at=datetime(2026, 7, 27, 10, 0, 0),
        dependency_snapshot=snapshot,
    )


def _common_perimeter(
    *,
    model_rev: str,
    tool_rev: str,
    finalize_prompt_rev: str,
) -> Tuple[List[ACIRevision], List[Relation], List[Evidence]]:
    """Construit le périmètre gouvernable commun aux trois frameworks.

    Les révisions des ACI perturbables (model, tool, finalize prompt) sont
    paramétrées : appeler avec r2 sur l'un d'eux matérialise la perturbation
    correspondante. Les autres restent r1.
    """
    # --- Révisions ---
    revs: List[ACIRevision] = [
        _rev(MODEL, ACIType.MODEL, model_rev),
        _rev(TOOL, ACIType.TOOL, tool_rev),
        _rev(PROMPTS["research"], ACIType.PROMPT),
        _rev(PROMPTS["review"], ACIType.PROMPT),
        _rev(PROMPTS["finalize"], ACIType.PROMPT, finalize_prompt_rev),
        _rev(PROMPTS["direct"], ACIType.PROMPT),
        _rev(AGENTS["researcher"], ACIType.AGENT),
        _rev(AGENTS["reviewer"], ACIType.AGENT),
        _rev(AGENTS["finalizer"], ACIType.AGENT),
        _rev(AGENTS["direct"], ACIType.AGENT),
        _rev(WORKFLOW, ACIType.WORKFLOW),
    ]

    # --- Relations gouvernables (identiques aux 3 frameworks) ---
    rels: List[Relation] = [
        # Agents -> Model (les 4 agents partagent shared-llm)
        _rel("rel:researcher:uses-model", AGENTS["researcher"], MODEL,
             RelationType.USES_MODEL, target_rev=model_rev),
        _rel("rel:reviewer:uses-model", AGENTS["reviewer"], MODEL,
             RelationType.USES_MODEL, target_rev=model_rev),
        _rel("rel:finalizer:uses-model", AGENTS["finalizer"], MODEL,
             RelationType.USES_MODEL, target_rev=model_rev),
        _rel("rel:direct:uses-model", AGENTS["direct"], MODEL,
             RelationType.USES_MODEL, target_rev=model_rev),
        # Agents -> Prompts
        _rel("rel:researcher:uses-prompt", AGENTS["researcher"], PROMPTS["research"],
             RelationType.USES_PROMPT),
        _rel("rel:reviewer:uses-prompt", AGENTS["reviewer"], PROMPTS["review"],
             RelationType.USES_PROMPT),
        _rel("rel:finalizer:uses-prompt", AGENTS["finalizer"], PROMPTS["finalize"],
             RelationType.USES_PROMPT, target_rev=finalize_prompt_rev),
        _rel("rel:direct:uses-prompt", AGENTS["direct"], PROMPTS["direct"],
             RelationType.USES_PROMPT),
        # Researcher -> Tool
        _rel("rel:researcher:uses-tool", AGENTS["researcher"], TOOL,
             RelationType.USES_TOOL, target_rev=tool_rev),
        # Workflow -> Agents (contains)
        _rel("rel:main:contains:researcher", WORKFLOW, AGENTS["researcher"],
             RelationType.CONTAINS),
        _rel("rel:main:contains:reviewer", WORKFLOW, AGENTS["reviewer"],
             RelationType.CONTAINS),
        _rel("rel:main:contains:finalizer", WORKFLOW, AGENTS["finalizer"],
             RelationType.CONTAINS),
        _rel("rel:main:contains:direct", WORKFLOW, AGENTS["direct"],
             RelationType.CONTAINS),
    ]

    # --- Preuves : chaque agent snapshote ses dépendances à r1 ---
    evidence: List[Evidence] = [
        _evidence_for(
            AGENTS["researcher"],
            snapshot=[
                ACIRef(id=MODEL, revision_id=R1),
                ACIRef(id=TOOL, revision_id=R1),
                ACIRef(id=PROMPTS["research"], revision_id=R1),
            ],
        ),
        _evidence_for(
            AGENTS["reviewer"],
            snapshot=[
                ACIRef(id=MODEL, revision_id=R1),
                ACIRef(id=PROMPTS["review"], revision_id=R1),
            ],
        ),
        _evidence_for(
            AGENTS["finalizer"],
            snapshot=[
                ACIRef(id=MODEL, revision_id=R1),
                ACIRef(id=PROMPTS["finalize"], revision_id=R1),
            ],
        ),
        _evidence_for(
            AGENTS["direct"],
            snapshot=[
                ACIRef(id=MODEL, revision_id=R1),
                ACIRef(id=PROMPTS["direct"], revision_id=R1),
            ],
        ),
    ]
    return revs, rels, evidence


def _release_baseline() -> Baseline:
    """Baseline de release B : snapshot des révisions r1 du périmètre.

    Utilise le VRAI modèle `Baseline.required_items` (aucune pseudo-relation).
    La baseline released est immuable : un changement d'un required_item déclenche
    un REASSESSMENT (statut opérationnel externe), calculé séparément — voir
    `baseline_reassessment.py`. Elle N'apparaît PAS dans P_f(c).
    """
    required = [
        ACIRef(id=MODEL, revision_id=R1),
        ACIRef(id=TOOL, revision_id=R1),
        *[ACIRef(id=p, revision_id=R1) for p in PROMPTS.values()],
        *[ACIRef(id=a, revision_id=R1) for a in AGENTS.values()],
        ACIRef(id=WORKFLOW, revision_id=R1),
    ]
    return Baseline(
        baseline_id=BASELINE,
        state=BaselineState.RELEASED,
        required_items=required,
    )


# --------------------------------------------------------------------------
# Perturbations : chacune paramètre une révision r1 -> r2
# --------------------------------------------------------------------------
# change_id -> (root_aci, kwarg to bump)
PERTURBATIONS = {
    "local-finalizer-prompt": (PROMPTS["finalize"], "finalize_prompt_rev"),
    "intermediate-research-tool": (TOOL, "tool_rev"),
    "global-shared-model": (MODEL, "model_rev"),
}


def _build_graph(
    *, model_rev=R1, tool_rev=R1, finalize_prompt_rev=R1
) -> Tuple[ConfigurationGraph, List[Evidence], Baseline]:
    revs, rels, evidence = _common_perimeter(
        model_rev=model_rev,
        tool_rev=tool_rev,
        finalize_prompt_rev=finalize_prompt_rev,
    )
    graph = ConfigurationGraph.build(revs, rels)
    return graph, evidence, _release_baseline()


# --------------------------------------------------------------------------
# API publique : trois builders par framework + application de perturbation
# --------------------------------------------------------------------------
# La topologie gouvernable ACM est identique ; le `framework_label` documente la
# provenance native (extraction indépendante). On ne réintroduit AUCUNE
# différence de périmètre gouvernable entre frameworks — c'est le contrôle de la
# variable « framework ».
def build_impact_langgraph(**bumps) -> Tuple[ConfigurationGraph, List[Evidence], Baseline]:
    """Variante LangGraph (sans la boucle reviewer->researcher)."""
    return _build_graph(**bumps)


def build_impact_crewai_flow(**bumps) -> Tuple[ConfigurationGraph, List[Evidence], Baseline]:
    """Variante CrewAI Flow au même périmètre gouvernable."""
    return _build_graph(**bumps)


def build_impact_openai_agents(**bumps) -> Tuple[ConfigurationGraph, List[Evidence], Baseline]:
    """Variante OpenAI Agents SDK au même périmètre gouvernable."""
    return _build_graph(**bumps)


BUILDERS = {
    "langgraph": build_impact_langgraph,
    "crewai": build_impact_crewai_flow,
    "openai-agents": build_impact_openai_agents,
}


def apply_perturbation(
    framework: str, change_id: str
) -> Tuple[
    Tuple[ConfigurationGraph, List[Evidence], Baseline],
    Tuple[ConfigurationGraph, List[Evidence], Baseline],
    str,
]:
    """Retourne (avant, après, root_aci) pour un (framework, change).

    `avant` = périmètre tout-r1 ; `après` = même périmètre avec la révision
    racine bumpée r1->r2. La comparaison des deux runs moteur donne P_f(c).
    """
    if framework not in BUILDERS:
        raise ValueError(f"framework inconnu: {framework}")
    if change_id not in PERTURBATIONS:
        raise ValueError(f"perturbation inconnue: {change_id}")

    builder = BUILDERS[framework]
    root_aci, bump_kwarg = PERTURBATIONS[change_id]

    before = builder()
    after = builder(**{bump_kwarg: "r2"})
    return before, after, root_aci
