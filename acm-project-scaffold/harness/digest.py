"""Sérialisation canonique et digests reproductibles (métrique §4, S25).

Ce module fournit la brique que le noyau n'avait pas encore : un digest dérivé
du CONTENU canonique (et non du seul couple id@revision_id). Il alimente
`configuration_digest` et `evidence_digest` du PropagationReport, exigés par la
section 4 du plan d'évaluation, et sert de fondation vérifiable pour S03/S16.

Principe : un seul `canonical_json()` — clés triées, séparateurs fixes, UTF-8,
pas d'espaces superflus — appliqué partout. Deux configurations identiques
produisent le même digest ; toute différence de contenu le change. L'invariance
à l'ordre des entrées (S25) découle du tri des clés et des collections.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from acm import ConfigurationGraph, Evidence


def canonical_json(obj: Any) -> str:
    """Représentation JSON canonique et déterministe d'une structure.

    - clés d'objets triées ;
    - séparateurs compacts et fixes ;
    - non-ASCII préservé en UTF-8 (ensure_ascii=False) pour stabilité ;
    - les nombres suivent la sérialisation JSON standard.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def sha256_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_content(rev) -> Dict[str, Any]:
    """Champs de CONTENU d'une révision entrant dans son digest matériel.

    On inclut l'identité logique, le type, les états déclarés (intrinsèques) et
    la politique d'assurance. On EXCLUT le digest lui-même (auto-référence) et
    les marqueurs de validation transitoires.
    """
    policy = rev.assurance_policy
    return {
        "id": rev.ref.id,
        "revision_id": rev.ref.revision_id,
        "aci_type": rev.aci_type.value,
        "lifecycle_state": rev.declared.lifecycle_state.value,
        "quality_state": rev.declared.quality_state.value,
        "assurance_state": rev.declared.assurance_state.value,
        "content_frozen": rev.content_frozen,
        "assurance_policy": None
        if policy is None
        else {
            "required_assurance_dimensions": sorted(
                policy.required_assurance_dimensions
            ),
            "composition_mode": policy.composition_mode.value,
            "allow_vacuous_assessment": policy.allow_vacuous_assessment,
        },
    }


def content_digest(rev) -> str:
    """Digest matériel d'une révision, dérivé de son contenu canonique.

    C'est le digest « de production » évoqué dans refs.py : un vrai hash du
    contenu, et non du couple id@revision_id. Permet à S03/S16 de comparer un
    digest DÉCLARÉ (dans la preuve ou la baseline) au digest RECALCULÉ.
    """
    return sha256_of(canonical_json(_revision_content(rev)))


def _relation_content(rel) -> Dict[str, Any]:
    return {
        "relation_id": rel.relation_id,
        "source": rel.source.id,
        "target": rel.target.id,
        "relation_type": rel.relation_type.value,
        "required": rel.required,
        "propagation_policy": rel.propagation_policy.value,
        "assurance_dependency": rel.assurance_dependency,
        "impact_dependency": rel.impact_dependency,
    }


def configuration_digest(graph: ConfigurationGraph) -> str:
    """Digest canonique d'un graphe de configuration entier (§4, S01/S25).

    Agrège les contenus de révisions et de relations, triés, de façon
    indépendante de l'ordre d'insertion. Deux graphes structurellement
    identiques produisent le même digest quelle que soit la permutation.
    """
    revisions = sorted(
        (_revision_content(r) for r in graph.revisions.values()),
        key=lambda d: (d["id"], d["revision_id"] or ""),
    )
    relations = sorted(
        (_relation_content(r) for r in graph.relations),
        key=lambda d: d["relation_id"],
    )
    payload = {"revisions": revisions, "relations": relations}
    return sha256_of(canonical_json(payload))


def _evidence_content(ev: Evidence) -> Dict[str, Any]:
    return {
        "evidence_id": ev.evidence_id,
        "evidence_type": ev.evidence_type,
        "target_id": ev.target.id,
        "target_revision_id": ev.target.revision_id,
        "target_digest": ev.target.digest,
        "scope_environment": ev.scope_environment,
        "scope_dimensions": sorted(ev.scope_dimensions),
        "result": ev.result.value,
        "blocking": ev.blocking,
        "valid_until": ev.valid_until.isoformat() if ev.valid_until else None,
        "dependency_snapshot": sorted(
            (
                {"id": s.id, "revision_id": s.revision_id, "digest": s.digest}
                for s in ev.dependency_snapshot
            ),
            key=lambda d: (d["id"], d["revision_id"] or ""),
        ),
        "revoked": ev.revoked,
    }


def evidence_digest(evidence: List[Evidence]) -> str:
    """Digest canonique d'un ensemble de preuves (§4), invariant à l'ordre."""
    items = sorted(
        (_evidence_content(e) for e in evidence),
        key=lambda d: d["evidence_id"],
    )
    return sha256_of(canonical_json(items))


def _ref_content(ref) -> Dict[str, Any]:
    """Contenu identifiant d'une référence (id + revision + digest)."""
    return {
        "id": ref.id,
        "revision_id": ref.revision_id,
        "digest": ref.digest,
    }


def baseline_digest(baseline) -> str:
    """Digest matériel d'une baseline, dérivé de ses required_items (§6, S04).

    Une baseline est un SNAPSHOT exact de révisions. Son digest est le hash
    canonique de l'ensemble (id, revision_id, digest) de ses membres, trié pour
    être indépendant de l'ordre. Toute mutation d'un membre (ajout, retrait,
    changement de révision) change le digest : c'est le mécanisme d'immutabilité
    LOGIQUE de S04 — la baseline n'est pas frozen en mémoire, mais toute
    modification est détectable par recalcul et divergence du digest.

    Le baseline_id et l'état de lifecycle n'entrent PAS dans le digest : deux
    baselines au même contenu ont le même digest matériel quel que soit leur
    état, et changer d'état (released → withdrawn) ne modifie pas le digest
    (essentiel pour S17 : le retrait n'altère pas les digests historiques).
    """
    members = sorted(
        (_ref_content(r) for r in baseline.required_items),
        key=lambda d: (d["id"], d["revision_id"] or ""),
    )
    return sha256_of(canonical_json({"required_items": members}))
