"""Harness d'évaluation ACM — fixtures déclaratives + oracles (§13.4, §4).

Point d'entrée pour exécuter les scénarios S01..S27 en deux modes :
  - pytest paramétré (CI) : voir tests/test_scenarios.py ;
  - runner autonome (rapport d'article) : voir run_evaluation().
"""
from .asserter import AssertionResult, Mismatch, assert_report
from .digest import (
    baseline_digest,
    canonical_json,
    configuration_digest,
    content_digest,
    evidence_digest,
)
from .loader import (
    LoadedScenario,
    discover_scenarios,
    load_scenario,
    load_scenario_dict,
)
from .reporter import EvaluationReport
from .runner import ScenarioResult, run_loaded, run_scenario_file

__all__ = [
    "LoadedScenario", "load_scenario", "load_scenario_dict", "discover_scenarios",
    "canonical_json", "configuration_digest", "evidence_digest", "content_digest",
    "baseline_digest",
    "assert_report", "AssertionResult", "Mismatch",
    "ScenarioResult", "run_loaded", "run_scenario_file",
    "EvaluationReport",
]
