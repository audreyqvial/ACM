# Emplacement : harness/engine_prediction.py
"""Extraction de l'ensemble affecté P_f(c) depuis le VRAI moteur ACM.

Décision (validée) : la prédiction publiée est l'ensemble effectivement marqué
par le moteur à point fixe (`propagate()`), PAS le résultat topologique de
`reach()`. `reach()` reste un oracle de cohérence statique (voir
`reach_consistency.py`), utile en test mais jamais publié.

Ce module vit dans `harness/` : il ORCHESTRE deux appels au moteur (avant/après
perturbation) et lit le rapport. Il ne réimplémente aucune règle de propagation
— tout vient de `acm.propagation.engine.propagate`.

Définition de « affecté »
-------------------------
Un ACI est affecté par le changement `c` si son `impact_state` calculé passe de
CURRENT (avant) à non-CURRENT (après), OU est non-CURRENT après si l'on ne
dispose que de l'état post-perturbation. Deux modes :

  affected_set_delta(before, after) : DIFFÉRENTIEL — ACI dont l'impact s'aggrave
      entre les deux runs. C'est la définition la plus propre de « affecté PAR
      ce changement » : elle isole l'effet de la perturbation d'un éventuel
      impact préexistant. Mode recommandé pour l'expérience.

  affected_set_absolute(after) : ABSOLU — tous les ACI non-CURRENT après. Utile
      quand l'état de départ est garanti « tout current » (baseline saine).

La racine du changement est EXCLUE de l'ensemble affecté (cohérent avec `reach`
et l'oracle) : on mesure ce qui est ATTEINT, pas la source.
"""
from __future__ import annotations

from typing import Optional, Set

from acm.models.enums import ImpactState
from acm.models.status import PropagationReport

# Sévérité (§11.3) : current < impacted < stale. On la reconstruit localement
# pour ne pas dépendre d'un détail interne de l'enum.
_SEVERITY = {
    ImpactState.CURRENT: 0,
    ImpactState.IMPACTED: 1,
    ImpactState.STALE: 2,
}


def _logical_id(item_key: str, report: PropagationReport) -> str:
    """id logique d'un item à partir de sa clé (id@revision)."""
    return report.items[item_key].ref.id


def affected_set_absolute(
    report: PropagationReport,
    *,
    root_id: Optional[str] = None,
) -> Set[str]:
    """Ids logiques dont l'impact est non-CURRENT dans le rapport (racine exclue)."""
    affected: Set[str] = set()
    for key, item in report.items.items():
        if item.computed.impact_state != ImpactState.CURRENT:
            affected.add(item.ref.id)
    if root_id is not None:
        affected.discard(root_id)
    return affected


def affected_set_delta(
    before: PropagationReport,
    after: PropagationReport,
    *,
    root_id: Optional[str] = None,
) -> Set[str]:
    """Ids logiques dont l'impact S'AGGRAVE entre `before` et `after`.

    Compare par id logique. Un ACI est « affecté par le changement » si sa
    sévérité d'impact augmente (p.ex. current -> stale). Isole l'effet de la
    perturbation d'un impact préexistant.

    Si un id n'existe que dans `after` (nouvel objet), il est considéré affecté
    ssi son état post est non-CURRENT. La racine est exclue.
    """
    # Impact « avant », le plus sévère par id logique (au cas où plusieurs
    # révisions du même id coexistent).
    before_sev: dict[str, int] = {}
    for item in before.items.values():
        sev = _SEVERITY[item.computed.impact_state]
        before_sev[item.ref.id] = max(before_sev.get(item.ref.id, 0), sev)

    after_sev: dict[str, int] = {}
    for item in after.items.values():
        sev = _SEVERITY[item.computed.impact_state]
        after_sev[item.ref.id] = max(after_sev.get(item.ref.id, 0), sev)

    affected: Set[str] = set()
    for logical_id, sev_after in after_sev.items():
        sev_before = before_sev.get(logical_id, 0)
        if sev_after > sev_before:
            affected.add(logical_id)

    if root_id is not None:
        affected.discard(root_id)
    return affected
