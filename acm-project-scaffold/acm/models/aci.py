"""Modèles ACI, relations, preuves et graphe de configuration."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ACIType,
    AssuranceState,
    CompositionAssuranceMode,
    EvidenceResult,
    LifecycleState,
    PropagationPolicy,
    QualityState,
    RelationType,
)
from .refs import ACIRef


# §21.4 — Types de relations sur lesquels v0.1 interdit les cycles.
# Les cycles autorisés (dépendances mutuelles légitimes) doivent passer par
# d'autres types de relations et être explicitement déclarés.
FORBIDDEN_CYCLE_RELATION_TYPES = [
    RelationType.CONTAINS,
    RelationType.TEMPLATES,
    RelationType.USES_PROMPT,
    RelationType.USES_MODEL,
]


class DeclaredStatus(BaseModel):
    """États intrinsèques attachés à une révision exacte (§3.2, §4.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lifecycle_state: LifecycleState = LifecycleState.DRAFT
    quality_state: QualityState = QualityState.UNKNOWN
    assurance_state: AssuranceState = AssuranceState.UNASSESSED


class AssurancePolicy(BaseModel):
    """Politique d'assurance d'un ACI (§16.2).

    Porte les exigences de preuve directe (R_d(x)) et le mode de composition.
    C'est ici — et non sur la preuve — que se déclare la dérogation agrégative.
    """

    model_config = ConfigDict(extra="forbid")
    # R_d(x) : dimensions d'assurance requises directement (§10.2).
    # Un ensemble vide DÉCLARÉ n'est pas la même chose qu'une exigence absente.
    required_assurance_dimensions: List[str] = Field(default_factory=list)

    composition_mode: CompositionAssuranceMode = CompositionAssuranceMode.HYBRID

    # Garde-fou anti-vacuité : aggregate_only sans aucune dépendance NE DOIT PAS
    # produire assessed, sauf autorisation explicite.
    allow_vacuous_assessment: bool = False


class ACIRevision(BaseModel):
    """Une révision exacte d'un objet de configuration (ACI).

    Modèle IMMUABLE (frozen) : toute modification du contenu canonique crée une
    nouvelle révision (nouveau revision_id + digest), cf. §19.1. Pour changer un
    état déclaré, on construit une nouvelle révision plutôt que muter celle-ci.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: ACIRef
    declared: DeclaredStatus = Field(default_factory=DeclaredStatus)
    aci_type: ACIType = Field(..., description="prompt | tool | model | agent | workflow | ...")
    schema_valid: bool = Field(default=True)
    digest_valid: bool = Field(default=True)
    # Marqueur de gel de contenu (candidate DOIT être figé, §5.2)
    content_frozen: bool = Field(default=False)
    # Politique d'assurance : exigences directes + mode de composition (§16.2).
    # Optionnelle : None = AUCUNE politique déclarée (distinct d'une politique
    # explicitement vide AssurancePolicy()). L'absence de politique implique
    # qu'aucune exigence d'assurance n'est posée sur cette révision.
    assurance_policy: Optional[AssurancePolicy] = None

    def effective_assurance_policy(self) -> AssurancePolicy:
        """Politique effective : la politique déclarée, ou une politique vide
        par défaut si aucune n'est déclarée. Utilisé par le moteur ; la
        distinction absente/vide reste visible via `assurance_policy is None`.
        """
        return self.assurance_policy if self.assurance_policy is not None else AssurancePolicy()

    def key(self) -> str:
        return self.ref.key()


class Relation(BaseModel):
    """Relation dirigée source -> target du ConfigurationGraph (§13)."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str
    source: ACIRef
    target: ACIRef
    relation_type: RelationType
    required: bool = Field(default=True, description="§13.3")
    propagation_policy: PropagationPolicy = Field(
        default=PropagationPolicy.BLOCKING, description="§13.4"
    )
    assurance_dependency: bool = Field(default=True, description="§14.3")
    impact_dependency: bool = Field(default=True, description="§14.1")


class Evidence(BaseModel):
    """Preuve normative (§10.4).

    Une preuve est applicable à une révision exacte selon les conditions du §10.3.
    Les preuves NE SONT PAS transitives par défaut (§10.5).
    IMMUABLE : une preuve historique ne doit pas être modifiée (§18.4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str
    evidence_type: str = Field(default="evaluation")
    target: ACIRef
    scope_environment: Optional[str] = Field(default=None)
    scope_dimensions: List[str] = Field(default_factory=list)
    result: EvidenceResult = Field(default=EvidenceResult.PASS)
    blocking: bool = Field(default=True)
    produced_at: Optional[datetime] = Field(default=None)
    valid_until: Optional[datetime] = Field(default=None)
    # Snapshot des dépendances au moment de la preuve (§18.1 staleness)
    dependency_snapshot: List[ACIRef] = Field(default_factory=list)
    revoked: bool = Field(default=False)

    def targets_revision(self, ref: ACIRef) -> bool:
        return self.target.matches_revision(ref)


class ConfigurationGraph(BaseModel):
    """Graphe de configuration : révisions + relations (§21.1)."""

    model_config = ConfigDict(extra="forbid")

    revisions: Dict[str, ACIRevision] = Field(default_factory=dict)
    relations: List[Relation] = Field(default_factory=list)

    @classmethod
    def build(
        cls, revisions: List[ACIRevision], relations: List[Relation]
    ) -> "ConfigurationGraph":
        return cls(
            revisions={r.key(): r for r in revisions},
            relations=list(relations),
        )

    def validate_integrity(self, *, strict: bool = False) -> List[str]:
        """Validation structurelle du graphe (§21.1, §21.4).

        Détecte : révisions dupliquées, relations dupliquées, références de
        relation (source/target) manquantes, et cycles sur les types de
        relations où v0.1 les interdit (contains, templates, uses_prompt,
        uses_model — §21.4). Retourne la liste des problèmes ; en mode strict,
        lève ValueError si non vide.
        """
        problems: List[str] = []

        # Révisions dupliquées (même clé id@revision).
        seen_rev: Dict[str, int] = {}
        for key in self.revisions:
            seen_rev[key] = seen_rev.get(key, 0) + 1

        # Relations dupliquées (même relation_id, ou même triplet src/tgt/type).
        seen_rel_id: Dict[str, int] = {}
        seen_triple: Dict[tuple, int] = {}
        for rel in self.relations:
            seen_rel_id[rel.relation_id] = seen_rel_id.get(rel.relation_id, 0) + 1
            triple = (rel.source.key(), rel.target.key(), rel.relation_type.value)
            seen_triple[triple] = seen_triple.get(triple, 0) + 1
        for rid, n in seen_rel_id.items():
            if n > 1:
                problems.append(f"Relation dupliquée (relation_id): {rid} x{n}")
        for triple, n in seen_triple.items():
            if n > 1:
                problems.append(f"Relation dupliquée (src/tgt/type): {triple} x{n}")

        # Références manquantes : source et target doivent exister dans le graphe.
        rev_keys = set(self.revisions.keys())
        for rel in self.relations:
            if rel.source.key() not in rev_keys:
                problems.append(
                    f"Référence source manquante: {rel.source.key()} (relation {rel.relation_id})"
                )
            if rel.target.key() not in rev_keys:
                problems.append(
                    f"Référence target manquante: {rel.target.key()} (relation {rel.relation_id})"
                )

        # Cycles interdits (§21.4) sur les types structurels.
        problems += self.validate_acyclic(FORBIDDEN_CYCLE_RELATION_TYPES)

        if strict and problems:
            raise ValueError("Graphe invalide:\n- " + "\n- ".join(problems))
        return problems

    def get(self, ref: ACIRef) -> Optional[ACIRevision]:
        return self.revisions.get(ref.key())

    def dependencies_of(self, ref: ACIRef) -> List[Relation]:
        """Relations sortantes : les dépendances directes de `ref`."""
        return [rel for rel in self.relations if rel.source.key() == ref.key()]

    def dependents_of(self, ref: ACIRef) -> List[Relation]:
        """Relations entrantes : les objets qui dépendent de `ref`."""
        return [rel for rel in self.relations if rel.target.key() == ref.key()]

    def find_cycles(
        self, relation_types: Optional[List["RelationType"]] = None
    ) -> List[List[str]]:
        """Détecte les cycles dans le graphe orienté des relations (§21.4).

        Si `relation_types` est fourni, ne considère que les relations de ces
        types (utile pour interdire les cycles sur contains/templates/etc.).
        Retourne la liste des cycles, chacun exprimé comme une liste de clés
        de nœuds (id@revision) dans l'ordre du cycle.
        """
        # Arêtes filtrées éventuellement par type.
        adj: Dict[str, List[str]] = {}
        for rel in self.relations:
            if relation_types is not None and rel.relation_type not in relation_types:
                continue
            adj.setdefault(rel.source.key(), []).append(rel.target.key())

        cycles: List[List[str]] = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {}
        stack: List[str] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            stack.append(node)
            for nxt in adj.get(node, []):
                c = color.get(nxt, WHITE)
                if c == WHITE:
                    dfs(nxt)
                elif c == GRAY:
                    # Cycle : extraire la portion de pile depuis nxt.
                    if nxt in stack:
                        i = stack.index(nxt)
                        cycles.append(stack[i:] + [nxt])
            stack.pop()
            color[node] = BLACK

        for node in list(adj.keys()):
            if color.get(node, WHITE) == WHITE:
                dfs(node)
        return cycles

    def validate_acyclic(
        self, relation_types: Optional[List["RelationType"]] = None, *, strict: bool = False
    ) -> List[str]:
        """§21.4 — signale les cycles (sur les types donnés). En strict, lève."""
        problems: List[str] = []
        for cyc in self.find_cycles(relation_types):
            problems.append("Cycle interdit: " + " -> ".join(cyc))
        if strict and problems:
            raise ValueError("Cycles détectés:\n- " + "\n- ".join(problems))
        return problems
