# Emplacement : acm/impact/inspection.py
"""Réduction du coût d'inspection (variante stricte uniquement).

Décision méthodologique (validée) : on ne retient PAS la « variante
algorithmique » (N inspections manuelles vs 1 requête ACM). Comparer une
requête machine à une inspection humaine mélange les unités et n'est pas
défendable en revue. On mesure uniquement le COÛT HUMAIN RÉSIDUEL.

Définition d'une inspection
---------------------------
Une inspection = l'examen manuel d'UN ACI (ou d'une relation) pour déterminer
si le changement racine peut s'y propager. Le protocole humain précis (ce qui
compte exactement comme une inspection) sera arrêté ensemble ; ce module ne
dérive AUCUN des deux comptes — ils lui sont fournis en entier.

  manual_count   : I_f^Manual(c) — nombre d'inspections de l'analyse exhaustive
                   (sans assistance ACM).
  assisted_count : I_f^ACM(c) — nombre d'inspections résiduelles APRÈS qu'ACM
                   a fourni l'ensemble affecté (ce qu'un humain doit encore
                   vérifier : p.ex. valider les frontières, les FP potentiels).

  InspectionReduction = 1 − assisted / manual

Bornes : dans [.., 1]. Vaut 1.0 quand aucune inspection résiduelle. Peut être
négative si l'assistance impose PLUS de vérifications que l'analyse directe
(cas pathologique à signaler, non à masquer — cohérent avec l'anti-silence).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InspectionResult:
    manual_count: int
    assisted_count: int
    reduction: float

    @property
    def avoided(self) -> int:
        """Nombre d'inspections évitées (peut être négatif)."""
        return self.manual_count - self.assisted_count


def inspection_reduction(manual_count: int, assisted_count: int) -> InspectionResult:
    """Calcule la réduction stricte du coût d'inspection.

    Aucune dérivation : les deux comptes sont fournis par le protocole
    expérimental. `manual_count` DOIT être > 0 (sinon la réduction n'est pas
    définie — il n'y avait rien à inspecter, cas à écarter en amont).

    Lève ValueError si manual_count <= 0 ou si un compte est négatif : ce sont
    des erreurs de protocole, pas des résultats à propager silencieusement.
    """
    if manual_count <= 0:
        raise ValueError(
            f"manual_count doit être > 0 (reçu {manual_count}) : "
            "la réduction d'inspection n'est pas définie sans base manuelle."
        )
    if assisted_count < 0:
        raise ValueError(f"assisted_count ne peut être négatif (reçu {assisted_count}).")

    reduction = 1.0 - (assisted_count / manual_count)
    return InspectionResult(
        manual_count=manual_count,
        assisted_count=assisted_count,
        reduction=reduction,
    )
