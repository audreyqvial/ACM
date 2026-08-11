"""Loader déclaratif du harness d'évaluation ACM.

Transforme une fixture YAML 100% déclarative en objets du noyau `acm` :
configuration (ConfigurationGraph), preuves (List[Evidence]) et contexte de
propagation (PropagationContext). Aucune logique de gouvernance ici — le loader
ne fait que de la traduction structurée, exactement comme un adaptateur.

Format de fixture (voir scenarios/*.yaml) :

    scenario_id: ACM-S01
    priority: P0
    frameworks: [core]
    description: ...
    context:
      eligibility_context: validation      # défaut: validation
      environment: local                   # défaut: null
      now: "2026-07-27T10:00:00Z"           # défaut: fixe et déterministe
    revisions:
      - id: aci:prompt:planner-system
        revision_id: 01JREV
        aci_type: prompt
        lifecycle_state: validated
        quality_state: ok
        assurance_state: assessed
        content_frozen: true
        assurance_policy:
          required_assurance_dimensions: [functional, robustness]
          composition_mode: hybrid
    relations:
      - id: rel:a1:uses-prompt:p1
        source: aci:agent:planner
        target: aci:prompt:planner-system
        relation_type: uses_prompt
        required: true
        propagation_policy: blocking
    evidence:
      - id: evidence:eval:planner:001
        target: aci:agent:planner
        scope_dimensions: [functional, robustness]
        result: pass
        blocking: true
    expected: {...}          # consommé par l'asserter, ignoré ici
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from acm import (
    ACIRef,
    ACIRevision,
    ConfigurationGraph,
    DeclaredStatus,
    Evidence,
    PropagationContext,
    Relation,
)
from acm.models.aci import AssurancePolicy
from acm.models.enums import (
    ACIType,
    AssuranceState,
    CompositionAssuranceMode,
    EvidenceResult,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)
from acm.policy import EligibilityContext

# Horodatage par défaut : FIXE et déterministe (reproductibilité, §13.1).
# Toute fixture qui ne précise pas `now` hérite de cette valeur stable, de sorte
# que deux exécutions produisent des digests identiques (S25).
DEFAULT_NOW = datetime(2026, 7, 27, 10, 0, 0, tzinfo=timezone.utc)


@dataclass
class LoadedScenario:
    """Résultat du chargement d'une fixture : entrées + oracle brut + méta."""

    scenario_id: str
    priority: str
    frameworks: List[str]
    description: str
    graph: ConfigurationGraph
    evidence: List[Evidence]
    context: PropagationContext
    expected: Dict[str, Any] = field(default_factory=dict)
    # Séquence runtime optionnelle (S12/S13) : liste de RuntimeEvent, ou None.
    runtime_sequence: Optional[List[Any]] = None
    # Métadonnées transverses conservées pour le reporter et l'asserter.
    raw: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[Path] = None


def _parse_datetime(value: Any) -> datetime:
    if value is None:
        return DEFAULT_NOW
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    # Chaîne ISO 8601, éventuellement suffixée 'Z'.
    text = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _build_ref(aci_id: str, revision_id: Optional[str], digest: Optional[str]) -> ACIRef:
    """Construit une référence, en renseignant le digest canoniquement si absent.

    Si un digest explicite est fourni (cas S03 : digest volontairement faux), il
    est conservé tel quel. Sinon on dérive un digest canonique cohérent via
    `with_digest()` pour que l'identité de révision soit toujours complète.
    """
    ref = ACIRef(id=aci_id, revision_id=revision_id, digest=digest)
    return ref.with_digest()


def _load_revision(entry: Dict[str, Any]) -> ACIRevision:
    policy_data = entry.get("assurance_policy")
    assurance_policy: Optional[AssurancePolicy] = None
    if policy_data is not None:
        assurance_policy = AssurancePolicy(
            required_assurance_dimensions=list(
                policy_data.get("required_assurance_dimensions", [])
            ),
            composition_mode=CompositionAssuranceMode(
                policy_data.get("composition_mode", "hybrid")
            ),
            allow_vacuous_assessment=bool(
                policy_data.get("allow_vacuous_assessment", False)
            ),
        )

    declared = DeclaredStatus(
        lifecycle_state=LifecycleState(entry.get("lifecycle_state", "draft")),
        quality_state=QualityState(entry.get("quality_state", "unknown")),
        assurance_state=AssuranceState(entry.get("assurance_state", "unassessed")),
    )

    ref = _build_ref(
        entry["id"], entry.get("revision_id"), entry.get("digest")
    )

    return ACIRevision(
        ref=ref,
        aci_type=ACIType(entry.get("aci_type", "other")),
        declared=declared,
        schema_valid=bool(entry.get("schema_valid", True)),
        digest_valid=bool(entry.get("digest_valid", True)),
        content_frozen=bool(entry.get("content_frozen", False)),
        assurance_policy=assurance_policy,
    )


def _resolve_ref_by_id(aci_id: str, revisions: List[ACIRevision]) -> ACIRef:
    """Résout un id logique vers la référence exacte de la révision du graphe.

    Les relations et preuves des fixtures ciblent par id logique ; on relie à la
    révision effectivement présente pour que source/target correspondent aux
    clés du graphe. Si l'id est inconnu (cas S02 : référence manquante), on
    fabrique une référence logique nue — le moteur la signalera comme absente.
    """
    for rev in revisions:
        if rev.ref.id == aci_id:
            return rev.ref
    return ACIRef(id=aci_id)


def _load_relation(entry: Dict[str, Any], revisions: List[ACIRevision]) -> Relation:
    return Relation(
        relation_id=entry["id"],
        source=_resolve_ref_by_id(entry["source"], revisions),
        target=_resolve_ref_by_id(entry["target"], revisions),
        relation_type=RelationType(entry["relation_type"]),
        required=bool(entry.get("required", True)),
        propagation_policy=PropagationPolicy(
            entry.get("propagation_policy", "blocking")
        ),
        assurance_dependency=bool(entry.get("assurance_dependency", True)),
        impact_dependency=bool(entry.get("impact_dependency", True)),
    )


def _load_evidence(
    entry: Dict[str, Any], revisions: List[ACIRevision]
) -> Evidence:
    # La cible d'une preuve peut préciser revision_id/digest pour tester
    # l'identité exacte (S03). Sinon on résout par id logique.
    target_id = entry["target"]
    explicit_rev = entry.get("target_revision_id")
    explicit_digest = entry.get("target_digest")

    if explicit_rev is not None or explicit_digest is not None:
        target = _build_ref(target_id, explicit_rev, explicit_digest)
        # Si seul le revision_id est donné, with_digest a comblé le digest ;
        # mais pour S03 on veut pouvoir forcer un digest FAUX distinct.
        if explicit_digest is not None:
            target = ACIRef(
                id=target_id, revision_id=explicit_rev, digest=explicit_digest
            )
    else:
        target = _resolve_ref_by_id(target_id, revisions)

    snapshot: List[ACIRef] = []
    for snap in entry.get("dependency_snapshot", []):
        if isinstance(snap, dict):
            snapshot.append(
                _build_ref(
                    snap["id"], snap.get("revision_id"), snap.get("digest")
                )
            )
        else:
            snapshot.append(_resolve_ref_by_id(snap, revisions))

    return Evidence(
        evidence_id=entry["id"],
        evidence_type=entry.get("evidence_type", "evaluation"),
        target=target,
        scope_environment=entry.get("scope_environment"),
        scope_dimensions=list(entry.get("scope_dimensions", [])),
        result=EvidenceResult(entry.get("result", "pass")),
        blocking=bool(entry.get("blocking", True)),
        produced_at=_parse_datetime(entry["produced_at"])
        if entry.get("produced_at")
        else None,
        valid_until=_parse_datetime(entry["valid_until"])
        if entry.get("valid_until")
        else None,
        dependency_snapshot=snapshot,
        revoked=bool(entry.get("revoked", False)),
    )


def _load_context(data: Dict[str, Any]) -> PropagationContext:
    ctx_data = data.get("context", {}) or {}
    return PropagationContext(
        eligibility_context=EligibilityContext(
            ctx_data.get("eligibility_context", "validation")
        ),
        now=_parse_datetime(ctx_data.get("now")),
        environment=ctx_data.get("environment"),
    )


def _load_runtime_sequence(data: Dict[str, Any]) -> Optional[List[Any]]:
    """Parse un bloc `runtime_sequence:` optionnel en RuntimeEvent (S12/S13).

    Import différé pour ne pas coupler le loader au module state_machines quand
    le scénario ne contient pas de séquence.
    """
    raw = data.get("runtime_sequence")
    if not raw:
        return None
    from acm.models.enums import RuntimeState
    from acm.state_machines import RuntimeEvent, RuntimeEventType

    events: List[Any] = []
    for entry in raw:
        to_state = entry.get("to_state")
        events.append(
            RuntimeEvent(
                event_type=RuntimeEventType(entry["event_type"]),
                to_state=RuntimeState(to_state) if to_state else None,
                sequence=entry.get("sequence"),
                event_id=entry.get("event_id"),
            )
        )
    return events


def load_scenario_dict(data: Dict[str, Any], source_path: Optional[Path] = None) -> LoadedScenario:
    """Charge un scénario depuis un dict déjà parsé (utile pour les tests)."""
    revisions = [_load_revision(e) for e in data.get("revisions", [])]
    relations = [_load_relation(e, revisions) for e in data.get("relations", [])]
    evidence = [_load_evidence(e, revisions) for e in data.get("evidence", [])]
    graph = ConfigurationGraph.build(revisions, relations)
    context = _load_context(data)

    return LoadedScenario(
        scenario_id=data["scenario_id"],
        priority=data.get("priority", "P0"),
        frameworks=list(data.get("frameworks", ["core"])),
        description=data.get("description", ""),
        graph=graph,
        evidence=evidence,
        context=context,
        expected=data.get("expected", {}) or {},
        runtime_sequence=_load_runtime_sequence(data),
        raw=data,
        source_path=source_path,
    )


def load_scenario(path: Path) -> LoadedScenario:
    """Charge une fixture YAML depuis le disque."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return load_scenario_dict(data, source_path=path)


def discover_scenarios(directory: Path) -> List[Path]:
    """Liste triée des fixtures *.yaml d'un répertoire (ordre déterministe)."""
    directory = Path(directory)
    return sorted(directory.glob("*.yaml"))
