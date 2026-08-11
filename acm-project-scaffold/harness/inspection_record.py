# Emplacement : harness/inspection_record.py
"""Coûts d'inspection figés — schéma, chargement, appariement à l'oracle.

Décision (validée) : les coûts d'inspection vivent dans un répertoire SÉPARÉ de
l'oracle (`inspection/` vs `oracle/`). L'oracle ne porte QUE l'ensemble affecté
M_f(c) ; le coût humain (variante stricte) est un artefact distinct, apparié à
l'oracle par la clé (framework, change_id).

Séparation utile : l'ensemble affecté est une donnée de correction (comparée à
la prédiction du moteur), tandis que le coût d'inspection est une donnée de
protocole opérationnel. Les mêlanger dans un seul fichier couplait deux
préoccupations de nature différente.

Comme pour l'oracle : ce module vit dans `harness/`, jamais importé par `acm/`.
Le calcul de réduction lui-même est dans `acm/impact/inspection.py` (pur) ;
ici on ne fait que charger/valider/apparier.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .impact_oracle import OracleValidationError

_FRAMEWORKS = {"langgraph", "crewai", "openai-agents"}
_SCHEMA_VERSION = "1"


class InspectionRecord(BaseModel):
    """Coûts d'inspection figés pour un couple (framework, change_id)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=_SCHEMA_VERSION)
    framework: str
    change_id: str = Field(..., min_length=1)
    manual_inspections: int = Field(..., ge=1)
    assisted_inspections: int = Field(..., ge=0)
    protocol_note: Optional[str] = None
    established_by: Optional[str] = None

    @model_validator(mode="after")
    def _check(self) -> "InspectionRecord":
        if self.schema_version != _SCHEMA_VERSION:
            raise ValueError(f"schema_version inconnue: {self.schema_version!r}")
        if self.framework not in _FRAMEWORKS:
            raise ValueError(f"framework inconnu: {self.framework!r}")
        # assisted > manual n'est pas interdit (réduction négative permise et
        # remontée telle quelle), mais on le note comme incohérence probable.
        return self

    def record_key(self) -> str:
        return f"{self.framework}::{self.change_id}"

    def consistency_problems(self) -> list[str]:
        out: list[str] = []
        if self.assisted_inspections > self.manual_inspections:
            out.append(
                f"assisted ({self.assisted_inspections}) > manual "
                f"({self.manual_inspections}) : réduction négative — à vérifier."
            )
        return out


def load_inspection(path: str | Path) -> InspectionRecord:
    import yaml

    p = Path(path)
    if not p.exists():
        raise OracleValidationError(f"Fichier d'inspection introuvable: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover
        raise OracleValidationError(f"YAML invalide ({p}): {exc}") from exc
    if not isinstance(raw, dict):
        raise OracleValidationError(f"Inspection {p}: racine YAML attendue = mapping")
    try:
        return InspectionRecord.model_validate(raw)
    except Exception as exc:
        raise OracleValidationError(f"Inspection invalide ({p}): {exc}") from exc


def load_inspection_dir(directory: str | Path) -> dict[str, InspectionRecord]:
    d = Path(directory)
    if not d.is_dir():
        raise OracleValidationError(f"Répertoire d'inspection introuvable: {d}")
    result: dict[str, InspectionRecord] = {}
    for path in sorted([*d.glob("*.yaml"), *d.glob("*.yml")]):
        rec = load_inspection(path)
        key = rec.record_key()
        if key in result:
            raise OracleValidationError(f"Clé d'inspection dupliquée: {key} ({path})")
        result[key] = rec
    return result
