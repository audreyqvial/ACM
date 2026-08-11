# Emplacement : generate_impact_experiment_report.py (racine du projet)
"""Génère le rapport de l'expérience quantitative d'impact.

Consomme les ExperimentRecord du runner (matrice framework × change) et produit :
  - un JSON exhaustif (un objet par cas, au schéma du document de review) ;
  - un rapport markdown lisible : tableaux par métrique + colonnes déterminisme
    et provenance.

Le résultat publié provient du MOTEUR (P_f(c) = ensemble marqué à point fixe),
jamais de reach(). La cohérence reach ⊆ moteur est tracée mais non « vendue »
comme résultat.

Usage :
    python reports/generate_impact_experiment_report.py \
        --oracle-dir scenarios/impact_experiment/oracle \
        --inspection-dir scenarios/impact_experiment/inspection \
        --manifest scenarios/impact_experiment/oracle_manifest.json \
        --out-dir docs
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from harness.impact_experiment_runner import ExperimentRecord, run_matrix


def _table(headers: List[str], rows: List[List[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def render_markdown(records: List[ExperimentRecord]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    frameworks = sorted({r.framework for r in records})
    classes = ["local", "intermediate", "global"]

    def cell(f: str, cls: str, attr) -> str:
        for r in records:
            if r.framework == f and r.change_class == cls:
                v = getattr(r, attr)
                return f"{v:.3f}" if isinstance(v, float) else str(v)
        return "—"

    out: List[str] = []
    out.append("# Rapport — Expérience quantitative d'impact")
    out.append("")
    out.append(f"Généré : {ts}")
    out.append("")
    out.append(
        "Chaîne : système natif-équivalent → moteur ACM (point fixe) → "
        "P_f(c) → comparaison à l'oracle figé (vérifié par digest). "
        "Le résultat publié provient du moteur, pas de `reach()`."
    )
    out.append("")

    # Vérifications globales
    all_verified = all(r.digest_verified for r in records)
    all_det = all(r.deterministic for r in records)
    all_incl = all(r.reach_inclusion_holds for r in records)
    out.append("## Vérifications transverses")
    out.append("")
    out.append(f"- Cas exécutés : {len(records)}")
    out.append(f"- Oracles vérifiés par digest : {'tous' if all_verified else 'INCOMPLET'}")
    out.append(f"- Déterminisme (répétitions identiques) : {'oui' if all_det else 'NON'}")
    out.append(
        f"- Cohérence statique P_f(c) ⊆ reach(root) : "
        f"{'tenue partout' if all_incl else 'VIOLÉE'}"
    )
    out.append("")

    # Tableau : taille d'impact
    out.append("## ImpactSize |P_f(c)|")
    out.append("")
    rows = [[f] + [cell(f, c, "impact_size") for c in classes] for f in frameworks]
    out.append(_table(["Framework", *classes], rows))
    out.append("")

    # Ratio
    out.append("## ImpactRatio |P_f(c)| / |V|")
    out.append("")
    rows = [[f] + [cell(f, c, "impact_ratio") for c in classes] for f in frameworks]
    out.append(_table(["Framework", *classes], rows))
    out.append("")

    # Precision / Recall
    out.append("## Précision / Rappel vs oracle figé")
    out.append("")
    rows = []
    for f in frameworks:
        for c in classes:
            for r in records:
                if r.framework == f and r.change_class == c:
                    rows.append([
                        f, c,
                        f"{r.precision:.2f}", f"{r.recall:.2f}", f"{r.f1:.2f}",
                        str(len(r.false_positive)), str(len(r.false_negative)),
                    ])
    out.append(_table(
        ["Framework", "Classe", "Precision", "Recall", "F1", "FP", "FN"], rows
    ))
    out.append("")

    # Réduction d'inspection
    out.append("## Réduction du coût d'inspection (variante stricte)")
    out.append("")
    rows = []
    for f in frameworks:
        for c in classes:
            for r in records:
                if r.framework == f and r.change_class == c:
                    red = (
                        f"{r.inspection_reduction:.3f}"
                        if r.inspection_reduction is not None
                        else "—"
                    )
                    rows.append([
                        f, c,
                        str(r.manual_inspections or "—"),
                        str(r.assisted_inspections or "—"),
                        red,
                    ])
    out.append(_table(
        ["Framework", "Classe", "Manual", "Assisted", "Reduction"], rows
    ))
    out.append("")

    # Déterminisme / itérations / temps
    out.append("## Reproductibilité")
    out.append("")
    rows = []
    for f in frameworks:
        for c in classes:
            for r in records:
                if r.framework == f and r.change_class == c:
                    rows.append([
                        f, c,
                        str(r.fixed_point_iterations),
                        f"{r.elapsed_ms:.2f}",
                        "oui" if r.deterministic else "NON",
                    ])
    out.append(_table(
        ["Framework", "Classe", "K itérations", "ms", "Déterministe"], rows
    ))
    out.append("")

    # Signal dérivé baseline
    out.append("## Reassessment de baseline (signal dérivé, hors P_f(c))")
    out.append("")
    out.append(
        "La baseline released est immuable : un changement d'un required_item "
        "déclenche un reassessment opérationnel externe (§6.5), calculé à partir "
        "de P_f(c). La baseline n'apparaît pas dans l'ensemble affecté."
    )
    out.append("")
    rows = []
    for f in frameworks:
        for c in classes:
            for r in records:
                if r.framework == f and r.change_class == c:
                    rows.append([
                        f, c,
                        "requis" if r.baseline_reassessment_required else "non",
                        ", ".join(r.baseline_triggering_items) or "—",
                    ])
    out.append(_table(
        ["Framework", "Classe", "Reassessment", "Déclencheurs"], rows
    ))
    out.append("")

    return "\n".join(out)


def generate(
    *,
    oracle_dir: str,
    inspection_dir: str,
    manifest_path: str,
    out_dir: str,
    repetitions: int = 5,
) -> tuple[Path, Path]:
    records = run_matrix(
        oracle_dir=oracle_dir,
        inspection_dir=inspection_dir,
        manifest_path=manifest_path,
        repetitions=repetitions,
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    json_path = out / f"impact_experiment_{stamp}.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in records], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_path = out / f"impact_experiment_{stamp}.md"
    md_path.write_text(render_markdown(records), encoding="utf-8")

    # Copie latest
    (out / "impact_experiment_latest.md").write_text(
        md_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return md_path, json_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle-dir", default="scenarios/impact_experiment/oracle")
    ap.add_argument("--inspection-dir", default="scenarios/impact_experiment/inspection")
    ap.add_argument("--manifest", default="scenarios/impact_experiment/oracle_manifest.json")
    ap.add_argument("--out-dir", default="docs")
    ap.add_argument("--repetitions", type=int, default=5)
    args = ap.parse_args()

    md, js = generate(
        oracle_dir=args.oracle_dir,
        inspection_dir=args.inspection_dir,
        manifest_path=args.manifest,
        out_dir=args.out_dir,
        repetitions=args.repetitions,
    )
    print(f"Rapport écrit : {md}")
    print(f"Données JSON  : {js}")


if __name__ == "__main__":
    main()
