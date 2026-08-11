# Emplacement : acm/impact/__init__.py
"""Analyse d'impact quantitative (bloc 1).

Sous-package normatif du cœur ACM. Fonctions PURES sur le graphe de
configuration : aucune dépendance framework, aucune dépendance à l'oracle
externe. C'est la garantie anti-circularité structurelle — le calcul des
métriques ci-dessous ne connaît jamais l'ensemble attendu M_f(c).

Trois modules :
  - metrics     : reach / size / depth / ratio / weight (portée de propagation)
  - comparison  : precision / recall vs un ensemble fourni (ni oracle ni moteur)
  - inspection  : réduction du coût d'inspection (variante stricte)
"""
from .comparison import ComparisonResult, compare
from .inspection import inspection_reduction
from .metrics import (
    DEFAULT_RELATION_WEIGHTS,
    ImpactMetrics,
    impact_depth,
    impact_metrics,
    impact_ratio,
    impact_size,
    impact_weight,
    reach,
)

__all__ = [
    "reach",
    "impact_size",
    "impact_depth",
    "impact_ratio",
    "impact_weight",
    "impact_metrics",
    "ImpactMetrics",
    "DEFAULT_RELATION_WEIGHTS",
    "compare",
    "ComparisonResult",
    "inspection_reduction",
]
