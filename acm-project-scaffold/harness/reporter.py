"""Reporter du harness : agrège les résultats en rapport JSON pour l'article.

Produit un rapport global reproductible (§4, §14) : liste des ScenarioResult,
compteurs pass/fail par priorité, couverture des invariants, et un résumé
lisible. Le rapport est déterministe (tri stable, temps d'exécution arrondis et
isolés). Destiné au dépôt et à la table de résultats de l'article.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .runner import ScenarioResult


@dataclass
class EvaluationReport:
    """Rapport agrégé de l'évaluation complète."""

    results: List[ScenarioResult] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def add(self, result: ScenarioResult) -> None:
        self.results.append(result)

    def summary(self) -> Dict[str, Any]:
        by_priority: Dict[str, Dict[str, int]] = {}
        invariants_seen: set[str] = set()
        invariants_violated: set[str] = set()
        passed = failed = 0

        for r in sorted(self.results, key=lambda x: x.scenario_id):
            bucket = by_priority.setdefault(r.priority, {"pass": 0, "fail": 0})
            bucket[r.result] += 1
            if r.result == "pass":
                passed += 1
            else:
                failed += 1
            invariants_seen.update(r.invariants_checked)
            invariants_violated.update(r.invariants_violated)

        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "by_priority": by_priority,
            "invariants_checked": sorted(invariants_seen),
            "invariants_violated_detected": sorted(invariants_violated),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "summary": self.summary(),
            "results": [
                r.to_dict() for r in sorted(self.results, key=lambda x: x.scenario_id)
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def write(self, path: Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def print_console(self) -> None:
        s = self.summary()
        print(f"\n=== ACM evaluation — {s['passed']}/{s['total']} pass ===")
        for prio in sorted(s["by_priority"]):
            b = s["by_priority"][prio]
            print(f"  {prio}: {b['pass']} pass, {b['fail']} fail")
        for r in sorted(self.results, key=lambda x: x.scenario_id):
            mark = "PASS" if r.result == "pass" else "FAIL"
            print(f"  [{mark}] {r.scenario_id} ({r.priority}) "
                  f"iters={r.propagation_iterations} conv={r.converged}")
            if r.result == "fail":
                for m in r.mismatches:
                    print(f"         {m}")
