# Emplacement : harness/impact_analysis.py
"""Analyse d'impact comparative — investigation manuelle vs ACM (vague 1.a).

Répond à la question de gouvernance centrale : « si je modifie l'ACI X, qu'est-ce
qui est affecté ? ». Le module compare deux façons d'y répondre sur le même
graphe :

  1. INVESTIGATION MANUELLE — ce qu'un ingénieur fait sans ACM : partir de X,
     lister ses dépendants directs, puis les dépendants de ceux-ci, etc. Chaque
     « pas » (inspection d'un ACI pour lister ses dépendants entrants) est compté.
     Sans discipline transitive, l'ingénieur s'arrête souvent au premier niveau
     et RATE les effets indirects — ce module modélise à la fois l'investigation
     complète (BFS exhaustif) et l'investigation naïve (1 niveau) pour quantifier
     l'écart.

  2. INVESTIGATION ACM — une seule propagation. L'ensemble affecté est lu dans le
     rapport : tout item dont l'état effectif se dégrade par rapport à son état
     intrinsèque, ou dont l'impact_state n'est pas `current`.

Le module produit un `ImpactComparison` chiffré : taille de l'ensemble affecté,
nombre d'inspections manuelles nécessaires, items manqués par l'approche naïve,
profondeur de propagation. Ces métriques alimentent le tableau comparatif de
l'article.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Set

from acm import (
    ACIRef,
    ConfigurationGraph,
    Evidence,
    PropagationContext,
    propagate,
)
from acm.models.status import ItemStatus


# --------------------------------------------------------------------------
# Investigation MANUELLE (simulée)
# --------------------------------------------------------------------------

@dataclass
class ManualInvestigation:
    """Résultat d'une investigation manuelle des dépendants d'un ACI."""

    root_id: str
    affected_ids: Set[str]          # ensemble complet trouvé (BFS exhaustif)
    naive_ids: Set[str]             # ce qu'on trouve en s'arrêtant à 1 niveau
    inspection_steps: int           # nb d'ACI inspectés (coût de l'investigation)
    max_depth: int                  # profondeur atteinte

    @property
    def missed_by_naive(self) -> Set[str]:
        """Items réellement affectés mais manqués par l'approche 1-niveau."""
        return self.affected_ids - self.naive_ids


def manual_impact_investigation(
    graph: ConfigurationGraph, root: ACIRef
) -> ManualInvestigation:
    """Simule l'investigation manuelle : BFS remontant les dépendants entrants.

    Chaque ACI visité compte pour une « inspection » (l'ingénieur ouvre l'ACI et
    lit qui en dépend). Le BFS complet donne l'ensemble transitif exact ; le
    premier niveau donne ce qu'une investigation naïve trouverait.
    """
    root_key = root.key()
    affected: Set[str] = set()
    naive: Set[str] = set()
    depth_of: Dict[str, int] = {root_key: 0}
    inspections = 0

    queue: deque[str] = deque([root_key])
    visited: Set[str] = {root_key}

    # On indexe les dépendants par clé une seule fois n'est PAS ce que ferait un
    # ingénieur : lui ré-inspecte chaque ACI. On compte donc une inspection par
    # nœud dépilé.
    while queue:
        current_key = queue.popleft()
        inspections += 1
        current_ref = _ref_from_key(graph, current_key)
        if current_ref is None:
            continue
        for rel in graph.dependents_of(current_ref):
            dep_key = rel.source.key()
            depth = depth_of[current_key] + 1
            if dep_key not in visited:
                visited.add(dep_key)
                depth_of[dep_key] = depth
                affected.add(rel.source.id)
                if depth == 1:
                    naive.add(rel.source.id)
                queue.append(dep_key)

    max_depth = max(depth_of.values()) if depth_of else 0
    return ManualInvestigation(
        root_id=root.id,
        affected_ids=affected,
        naive_ids=naive,
        inspection_steps=inspections,
        max_depth=max_depth,
    )


def _ref_from_key(graph: ConfigurationGraph, key: str) -> ACIRef | None:
    for rev in graph.revisions.values():
        if rev.ref.key() == key:
            return rev.ref
    return None


# --------------------------------------------------------------------------
# Investigation ACM (une propagation)
# --------------------------------------------------------------------------

@dataclass
class ACMInvestigation:
    """Résultat de l'analyse d'impact via propagation ACM."""

    root_id: str
    affected_ids: Set[str]          # items dont l'état effectif est dégradé
    iterations: int                 # itérations du point-fixe (coût ACM)
    queries: int = 1                # nombre de « requêtes » ACM (une propagation)


def acm_impact_analysis(
    graph: ConfigurationGraph,
    evidence: List[Evidence],
    root: ACIRef,
    context: PropagationContext | None = None,
) -> ACMInvestigation:
    """Analyse d'impact ACM : une propagation, lecture de l'ensemble affecté.

    Un item est « affecté » si son impact_state n'est pas `current`, ou si son
    éligibilité est dégradée (blocked/warning), à l'exclusion de la racine
    elle-même.
    """
    context = context or PropagationContext()
    report = propagate(graph, evidence, context)

    affected: Set[str] = set()
    for item in report.items.values():
        if item.ref.id == root.id:
            continue
        degraded = (
            item.computed.impact_state.value != "current"
            or item.computed.eligibility_state.value in ("blocked", "warning")
        )
        if degraded:
            affected.add(item.ref.id)

    return ACMInvestigation(
        root_id=root.id,
        affected_ids=affected,
        iterations=report.iterations,
    )


# --------------------------------------------------------------------------
# Comparaison
# --------------------------------------------------------------------------

@dataclass
class ImpactComparison:
    """Comparaison chiffrée manuel vs ACM pour un changement donné."""

    root_id: str
    graph_size: int
    relation_count: int
    manual: ManualInvestigation
    acm: ACMInvestigation
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "root_id": self.root_id,
            "graph_size": self.graph_size,
            "relation_count": self.relation_count,
            "manual": {
                "affected_count": len(self.manual.affected_ids),
                "naive_affected_count": len(self.manual.naive_ids),
                "missed_by_naive_count": len(self.manual.missed_by_naive),
                "missed_by_naive": sorted(self.manual.missed_by_naive),
                "inspection_steps": self.manual.inspection_steps,
                "max_depth": self.manual.max_depth,
            },
            "acm": {
                "affected_count": len(self.acm.affected_ids),
                "queries": self.acm.queries,
                "iterations": self.acm.iterations,
            },
            "agreement": {
                "exhaustive_manual_matches_acm":
                    self.manual.affected_ids == self.acm.affected_ids,
                "only_in_manual": sorted(self.manual.affected_ids - self.acm.affected_ids),
                "only_in_acm": sorted(self.acm.affected_ids - self.manual.affected_ids),
            },
            "notes": self.notes,
        }


def compare_impact_analysis(
    graph: ConfigurationGraph,
    evidence: List[Evidence],
    root: ACIRef,
    context: PropagationContext | None = None,
) -> ImpactComparison:
    """Exécute les deux investigations et retourne la comparaison chiffrée."""
    manual = manual_impact_investigation(graph, root)
    acm = acm_impact_analysis(graph, evidence, root, context)

    notes: List[str] = []
    if manual.missed_by_naive:
        notes.append(
            f"L'investigation naïve (1 niveau) manque {len(manual.missed_by_naive)} "
            f"item(s) réellement affecté(s) : {sorted(manual.missed_by_naive)}."
        )
    if manual.affected_ids == acm.affected_ids:
        notes.append(
            "L'investigation manuelle EXHAUSTIVE et ACM concordent sur l'ensemble "
            "affecté ; ACM l'obtient en une propagation contre "
            f"{manual.inspection_steps} inspections manuelles."
        )

    return ImpactComparison(
        root_id=root.id,
        graph_size=len(graph.revisions),
        relation_count=len(graph.relations),
        manual=manual,
        acm=acm,
        notes=notes,
    )
