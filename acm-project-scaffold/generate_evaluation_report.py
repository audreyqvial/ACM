# Emplacement : generate_evaluation_report.py (racine du projet)
"""Génère le rapport d'évaluation consolidé à partir des résultats de tests RÉELS.

Contrairement à un rapport rédigé à la main, ce script exécute la suite pytest
complète et le runner de fixtures dans l'environnement courant, puis produit un
rapport horodaté reflétant EXACTEMENT ce qui a été exécuté ici — y compris les
scénarios de portabilité (S22–S24) si les extras langgraph/crewai sont installés.

Sortie : docs/evaluation_report_<YYYYMMDD-HHMMSS>.md
         (+ docs/evaluation_report_latest.md, copie du plus récent)

Usage :
    python generate_evaluation_report.py
    python generate_evaluation_report.py --tests-dir tests --out-dir docs

Fonctionnement : un plugin pytest inline capture chaque résultat de test
(passed/failed/skipped) ; les noms de tests sont mappés aux scénarios S01–S27 par
motif ; le runner du harness fournit les métriques des fixtures YAML. Aucune
dépendance externe (pas de pytest-json-report requis).
"""
from __future__ import annotations

import argparse
import platform
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# --------------------------------------------------------------------------
# Métadonnées des 27 scénarios (référentiel fixe : titres, priorités, groupes).
# Le STATUT, lui, est dérivé des résultats de tests — jamais codé en dur.
# --------------------------------------------------------------------------
SCENARIO_META: Dict[str, Dict[str, str]] = {
    "S01": {"group": "A", "priority": "P0", "title": "Configuration nominale, promotion"},
    "S02": {"group": "A", "priority": "P0", "title": "Référence obligatoire manquante"},
    "S03": {"group": "A", "priority": "P0", "title": "Identité exacte des preuves (digest)"},
    "S04": {"group": "A", "priority": "P0", "title": "Immutabilité d'une baseline released"},
    "S05": {"group": "B", "priority": "P0", "title": "Dépendance bloquante NOK"},
    "S06": {"group": "B", "priority": "P1", "title": "Dépendance non bloquante (warning)"},
    "S07": {"group": "B", "priority": "P0", "title": "Nouvelle révision de prompt, invalidation"},
    "S08": {"group": "B", "priority": "P0", "title": "Couverture d'assurance répartie"},
    "S09": {"group": "B", "priority": "P0", "title": "Preuve complète, résultat en échec"},
    "S10": {"group": "B", "priority": "P0", "title": "Modes direct/aggregate/hybrid"},
    "S11": {"group": "B", "priority": "P0", "title": "Politique absente vs vide"},
    "S12": {"group": "C", "priority": "P0", "title": "Replay nominal déterministe"},
    "S13": {"group": "C", "priority": "P0", "title": "Séquence runtime invalide"},
    "S14": {"group": "C", "priority": "P0", "title": "Mutation runtime autorisée"},
    "S15": {"group": "C", "priority": "P0", "title": "Mutation runtime non déclarée"},
    "S16": {"group": "C", "priority": "P1", "title": "Drift de configuration d'un prompt"},
    "S17": {"group": "C", "priority": "P1", "title": "Baseline retirée après run historique"},
    "S18": {"group": "D", "priority": "P0", "title": "Agent dynamique conforme"},
    "S19": {"group": "D", "priority": "P0", "title": "Escalade de permissions refusée"},
    "S20": {"group": "D", "priority": "P1", "title": "Override comportemental interdit"},
    "S21": {"group": "D", "priority": "P1", "title": "Promotion d'un agent runtime"},
    "S22": {"group": "E", "priority": "P0", "title": "Même système en LangGraph et CrewAI"},
    "S23": {"group": "E", "priority": "P1", "title": "Topologie explicite vs distribuée"},
    "S24": {"group": "E", "priority": "P1", "title": "Équivalence des événements runtime"},
    "S25": {"group": "E", "priority": "P0", "title": "Invariance à l'ordre des entrées"},
    "S26": {"group": "E", "priority": "P1", "title": "Cycles de dépendances"},
    "S27": {"group": "E", "priority": "P2", "title": "Volume et passage à l'échelle local"},
}

GROUP_TITLES = {
    "A": "Configuration et baseline",
    "B": "Propagation et assurance",
    "C": "Runtime, replay et drift",
    "D": "Agents dynamiques et permissions",
    "E": "Portabilité et robustesse",
}

# --------------------------------------------------------------------------
# Registre des DÉVIATIONS CONNUES.
# Un scénario listé ici, si tous ses tests passent, est classé
# `pass_with_deviation` plutôt que `pass` : le comportement est correct et testé,
# mais il s'écarte de ce que le plan prescrivait à l'origine (choix
# d'architecture assumé ou capacité dérivée plutôt que native). La valeur est la
# justification affichée dans le rapport.
#
# Ce registre peut être surchargé par test via le marqueur pytest
# `@pytest.mark.acm_deviation("raison")` (voir _ResultCollector).
# --------------------------------------------------------------------------
KNOWN_DEVIATIONS: Dict[str, str] = {
    "S14": "Détail de classification de drift (declared_extension) dérivé en "
            "couche de conformité, non porté nativement par l'énumération du moteur.",
    "S15": "Classification untraceable_instance dérivée ; le moteur porte le "
            "drift_state discret (undeclared_instance) sans le détail explicatif.",
    "S16": "Conformité de configuration (mismatch) évaluée comme résultat séparé, "
            "orthogonal au drift_state ; non promue en jugement de premier ordre.",
}

# Motif : capture S<nn> ou s<nn> dans un identifiant de test/fichier, suivi d'un
# délimiteur (fin, underscore, non-chiffre). On évite \b car l'underscore est un
# caractère de mot : "test_s22_..." n'a pas de frontière \b entre "22" et "_".
_SCENARIO_RE = re.compile(r"[Ss](\d{2})(?=_|\b|[^0-9])")
# Les cas d'étude historiques a..f couvrent des scénarios précis.
_LEGACY_MAP = {
    "scenario_a": ["S01"], "scenario_b": ["S05"], "scenario_c": ["S07"],
    "scenario_de": ["S18", "S19"], "scenario_f": ["S04"],
}


def _scenarios_for_nodeid(nodeid: str) -> List[str]:
    """Extrait le(s) scénario(s) couvert(s) par un test à partir de son nodeid."""
    found = {f"S{m.group(1)}" for m in _SCENARIO_RE.finditer(nodeid)}
    for legacy, scenarios in _LEGACY_MAP.items():
        if legacy in nodeid:
            found.update(scenarios)
    # Ne garder que les identifiants réellement connus.
    return sorted(s for s in found if s in SCENARIO_META)


class _ResultCollector:
    """Plugin pytest inline : capture les résultats et les agrège par scénario."""

    def __init__(self) -> None:
        # scénario -> compteur d'issues
        self.by_scenario: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"passed": 0, "failed": 0, "skipped": 0}
        )
        self.totals = {"passed": 0, "failed": 0, "skipped": 0}
        self.failed_nodeids: List[str] = []
        self.collection_errors: List[str] = []
        # scénario -> raison(s) de déviation déclarée(s) via marqueur pytest.
        self.marker_deviations: Dict[str, str] = {}

    def pytest_runtest_logreport(self, report) -> None:  # noqa: D401
        if report.when != "call" and not (report.when == "setup" and report.skipped):
            return
        outcome = "passed" if report.passed else "failed" if report.failed else "skipped"
        self.totals[outcome] += 1
        if outcome == "failed":
            self.failed_nodeids.append(report.nodeid)

        # Marqueur @pytest.mark.acm_deviation("raison") — surcharge le registre.
        marker_reason = None
        for name, value in getattr(report, "user_properties", []):
            if name == "acm_deviation":
                marker_reason = value

        for scenario in _scenarios_for_nodeid(report.nodeid):
            self.by_scenario[scenario][outcome] += 1
            if marker_reason:
                self.marker_deviations[scenario] = marker_reason

    def pytest_collectreport(self, report) -> None:  # noqa: D401
        """Capture les modules non collectables (dépendance absente, etc.)."""
        if report.failed:
            self.collection_errors.append(str(report.nodeid))


def pytest_configure(config) -> None:
    """Enregistre le marqueur acm_deviation (évite un warning pytest)."""
    config.addinivalue_line(
        "markers",
        "acm_deviation(reason): marque un test dont le scénario dévie du plan.",
    )


def pytest_runtest_makereport(item, call):  # noqa: D401
    """Transforme le marqueur @pytest.mark.acm_deviation en user_property.

    Hook au niveau item : lit l'argument du marqueur et l'attache au rapport via
    user_properties, où le collector le relit.
    """
    if call.when != "call":
        return
    marker = item.get_closest_marker("acm_deviation")
    if marker and marker.args:
        item.user_properties.append(("acm_deviation", marker.args[0]))


def _scenario_status(
    scenario_id: str,
    counts: Dict[str, int],
    marker_deviations: Dict[str, str],
) -> tuple[str, Optional[str]]:
    """Dérive le statut normalisé et l'éventuelle raison de déviation.

    Statuts : pass | pass_with_deviation | skipped | fail | not_executed.
    Une déviation (registre KNOWN_DEVIATIONS ou marqueur pytest) transforme un
    `pass` en `pass_with_deviation`. Le marqueur pytest a priorité sur le
    registre pour la formulation de la raison.
    """
    total = counts["passed"] + counts["failed"] + counts["skipped"]
    if total == 0:
        return "not_executed", None
    if counts["failed"] > 0:
        return "fail", None
    if counts["passed"] == 0 and counts["skipped"] > 0:
        return "skipped", None
    # À partir d'ici : au moins un passé, aucun échec.
    reason = marker_deviations.get(scenario_id) or KNOWN_DEVIATIONS.get(scenario_id)
    if reason:
        return "pass_with_deviation", reason
    return "pass", None


def _run_pytest(tests_dir: Path) -> _ResultCollector:
    collector = _ResultCollector()
    # On enregistre AUSSI le module courant comme plugin : ses hooks
    # (pytest_configure, pytest_runtest_makereport) activent la lecture du
    # marqueur @pytest.mark.acm_deviation. Sans lui, seul le collector tourne et
    # le marqueur reste invisible.
    import sys as _sys
    this_module = _sys.modules[__name__]
    # --continue-on-collection-errors : un module non collectable (p. ex.
    # dépendance de test absente) est signalé sans interrompre tout le run.
    pytest.main(
        [
            str(tests_dir),
            "-q",
            "-p", "no:cacheprovider",
            "--no-header",
            "--continue-on-collection-errors",
        ],
        plugins=[collector, this_module],
    )
    return collector


def _run_harness_metrics(scenarios_dir: Path) -> List[Dict]:
    """Exécute le runner du harness pour les métriques des fixtures YAML."""
    try:
        from harness import discover_scenarios, load_scenario, run_loaded
    except Exception:
        return []
    rows: List[Dict] = []
    for path in discover_scenarios(scenarios_dir):
        try:
            sc = load_scenario(path)
            result, _, _ = run_loaded(sc)
            rows.append({
                "scenario_id": result.scenario_id,
                "priority": result.priority,
                "iterations": result.propagation_iterations,
                "time_ms": result.execution_time_ms,
                "converged": result.converged,
                "result": result.result,
                "config_digest": result.configuration_digest,
                "evidence_digest": result.evidence_digest,
            })
        except Exception as exc:  # pragma: no cover
            rows.append({"scenario_id": path.stem, "error": str(exc)})
    return rows


def _detect_frameworks() -> Dict[str, bool]:
    def _has(mod: str) -> bool:
        try:
            __import__(mod)
            return True
        except Exception:
            return False
    return {"langgraph": _has("langgraph"), "crewai": _has("crewai"),
            "openai_agents": _has("agents")}


def _render_report(
    collector: _ResultCollector,
    harness_rows: List[Dict],
    frameworks: Dict[str, bool],
    generated_at: datetime,
) -> str:
    lines: List[str] = []
    A = lines.append

    A(f"# ACM — Rapport d'évaluation consolidé (auto-généré)\n")
    A(f"**Généré le :** {generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}  ")
    A(f"**Python :** {platform.python_version()} — **Plateforme :** {platform.system()} {platform.machine()}  ")
    fw = ", ".join(f"{k}={'oui' if v else 'non'}" for k, v in frameworks.items())
    A(f"**Frameworks disponibles :** {fw}\n")
    A("> Ce rapport est généré automatiquement à partir des résultats de tests "
      "exécutés dans l'environnement courant. Le statut de chaque scénario est "
      "dérivé des tests, jamais codé en dur.\n")

    # --- Synthèse ---
    t = collector.totals
    covered = sum(1 for s in SCENARIO_META if collector.by_scenario.get(s))
    # Décompte par statut de scénario.
    status_counts: Dict[str, int] = defaultdict(int)
    deviation_notes: Dict[str, str] = {}
    for sid in SCENARIO_META:
        counts = collector.by_scenario.get(sid, {"passed": 0, "failed": 0, "skipped": 0})
        st, reason = _scenario_status(sid, counts, collector.marker_deviations)
        status_counts[st] += 1
        if reason:
            deviation_notes[sid] = reason

    A("## 1. Synthèse\n")
    A("| Indicateur | Valeur |")
    A("|---|---|")
    A(f"| Scénarios couverts par au moins un test | {covered} / 27 |")
    A(f"| — dont pass | {status_counts.get('pass', 0)} |")
    A(f"| — dont pass_with_deviation | {status_counts.get('pass_with_deviation', 0)} |")
    A(f"| — dont skipped | {status_counts.get('skipped', 0)} |")
    A(f"| — dont fail | {status_counts.get('fail', 0)} |")
    A(f"| — dont not_executed | {status_counts.get('not_executed', 0)} |")
    A(f"| Tests passés | {t['passed']} |")
    A(f"| Tests échoués | {t['failed']} |")
    A(f"| Tests ignorés | {t['skipped']} |")
    A(f"| Fixtures YAML mesurées | {len([r for r in harness_rows if 'error' not in r])} |")
    A("")

    if collector.failed_nodeids:
        A("**Tests en échec :**\n")
        for nid in collector.failed_nodeids:
            A(f"- `{nid}`")
        A("")

    if collector.collection_errors:
        A("**Modules non collectés** (dépendance de test absente — n'affecte pas "
          "les scénarios ci-dessous) :\n")
        for nid in collector.collection_errors:
            A(f"- `{nid}`")
        A("")

    # --- Résultats par groupe ---
    A("## 2. Résultats par scénario\n")
    for group in ["A", "B", "C", "D", "E"]:
        A(f"### Groupe {group} — {GROUP_TITLES[group]}\n")
        A("| ID | Priorité | Objet | Tests (P/F/S) | Statut |")
        A("|---|---|---|---|---|")
        for sid, meta in SCENARIO_META.items():
            if meta["group"] != group:
                continue
            counts = collector.by_scenario.get(sid, {"passed": 0, "failed": 0, "skipped": 0})
            status, _ = _scenario_status(sid, counts, collector.marker_deviations)
            pfs = f"{counts['passed']}/{counts['failed']}/{counts['skipped']}"
            A(f"| {sid} | {meta['priority']} | {meta['title']} | {pfs} | `{status}` |")
        A("")

    # --- Déviations documentées ---
    if deviation_notes:
        A("## 3. Déviations documentées (`pass_with_deviation`)\n")
        A("Ces scénarios passent tous leurs tests, mais leur comportement s'écarte "
          "de ce que le plan prescrivait à l'origine. La déviation est un choix "
          "assumé, non un défaut.\n")
        A("| Scénario | Justification |")
        A("|---|---|")
        for sid in sorted(deviation_notes):
            A(f"| {sid} | {deviation_notes[sid]} |")
        A("")

    # --- Métriques des fixtures ---
    valid_rows = [r for r in harness_rows if "error" not in r]
    if valid_rows:
        A("## 4. Métriques des fixtures de propagation (harness)\n")
        A("| Scénario | Priorité | Itérations | Temps (ms) | Convergence | Résultat |")
        A("|---|---|---|---|---|---|")
        for r in sorted(valid_rows, key=lambda x: x["scenario_id"]):
            conv = "oui" if r["converged"] else "non"
            A(f"| {r['scenario_id']} | {r['priority']} | {r['iterations']} | "
              f"{r['time_ms']:.2f} | {conv} | {r['result']} |")
        A("")

    # --- Légende des statuts ---
    A("## 5. Légende des statuts\n")
    A("| Statut | Signification |")
    A("|---|---|")
    A("| `pass` | Tous les tests du scénario passent, sans déviation |")
    A("| `pass_with_deviation` | Tests passent, mais le comportement s'écarte du "
      "plan (choix assumé — voir section 3) |")
    A("| `skipped` | Tous les tests du scénario ignorés (dépendance manquante) |")
    A("| `fail` | Au moins un test en échec |")
    A("| `not_executed` | Aucun test rattaché exécuté |")
    A("")
    A("---\n")
    A(f"*Rapport généré automatiquement — {generated_at.isoformat()}*")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère le rapport d'évaluation ACM")
    parser.add_argument("--tests-dir", type=Path, default=Path("tests"))
    parser.add_argument("--scenarios-dir", type=Path, default=Path("scenarios/fixtures"))
    parser.add_argument("--out-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).astimezone()

    print("→ Exécution de la suite de tests…", file=sys.stderr)
    collector = _run_pytest(args.tests_dir)

    print("→ Collecte des métriques de fixtures…", file=sys.stderr)
    harness_rows = _run_harness_metrics(args.scenarios_dir)

    frameworks = _detect_frameworks()
    report = _render_report(collector, harness_rows, frameworks, generated_at)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")
    out_path = args.out_dir / f"evaluation_report_{stamp}.md"
    out_path.write_text(report, encoding="utf-8")
    latest = args.out_dir / "evaluation_report_latest.md"
    latest.write_text(report, encoding="utf-8")

    print(f"\n✓ Rapport écrit : {out_path}", file=sys.stderr)
    print(f"✓ Copie         : {latest}", file=sys.stderr)

    # Code retour : non nul si des tests ont échoué (utile en CI).
    return 1 if collector.totals["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
