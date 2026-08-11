"""Runner du harness : exécute un scénario et produit le résultat §4.

Chaîne : loader -> propagate() -> digests -> asserter -> ScenarioResult.
Le ScenarioResult reprend EXACTEMENT le schéma de la section 4 du plan
(scenario_id, framework, configuration_digest, evidence_digest, expected/observed
status, invariants, itérations, convergence, temps, pass/fail).

Le runner est déterministe : mêmes entrées -> même sortie (hors execution_time_ms
qui est purement diagnostique et exclu de toute assertion).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from acm import PropagationContext, PropagationReport, propagate
from acm.invariants import check_report_invariants

from .asserter import AssertionResult, assert_report
from .digest import configuration_digest, evidence_digest
from .loader import LoadedScenario, load_scenario


@dataclass
class ScenarioResult:
    """Résultat structuré conforme à la section 4 du plan d'évaluation."""

    scenario_id: str
    framework: str
    configuration_digest: str
    evidence_digest: str
    expected_status: Dict[str, Any]
    observed_status: Dict[str, Any]
    invariants_checked: List[str]
    invariants_violated: List[str]
    runtime_event_count: int
    propagation_iterations: int
    converged: bool
    execution_time_ms: float
    result: str                     # "pass" | "fail"
    mismatches: List[str] = field(default_factory=list)
    priority: str = "P0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "framework": self.framework,
            "priority": self.priority,
            "configuration_digest": self.configuration_digest,
            "evidence_digest": self.evidence_digest,
            "expected_status": self.expected_status,
            "observed_status": self.observed_status,
            "invariants_checked": self.invariants_checked,
            "invariants_violated": self.invariants_violated,
            "runtime_event_count": self.runtime_event_count,
            "propagation_iterations": self.propagation_iterations,
            "converged": self.converged,
            "execution_time_ms": round(self.execution_time_ms, 3),
            "result": self.result,
            "mismatches": self.mismatches,
        }


def _observed_status(report: PropagationReport, runtime_seq_result=None) -> Dict[str, Any]:
    """Projection compacte du rapport pour le champ observed_status."""
    items: Dict[str, Any] = {}
    for item in report.items.values():
        c = item.computed
        items[item.ref.id] = {
            "effective_quality": c.effective_quality.value,
            "effective_assurance": c.effective_assurance.value,
            "impact_state": c.impact_state.value,
            "eligibility_state": c.eligibility_state.value,
            "lifecycle_state": item.lifecycle_state.value,
            "reason_codes": sorted({r.code for r in c.reasons}),
            "applicable_evidence": sorted(item.applicable_evidence_ids),
            "stale_evidence": sorted(item.stale_evidence_ids),
            "inapplicable_evidence": sorted(item.inapplicable_evidence_ids),
        }
    observed: Dict[str, Any] = {
        "converged": report.converged,
        "valid": report.valid,
        "iterations": report.iterations,
        "summary": report.summary,
        "graph_problems": report.graph_problems,
        "items": items,
    }
    if runtime_seq_result is not None:
        observed["runtime_sequence"] = {
            "valid": runtime_seq_result.valid,
            "reliable": runtime_seq_result.reliable,
            "final_state": runtime_seq_result.final_state.value
            if runtime_seq_result.final_state
            else None,
            "problem_codes": sorted({p.code for p in runtime_seq_result.problems}),
        }
    return observed


def run_loaded(
    scenario: LoadedScenario,
    *,
    framework: str = "core",
    check_invariants: bool = True,
) -> tuple[ScenarioResult, PropagationReport, AssertionResult]:
    """Exécute un scénario déjà chargé. Retourne (résultat §4, rapport, assertion)."""
    started = time.perf_counter()

    report = propagate(
        scenario.graph,
        scenario.evidence,
        scenario.context,
        validate_graph=True,
        strict=False,
    )
    # Remplir les digests §4 que le rapport prévoit mais ne calcule pas seul.
    report.configuration_digest = configuration_digest(scenario.graph)
    report.evidence_digest = evidence_digest(scenario.evidence)

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    # Invariants : on liste ceux vérifiés et ceux violés (détection correcte).
    invariants_checked: List[str] = []
    invariants_violated: List[str] = []
    if check_invariants:
        violations = check_report_invariants(scenario.graph, report)
        invariants_violated = sorted({v.invariant for v in violations})
        # La liste "checked" est fournie par le module invariants s'il l'expose ;
        # sinon on rapporte au minimum ceux effectivement évalués.
        invariants_checked = _all_invariant_ids()

    # Validation optionnelle d'une séquence runtime (S12/S13). En mode
    # permissif : on collecte toutes les anomalies pour les confronter à
    # l'oracle plutôt que de lever à la première.
    runtime_seq_result = None
    runtime_event_count = 0
    if scenario.runtime_sequence is not None:
        from acm.state_machines import TransitionValidator

        runtime_event_count = len(scenario.runtime_sequence)
        runtime_seq_result = TransitionValidator(strict=False).validate_runtime_sequence(
            scenario.runtime_sequence
        )

    assertion = assert_report(
        scenario.scenario_id, report, scenario.expected, runtime_seq_result
    )

    result = ScenarioResult(
        scenario_id=scenario.scenario_id,
        framework=framework,
        configuration_digest=report.configuration_digest,
        evidence_digest=report.evidence_digest,
        expected_status=scenario.expected,
        observed_status=_observed_status(report, runtime_seq_result),
        invariants_checked=invariants_checked,
        invariants_violated=invariants_violated,
        runtime_event_count=runtime_event_count,
        propagation_iterations=report.iterations,
        converged=report.converged,
        execution_time_ms=elapsed_ms,
        result="pass" if assertion.passed else "fail",
        mismatches=[str(m) for m in assertion.mismatches],
        priority=scenario.priority,
    )
    return result, report, assertion


def run_scenario_file(
    path: Path, *, framework: str = "core"
) -> tuple[ScenarioResult, PropagationReport, AssertionResult]:
    """Charge puis exécute une fixture YAML."""
    scenario = load_scenario(path)
    return run_loaded(scenario, framework=framework)


def _all_invariant_ids() -> List[str]:
    """Liste des identifiants d'invariants I1..I14 (pour le champ checked)."""
    return [f"I{i}" for i in range(1, 15)]
