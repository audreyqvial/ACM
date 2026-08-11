"""Scénario B — Dépendance NOK (§24.2).

Part de la configuration nominale du scénario A, puis dégrade la qualité
intrinsèque de l'outil T1 à `nok`.

Relation en jeu :
    A1 uses_tool T1
    required = true
    propagation_policy = blocking

Résultat attendu (§24.2) :
    T1.effective_quality   = nok
    A1.quality_state       = INCHANGÉ (reste ok)   <- point clé §3.4
    A1.effective_quality   = nok
    A1.eligibility_state   = blocked
    W1.eligibility_state   = blocked
    baseline release       = forbidden

Le lifecycle intrinsèque de A1 et W1 ne change pas automatiquement.
A2 (writer), qui n'utilise pas T1, reste éligible : la propagation est
ciblée sur le chemin de dépendance réel, pas globale.
"""
from __future__ import annotations

from typing import List, Tuple

from acm import ConfigurationGraph, Evidence
from acm.models.enums import QualityState

from . import scenario_a

T1_KEY = "aci:tool:web-search@01JREV"


def build() -> Tuple[ConfigurationGraph, List[Evidence]]:
    """Config du scénario A avec T1.quality_state = nok.

    Comme ACIRevision est immuable (frozen), on reconstruit la révision T1 avec
    une qualité déclarée nok plutôt que de muter l'existante.
    """
    graph, evidence = scenario_a.build()

    old_t1 = graph.revisions[T1_KEY]
    new_declared = old_t1.declared.model_copy(update={"quality_state": QualityState.NOK})
    new_t1 = old_t1.model_copy(update={"declared": new_declared})
    graph.revisions[T1_KEY] = new_t1

    return graph, evidence
