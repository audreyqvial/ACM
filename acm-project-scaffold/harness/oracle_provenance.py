# Emplacement : harness/oracle_provenance.py
"""Chaîne de preuve de l'oracle : digest, manifest, provenance de run.

Objectif anti-circularité (renforcé)
------------------------------------
`established_before_run: true` est auto-déclaré et donc insuffisant pour la
version finale. La chaîne de preuve ancre l'oracle par un digest et enregistre,
dans chaque run, de quoi vérifier intégrité, appariement et antériorité :

    oracle file → SHA-256 (canonique) → manifest → le run enregistre le digest

Trois garanties, par ordre de force :
  1. Intégrité + appariement (FORTE, mécanique) : le run recalcule le digest de
     l'oracle chargé et le compare au manifest. Divergence => run invalide
     (anti-silence). Prouve que l'oracle utilisé est bien celui figé, non altéré.
  2. Antériorité par git (FORTE, non-falsifiable) : `oracle_git_commit` — le SHA
     du commit ayant introduit l'oracle. L'historique git est indépendant du run.
  3. Antériorité par timestamp (DOCUMENTAIRE, auto-déclarée) : `oracle_created_at`
     / `experiment_started_at`. Utiles mais falsifiables ; ne jamais les
     présenter comme preuve d'antériorité à eux seuls.

Deux digests sont fournis :
  - `content_digest` : CANONIQUE, calculé sur l'oracle re-sérialisé via son
    modèle pydantic (clés triées, commentaires et mise en forme ignorés). Suit
    le SENS de l'oracle, pas sa mise en page. C'est le digest primaire.
  - `file_digest` : SHA-256 des octets bruts du fichier. Trivialement
    reproductible par un reviewer avec `sha256sum`. Vérifiabilité externe.

Ce module vit dans `harness/`. Le cœur `acm/` ne l'importe jamais.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .impact_oracle import ImpactOracle, OracleValidationError, load_oracle


# --------------------------------------------------------------------------
# Digests
# --------------------------------------------------------------------------
def _canonical_payload(oracle: ImpactOracle) -> str:
    """Sérialisation canonique et déterministe d'un oracle (pour le digest).

    On dumpe le modèle pydantic en dict, puis en JSON avec clés triées et
    séparateurs fixes. Deux oracles de même SENS produisent la même chaîne,
    quelle que soit la mise en forme YAML d'origine (ordre des clés,
    commentaires, espaces). L'ordre de `affected` EST significatif et préservé
    tel quel — si l'on voulait l'ignorer, il faudrait trier ; on choisit de le
    conserver car un oracle est un artefact ordonné et révisé à la main.
    """
    data = oracle.model_dump(mode="json")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_digest(oracle: ImpactOracle) -> str:
    """Digest canonique SHA-256 (suit le sens de l'oracle)."""
    payload = _canonical_payload(oracle).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def file_digest(path: str | Path) -> str:
    """Digest SHA-256 des octets bruts du fichier (vérifiable via sha256sum)."""
    raw = Path(path).read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _git_commit_for(path: str | Path) -> Optional[str]:
    """SHA du dernier commit ayant touché `path`, ou None si hors git / erreur.

    Antériorité forte : l'historique git du fichier oracle est indépendant du
    run. Best-effort — ne lève jamais (un dépôt absent n'est pas une erreur).
    """
    p = Path(path)
    try:
        out = subprocess.run(
            ["git", "log", "-n", "1", "--format=%H", "--", p.name],
            cwd=p.parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = out.stdout.strip()
        return sha or None
    except (subprocess.SubprocessError, OSError):  # pragma: no cover
        return None


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------
class OracleManifestEntry(BaseModel):
    """Une entrée du manifest : identité + digests + antériorité d'un oracle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    oracle_key: str  # framework::change_id
    relative_path: str
    content_digest: str
    file_digest: str
    created_at: Optional[str] = None
    git_commit: Optional[str] = None


class OracleManifest(BaseModel):
    """Manifest figé de tous les oracles d'une expérience.

    Généré une fois, versionné (git), checké à la main. Sert de source de
    vérité contre laquelle chaque run vérifie l'oracle qu'il charge.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1"
    generated_at: Optional[str] = None
    entries: Dict[str, OracleManifestEntry] = Field(default_factory=dict)

    def digest_for(self, oracle_key: str) -> Optional[str]:
        e = self.entries.get(oracle_key)
        return e.content_digest if e else None


def build_manifest(oracle_dir: str | Path) -> OracleManifest:
    """Construit un manifest en scannant un répertoire d'oracles figés.

    Recalcule les deux digests et capture le commit git de chaque fichier.
    Le `created_at` d'un oracle provient de son champ (auto-déclaré) s'il
    existe ; l'antériorité forte reste le `git_commit`.
    """
    d = Path(oracle_dir)
    if not d.is_dir():
        raise OracleValidationError(f"Répertoire d'oracles introuvable: {d}")

    entries: Dict[str, OracleManifestEntry] = {}
    for path in sorted([*d.glob("*.yaml"), *d.glob("*.yml")]):
        oracle = load_oracle(path)
        key = oracle.oracle_key()
        if key in entries:
            raise OracleValidationError(f"Clé d'oracle dupliquée: {key} ({path})")
        entries[key] = OracleManifestEntry(
            oracle_key=key,
            relative_path=path.name,
            content_digest=content_digest(oracle),
            file_digest=file_digest(path),
            created_at=None,  # renseigné via un champ dédié si ajouté au schéma
            git_commit=_git_commit_for(path),
        )
    return OracleManifest(
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
    )


def save_manifest(manifest: OracleManifest, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> OracleManifest:
    p = Path(path)
    if not p.exists():
        raise OracleValidationError(f"Manifest introuvable: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return OracleManifest.model_validate(data)


# --------------------------------------------------------------------------
# Provenance enregistrée par un run
# --------------------------------------------------------------------------
class OracleProvenance(BaseModel):
    """Bloc de provenance que CHAQUE run d'expérience enregistre pour un oracle.

    `digest_verified` est le cœur de la garantie mécanique : le run recalcule le
    digest canonique de l'oracle chargé et le compare au manifest. Si faux, le
    run DOIT être marqué invalide (le rapport ne publie pas de métriques d'un
    oracle non vérifié).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    oracle_key: str
    oracle_content_sha256: str
    oracle_file_sha256: str
    manifest_content_sha256: Optional[str] = None
    digest_verified: bool
    oracle_git_commit: Optional[str] = None
    oracle_created_at: Optional[str] = None
    experiment_started_at: str

    def problems(self) -> List[str]:
        """Anomalies de provenance (non-silence)."""
        out: List[str] = []
        if not self.digest_verified:
            out.append(
                f"digest_verified=false pour {self.oracle_key} : l'oracle chargé "
                "ne correspond pas au manifest (intégrité/appariement rompus)."
            )
        if self.oracle_git_commit is None:
            out.append(
                f"{self.oracle_key} : pas de commit git — antériorité forte non "
                "attestée (seuls les timestamps documentaires sont disponibles)."
            )
        return out


def make_provenance(
    oracle_path: str | Path,
    manifest: Optional[OracleManifest],
    *,
    experiment_started_at: Optional[str] = None,
) -> tuple[ImpactOracle, OracleProvenance]:
    """Charge un oracle et construit sa provenance vérifiée contre le manifest.

    Retourne (oracle, provenance). Si un manifest est fourni, `digest_verified`
    reflète la correspondance du digest canonique. Sans manifest, la
    vérification n'a pas lieu (`digest_verified=False`, `manifest_*=None`) et
    `problems()` le signalera.
    """
    oracle = load_oracle(oracle_path)
    key = oracle.oracle_key()
    c_digest = content_digest(oracle)
    f_digest = file_digest(oracle_path)

    manifest_digest = manifest.digest_for(key) if manifest else None
    verified = manifest_digest is not None and manifest_digest == c_digest

    prov = OracleProvenance(
        oracle_key=key,
        oracle_content_sha256=c_digest,
        oracle_file_sha256=f_digest,
        manifest_content_sha256=manifest_digest,
        digest_verified=verified,
        oracle_git_commit=_git_commit_for(oracle_path),
        oracle_created_at=None,
        experiment_started_at=experiment_started_at
        or datetime.now(timezone.utc).isoformat(),
    )
    return oracle, prov
