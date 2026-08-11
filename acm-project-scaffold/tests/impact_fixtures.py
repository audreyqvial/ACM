# Emplacement : tests/impact_fixtures.py
"""Graphes jouets pour tester les métriques d'impact (réponses connues).

Construits avec les VRAIS modèles ACM (ConfigurationGraph/Relation/ACIRevision)
en pure-Python — aucune dépendance framework. Chaque graphe documente la
topologie et la portée de propagation attendue depuis chaque racine.

Rappel sémantique : une relation source -> target signifie « source dépend de
target » ; l'impact remonte de target vers source. Donc modifier `target`
affecte `source`. Reach(v) = dépendants transitifs de v.
"""
from __future__ import annotations

from acm.models.aci import ACIRevision, ConfigurationGraph, Relation
from acm.models.enums import ACIType, RelationType
from acm.models.refs import ACIRef


def _rev(aci_id: str, aci_type: ACIType, rev: str = "r1") -> ACIRevision:
    return ACIRevision(ref=ACIRef(id=aci_id, revision_id=rev), aci_type=aci_type)


def _rel(
    rid: str,
    source: str,
    target: str,
    rtype: RelationType,
    *,
    impact: bool = True,
    src_rev: str = "r1",
    tgt_rev: str = "r1",
) -> Relation:
    return Relation(
        relation_id=rid,
        source=ACIRef(id=source, revision_id=src_rev),
        target=ACIRef(id=target, revision_id=tgt_rev),
        relation_type=rtype,
        impact_dependency=impact,
    )


def linear_chain() -> ConfigurationGraph:
    """Chaîne : workflow -> agent -> prompt -> model.

    (source dépend de target). Modifier `model` remonte jusqu'à `workflow`.

      Reach(model)    = {prompt, agent, workflow}   size 3, depth 3
      Reach(prompt)   = {agent, workflow}            size 2, depth 2
      Reach(agent)    = {workflow}                   size 1, depth 1
      Reach(workflow) = {}                           size 0, depth 0
      |V| = 4
    """
    revs = [
        _rev("wf", ACIType.WORKFLOW),
        _rev("agent", ACIType.AGENT),
        _rev("prompt", ACIType.PROMPT),
        _rev("model", ACIType.MODEL),
    ]
    rels = [
        _rel("r-wf-agent", "wf", "agent", RelationType.CONTAINS),
        _rel("r-agent-prompt", "agent", "prompt", RelationType.USES_PROMPT),
        _rel("r-prompt-model", "prompt", "model", RelationType.USES_MODEL),
    ]
    return ConfigurationGraph.build(revs, rels)


def shared_model_fanout() -> ConfigurationGraph:
    """Modèle partagé par trois agents, tous contenus dans un workflow.

        wf -> a1, wf -> a2, wf -> a3         (contains)
        a1 -> model, a2 -> model, a3 -> model (uses_model)

    Modifier `model` affecte a1,a2,a3 (dist 1) puis wf (dist 2).
      Reach(model) = {a1, a2, a3, wf}   size 4, depth 2
      Reach(a1)    = {wf}               size 1, depth 1
      Reach(wf)    = {}                 size 0
      |V| = 5   -> ImpactRatio(model) = 4/5 = 0.8
    """
    revs = [
        _rev("wf", ACIType.WORKFLOW),
        _rev("a1", ACIType.AGENT),
        _rev("a2", ACIType.AGENT),
        _rev("a3", ACIType.AGENT),
        _rev("model", ACIType.MODEL),
    ]
    rels = [
        _rel("r-wf-a1", "wf", "a1", RelationType.CONTAINS),
        _rel("r-wf-a2", "wf", "a2", RelationType.CONTAINS),
        _rel("r-wf-a3", "wf", "a3", RelationType.CONTAINS),
        _rel("r-a1-model", "a1", "model", RelationType.USES_MODEL),
        _rel("r-a2-model", "a2", "model", RelationType.USES_MODEL),
        _rel("r-a3-model", "a3", "model", RelationType.USES_MODEL),
    ]
    return ConfigurationGraph.build(revs, rels)


def graph_with_noimpact_edge() -> ConfigurationGraph:
    """Comme la chaîne linéaire, mais l'arête agent->prompt est NON propageante
    (impact_dependency=false). La propagation depuis `model` s'arrête à prompt.

      Reach(model) = {prompt}   size 1, depth 1   (agent/wf non atteints)
      |V| = 4
    """
    revs = [
        _rev("wf", ACIType.WORKFLOW),
        _rev("agent", ACIType.AGENT),
        _rev("prompt", ACIType.PROMPT),
        _rev("model", ACIType.MODEL),
    ]
    rels = [
        _rel("r-wf-agent", "wf", "agent", RelationType.CONTAINS),
        _rel("r-agent-prompt", "agent", "prompt", RelationType.USES_PROMPT, impact=False),
        _rel("r-prompt-model", "prompt", "model", RelationType.USES_MODEL),
    ]
    return ConfigurationGraph.build(revs, rels)


def cyclic_graph() -> ConfigurationGraph:
    """Cycle de propagation a -> b -> c -> a (via USES_TOOL, hors types
    interdits de cycle). Sert à vérifier que `reach` termine et exclut la racine.

      Reach(a) = {b, c}   (b et c, pas a elle-même)  size 2
    """
    revs = [
        _rev("a", ACIType.AGENT),
        _rev("b", ACIType.AGENT),
        _rev("c", ACIType.AGENT),
    ]
    rels = [
        _rel("r-a-b", "a", "b", RelationType.USES_TOOL),
        _rel("r-b-c", "b", "c", RelationType.USES_TOOL),
        _rel("r-c-a", "c", "a", RelationType.USES_TOOL),
    ]
    return ConfigurationGraph.build(revs, rels)
