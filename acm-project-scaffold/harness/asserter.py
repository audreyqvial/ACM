"""Asserter du harness : rapport observé vs oracle déclaratif (§13.4).

L'oracle ne vérifie pas seulement l'état global. Conformément à la section 13.4
du plan, il peut asserter, par item :
  - les quatre états calculés (effective_quality, effective_assurance,
    impact_state, eligibility_state) ;
  - le lifecycle_state (intrinsèque — ne doit PAS être contaminé) ;
  - les codes de raison présents (existence, jamais le message exact) ;
  - la classification des preuves (applicable / stale / inapplicable) par id ;
et, au niveau global :
  - convergence, borne d'itérations, validité, problèmes de graphe attendus.

Chaque écart produit un `Mismatch` lisible ; l'ensemble forme un diff exploitable
en cas d'échec (indispensable pour 27 scénarios × 10 répétitions).

Format d'oracle (bloc `expected:` de la fixture) :

    expected:
      converged: true
      valid: false
      items:
        "aci:agent:planner":
          effective_quality: nok
          effective_assurance: partially_assessed
          impact_state: stale
          eligibility_state: blocked
          lifecycle_state: draft          # optionnel
          reason_codes: [ACM-PROP-QUALITY-BLOCK]   # existence
          applicable_evidence: [evidence:eval:planner:001]
          stale_evidence: [evidence:eval:planner:002]
          inapplicable_evidence: []
      graph_problems_contains: ["Référence target manquante"]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from acm import PropagationReport
from acm.models.status import ItemStatus


@dataclass
class Mismatch:
    """Un écart précis entre observé et attendu."""

    scope: str          # "global" ou la clé/id d'item
    field: str          # champ concerné
    expected: Any
    observed: Any

    def __str__(self) -> str:
        return (
            f"[{self.scope}] {self.field}: "
            f"attendu={self.expected!r} observé={self.observed!r}"
        )


@dataclass
class AssertionResult:
    """Résultat structuré d'une assertion de scénario."""

    scenario_id: str
    passed: bool
    mismatches: List[Mismatch] = field(default_factory=list)
    checks_run: int = 0

    def diff(self) -> str:
        if self.passed:
            return "OK"
        return "\n".join(f"  - {m}" for m in self.mismatches)


def _find_item(report: PropagationReport, id_or_key: str) -> Optional[ItemStatus]:
    """Retrouve un item par clé exacte (id@rev) ou par id logique seul."""
    item = report.items.get(id_or_key)
    if item is not None:
        return item
    for it in report.items.values():
        if it.ref.id == id_or_key:
            return it
    return None


_COMPUTED_FIELDS = {
    "effective_quality": lambda it: it.computed.effective_quality.value,
    "effective_assurance": lambda it: it.computed.effective_assurance.value,
    "impact_state": lambda it: it.computed.impact_state.value,
    "eligibility_state": lambda it: it.computed.eligibility_state.value,
    "lifecycle_state": lambda it: it.lifecycle_state.value,
    "declared_quality": lambda it: it.declared_quality.value,
    "declared_assurance": lambda it: it.declared_assurance.value,
}


def _assert_item(
    item_id: str,
    expected: Dict[str, Any],
    item: Optional[ItemStatus],
    out: List[Mismatch],
) -> int:
    checks = 0
    if item is None:
        out.append(Mismatch(item_id, "presence", "présent dans le rapport", "absent"))
        return 1

    for field_name, accessor in _COMPUTED_FIELDS.items():
        if field_name in expected:
            checks += 1
            observed = accessor(item)
            if observed != expected[field_name]:
                out.append(Mismatch(item_id, field_name, expected[field_name], observed))

    # Codes de raison : on vérifie l'EXISTENCE de chaque code attendu, jamais
    # le message (qui est de la présentation, §13.4).
    if "reason_codes" in expected:
        checks += 1
        observed_codes = {r.code for r in item.computed.reasons}
        for code in expected["reason_codes"]:
            if code not in observed_codes:
                out.append(
                    Mismatch(item_id, "reason_code", f"présent: {code}", sorted(observed_codes))
                )

    # Classification des preuves par id.
    for key, attr in (
        ("applicable_evidence", "applicable_evidence_ids"),
        ("stale_evidence", "stale_evidence_ids"),
        ("inapplicable_evidence", "inapplicable_evidence_ids"),
    ):
        if key in expected:
            checks += 1
            observed_ids = set(getattr(item, attr))
            expected_ids = set(expected[key])
            if observed_ids != expected_ids:
                out.append(
                    Mismatch(item_id, key, sorted(expected_ids), sorted(observed_ids))
                )

    return checks


_GLOBAL_FIELDS = {
    "converged": lambda r: r.converged,
    "valid": lambda r: r.valid,
}


def _assert_runtime_sequence(
    expected_seq: Dict[str, Any],
    seq_result: Any,
    out: List[Mismatch],
) -> int:
    """Confronte le résultat de validation de séquence runtime à l'oracle (S13)."""
    checks = 0
    if seq_result is None:
        out.append(Mismatch("runtime_sequence", "presence", "séquence validée", "absente"))
        return 1

    if "valid" in expected_seq:
        checks += 1
        if seq_result.valid != expected_seq["valid"]:
            out.append(Mismatch("runtime_sequence", "valid", expected_seq["valid"], seq_result.valid))

    if "reliable" in expected_seq:
        checks += 1
        if seq_result.reliable != expected_seq["reliable"]:
            out.append(Mismatch("runtime_sequence", "reliable", expected_seq["reliable"], seq_result.reliable))

    if "final_state" in expected_seq:
        checks += 1
        observed = seq_result.final_state.value if seq_result.final_state else None
        if observed != expected_seq["final_state"]:
            out.append(Mismatch("runtime_sequence", "final_state", expected_seq["final_state"], observed))

    # Codes d'anomalie : chaque code attendu doit être présent (existence).
    if "problem_codes" in expected_seq:
        checks += 1
        observed_codes = {p.code for p in seq_result.problems}
        for code in expected_seq["problem_codes"]:
            if code not in observed_codes:
                out.append(Mismatch("runtime_sequence", "problem_code", f"présent: {code}", sorted(observed_codes)))

    return checks


def assert_report(
    scenario_id: str,
    report: PropagationReport,
    expected: Dict[str, Any],
    runtime_seq_result: Any = None,
) -> AssertionResult:
    """Compare le rapport observé à l'oracle. Retourne un résultat structuré."""
    mismatches: List[Mismatch] = []
    checks = 0

    # Champs globaux.
    for field_name, accessor in _GLOBAL_FIELDS.items():
        if field_name in expected:
            checks += 1
            observed = accessor(report)
            if observed != expected[field_name]:
                mismatches.append(
                    Mismatch("global", field_name, expected[field_name], observed)
                )

    # Borne d'itérations (reproductibilité §4.2) : on autorise <=.
    if "max_iterations" in expected:
        checks += 1
        if report.iterations > expected["max_iterations"]:
            mismatches.append(
                Mismatch("global", "iterations<=", expected["max_iterations"], report.iterations)
            )

    # Problèmes de graphe attendus (S02) : chaque motif doit apparaître dans au
    # moins un problème signalé.
    if "graph_problems_contains" in expected:
        for pattern in expected["graph_problems_contains"]:
            checks += 1
            if not any(pattern in p for p in report.graph_problems):
                mismatches.append(
                    Mismatch("global", "graph_problems", f"contient: {pattern}", report.graph_problems)
                )

    # Items.
    for item_id, item_expected in (expected.get("items", {}) or {}).items():
        item = _find_item(report, item_id)
        checks += _assert_item(item_id, item_expected, item, mismatches)

    # Séquence runtime (S12/S13).
    if "runtime_sequence" in expected:
        checks += _assert_runtime_sequence(
            expected["runtime_sequence"], runtime_seq_result, mismatches
        )

    return AssertionResult(
        scenario_id=scenario_id,
        passed=len(mismatches) == 0,
        mismatches=mismatches,
        checks_run=checks,
    )
