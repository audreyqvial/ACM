# Emplacement : tests/test_impact_inspection.py
"""Tests de la réduction du coût d'inspection (variante stricte)."""
from __future__ import annotations

import pytest

from acm.impact import inspection_reduction


def test_basic_reduction():
    # 10 inspections manuelles, 2 résiduelles => 1 - 2/10 = 0.8
    r = inspection_reduction(manual_count=10, assisted_count=2)
    assert r.reduction == pytest.approx(0.8)
    assert r.avoided == 8


def test_full_reduction():
    r = inspection_reduction(10, 0)
    assert r.reduction == 1.0
    assert r.avoided == 10


def test_no_reduction():
    r = inspection_reduction(5, 5)
    assert r.reduction == 0.0
    assert r.avoided == 0


def test_negative_reduction_is_surfaced_not_hidden():
    # Cas pathologique : l'assistance impose PLUS de vérifications.
    r = inspection_reduction(4, 6)
    assert r.reduction == pytest.approx(-0.5)
    assert r.avoided == -2


def test_manual_zero_raises():
    with pytest.raises(ValueError):
        inspection_reduction(0, 0)


def test_negative_manual_raises():
    with pytest.raises(ValueError):
        inspection_reduction(-1, 0)


def test_negative_assisted_raises():
    with pytest.raises(ValueError):
        inspection_reduction(10, -1)
