# Emplacement : acm/impact/metrics.py
"""Métriques de portée de propagation d'impact (fonctions pures, §14.1).

Sémantique de propagation (alignée sur `propagation/impact.py`)
--------------------------------------------------------------
Dans ACM, une relation est dirigée source -> target et l'impact REMONTE :
si une *target* devient impacted, la *source* le devient (§14.1). Autrement
dit, modifier un ACI `v` affecte les ACI qui DÉPENDENT de `v`, c.-à-d. les
sources des relations entrantes de `v` (`dependents_of`), transitivement.

Reach(v) est donc l'ensemble des dépendants transitifs de `v` via les seules
relations où `impact_dependency=true`. C'est cet ensemble que le moteur
marquerait au minimum `impacted` après une modification de `v`.

Ces fonctions NE modifient pas d'état, NE lancent pas le moteur, et NE
connaissent PAS l'oracle. Elles opèrent sur la topologie du graphe. La
`reach` se calcule sur l'identité LOGIQUE des ACI (id sans revision_id) :
une analyse d'impact raisonne sur « quel objet est touché », pas sur une
révision exacte figée.

Convention de clé
-----------------
Un « nœud » d'impact est identifié par son id logique (`ACIRef.id`). Le graphe
peut contenir plusieurs révisions d'un même id ; pour la portée d'impact on
les considère comme un seul sommet logique. `reach` retourne donc un
`set[str]` d'ids logiques, la racine EXCLUE (on mesure ce qui est *atteint*,
pas la racine elle-même).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Set

from ..models.aci import ConfigurationGraph, Relation
from ..models.enums import RelationType

# Poids par défaut : tous à 1 (aucune hiérarchie imposée). Les poids
# différenciés (depends_on/composed_of/baseline_member...) sont un PARAMÈTRE
# exploratoire injecté par l'appelant, jamais codé en dur dans le calcul.
# Cf. critique méthodologique : le barème est un choix d'auteur, pas une
# revendication centrale ; il fait l'objet d'une analyse de sensibilité.
DEFAULT_RELATION_WEIGHTS: Dict[RelationType, float] = {
    rt: 1.0 for rt in RelationType
}


def _impact_edges(
    graph: ConfigurationGraph,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> list[Relation]:
    """Relations participant à la propagation d'impact.

    Ne retient que `impact_dependency=true` (§14.1). Un filtre optionnel par
    type de relation permet des analyses ciblées ; par défaut tous les types
    portant `impact_dependency` sont pris.
    """
    allowed = set(relation_types) if relation_types is not None else None
    edges: list[Relation] = []
    for rel in graph.relations:
        if not rel.impact_dependency:
            continue
        if allowed is not None and rel.relation_type not in allowed:
            continue
        edges.append(rel)
    return edges


def _reverse_adjacency(
    edges: Iterable[Relation],
) -> Dict[str, list[tuple[str, RelationType]]]:
    """Adjacence de PROPAGATION : target_id -> [(source_id, type), ...].

    On inverse la direction déclarée (source->target) parce que l'impact
    remonte de la target vers la source. Depuis un nœud modifié, on marche
    donc vers ses dépendants en suivant cette adjacence inversée.
    """
    adj: Dict[str, list[tuple[str, RelationType]]] = {}
    for rel in edges:
        adj.setdefault(rel.target.id, []).append((rel.source.id, rel.relation_type))
    return adj


@dataclass(frozen=True)
class ImpactMetrics:
    """Agrégat des métriques de portée pour une racine donnée."""

    root: str
    reach: Set[str]
    size: int
    depth: int
    ratio: float
    weight: float
    # Type de relation retenu pour chaque nœud atteint sur le plus court chemin
    # de propagation (pour la métrique de poids). Interne / traçabilité.
    _reach_relation: Dict[str, RelationType] = field(default_factory=dict, repr=False)


def reach(
    graph: ConfigurationGraph,
    root: str,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> Set[str]:
    """Ensemble des ids logiques atteints par la propagation depuis `root`.

    Parcours en largeur sur l'adjacence de propagation (dépendants transitifs).
    La racine est EXCLUE du résultat. Robuste aux cycles (nœuds visités).

    `root` est un id logique (ex. "aci:model:shared-llm").
    """
    edges = _impact_edges(graph, relation_types=relation_types)
    adj = _reverse_adjacency(edges)

    visited: Set[str] = set()
    queue: deque[str] = deque([root])
    seen_seed = {root}
    while queue:
        node = queue.popleft()
        for nxt, _rtype in adj.get(node, []):
            if nxt not in seen_seed:
                seen_seed.add(nxt)
                visited.add(nxt)
                queue.append(nxt)
    visited.discard(root)
    return visited


def _reach_with_distance_and_relation(
    graph: ConfigurationGraph,
    root: str,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> tuple[Dict[str, int], Dict[str, RelationType]]:
    """BFS renvoyant la distance de propagation minimale ET le type de relation
    entrant sur le plus court chemin, pour chaque nœud atteint (racine exclue).

    La distance est le nombre d'arêtes de propagation depuis `root`. Le type de
    relation retenu est celui de la première arête qui atteint le nœud au plus
    court (déterministe via ordre BFS + tri des voisins).
    """
    edges = _impact_edges(graph, relation_types=relation_types)
    adj = _reverse_adjacency(edges)

    dist: Dict[str, int] = {root: 0}
    rel_in: Dict[str, RelationType] = {}
    queue: deque[str] = deque([root])
    while queue:
        node = queue.popleft()
        # Tri des voisins pour un parcours déterministe (§I14 esprit).
        for nxt, rtype in sorted(adj.get(node, []), key=lambda t: (t[0], t[1].value)):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                rel_in[nxt] = rtype
                queue.append(nxt)
    dist.pop(root, None)
    return dist, rel_in


def impact_size(
    graph: ConfigurationGraph,
    root: str,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> int:
    """ImpactSize(v) = |Reach(v)| — nombre d'ACI logiques atteints."""
    return len(reach(graph, root, relation_types=relation_types))


def impact_depth(
    graph: ConfigurationGraph,
    root: str,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> int:
    """ImpactDepth(v) = max_{u in Reach(v)} dist(v, u).

    Longueur maximale (en arêtes) d'une chaîne de propagation issue de `root`.
    Vaut 0 si la portée est vide (aucun dépendant).
    """
    dist, _ = _reach_with_distance_and_relation(
        graph, root, relation_types=relation_types
    )
    return max(dist.values()) if dist else 0


def _logical_node_count(graph: ConfigurationGraph) -> int:
    """Nombre de sommets LOGIQUES du graphe (ids distincts, révisions fusionnées).

    Le dénominateur de ImpactRatio est |V| en ids logiques, cohérent avec le
    fait que `reach` raisonne en ids logiques.
    """
    return len({rev.ref.id for rev in graph.revisions.values()})


def impact_ratio(
    graph: ConfigurationGraph,
    root: str,
    *,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> float:
    """ImpactRatio(v) = |Reach(v)| / |V|.

    0 = impact local, tend vers 1 = impact global. Dénominateur = nombre d'ids
    logiques. Retourne 0.0 si le graphe est vide (garde anti-division par zéro).
    Le dénominateur inclut la racine (|V| total), conformément à la définition
    du document.
    """
    denom = _logical_node_count(graph)
    if denom == 0:
        return 0.0
    return len(reach(graph, root, relation_types=relation_types)) / denom


def impact_weight(
    graph: ConfigurationGraph,
    root: str,
    *,
    weights: Optional[Mapping[RelationType, float]] = None,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> float:
    """ImpactWeight(v) = somme des poids des nœuds atteints.

    Le poids d'un nœud atteint est celui du type de relation par lequel il est
    atteint sur le plus court chemin de propagation. `weights` est INJECTÉ ;
    par défaut tous les types valent 1.0 (=> ImpactWeight == ImpactSize).

    Choix de conception : on pondère par nœud (via son arête entrante), pas par
    arête, pour rester homogène avec ImpactSize (un nœud compté une fois). Le
    barème différencié reste un paramètre exploratoire, hors revendication
    centrale (cf. critique méthodologique).
    """
    w = dict(DEFAULT_RELATION_WEIGHTS)
    if weights:
        w.update(weights)
    _, rel_in = _reach_with_distance_and_relation(
        graph, root, relation_types=relation_types
    )
    return float(sum(w.get(rtype, 1.0) for rtype in rel_in.values()))


def impact_metrics(
    graph: ConfigurationGraph,
    root: str,
    *,
    weights: Optional[Mapping[RelationType, float]] = None,
    relation_types: Optional[Iterable[RelationType]] = None,
) -> ImpactMetrics:
    """Calcule toutes les métriques de portée en un seul parcours cohérent.

    Préférable aux appels séparés lorsqu'on veut plusieurs métriques : garantit
    que size/depth/ratio/weight portent exactement sur le même `reach`.
    """
    dist, rel_in = _reach_with_distance_and_relation(
        graph, root, relation_types=relation_types
    )
    reached = set(dist.keys())
    w = dict(DEFAULT_RELATION_WEIGHTS)
    if weights:
        w.update(weights)
    denom = _logical_node_count(graph)
    return ImpactMetrics(
        root=root,
        reach=reached,
        size=len(reached),
        depth=max(dist.values()) if dist else 0,
        ratio=(len(reached) / denom) if denom else 0.0,
        weight=float(sum(w.get(rtype, 1.0) for rtype in rel_in.values())),
        _reach_relation=dict(rel_in),
    )
