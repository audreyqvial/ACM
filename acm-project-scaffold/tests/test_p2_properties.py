"""Tests P2 property-based (Hypothesis).

Vérifie sur des centaines de graphes générés aléatoirement les propriétés
fondamentales du moteur :

  - convergence : tout graphe DAG valide converge ;
  - idempotence : re-propager un rapport ne change pas les états ;
  - invariance à l'ordre : l'ordre d'insertion n'affecte pas le résultat ;
  - monotonie : dégrader une entrée ne peut qu'aggraver (ou laisser stable)
    les états effectifs, jamais les améliorer ;
  - stabilité de sérialisation : round-trip JSON du rapport préservé.

Au lieu de tester des cas choisis, Hypothesis cherche activement des
contre-exemples parmi de nombreuses configurations générées.
"""
from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis non installé")

from hypothesis import HealthCheck, given, settings

from acm import ConfigurationGraph, PropagationContext, propagate
from acm.models.enums import (
    ELIGIBILITY_SEVERITY,
    IMPACT_SEVERITY,
    QUALITY_SEVERITY,
    QualityState,
)
from acm.models.status import PropagationReport
from tests.strategies import acm_graph

# Réglages communs : pas de deadline (propagation + génération), santé relâchée.
P2_SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


# --- Convergence ---

@given(acm_graph())
@P2_SETTINGS
def test_property_always_converges(graph_data):
    graph, evidence = graph_data
    report = propagate(graph, evidence, PropagationContext())
    assert report.converged is True


# --- Idempotence ---

@given(acm_graph())
@P2_SETTINGS
def test_property_idempotent(graph_data):
    """Re-propager le même graphe donne des états effectifs identiques."""
    graph, evidence = graph_data
    ctx = PropagationContext()
    r1 = propagate(graph, evidence, ctx)
    r2 = propagate(graph, evidence, ctx)
    for key in r1.items:
        c1, c2 = r1.items[key].computed, r2.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


# --- Invariance à l'ordre ---

@given(acm_graph())
@P2_SETTINGS
def test_property_order_invariance(graph_data):
    """L'ordre d'insertion des révisions/relations ne change pas le résultat."""
    graph, evidence = graph_data
    ctx = PropagationContext()

    # Graphe ré-ordonné : mêmes révisions/relations, ordre inversé.
    revs = list(graph.revisions.values())
    rels = list(graph.relations)
    reordered = ConfigurationGraph.build(list(reversed(revs)), list(reversed(rels)))

    r1 = propagate(graph, evidence, ctx)
    r2 = propagate(reordered, list(reversed(evidence)), ctx)

    for key in r1.items:
        c1, c2 = r1.items[key].computed, r2.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


# --- Monotonie ---

@given(acm_graph())
@P2_SETTINGS
def test_property_monotonic_quality_degradation(graph_data):
    """Dégrader la qualité déclarée d'une feuille ne peut PAS améliorer la
    qualité effective d'un autre nœud (opérateurs monotones, §21.5)."""
    graph, evidence = graph_data
    ctx = PropagationContext()

    baseline = propagate(graph, evidence, ctx)

    # Dégrader la qualité déclarée du prompt à nok (le pire).
    p_key = "aci:prompt:p@01J"
    if p_key not in graph.revisions:
        return
    prompt = graph.revisions[p_key]
    degraded_prompt = prompt.model_copy(update={
        "declared": prompt.declared.model_copy(update={"quality_state": QualityState.NOK})
    })
    degraded_revs = [
        degraded_prompt if r.key() == p_key else r
        for r in graph.revisions.values()
    ]
    degraded_graph = ConfigurationGraph.build(degraded_revs, list(graph.relations))
    degraded = propagate(degraded_graph, evidence, ctx)

    # Pour chaque nœud, la qualité effective dégradée est >= (au moins aussi
    # sévère que) la baseline — jamais meilleure.
    for key in baseline.items:
        base_q = baseline.items[key].computed.effective_quality
        degr_q = degraded.items[key].computed.effective_quality
        assert QUALITY_SEVERITY[degr_q] >= QUALITY_SEVERITY[base_q], (
            f"{key}: dégradation a AMÉLIORÉ la qualité "
            f"({base_q.value} -> {degr_q.value})"
        )


@given(acm_graph())
@P2_SETTINGS
def test_property_monotonic_eligibility(graph_data):
    """Dégrader une feuille ne peut pas améliorer l'éligibilité d'un nœud."""
    graph, evidence = graph_data
    ctx = PropagationContext()
    baseline = propagate(graph, evidence, ctx)

    t_key = "aci:tool:t@01J"
    if t_key not in graph.revisions:
        return
    tool = graph.revisions[t_key]
    degraded_tool = tool.model_copy(update={
        "declared": tool.declared.model_copy(update={"quality_state": QualityState.NOK})
    })
    degraded_revs = [
        degraded_tool if r.key() == t_key else r
        for r in graph.revisions.values()
    ]
    degraded_graph = ConfigurationGraph.build(degraded_revs, list(graph.relations))
    degraded = propagate(degraded_graph, evidence, ctx)

    for key in baseline.items:
        base_e = baseline.items[key].computed.eligibility_state
        degr_e = degraded.items[key].computed.eligibility_state
        assert ELIGIBILITY_SEVERITY[degr_e] >= ELIGIBILITY_SEVERITY[base_e], (
            f"{key}: dégradation a AMÉLIORÉ l'éligibilité "
            f"({base_e.value} -> {degr_e.value})"
        )


# --- Stabilité de sérialisation ---

@given(acm_graph())
@P2_SETTINGS
def test_property_report_serialization_roundtrip(graph_data):
    """Le rapport survit à un aller-retour JSON sans perte d'états."""
    graph, evidence = graph_data
    report = propagate(graph, evidence, PropagationContext())

    dumped = report.model_dump_json()
    restored = PropagationReport.model_validate_json(dumped)

    assert restored.converged == report.converged
    assert restored.summary == report.summary
    for key in report.items:
        c1 = report.items[key].computed
        c2 = restored.items[key].computed
        assert c1.effective_quality == c2.effective_quality
        assert c1.effective_assurance == c2.effective_assurance
        assert c1.impact_state == c2.impact_state
        assert c1.eligibility_state == c2.eligibility_state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
