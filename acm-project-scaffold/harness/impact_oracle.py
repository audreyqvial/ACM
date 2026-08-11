# Emplacement : harness/impact_oracle.py
"""Oracle d'impact figé — schéma, chargement, validation.

RÔLE ANTI-CIRCULARITÉ
---------------------
Un oracle d'impact est un artefact FIGÉ, VERSIONNÉ et RÉVISÉ À LA MAIN qui
énumère les ACI affectés par un changement racine donné, dans un framework
donné, tels qu'établis par une inspection INDÉPENDANTE du code natif — jamais
par le moteur ACM.

Contrainte structurelle (et non seulement conventionnelle) : ce module vit dans
`harness/`, PAS dans `acm/`. Le cœur normatif n'importe jamais l'oracle. La
comparaison P vs M se fait dans `acm/impact/comparison.py`, qui ne reçoit que
deux ensembles opaques et ne sait pas lequel vient du moteur, lequel de
l'humain. L'oracle ne peut donc pas « fuiter » dans le calcul.

L'oracle DOIT être établi avant l'exécution de la propagation ACM (ou au moins
conservé dans un fichier séparé dont le moteur ne dépend pas). Le champ
`rationale` de chaque élément affecté documente POURQUOI il est touché selon
l'inspection native — c'est ce qui rend l'oracle défendable en revue et
distingue « analyse indépendante » de « ré-exécution mentale des règles ACM ».

FORMAT (YAML, un fichier par (framework × change))
--------------------------------------------------
    schema_version: "1"
    framework: langgraph            # langgraph | crewai | openai-agents
    change_id: global-shared-model  # identifiant libre stable
    change_class: global            # local | intermediate | global
    root_aci: "aci:model:shared-llm"
    root_revision_from: r1          # révision avant
    root_revision_to: r2            # révision après (la perturbation)
    description: >
      Remplacement du modèle partagé r1 -> r2.
    affected:                       # M_f(c) : ids logiques attendus
      - aci: "aci:agent:researcher"
        rationale: "uses_model shared-llm ; réécriture requise."
      - aci: "aci:agent:reviewer"
        rationale: "uses_model shared-llm."
    # Optionnel : coûts d'inspection du protocole humain (variante stricte).
    manual_inspections: 13
    assisted_inspections: 3
    established_by: "AB"            # traçabilité de l'établissement humain
    established_before_run: true    # atteste l'antériorité sur la propagation

Le schéma est validé par pydantic (dépendance déjà présente dans le cœur),
sans introduire de validateur ad hoc.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valeurs autorisées, gardées volontairement locales au harness (pas de
# dépendance vers un enum du cœur : l'oracle est un artefact externe).
_FRAMEWORKS = {"langgraph", "crewai", "openai-agents"}
_CHANGE_CLASSES = {"local", "intermediate", "global"}
_SCHEMA_VERSION = "1"


class AffectedItem(BaseModel):
    """Un ACI affecté selon l'inspection native indépendante."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    aci: str = Field(..., description="id logique, ex. aci:agent:researcher")
    rationale: str = Field(
        ...,
        min_length=1,
        description="Pourquoi cet ACI est affecté, selon le code natif "
        "(justification humaine, pas dérivée du moteur).",
    )

    @field_validator("aci")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("aci ne peut être vide")
        return v


class ImpactOracle(BaseModel):
    """Oracle figé M_f(c) pour un couple (framework, change).

    Immuable une fois chargé (frozen). `extra=forbid` : tout champ inconnu dans
    le YAML est une erreur — un oracle mal formé ne doit pas passer silencieusement
    (anti-silence).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default=_SCHEMA_VERSION)
    framework: str
    change_id: str = Field(..., min_length=1)
    change_class: str
    root_aci: str = Field(..., min_length=1)
    root_revision_from: Optional[str] = None
    root_revision_to: Optional[str] = None
    description: Optional[str] = None
    affected: List[AffectedItem] = Field(default_factory=list)

    # Coûts d'inspection (protocole humain, variante stricte). Optionnels :
    # un oracle peut ne documenter que l'ensemble affecté et laisser les coûts
    # au protocole. Si présents, ils alimentent inspection_reduction.
    manual_inspections: Optional[int] = Field(default=None, ge=0)
    assisted_inspections: Optional[int] = Field(default=None, ge=0)

    # Traçabilité de l'établissement humain (anti-circularité).
    established_by: Optional[str] = None
    established_before_run: Optional[bool] = None

    @field_validator("schema_version")
    @classmethod
    def _known_schema(cls, v: str) -> str:
        if v != _SCHEMA_VERSION:
            raise ValueError(
                f"schema_version inconnue: {v!r} (attendu {_SCHEMA_VERSION!r})"
            )
        return v

    @field_validator("framework")
    @classmethod
    def _known_framework(cls, v: str) -> str:
        if v not in _FRAMEWORKS:
            raise ValueError(
                f"framework inconnu: {v!r} (attendus: {sorted(_FRAMEWORKS)})"
            )
        return v

    @field_validator("change_class")
    @classmethod
    def _known_change_class(cls, v: str) -> str:
        if v not in _CHANGE_CLASSES:
            raise ValueError(
                f"change_class inconnue: {v!r} (attendues: {sorted(_CHANGE_CLASSES)})"
            )
        return v

    @field_validator("affected")
    @classmethod
    def _no_duplicate_affected(cls, v: List[AffectedItem]) -> List[AffectedItem]:
        seen = set()
        for item in v:
            if item.aci in seen:
                raise ValueError(f"ACI affecté dupliqué dans l'oracle: {item.aci}")
            seen.add(item.aci)
        return v

    # ----------------------------------------------------------------------
    # Accès dérivés
    # ----------------------------------------------------------------------
    def affected_ids(self) -> set[str]:
        """M_f(c) sous forme d'ensemble d'ids logiques — l'entrée de `compare`.

        NB : la racine n'est PAS incluse (cohérent avec `reach`, qui exclut la
        racine). Si un oracle liste par erreur la racine dans `affected`, on la
        retire ici et on le signale via `self_consistency_problems()`.
        """
        return {a.aci for a in self.affected} - {self.root_aci}

    def self_consistency_problems(self) -> List[str]:
        """Vérifications de cohérence interne (au-delà du schéma).

        - la racine ne devrait pas figurer dans `affected` (on mesure ce qui
          est ATTEINT, racine exclue) ;
        - si les deux coûts d'inspection sont donnés, assisted <= manual ;
        - `established_before_run` devrait être vrai (antériorité), sinon
          l'antériorité de l'oracle n'est pas attestée — avertissement, pas
          erreur bloquante.
        """
        problems: List[str] = []
        if any(a.aci == self.root_aci for a in self.affected):
            problems.append(
                f"La racine {self.root_aci} figure dans 'affected' "
                "(elle devrait en être exclue)."
            )
        if (
            self.manual_inspections is not None
            and self.assisted_inspections is not None
            and self.assisted_inspections > self.manual_inspections
        ):
            problems.append(
                f"assisted_inspections ({self.assisted_inspections}) > "
                f"manual_inspections ({self.manual_inspections})."
            )
        if self.established_before_run is False:
            problems.append(
                "established_before_run=false : l'antériorité de l'oracle sur "
                "la propagation n'est pas attestée (risque de circularité)."
            )
        return problems

    def oracle_key(self) -> str:
        """Clé stable (framework, change_id) pour indexer/apparier au runner."""
        return f"{self.framework}::{self.change_id}"


class OracleValidationError(ValueError):
    """Erreur de chargement/validation d'un oracle figé."""


def load_oracle(path: str | Path) -> ImpactOracle:
    """Charge et valide un oracle YAML figé.

    Lève `OracleValidationError` en cas de YAML invalide, de champ inconnu, de
    valeur hors domaine, ou d'incohérence de schéma. Les incohérences internes
    NON bloquantes (self_consistency_problems) ne lèvent pas ici : l'appelant
    (loader de répertoire, tests) décide de leur criticité.
    """
    import yaml  # import local : pyyaml est une dépendance d'expérience, pas du cœur

    p = Path(path)
    if not p.exists():
        raise OracleValidationError(f"Oracle introuvable: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - dépend du contenu
        raise OracleValidationError(f"YAML invalide ({p}): {exc}") from exc

    if not isinstance(raw, dict):
        raise OracleValidationError(
            f"Oracle {p}: racine YAML attendue = mapping, obtenu {type(raw).__name__}"
        )
    try:
        return ImpactOracle.model_validate(raw)
    except Exception as exc:
        raise OracleValidationError(f"Oracle invalide ({p}): {exc}") from exc


def load_oracle_dir(
    directory: str | Path, *, strict_consistency: bool = True
) -> dict[str, ImpactOracle]:
    """Charge tous les oracles *.yaml/*.yml d'un répertoire, indexés par clé.

    Détecte les clés (framework, change_id) dupliquées entre fichiers. Si
    `strict_consistency`, lève dès qu'un oracle présente des problèmes de
    cohérence interne (racine dans affected, coûts incohérents, antériorité non
    attestée) ; sinon ces problèmes sont ignorés au chargement (à l'appelant
    de les inspecter).
    """
    d = Path(directory)
    if not d.is_dir():
        raise OracleValidationError(f"Répertoire d'oracles introuvable: {d}")

    result: dict[str, ImpactOracle] = {}
    for path in sorted([*d.glob("*.yaml"), *d.glob("*.yml")]):
        oracle = load_oracle(path)
        if strict_consistency:
            problems = oracle.self_consistency_problems()
            if problems:
                raise OracleValidationError(
                    f"Oracle incohérent ({path}):\n- " + "\n- ".join(problems)
                )
        key = oracle.oracle_key()
        if key in result:
            raise OracleValidationError(
                f"Clé d'oracle dupliquée entre fichiers: {key} (dernier: {path})"
            )
        result[key] = oracle
    return result
