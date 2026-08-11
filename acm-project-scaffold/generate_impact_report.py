# Emplacement : generate_impact_report.py (racine du projet)
"""Génère le rapport de l'étude d'impact comparative (vague 1.a).

Exécute le cas d'étude « changement d'un modèle partagé » et produit un rapport
Markdown + JSON chiffrant l'écart entre investigation manuelle et investigation
ACM. Destiné à la section « analyse d'impact » de l'article.

Sortie :
    docs/impact_report_<horodatage>.md
    docs/impact_report_<horodatage>.json
    docs/impact_report_latest.{md,json}

Usage :
    python generate_impact_report.py [--out-dir docs]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from acm.models.enums import QualityState
from harness.impact_analysis import compare_impact_analysis
from scenarios import impact_case_study as cs


def _render_md(data: dict, generated_at: datetime) -> str:
    m = data["manual"]
    a = data["acm"]
    lines = [
        "# ACM — Étude d'impact comparative (auto-générée)\n",
        f"**Généré le :** {generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}\n",
        "> Compare deux façons de répondre à « si je modifie cet ACI, qu'est-ce "
        "qui est affecté ? » : investigation manuelle vs propagation ACM. "
        "Chiffres dérivés de l'exécution, jamais codés en dur.\n",
        "## Cas d'étude\n",
        f"Changement du composant partagé `{data['root_id']}` dans un système de "
        f"{data['graph_size']} ACI et {data['relation_count']} relations.\n",
        "## Résultats\n",
        "| Métrique | Investigation manuelle | Investigation ACM |",
        "|---|---|---|",
        f"| Items affectés identifiés | {m['affected_count']} (exhaustif) | "
        f"{a['affected_count']} |",
        f"| Coût | {m['inspection_steps']} inspections | {a['queries']} requête |",
        f"| Profondeur de propagation | {m['max_depth']} niveaux | "
        f"{a['iterations']} itérations (point-fixe) |",
        "",
        "## Le risque de l'investigation naïve\n",
        f"Une investigation manuelle qui s'arrête aux dépendants directs (1 niveau) "
        f"n'identifie que **{m['naive_affected_count']}** des **{m['affected_count']}** "
        f"items réellement affectés — elle en **manque {m['missed_by_naive_count']}** :\n",
    ]
    for wid in m["missed_by_naive"]:
        lines.append(f"- `{wid}`")
    lines.append("")
    lines.append("Ces items sont affectés *indirectement* : ils dépendent d'un ACI "
                 "qui dépend lui-même du composant changé. C'est précisément le type "
                 "d'effet qu'une investigation manuelle rate.\n")

    lines.append("## Validation croisée\n")
    agree = data["agreement"]["exhaustive_manual_matches_acm"]
    if agree:
        lines.append(
            "L'ensemble affecté calculé par ACM **coïncide exactement** avec "
            "l'investigation manuelle exhaustive : ACM ne fabrique aucun faux "
            "positif et ne manque aucun effet. La différence est le **coût** et la "
            "**fiabilité** : ACM garantit l'exhaustivité en une propagation, là où "
            "l'investigation manuelle exige une discipline transitive parfaite.\n"
        )
    else:
        lines.append(
            "Écart détecté entre ACM et l'investigation manuelle exhaustive — "
            f"seulement dans manuel : {data['agreement']['only_in_manual']} ; "
            f"seulement dans ACM : {data['agreement']['only_in_acm']}.\n"
        )

    lines.append("---\n")
    lines.append(f"*Rapport généré automatiquement — {generated_at.isoformat()}*")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rapport d'étude d'impact ACM")
    parser.add_argument("--out-dir", type=Path, default=Path("docs"))
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).astimezone()

    graph, evidence, model_ref = cs.build(model_quality=QualityState.NOK)
    comparison = compare_impact_analysis(graph, evidence, model_ref)
    data = comparison.to_dict()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")

    md = _render_md(data, generated_at)
    (args.out_dir / f"impact_report_{stamp}.md").write_text(md, encoding="utf-8")
    (args.out_dir / "impact_report_latest.md").write_text(md, encoding="utf-8")

    payload = {"generated_at": generated_at.isoformat(), **data}
    js = json.dumps(payload, indent=2, ensure_ascii=False)
    (args.out_dir / f"impact_report_{stamp}.json").write_text(js, encoding="utf-8")
    (args.out_dir / "impact_report_latest.json").write_text(js, encoding="utf-8")

    print(f"✓ Rapport : {args.out_dir / f'impact_report_{stamp}.md'}")
    print(f"✓ JSON    : {args.out_dir / f'impact_report_{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
