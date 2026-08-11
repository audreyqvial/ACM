"""Pont pytest du harness — mode CI.

Chaque fixture scenarios/*.yaml est collectée comme un cas de test paramétré.
L'identifiant du test est le scenario_id, de sorte qu'un échec pointe droit sur
le scénario fautif avec le diff de l'asserter.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import discover_scenarios, load_scenario, run_loaded

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios" / "fixtures"

_SCENARIO_PATHS = discover_scenarios(SCENARIOS_DIR)


@pytest.mark.parametrize(
    "scenario_path",
    _SCENARIO_PATHS,
    ids=[p.stem for p in _SCENARIO_PATHS],
)
def test_scenario_matches_oracle(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    result, report, assertion = run_loaded(scenario)
    assert assertion.passed, (
        f"\nScénario {scenario.scenario_id} — {len(assertion.mismatches)} écart(s):\n"
        + assertion.diff()
    )


@pytest.mark.parametrize(
    "scenario_path",
    _SCENARIO_PATHS,
    ids=[p.stem for p in _SCENARIO_PATHS],
)
def test_scenario_is_deterministic(scenario_path: Path) -> None:
    """Reproductibilité (§4.2) : deux exécutions donnent des digests identiques."""
    scenario = load_scenario(scenario_path)
    r1, _, _ = run_loaded(scenario)
    r2, _, _ = run_loaded(scenario)
    assert r1.configuration_digest == r2.configuration_digest
    assert r1.evidence_digest == r2.evidence_digest
    assert r1.observed_status == r2.observed_status
