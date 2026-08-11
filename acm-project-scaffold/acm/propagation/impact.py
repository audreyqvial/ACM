"""Propagation d'impact (§11.4, §14.1).

Impact local (§11.4) — un ACI devient au minimum `impacted` lorsque, entre
autres, une dépendance obligatoire change de révision, une politique change,
ou un modèle/outil/prompt est déprécié.

Impact propagé (§14.1) :
  - si une cible devient impacted, la source devient au minimum impacted ;
  - si une cible devient stale et que la source a une preuve dépendant de
    cette cible, la source devient stale.

Note : le calcul de l'assurance effective vit dans assurance.py (§16.2).
"""
from __future__ import annotations

from typing import Dict, List

from ..models.aci import ConfigurationGraph
from ..models.enums import ImpactState, LifecycleState, worst_impact
from ..models.refs import ACIRef
from ..models.status import ItemStatus


def compute_local_impact(
    graph: ConfigurationGraph,
    ref: ACIRef,
) -> ImpactState:
    """§11.4 — Impact local dérivé de déclencheurs détectables dans le graphe.

    Version v0.1 : détecte le déclencheur « une dépendance (obligatoire) est
    dépréciée ». Une dépendance deprecated rend le dépendant au minimum
    `impacted` (le composite doit être réanalysé).

    D'autres déclencheurs (§11.4 : changement de révision de dépendance,
    vulnérabilité, résultat runtime...) seront injectés via signaux/preuves
    dans les scénarios ultérieurs. Le déclencheur `stale` lié à la péremption
    des preuves est traité côté applicabilité (§18).
    """
    rev = graph.get(ref)
    if rev is None:
        return ImpactState.CURRENT

    for rel in graph.dependencies_of(ref):
        if not rel.impact_dependency:
            continue
        dep = graph.get(rel.target)
        if dep is None:
            continue
        if dep.declared.lifecycle_state == LifecycleState.DEPRECATED and rel.required:
            return ImpactState.IMPACTED

    return ImpactState.CURRENT


def compute_effective_impact(
    graph: ConfigurationGraph,
    ref: ACIRef,
    status: Dict[str, ItemStatus],
) -> ImpactState:
    """§14.1 — Propagation d'impact via relations impact_dependency=true."""
    item = status[ref.key()]
    states: List[ImpactState] = [item.local_impact]

    for rel in graph.dependencies_of(ref):
        if not rel.impact_dependency:
            continue
        dep = status.get(rel.target.key())
        if dep is None:
            continue
        states.append(dep.computed.impact_state)

    return worst_impact(*states)
