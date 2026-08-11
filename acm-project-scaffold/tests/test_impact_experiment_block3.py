# Emplacement : tests/test_impact_experiment_block3.py
"""Tests du bloc 3 : chaîne de preuve, prédiction moteur, cohérence, inspection.

Le point cardinal testé ici : la prédiction P_f(c) provient du VRAI moteur
(`propagate`), et l'ensemble marqué par le moteur est INCLUS dans la portée
topologique `reach` (cohérence statique ↔ point fixe).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from acm.impact.comparison import compare
from acm.models.aci import (
    ConfigurationGraph,
    ACIRevision,
    DeclaredStatus,
    Evidence,
    Relation,
)
from acm.models.enums import (
    ACIType,
    EvidenceResult,
    ImpactState,
    LifecycleState,
    RelationType,
)
from acm.models.refs import ACIRef
from acm.policy import PropagationContext
from acm.propagation.engine import propagate

from harness.engine_prediction import affected_set_absolute, affected_set_delta
from harness.reach_consistency import check_consistency
from harness.impact_oracle import load_oracle, load_oracle_dir
from harness.inspection_record import load_inspection, load_inspection_dir
from harness.oracle_provenance import (
    OracleManifest,
    build_manifest,
    content_digest,
    file_digest,
    make_provenance,
)

EXP_DIR = Path(__file__).parent.parent / "scenarios" / "impact_experiment"
ORACLE_DIR = EXP_DIR / "oracle"
INSPECTION_DIR = EXP_DIR / "inspection"


# --------------------------------------------------------------------------
# Fixture native-équivalente minimale : modèle partagé + 3 agents + workflow,
# avec preuves snapshotant le modèle@r1 (mécanisme de staleness réel).
# --------------------------------------------------------------------------
def _build_shared_model_system(model_rev: str) -> tuple[ConfigurationGraph, list[Evidence]]:
    def rev(i, t, r="r1", life=LifecycleState.VALIDATED):
        return ACIRevision(
            ref=ACIRef(id=i, revision_id=r),
            aci_type=t,
            declared=DeclaredStatus(lifecycle_state=life),
        )

    def rel(rid, s, t, rt, tr="r1"):
        return Relation(
            relation_id=rid,
            source=ACIRef(id=s, revision_id="r1"),
            target=ACIRef(id=t, revision_id=tr),
            relation_type=rt,
        )

    revs = [
        rev("aci:model:shared-llm", ACIType.MODEL, model_rev),
        rev("aci:agent:researcher", ACIType.AGENT),
        rev("aci:agent:reviewer", ACIType.AGENT),
        rev("aci:agent:finalizer", ACIType.AGENT),
        rev("aci:workflow:main", ACIType.WORKFLOW),
    ]
    rels = [
        rel("r-res-model", "aci:agent:researcher", "aci:model:shared-llm",
            RelationType.USES_MODEL, tr=model_rev),
        rel("r-rev-model", "aci:agent:reviewer", "aci:model:shared-llm",
            RelationType.USES_MODEL, tr=model_rev),
        rel("r-fin-model", "aci:agent:finalizer", "aci:model:shared-llm",
            RelationType.USES_MODEL, tr=model_rev),
        rel("r-wf-res", "aci:workflow:main", "aci:agent:researcher", RelationType.CONTAINS),
        rel("r-wf-rev", "aci:workflow:main", "aci:agent:reviewer", RelationType.CONTAINS),
        rel("r-wf-fin", "aci:workflow:main", "aci:agent:finalizer", RelationType.CONTAINS),
    ]
    # Preuves : chaque agent a une preuve snapshotant le modèle@r1.
    def ev(agent):
        return Evidence(
            evidence_id=f"ev-{agent}",
            target=ACIRef(id=f"aci:agent:{agent}", revision_id="r1"),
            result=EvidenceResult.PASS,
            dependency_snapshot=[ACIRef(id="aci:model:shared-llm", revision_id="r1")],
        )

    evidence = [ev("researcher"), ev("reviewer"), ev("finalizer")]
    return ConfigurationGraph.build(revs, rels), evidence


# --------------------------------------------------------------------------
# Prédiction depuis le VRAI moteur
# --------------------------------------------------------------------------
def test_engine_delta_matches_oracle_global():
    ctx = PropagationContext()
    g1, e1 = _build_shared_model_system("r1")
    g2, e2 = _build_shared_model_system("r2")
    before = propagate(g1, e1, ctx)
    after = propagate(g2, e2, ctx)

    P = affected_set_delta(before, after, root_id="aci:model:shared-llm")
    # Les 3 agents deviennent stale (preuve snapshot cassée) ; le workflow
    # remonte impacted via §14.1.
    assert "aci:agent:researcher" in P
    assert "aci:agent:reviewer" in P
    assert "aci:agent:finalizer" in P
    assert "aci:workflow:main" in P
    assert "aci:model:shared-llm" not in P  # racine exclue


def test_engine_prediction_vs_frozen_oracle():
    ctx = PropagationContext()
    g1, e1 = _build_shared_model_system("r1")
    g2, e2 = _build_shared_model_system("r2")
    before, after = propagate(g1, e1, ctx), propagate(g2, e2, ctx)
    P = affected_set_delta(before, after, root_id="aci:model:shared-llm")

    # La fixture minimale du bloc 3 a 3 agents (sans 'direct') ; on compare à
    # l'ensemble attendu de CETTE fixture, pas à l'oracle 4-agents du bloc 4.
    M = {"aci:agent:researcher", "aci:agent:reviewer",
         "aci:agent:finalizer", "aci:workflow:main"}
    result = compare(P, M)
    assert result.exact_match, (
        f"FP={sorted(result.false_positive)} FN={sorted(result.false_negative)}"
    )


def test_absolute_mode_from_healthy_baseline():
    ctx = PropagationContext()
    g2, e2 = _build_shared_model_system("r2")
    after = propagate(g2, e2, ctx)
    P = affected_set_absolute(after, root_id="aci:model:shared-llm")
    assert P == {
        "aci:agent:researcher",
        "aci:agent:reviewer",
        "aci:agent:finalizer",
        "aci:workflow:main",
    }


# --------------------------------------------------------------------------
# Cohérence reach (statique) ⊆ moteur (point fixe)
# --------------------------------------------------------------------------
def test_engine_affected_subset_of_reach():
    ctx = PropagationContext()
    g1, e1 = _build_shared_model_system("r1")
    g2, e2 = _build_shared_model_system("r2")
    before, after = propagate(g1, e1, ctx), propagate(g2, e2, ctx)
    P = affected_set_delta(before, after, root_id="aci:model:shared-llm")

    cons = check_consistency(g2, "aci:model:shared-llm", P)
    assert cons.inclusion_holds, (
        f"moteur hors reach: {sorted(cons.engine_outside_reach)}"
    )
    assert not cons.engine_outside_reach


def test_reach_can_overapproximate():
    # Un graphe où un dépendant topologique n'a PAS de preuve snapshotant la
    # racine : reach l'inclut, le moteur ne l'active pas.
    def rev(i, t, r="r1"):
        return ACIRevision(ref=ACIRef(id=i, revision_id=r), aci_type=t,
                           declared=DeclaredStatus(lifecycle_state=LifecycleState.VALIDATED))

    revs = [
        rev("aci:model:m", ACIType.MODEL, "r2"),
        rev("aci:agent:a", ACIType.AGENT),  # PAS de preuve snapshot
    ]
    rels = [Relation(relation_id="r1",
                     source=ACIRef(id="aci:agent:a", revision_id="r1"),
                     target=ACIRef(id="aci:model:m", revision_id="r2"),
                     relation_type=RelationType.USES_MODEL)]
    g = ConfigurationGraph.build(revs, rels)
    after = propagate(g, [], PropagationContext())
    P = affected_set_absolute(after, root_id="aci:model:m")

    cons = check_consistency(g, "aci:model:m", P)
    # reach inclut agent:a ; le moteur ne l'a pas marqué (pas de déclencheur).
    assert "aci:agent:a" in cons.reachable
    assert cons.inclusion_holds  # inclusion tient (moteur ⊆ reach)
    assert "aci:agent:a" in cons.reach_not_activated


# --------------------------------------------------------------------------
# Chaîne de preuve : digests, manifest, provenance
# --------------------------------------------------------------------------
def test_content_digest_tracks_semantic_content(tmp_path):
    # Le digest canonique suit TOUT le contenu sémantique (rationales incluses),
    # pas seulement la mise en forme : un contenu réellement différent => digest
    # différent, quelle que soit la mise en page.
    o1 = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    d1 = content_digest(o1)

    reformatted = tmp_path / "ref.yaml"
    reformatted.write_text(
        'change_class: global\n'
        'framework: langgraph\n'
        'schema_version: "1"\n'
        'change_id: global-shared-model\n'
        'root_aci: "aci:model:shared-llm"\n'
        'root_revision_from: r1\n'
        'root_revision_to: r2\n'
        'established_by: "AB"\n'
        'established_before_run: true\n'
        'description: "Remplacement du modele partage r1 -> r2."\n'
        'affected:\n'
        '  - {aci: "aci:agent:researcher", rationale: "x"}\n'
        '  - {aci: "aci:agent:reviewer", rationale: "x"}\n'
        '  - {aci: "aci:agent:finalizer", rationale: "x"}\n'
        '  - {aci: "aci:workflow:main", rationale: "x"}\n',
        encoding="utf-8",
    )
    o2 = load_oracle(reformatted)
    # rationales/description diffèrent -> digest canonique différent.
    assert content_digest(o2) != d1


def test_content_digest_identical_for_same_meaning(tmp_path):
    src = (ORACLE_DIR / "oracle_langgraph_global.yaml").read_text(encoding="utf-8")
    # Copie identique mais commentaires retirés et clés réordonnées trivialement.
    copy = tmp_path / "copy.yaml"
    copy.write_text(src, encoding="utf-8")
    o1 = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    o2 = load_oracle(copy)
    assert content_digest(o1) == content_digest(o2)


def test_file_digest_changes_with_bytes(tmp_path):
    src = (ORACLE_DIR / "oracle_langgraph_global.yaml").read_text(encoding="utf-8")
    copy = tmp_path / "copy.yaml"
    copy.write_text(src + "\n# commentaire ajouté\n", encoding="utf-8")
    d_orig = file_digest(ORACLE_DIR / "oracle_langgraph_global.yaml")
    d_copy = file_digest(copy)
    assert d_orig != d_copy  # les octets diffèrent


def test_manifest_build_and_verify():
    manifest = build_manifest(ORACLE_DIR)
    assert "langgraph::global-shared-model" in manifest.entries
    oracle, prov = make_provenance(
        ORACLE_DIR / "oracle_langgraph_global.yaml", manifest
    )
    assert prov.digest_verified is True
    assert prov.oracle_content_sha256 == manifest.digest_for(oracle.oracle_key())


def test_provenance_detects_tampering(tmp_path):
    import yaml

    manifest = build_manifest(ORACLE_DIR)
    # Oracle altéré : injecter un ACI affecté supplémentaire, proprement dans
    # la structure YAML (via re-dump), de sorte que le digest canonique diffère.
    raw = yaml.safe_load(
        (ORACLE_DIR / "oracle_langgraph_global.yaml").read_text(encoding="utf-8")
    )
    raw["affected"].append(
        {"aci": "aci:agent:injected", "rationale": "injecté après coup"}
    )
    tampered = tmp_path / "oracle_langgraph_global.yaml"
    tampered.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    _, prov = make_provenance(tampered, manifest)
    assert prov.digest_verified is False
    assert any("digest_verified=false" in p for p in prov.problems())


def test_provenance_without_manifest_flags_problem():
    _, prov = make_provenance(ORACLE_DIR / "oracle_langgraph_global.yaml", None)
    assert prov.digest_verified is False
    assert any("manifest" in p.lower() or "antériorité" in p for p in prov.problems())


# --------------------------------------------------------------------------
# Inspection (répertoire séparé)
# --------------------------------------------------------------------------
def test_load_inspection_dir():
    recs = load_inspection_dir(INSPECTION_DIR)
    langgraph = {k for k in recs if k.startswith("langgraph::")}
    assert langgraph == {
        "langgraph::local-finalizer-prompt",
        "langgraph::intermediate-research-tool",
        "langgraph::global-shared-model",
    }


def test_inspection_pairs_with_oracle_by_key():
    oracles = load_oracle_dir(ORACLE_DIR)
    inspections = load_inspection_dir(INSPECTION_DIR)
    # Chaque oracle a un enregistrement d'inspection apparié.
    assert set(oracles) == set(inspections)


def test_inspection_feeds_reduction():
    from acm.impact import inspection_reduction

    rec = load_inspection(INSPECTION_DIR / "inspection_langgraph_global.yaml")
    r = inspection_reduction(rec.manual_inspections, rec.assisted_inspections)
    assert r.reduction == pytest.approx(1 - 5 / 13)
