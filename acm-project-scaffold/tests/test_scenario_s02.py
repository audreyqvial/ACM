# Emplacement : tests/test_scenario_s02.py
"""Test S02 — Référence obligatoire manquante (§ plan ACM-S02).

Complète la fixture scenarios/fixtures/ACM-S02.yaml en vérifiant les deux
aspects que l'oracle déclaratif ne capture pas directement :

  1. la référence manquante est bien détectée (graph_problems) ;
  2. le refus effectif de toute création de baseline / promotion se manifeste
     en mode strict : propagate(..., strict=True) LÈVE sur une configuration
     structurellement invalide — c'est le mécanisme actuel qui interdit de
     promouvoir une config cassée.

Séparation assumée (cf. conception) : validité structurelle ≠ éligibilité
calculée. A1 reste `eligible` en mode permissif, mais ce statut est un artefact
d'une config invalide et ne survit pas à une validation stricte.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from acm import PropagationContext, propagate
from acm.policy import EligibilityContext
from harness import load_scenario

FIXTURE = Path(__file__).resolve().parent.parent / "scenarios" / "fixtures" / "ACM-S02.yaml"


def _load():
    return load_scenario(FIXTURE)


def test_s02_missing_reference_is_detected():
    """La référence modèle manquante apparaît dans graph_problems."""
    sc = _load()
    report = propagate(sc.graph, sc.evidence, sc.context)
    assert any("aci:model:missing" in p for p in report.graph_problems)
    assert any("manquante" in p for p in report.graph_problems)


def test_s02_strict_mode_refuses_invalid_configuration():
    """En mode strict, une config avec référence manquante est REJETÉE.

    C'est le mécanisme actuel de refus : aucune baseline/promotion ne peut être
    construite sur une configuration que la validation stricte rejette.
    """
    sc = _load()
    with pytest.raises(ValueError):
        propagate(sc.graph, sc.evidence, sc.context, strict=True)


def test_s02_baseline_release_context_also_refuses_strict():
    """Même en contexte baseline_release, la config invalide est rejetée strict."""
    sc = _load()
    ctx = PropagationContext(
        eligibility_context=EligibilityContext.BASELINE_RELEASE,
        now=sc.context.now,
        environment=sc.context.environment,
    )
    with pytest.raises(ValueError):
        propagate(sc.graph, sc.evidence, ctx, strict=True)


def test_s02_unresolved_reference_blocks_eligibility():
    """CORRECTIF S02 : une référence requise non résolue rend l'ACI blocked.

    La validité structurelle et l'éligibilité restent distinctes, mais reliées
    quand l'erreur est directement attribuable à l'ACI : A1 dépend d'un modèle
    absent via une relation requise → eligibility = blocked + ACM-REF-UNRESOLVED.
    """
    sc = _load()
    report = propagate(sc.graph, sc.evidence, sc.context)  # permissif
    a1 = next(i for i in report.items.values() if i.ref.id == "aci:agent:planner")
    assert a1.computed.eligibility_state.value == "blocked"
    codes = {r.code for r in a1.computed.reasons}
    assert "ACM-REF-UNRESOLVED" in codes
    # La détection structurelle reste présente en parallèle.
    assert report.graph_problems, "la config doit être signalée structurellement invalide"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
