# Emplacement : tests/test_impact_metrics.py
"""Tests des métriques de portée (bloc 1) sur graphes jouets à réponses connues.

Doubles pure-Python via les vrais modèles ACM. Aucune dépendance framework.
"""
from __future__ import annotations

import pytest

from acm.impact import (
    impact_depth,
    impact_metrics,
    impact_ratio,
    impact_size,
    impact_weight,
    reach,
)
from acm.models.enums import RelationType

from .impact_fixtures import (
    cyclic_graph,
    graph_with_noimpact_edge,
    linear_chain,
    shared_model_fanout,
)


# --------------------------------------------------------------------------
# reach — direction de propagation (dépendants transitifs)
# --------------------------------------------------------------------------
def test_reach_linear_from_model_reaches_all_upstream():
    g = linear_chain()
    assert reach(g, "model") == {"prompt", "agent", "wf"}


def test_reach_linear_excludes_root():
    g = linear_chain()
    assert "model" not in reach(g, "model")


def test_reach_linear_from_middle():
    g = linear_chain()
    assert reach(g, "prompt") == {"agent", "wf"}


def test_reach_linear_from_top_is_empty():
    # wf ne dépend de personne en amont => rien ne le "réatteint".
    g = linear_chain()
    assert reach(g, "wf") == set()


def test_reach_unknown_root_is_empty():
    g = linear_chain()
    assert reach(g, "does-not-exist") == set()


def test_reach_fanout():
    g = shared_model_fanout()
    assert reach(g, "model") == {"a1", "a2", "a3", "wf"}


# --------------------------------------------------------------------------
# arêtes non-propageantes (impact_dependency=false)
# --------------------------------------------------------------------------
def test_noimpact_edge_blocks_propagation():
    g = graph_with_noimpact_edge()
    # agent->prompt non propageant : depuis model on n'atteint que prompt.
    assert reach(g, "model") == {"prompt"}


def test_size_respects_noimpact_edge():
    g = graph_with_noimpact_edge()
    assert impact_size(g, "model") == 1


# --------------------------------------------------------------------------
# cycles — terminaison + exclusion racine
# --------------------------------------------------------------------------
def test_reach_cyclic_terminates_and_excludes_root():
    g = cyclic_graph()
    assert reach(g, "a") == {"b", "c"}


# --------------------------------------------------------------------------
# size / depth / ratio
# --------------------------------------------------------------------------
def test_size_linear():
    g = linear_chain()
    assert impact_size(g, "model") == 3
    assert impact_size(g, "prompt") == 2
    assert impact_size(g, "agent") == 1
    assert impact_size(g, "wf") == 0


def test_depth_linear():
    g = linear_chain()
    assert impact_depth(g, "model") == 3
    assert impact_depth(g, "prompt") == 2
    assert impact_depth(g, "wf") == 0


def test_depth_fanout():
    g = shared_model_fanout()
    # model -> agents (1) -> wf (2)
    assert impact_depth(g, "model") == 2
    assert impact_depth(g, "a1") == 1


def test_ratio_fanout():
    g = shared_model_fanout()
    # |Reach(model)| = 4, |V| = 5
    assert impact_ratio(g, "model") == pytest.approx(0.8)


def test_ratio_local_is_zero():
    g = linear_chain()
    assert impact_ratio(g, "wf") == pytest.approx(0.0)


def test_ratio_empty_graph_no_division_error():
    from acm.models.aci import ConfigurationGraph

    g = ConfigurationGraph.build([], [])
    assert impact_ratio(g, "whatever") == 0.0


# --------------------------------------------------------------------------
# weight — défaut = size ; barème injecté = pondéré
# --------------------------------------------------------------------------
def test_weight_default_equals_size():
    g = shared_model_fanout()
    # poids par défaut 1.0 partout => weight == size
    assert impact_weight(g, "model") == float(impact_size(g, "model"))


def test_weight_injected_barometer():
    g = shared_model_fanout()
    # a1,a2,a3 atteints via USES_MODEL (poids 3) ; wf via CONTAINS (poids 2).
    weights = {
        RelationType.USES_MODEL: 3.0,
        RelationType.CONTAINS: 2.0,
    }
    # 3 nœuds * 3.0 + 1 nœud (wf) * 2.0 = 11.0
    assert impact_weight(g, "model", weights=weights) == pytest.approx(11.0)


# --------------------------------------------------------------------------
# agrégat cohérent
# --------------------------------------------------------------------------
def test_impact_metrics_aggregate_consistent():
    g = shared_model_fanout()
    m = impact_metrics(g, "model")
    assert m.root == "model"
    assert m.size == len(m.reach) == 4
    assert m.depth == 2
    assert m.ratio == pytest.approx(0.8)
    assert m.weight == float(m.size)  # défaut


def test_impact_metrics_deterministic():
    g = shared_model_fanout()
    m1 = impact_metrics(g, "model")
    m2 = impact_metrics(g, "model")
    assert m1.reach == m2.reach
    assert (m1.size, m1.depth, m1.ratio, m1.weight) == (
        m2.size,
        m2.depth,
        m2.ratio,
        m2.weight,
    )
