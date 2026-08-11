# Emplacement : harness/baseline_reassessment.py
"""Reassessment de baseline : signal DÉRIVÉ, distinct de P_f(c).

Décision (validée) : la baseline released est IMMUABLE. Un changement d'un de
ses `required_items` ne propage PAS structurellement vers la baseline et ne la
marque pas `impacted` dans le graphe. Il déclenche un REASSESSMENT — un statut
opérationnel externe (§6.5, `OperationalStatus.REASSESSMENT_REQUIRED`), calculé
dans un registre séparé.

Conséquence pour l'expérience : la baseline n'apparaît JAMAIS dans P_f(c) ni
dans l'oracle `affected`. Le reassessment est un résultat secondaire, calculé
ici à partir de P_f(c) (l'ensemble affecté) et de `Baseline.required_items`.

Règle : une baseline requiert reassessment ssi au moins un de ses required_items
(par id logique) figure dans l'ensemble affecté OU est la racine du changement
(le required_item lui-même a changé de révision).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set

from acm.state_machines.baselines import Baseline, OperationalStatus


@dataclass(frozen=True)
class BaselineReassessment:
    baseline_id: str
    reassessment_required: bool
    triggering_items: Set[str]  # ids logiques de required_items touchés
    operational_status: OperationalStatus


def evaluate_baseline_reassessment(
    baseline: Baseline,
    affected_ids: Set[str],
    *,
    root_id: Optional[str] = None,
) -> BaselineReassessment:
    """Calcule le besoin de reassessment SANS muter la baseline released.

    `affected_ids` = P_f(c) (racine exclue). `root_id` = la racine du changement
    (le required_item directement modifié), incluse ici car un required_item qui
    change de révision rend la baseline à réévaluer même s'il n'a pas de
    dépendant affecté.
    """
    required_ids = {ref.id for ref in baseline.required_items}
    trigger = set(affected_ids) & required_ids
    if root_id is not None and root_id in required_ids:
        trigger.add(root_id)

    required = bool(trigger)
    status = (
        OperationalStatus.REASSESSMENT_REQUIRED if required else OperationalStatus.NONE
    )
    return BaselineReassessment(
        baseline_id=baseline.baseline_id,
        reassessment_required=required,
        triggering_items=trigger,
        operational_status=status,
    )


def flag_if_required(
    baseline: Baseline,
    affected_ids: Set[str],
    *,
    root_id: Optional[str] = None,
) -> BaselineReassessment:
    """Comme `evaluate_...` mais applique le statut opérationnel à une COPIE.

    On ne mute pas la baseline released d'origine (immuabilité §6.5) ; le statut
    opérationnel vit dans un registre externe. Cette fonction retourne le verdict
    et, si nécessaire, l'applique à une copie pour usage aval (rapport).
    """
    verdict = evaluate_baseline_reassessment(baseline, affected_ids, root_id=root_id)
    if verdict.reassessment_required:
        # Copie défensive : le registre opérationnel est externe au lifecycle.
        copy = baseline.model_copy(deep=True)
        copy.flag_operational(OperationalStatus.REASSESSMENT_REQUIRED)
    return verdict
