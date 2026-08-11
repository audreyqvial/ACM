# Emplacement : harness/reach_consistency.py
r"""Cohérence entre la portée topologique (`reach`) et le résultat du moteur.

`reach()` (acm/impact/metrics.py) est un calcul topologique statique : les
dépendants transitifs via `impact_dependency`. Le moteur (`propagate`) est la
source de vérité PUBLIÉE : l'ensemble effectivement marqué non-CURRENT après
perturbation.

Les deux ne coïncident PAS toujours, et c'est normal :
  - `reach` est une SUR-approximation topologique : il inclut tout dépendant
    transitif, que le déclencheur d'impact se propage réellement ou non.
  - le moteur applique la sémantique fine (staleness par snapshot de preuve,
    dépréciation, blocages) : un dépendant topologique peut rester CURRENT si
    aucun déclencheur effectif ne l'atteint (p.ex. pas de preuve snapshotant la
    dépendance changée).

Donc la propriété de cohérence attendue est une INCLUSION, pas une égalité :

    engine_affected(c)  ⊆  reach(root)

Le moteur ne doit jamais marquer affecté un ACI hors de la portée topologique
(sinon il y aurait propagation par un chemin non déclaré comme
`impact_dependency` — une anomalie). L'écart `reach \ engine` est l'ensemble des
dépendants topologiques que la sémantique fine n'a pas activés : information
diagnostique, pas une erreur.

Ce module fournit le test de cohérence ; il ne publie rien.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Set

from acm.impact import reach
from acm.models.aci import ConfigurationGraph


@dataclass(frozen=True)
class ConsistencyResult:
    root: str
    reachable: Set[str]           # sur-approximation topologique
    engine_affected: Set[str]     # marqués par le moteur (racine exclue)
    inclusion_holds: bool         # engine ⊆ reach
    engine_outside_reach: Set[str]  # DOIT être vide (anomalie sinon)
    reach_not_activated: Set[str]   # reach \ engine — diagnostic, normal

    @property
    def exact(self) -> bool:
        """Coïncidence parfaite (rare : suppose que tout dépendant est activé)."""
        return self.inclusion_holds and not self.reach_not_activated


def check_consistency(
    graph: ConfigurationGraph,
    root_id: str,
    engine_affected: Set[str],
) -> ConsistencyResult:
    """Vérifie engine_affected ⊆ reach(root) et calcule les écarts."""
    reachable = reach(graph, root_id)
    outside = set(engine_affected) - reachable
    not_activated = reachable - set(engine_affected)
    return ConsistencyResult(
        root=root_id,
        reachable=reachable,
        engine_affected=set(engine_affected),
        inclusion_holds=not outside,
        engine_outside_reach=outside,
        reach_not_activated=not_activated,
    )
