# Emplacement : acm/impact/comparison.py
"""Comparaison ensembliste prédiction vs oracle (precision / recall).

Ce module est DÉLIBÉRÉMENT ignorant : il ne connaît ni le moteur ACM, ni le
format de l'oracle, ni les frameworks. Il prend deux ensembles d'ids logiques
— `predicted` (P, produit par ACM) et `manual` (M, l'oracle humain figé) — et
retourne TP / FP / FN + precision / recall.

Cette séparation est ce qui rend la mesure défendable : le *calcul* de
comparaison ne peut pas « tricher » car il n'a accès qu'à deux ensembles
opaques. Le chargement de l'oracle (un artefact figé, versionné, révisé à la
main) vit ailleurs et n'est jamais importé par le cœur normatif.

Conventions numériques (bornes)
-------------------------------
- Precision = |P ∩ M| / |P|. Si P est vide : precision = 1.0 par convention
  SSI M est aussi vide (aucune prédiction, aucun impact attendu => accord
  parfait vacuité) ; sinon 0.0 (rien prédit alors qu'un impact était attendu).
- Recall = |P ∩ M| / |M|. Si M est vide : recall = 1.0 par convention (vérité
  vacuité : aucun impact attendu, donc aucun manqué), y compris si P est non
  vide — dans ce cas ce sont des faux positifs que la PRECISION pénalise, pas
  le recall.

Ces conventions de bord sont explicitées car elles déterminent l'interprétation
du cas « aucun impact » (perturbation local sans propagation, p.ex.).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, FrozenSet, Set


@dataclass(frozen=True)
class ComparisonResult:
    """Résultat d'une comparaison P vs M sur ids logiques."""

    predicted: FrozenSet[str]
    manual: FrozenSet[str]
    true_positive: FrozenSet[str]
    false_positive: FrozenSet[str]
    false_negative: FrozenSet[str]
    precision: float
    recall: float

    @property
    def tp(self) -> int:
        return len(self.true_positive)

    @property
    def fp(self) -> int:
        return len(self.false_positive)

    @property
    def fn(self) -> int:
        return len(self.false_negative)

    @property
    def exact_match(self) -> bool:
        """Accord exact avec l'oracle (aucun FP, aucun FN)."""
        return not self.false_positive and not self.false_negative

    @property
    def f1(self) -> float:
        """F1 = 2PR/(P+R). 0.0 si precision et recall sont tous deux nuls."""
        denom = self.precision + self.recall
        if denom == 0.0:
            return 0.0
        return 2.0 * self.precision * self.recall / denom


def compare(
    predicted: AbstractSet[str],
    manual: AbstractSet[str],
) -> ComparisonResult:
    """Compare l'ensemble prédit par ACM (P) à l'oracle manuel (M).

    Les deux arguments sont des ensembles d'ids logiques. La fonction est pure
    et symétrique en structure (TP/FP/FN dérivés uniquement des opérations
    ensemblistes). Voir les conventions de bord dans le docstring du module.
    """
    P: Set[str] = set(predicted)
    M: Set[str] = set(manual)

    tp = P & M
    fp = P - M
    fn = M - P

    # Precision = TP / |P|, avec convention de vacuité.
    if not P:
        precision = 1.0 if not M else 0.0
    else:
        precision = len(tp) / len(P)

    # Recall = TP / |M|, avec convention de vacuité : si aucun impact n'était
    # attendu (M vide), il n'y a rien à manquer => recall = 1.0 (vérité
    # vacuité), y compris lorsque P est non vide (ces prédictions sont des FP
    # que la PRECISION pénalise, pas le recall).
    if not M:
        recall = 1.0
    else:
        recall = len(tp) / len(M)

    return ComparisonResult(
        predicted=frozenset(P),
        manual=frozenset(M),
        true_positive=frozenset(tp),
        false_positive=frozenset(fp),
        false_negative=frozenset(fn),
        precision=precision,
        recall=recall,
    )
