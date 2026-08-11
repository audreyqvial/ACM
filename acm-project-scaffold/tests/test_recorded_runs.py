"""Test de comparaison automatisé des records réels (examples/records/).

Vérifie sur des RuntimeSignal enregistrés que LangGraph et CrewAI produisent :
  - le MÊME resolved_config_digest ;
  - les MÊMES digests de références individuelles (§3.5) ;
  - un contenu de gouvernance identique ;
  - des différences UNIQUEMENT sur les champs attendus (adapter_name,
    produced_at) ;
  - un verdict de gouvernance identique une fois réévalués par le cœur.

Transforme la vérification manuelle « les deux records coïncident » en garantie
permanente. Les records sont générés par examples/*_demo.py (réels avec gpt-5.4,
ou déterministes en mock) et déposés dans examples/records/.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from acm import evaluate_runtime_instance
from acm.runtime.signal import RuntimeSignal

RECORDS_DIR = Path(__file__).parent.parent / "examples" / "records"
LG_RECORD = RECORDS_DIR / "recorded_run_langgraph.json"
CW_RECORD = RECORDS_DIR / "recorded_run_crewai.json"

# Champs autorisés à différer entre deux adaptateurs (empreinte + horodatage).
ALLOWED_DIFF_FIELDS = {"adapter_name", "produced_at", "instance_id"}


def _load(path: Path) -> dict:
    if not path.exists():
        pytest.skip(f"Record absent : {path} (lancer examples/*_demo.py)")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _records_available() -> bool:
    return LG_RECORD.exists() and CW_RECORD.exists()


@pytest.mark.skipif(not _records_available(), reason="records non générés")
def test_resolved_config_digest_identical():
    lg = _load(LG_RECORD)
    cw = _load(CW_RECORD)
    assert lg["resolved_config_digest"] == cw["resolved_config_digest"]
    assert lg["resolved_config_digest"].startswith("sha256:")


@pytest.mark.skipif(not _records_available(), reason="records non générés")
def test_individual_ref_digests_filled_and_equal():
    """Les digests de références individuelles sont renseignés ET identiques."""
    lg = _load(LG_RECORD)
    cw = _load(CW_RECORD)

    for path in [
        ["definition_ref"],
        ["resolved_config", "prompt_ref"],
        ["resolved_config", "model_ref"],
        ["traceability", "factory_ref"],
        ["traceability", "template_ref"],
    ]:
        lg_ref = lg
        cw_ref = cw
        for k in path:
            lg_ref = lg_ref[k]
            cw_ref = cw_ref[k]
        assert lg_ref["digest"] is not None, f"digest manquant: {path}"
        assert lg_ref["digest"].startswith("sha256:"), f"digest non sha256: {path}"
        assert lg_ref["digest"] == cw_ref["digest"], f"digest différent: {path}"


@pytest.mark.skipif(not _records_available(), reason="records non générés")
def test_records_differ_only_on_expected_fields():
    """Toute différence entre les deux records est sur un champ autorisé."""
    lg = _load(LG_RECORD)
    cw = _load(CW_RECORD)

    diffs = _diff_keys(lg, cw)
    unexpected = [d for d in diffs if d.split(".")[0] not in ALLOWED_DIFF_FIELDS]
    assert unexpected == [], f"Différences inattendues : {unexpected}"


@pytest.mark.skipif(not _records_available(), reason="records non générés")
def test_governance_verdict_identical():
    """Réévalués par le cœur, les deux signaux donnent le même verdict."""
    lg_sig = RuntimeSignal.from_record(_load(LG_RECORD))
    cw_sig = RuntimeSignal.from_record(_load(CW_RECORD))

    v_lg = evaluate_runtime_instance(lg_sig).model_dump(exclude={"instance_id"})
    v_cw = evaluate_runtime_instance(cw_sig).model_dump(exclude={"instance_id"})
    assert v_lg == v_cw


def _diff_keys(a, b, prefix: str = "") -> list:
    """Liste des chemins de clés dont les valeurs diffèrent entre a et b."""
    diffs: list = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            p = f"{prefix}.{k}" if prefix else k
            if k not in a or k not in b:
                diffs.append(p)
            else:
                diffs += _diff_keys(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(prefix)
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs += _diff_keys(x, y, f"{prefix}[{i}]")
    else:
        if a != b:
            diffs.append(prefix)
    return diffs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
