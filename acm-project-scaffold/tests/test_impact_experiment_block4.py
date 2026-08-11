# Emplacement : tests/test_impact_experiment_block4.py
"""Tests du bloc 4 : systèmes natifs-équivalents, runner matrice, baseline, rapport.

Vérifie que la matrice 3×3 s'exécute, que les métriques discriminent les classes
de perturbation, que le résultat vient du moteur, et que la baseline reçoit un
reassessment (signal dérivé) sans figurer dans P_f(c).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from acm.policy import PropagationContext
from acm.propagation.engine import propagate
from acm.state_machines.baselines import BaselineState, OperationalStatus

from harness.baseline_reassessment import evaluate_baseline_reassessment
from harness.engine_prediction import affected_set_delta
from harness.impact_experiment_runner import run_case, run_matrix
from harness.impact_oracle import load_oracle_dir
from harness.inspection_record import load_inspection_dir
from harness.oracle_provenance import build_manifest

from scenarios.impact_experiment.native_equivalent import (
    AGENTS,
    BUILDERS,
    MODEL,
    PERTURBATIONS,
    WORKFLOW,
    apply_perturbation,
    build_impact_langgraph,
)

EXP = Path(__file__).parent.parent / "scenarios" / "impact_experiment"
ORACLE_DIR = EXP / "oracle"
INSPECTION_DIR = EXP / "inspection"


# --------------------------------------------------------------------------
# Fixtures natives-équivalentes : même périmètre gouvernable
# --------------------------------------------------------------------------
def test_three_builders_same_perimeter():
    graphs = {name: b()[0] for name, b in BUILDERS.items()}
    # Même nombre de révisions et mêmes ids logiques dans les trois.
    id_sets = {
        name: {r.ref.id for r in g.revisions.values()} for name, g in graphs.items()
    }
    sets = list(id_sets.values())
    assert sets[0] == sets[1] == sets[2], "périmètre gouvernable divergent"


def test_perimeter_inventory():
    g, ev, baseline = build_impact_langgraph()
    ids = {r.ref.id for r in g.revisions.values()}
    # 4 agents + 4 prompts + 1 model + 1 tool + 1 workflow = 11
    assert len(ids) == 11
    assert MODEL in ids and WORKFLOW in ids
    assert baseline.state == BaselineState.RELEASED


def test_graph_integrity():
    g, _, _ = build_impact_langgraph()
    problems = g.validate_integrity()
    assert problems == [], f"graphe invalide: {problems}"


# --------------------------------------------------------------------------
# Le moteur produit P_f(c) ; les classes discriminent
# --------------------------------------------------------------------------
def _engine_P(framework, change_id):
    ctx = PropagationContext()
    before, after, root = apply_perturbation(framework, change_id)
    gb, eb, _ = before
    ga, ea, _ = after
    return affected_set_delta(propagate(gb, eb, ctx), propagate(ga, ea, ctx), root_id=root), root


def test_local_perturbation():
    P, root = _engine_P("langgraph", "local-finalizer-prompt")
    assert P == {AGENTS["finalizer"], WORKFLOW}
    assert root not in P


def test_intermediate_perturbation():
    P, root = _engine_P("langgraph", "intermediate-research-tool")
    assert P == {AGENTS["researcher"], WORKFLOW}


def test_global_perturbation():
    P, root = _engine_P("langgraph", "global-shared-model")
    assert P == {
        AGENTS["researcher"], AGENTS["reviewer"],
        AGENTS["finalizer"], AGENTS["direct"], WORKFLOW,
    }


def test_classes_discriminate_by_size():
    local, _ = _engine_P("langgraph", "local-finalizer-prompt")
    inter, _ = _engine_P("langgraph", "intermediate-research-tool")
    glob, _ = _engine_P("langgraph", "global-shared-model")
    assert len(local) == len(inter) == 2 < len(glob) == 5


def test_local_intermediate_differ_by_content():
    # Même taille mais ensembles différents : les métriques de contenu séparent.
    local, _ = _engine_P("langgraph", "local-finalizer-prompt")
    inter, _ = _engine_P("langgraph", "intermediate-research-tool")
    assert local != inter


def test_frameworks_produce_same_sets():
    # Périmètre contrôlé => mêmes P_f(c) entre frameworks (H2 par construction).
    for change_id in PERTURBATIONS:
        sets = {f: _engine_P(f, change_id)[0] for f in BUILDERS}
        vals = list(sets.values())
        assert vals[0] == vals[1] == vals[2], f"divergence sur {change_id}: {sets}"


# --------------------------------------------------------------------------
# Baseline reassessment : signal dérivé, hors P_f(c)
# --------------------------------------------------------------------------
def test_baseline_not_in_predicted():
    P, _ = _engine_P("langgraph", "global-shared-model")
    assert not any("baseline" in x for x in P)


def test_baseline_reassessment_triggered_on_global():
    _, _, baseline = build_impact_langgraph()
    P, root = _engine_P("langgraph", "global-shared-model")
    reass = evaluate_baseline_reassessment(baseline, P, root_id=root)
    assert reass.reassessment_required
    assert reass.operational_status == OperationalStatus.REASSESSMENT_REQUIRED
    # Le modèle partagé (racine, required_item) déclenche.
    assert MODEL in reass.triggering_items


def test_baseline_immutable_not_mutated():
    _, _, baseline = build_impact_langgraph()
    P, root = _engine_P("langgraph", "global-shared-model")
    evaluate_baseline_reassessment(baseline, P, root_id=root)
    # L'évaluation NE mute PAS la baseline d'origine (immuabilité §6.5).
    assert baseline.operational_status == OperationalStatus.NONE
    assert baseline.state == BaselineState.RELEASED


# --------------------------------------------------------------------------
# Runner : cas unique et matrice complète
# --------------------------------------------------------------------------
def test_run_case_exact_match():
    oracles = load_oracle_dir(ORACLE_DIR)
    inspections = load_inspection_dir(INSPECTION_DIR)
    manifest = build_manifest(ORACLE_DIR)
    rec = run_case(
        "langgraph", "global-shared-model",
        oracles=oracles, inspections=inspections,
        manifest=manifest, oracle_dir=ORACLE_DIR, repetitions=3,
    )
    assert rec.precision == 1.0 and rec.recall == 1.0
    assert rec.false_positive == [] and rec.false_negative == []
    assert rec.digest_verified is True
    assert rec.deterministic is True
    assert rec.reach_inclusion_holds is True
    assert rec.baseline_reassessment_required is True


def test_run_matrix_full():
    manifest = build_manifest(ORACLE_DIR)
    import json, tempfile
    with tempfile.TemporaryDirectory() as td:
        mpath = Path(td) / "manifest.json"
        mpath.write_text(
            json.dumps(manifest.model_dump(mode="json")), encoding="utf-8"
        )
        records = run_matrix(
            oracle_dir=ORACLE_DIR,
            inspection_dir=INSPECTION_DIR,
            manifest_path=mpath,
            repetitions=3,
        )
    assert len(records) == 9  # 3 frameworks × 3 changements
    assert all(r.digest_verified for r in records)
    assert all(r.deterministic for r in records)
    assert all(r.precision == 1.0 and r.recall == 1.0 for r in records)
    assert all(r.reach_inclusion_holds for r in records)


def test_matrix_ratio_invariant_across_frameworks():
    manifest = build_manifest(ORACLE_DIR)
    import json, tempfile
    with tempfile.TemporaryDirectory() as td:
        mpath = Path(td) / "m.json"
        mpath.write_text(json.dumps(manifest.model_dump(mode="json")), encoding="utf-8")
        records = run_matrix(
            oracle_dir=ORACLE_DIR, inspection_dir=INSPECTION_DIR,
            manifest_path=mpath, repetitions=1,
        )
    # H2 : pour une même classe, le ratio est identique entre frameworks.
    by_class: dict[str, set[float]] = {}
    for r in records:
        by_class.setdefault(r.change_class, set()).add(r.impact_ratio)
    for cls, ratios in by_class.items():
        assert len(ratios) == 1, f"ratio non invariant pour {cls}: {ratios}"


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------
def test_report_generation(tmp_path):
    from generate_impact_experiment_report import generate

    manifest = build_manifest(ORACLE_DIR)
    import json
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps(manifest.model_dump(mode="json")), encoding="utf-8")

    md, js = generate(
        oracle_dir=str(ORACLE_DIR),
        inspection_dir=str(INSPECTION_DIR),
        manifest_path=str(mpath),
        out_dir=str(tmp_path / "out"),
        repetitions=2,
    )
    assert md.exists() and js.exists()
    content = md.read_text(encoding="utf-8")
    assert "ImpactSize" in content and "Precision" in content
    data = json.loads(js.read_text(encoding="utf-8"))
    assert len(data) == 9
