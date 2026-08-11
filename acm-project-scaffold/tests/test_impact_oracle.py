# Emplacement : tests/test_impact_oracle.py
"""Tests du schéma d'oracle figé, du loader, et de l'intégration avec compare().

Couvre : chargement valide, rejet des oracles mal formés (champ inconnu, valeur
hors domaine, doublons), cohérence interne, et le pont oracle -> compare() du
bloc 1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from acm.impact import compare
from harness.impact_oracle import (
    ImpactOracle,
    OracleValidationError,
    load_oracle,
    load_oracle_dir,
)

ORACLE_DIR = Path(__file__).parent.parent / "scenarios" / "impact_experiment" / "oracle"


# --------------------------------------------------------------------------
# Chargement des oracles figés fournis
# --------------------------------------------------------------------------
def test_load_all_shipped_oracles():
    oracles = load_oracle_dir(ORACLE_DIR)
    langgraph_keys = {k for k in oracles if k.startswith("langgraph::")}
    assert langgraph_keys == {
        "langgraph::local-finalizer-prompt",
        "langgraph::intermediate-research-tool",
        "langgraph::global-shared-model",
    }
    # 3 frameworks x 3 changements = 9
    assert len(oracles) == 9


def test_global_oracle_affected_ids():
    o = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    assert o.affected_ids() == {
        "aci:agent:researcher",
        "aci:agent:reviewer",
        "aci:agent:finalizer",
        "aci:agent:direct",
        "aci:workflow:main",
    }


def test_root_excluded_from_affected_ids():
    o = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    assert o.root_aci not in o.affected_ids()


def test_change_class_monotone_sizes():
    # local < intermediate < global en taille d'ensemble affecté (par construction).
    oracles = load_oracle_dir(ORACLE_DIR)
    local = oracles["langgraph::local-finalizer-prompt"].affected_ids()
    inter = oracles["langgraph::intermediate-research-tool"].affected_ids()
    glob = oracles["langgraph::global-shared-model"].affected_ids()
    # local et intermediate ont la même taille mais DIFFÈRENT par le contenu ;
    # global est strictement plus grand. Les métriques discriminent par contenu.
    assert local != inter
    assert len(local) == len(inter) < len(glob)


# --------------------------------------------------------------------------
# Pont oracle -> compare() (bloc 1)
# --------------------------------------------------------------------------
def test_oracle_feeds_compare_exact_match():
    o = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    M = o.affected_ids()
    # Simulé : ACM prédit exactement M.
    P = set(M)
    r = compare(P, M)
    assert r.exact_match and r.precision == 1.0 and r.recall == 1.0


def test_oracle_feeds_compare_with_divergence():
    o = load_oracle(ORACLE_DIR / "oracle_langgraph_global.yaml")
    M = o.affected_ids()
    # Simulé : ACM manque le workflow (FN) et invente un extra (FP).
    P = (M - {"aci:workflow:main"}) | {"aci:agent:phantom"}
    r = compare(P, M)
    assert "aci:workflow:main" in r.false_negative
    assert "aci:agent:phantom" in r.false_positive
    assert r.recall < 1.0 and r.precision < 1.0


# --------------------------------------------------------------------------
# Rejet des oracles mal formés
# --------------------------------------------------------------------------
def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "oracle.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_reject_unknown_field(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "1"
framework: langgraph
change_id: x
change_class: local
root_aci: "aci:model:m"
affected: []
bogus_field: 123
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_unknown_framework(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "1"
framework: autogen
change_id: x
change_class: local
root_aci: "aci:model:m"
affected: []
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_unknown_change_class(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "1"
framework: langgraph
change_id: x
change_class: catastrophic
root_aci: "aci:model:m"
affected: []
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_unknown_schema_version(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "99"
framework: langgraph
change_id: x
change_class: local
root_aci: "aci:model:m"
affected: []
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_affected_without_rationale(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "1"
framework: langgraph
change_id: x
change_class: local
root_aci: "aci:model:m"
affected:
  - aci: "aci:agent:a"
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_duplicate_affected(tmp_path):
    p = _write(
        tmp_path,
        """
schema_version: "1"
framework: langgraph
change_id: x
change_class: local
root_aci: "aci:model:m"
affected:
  - aci: "aci:agent:a"
    rationale: "r1"
  - aci: "aci:agent:a"
    rationale: "r2"
""",
    )
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_reject_non_mapping_root(tmp_path):
    p = _write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(OracleValidationError):
        load_oracle(p)


def test_missing_file_raises():
    with pytest.raises(OracleValidationError):
        load_oracle("/does/not/exist.yaml")


# --------------------------------------------------------------------------
# Cohérence interne (self_consistency_problems)
# --------------------------------------------------------------------------
def test_consistency_flags_root_in_affected():
    o = ImpactOracle(
        framework="langgraph",
        change_id="x",
        change_class="local",
        root_aci="aci:model:m",
        affected=[{"aci": "aci:model:m", "rationale": "racine à tort"}],
    )
    problems = o.self_consistency_problems()
    assert any("racine" in p.lower() or "aci:model:m" in p for p in problems)



def test_consistency_flags_antecedence_not_attested():
    o = ImpactOracle(
        framework="langgraph",
        change_id="x",
        change_class="local",
        root_aci="aci:model:m",
        established_before_run=False,
    )
    assert any("antériorité" in p or "established_before_run" in p
               for p in o.self_consistency_problems())


def test_load_dir_strict_rejects_inconsistent(tmp_path):
    # Oracle syntaxiquement valide mais interne-incohérent (racine dans affected).
    (tmp_path / "bad.yaml").write_text(
        """
schema_version: "1"
framework: langgraph
change_id: bad
change_class: local
root_aci: "aci:model:m"
affected:
  - aci: "aci:model:m"
    rationale: "racine à tort"
""",
        encoding="utf-8",
    )
    with pytest.raises(OracleValidationError):
        load_oracle_dir(tmp_path, strict_consistency=True)


def test_load_dir_non_strict_allows_inconsistent(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        """
schema_version: "1"
framework: langgraph
change_id: bad
change_class: local
root_aci: "aci:model:m"
affected:
  - aci: "aci:model:m"
    rationale: "racine à tort"
""",
        encoding="utf-8",
    )
    oracles = load_oracle_dir(tmp_path, strict_consistency=False)
    assert "langgraph::bad" in oracles


def test_load_dir_rejects_duplicate_key(tmp_path):
    body = """
schema_version: "1"
framework: langgraph
change_id: dup
change_class: local
root_aci: "aci:model:m"
affected: []
"""
    (tmp_path / "a.yaml").write_text(body, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(body, encoding="utf-8")
    with pytest.raises(OracleValidationError):
        load_oracle_dir(tmp_path)
