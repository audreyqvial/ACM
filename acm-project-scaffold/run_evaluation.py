"""Runner autonome du harness — mode rapport d'article.

Exécute toutes les fixtures scenarios/*.yaml, imprime un résumé console et écrit
un rapport JSON agrégé (schéma §4) exploitable pour la table de résultats de
l'article et le dépôt.

    python run_evaluation.py [--out evaluation_report.json] [--repeat N]

`--repeat N` rejoue chaque scénario N fois et vérifie la stabilité des digests
(reproductibilité §13.1) ; N=1 par défaut.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from harness import discover_scenarios, load_scenario, run_loaded
from harness.reporter import EvaluationReport

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios" / "fixtures"


def main() -> int:
    parser = argparse.ArgumentParser(description="ACM scenario evaluation harness")
    parser.add_argument("--out", type=Path, default=Path("evaluation_report.json"))
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS_DIR)
    args = parser.parse_args()

    report = EvaluationReport()
    unstable: list[str] = []

    for path in discover_scenarios(args.scenarios):
        scenario = load_scenario(path)
        first, _, _ = run_loaded(scenario)
        report.add(first)

        # Contrôle de reproductibilité sur --repeat exécutions.
        for _ in range(max(0, args.repeat - 1)):
            again, _, _ = run_loaded(scenario)
            if (
                again.configuration_digest != first.configuration_digest
                or again.evidence_digest != first.evidence_digest
                or again.observed_status != first.observed_status
            ):
                unstable.append(scenario.scenario_id)
                break

    report.print_console()
    if unstable:
        print(f"\n⚠ Scénarios non reproductibles: {sorted(set(unstable))}")
    report.write(args.out)
    print(f"\nRapport écrit: {args.out}")

    s = report.summary()
    return 0 if s["failed"] == 0 and not unstable else 1


if __name__ == "__main__":
    raise SystemExit(main())
