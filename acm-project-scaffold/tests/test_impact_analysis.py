# Emplacement : tests/test_impact_analysis.py
"""Tests de l'analyse d'impact comparative (vague 1.a — manuel vs ACM).

Verrouillent les propriétés du cas d'étude :
  - ACM et l'investigation manuelle EXHAUSTIVE trouvent le même ensemble affecté
    (validation croisée : ACM ne fabrique ni ne rate rien) ;
  - l'investigation NAÏVE (1 niveau) manque les effets transitifs ;
  - ACM répond en une seule propagation.
"""
from __future__ import annotations

from acm.models.enums import QualityState
from harness.impact_analysis import (
    acm_impact_analysis,
    compare_impact_analysis,
    manual_impact_investigation,
)
from scenarios import impact_case_study as cs


def _degraded_case():
    return cs.build(model_quality=QualityState.NOK)


def test_manual_exhaustive_matches_acm():
    """L'ensemble affecté ACM == investigation manuelle exhaustive (BFS)."""
    graph, evidence, model_ref = _degraded_case()
    comp = compare_impact_analysis(graph, evidence, model_ref)
    assert comp.manual.affected_ids == comp.acm.affected_ids
    assert comp.to_dict()["agreement"]["exhaustive_manual_matches_acm"] is True


def test_naive_investigation_misses_transitive_effects():
    """L'approche naïve (1 niveau) manque au moins un item transitif."""
    graph, _, model_ref = _degraded_case()
    manual = manual_impact_investigation(graph, model_ref)
    assert manual.missed_by_naive, "le cas doit exhiber des effets transitifs manqués"
    # Les workflows (niveau 2) sont manqués par l'approche 1-niveau.
    assert all("workflow" in wid for wid in manual.missed_by_naive)


def test_acm_uses_single_propagation():
    """ACM répond à la question d'impact en une seule requête."""
    graph, evidence, model_ref = _degraded_case()
    acm = acm_impact_analysis(graph, evidence, model_ref)
    assert acm.queries == 1


def test_manual_costs_more_inspections_than_acm_queries():
    """Le coût manuel (inspections) dépasse le coût ACM (requêtes)."""
    graph, evidence, model_ref = _degraded_case()
    comp = compare_impact_analysis(graph, evidence, model_ref)
    assert comp.manual.inspection_steps > comp.acm.queries


def test_impact_propagates_to_multiple_levels():
    """La propagation atteint une profondeur > 1 (effets indirects réels)."""
    graph, _, model_ref = _degraded_case()
    manual = manual_impact_investigation(graph, model_ref)
    assert manual.max_depth >= 2


def test_healthy_model_has_no_degraded_dependents():
    """Sans dégradation du modèle, aucun dépendant n'est marqué affecté par ACM."""
    graph, evidence, model_ref = cs.build(model_quality=QualityState.OK)
    acm = acm_impact_analysis(graph, evidence, model_ref)
    assert acm.affected_ids == set()


def test_comparison_is_deterministic():
    """Deux exécutions du comparateur donnent le même résultat."""
    graph, evidence, model_ref = _degraded_case()
    c1 = compare_impact_analysis(graph, evidence, model_ref).to_dict()
    c2 = compare_impact_analysis(graph, evidence, model_ref).to_dict()
    assert c1 == c2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
