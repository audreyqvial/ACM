# Emplacement : tests/test_impact_comparison.py
"""Tests de la comparaison P vs M (precision/recall).

On teste explicitement les DIVERGENCES (FP, FN) et les cas de bord (ensembles
vides), pas seulement l'accord parfait 1/1 — c'est là que se trouve le signal
méthodologiquement intéressant.
"""
from __future__ import annotations

import pytest

from acm.impact import compare


def test_exact_match():
    r = compare({"a", "b", "c"}, {"a", "b", "c"})
    assert r.precision == 1.0
    assert r.recall == 1.0
    assert r.exact_match
    assert r.tp == 3 and r.fp == 0 and r.fn == 0
    assert r.f1 == pytest.approx(1.0)


def test_false_positives_lower_precision():
    # ACM prédit d en trop.
    r = compare({"a", "b", "c", "d"}, {"a", "b", "c"})
    assert r.false_positive == frozenset({"d"})
    assert r.precision == pytest.approx(3 / 4)
    assert r.recall == 1.0
    assert not r.exact_match


def test_false_negatives_lower_recall():
    # ACM manque c.
    r = compare({"a", "b"}, {"a", "b", "c"})
    assert r.false_negative == frozenset({"c"})
    assert r.precision == 1.0
    assert r.recall == pytest.approx(2 / 3)


def test_mixed_fp_and_fn():
    r = compare({"a", "x"}, {"a", "y"})
    assert r.tp == 1
    assert r.false_positive == frozenset({"x"})
    assert r.false_negative == frozenset({"y"})
    assert r.precision == pytest.approx(1 / 2)
    assert r.recall == pytest.approx(1 / 2)
    assert r.f1 == pytest.approx(0.5)


def test_both_empty_is_vacuous_agreement():
    r = compare(set(), set())
    assert r.precision == 1.0
    assert r.recall == 1.0
    assert r.exact_match


def test_predicted_empty_manual_nonempty():
    # Rien prédit alors qu'un impact était attendu : recall 0, precision 0.
    r = compare(set(), {"a"})
    assert r.precision == 0.0
    assert r.recall == 0.0
    assert r.fn == 1


def test_manual_empty_predicted_nonempty():
    # Impact prédit alors qu'aucun attendu : precision 0, recall vacuité 1.
    r = compare({"a"}, set())
    assert r.precision == 0.0
    assert r.recall == 1.0
    assert r.fp == 1


def test_f1_zero_when_no_overlap():
    r = compare({"a"}, {"b"})
    assert r.precision == 0.0
    assert r.recall == 0.0
    assert r.f1 == 0.0


def test_accepts_frozenset_and_list_like():
    # compare tolère tout AbstractSet ; on passe des frozensets.
    r = compare(frozenset({"a", "b"}), frozenset({"a"}))
    assert r.tp == 1 and r.fp == 1 and r.fn == 0
