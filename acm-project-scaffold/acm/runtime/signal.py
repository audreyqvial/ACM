"""RuntimeSignal — contrat de sortie normalisé (frontière exécution/gouvernance).

Ce module définit CE QUE le cœur ACM attend d'un framework d'exécution
(LangGraph, CrewAI, ou stub déterministe), JAMAIS un objet framework brut.

Principe (établi lors du cadrage) :
  - le déterminisme est une propriété du CŒUR, pas de l'adaptateur ;
  - un adaptateur réel sera non-déterministe dans son exécution, mais doit
    produire un RuntimeSignal que le cœur traite de façon déterministe ;
  - le RuntimeSignal est sérialisable JSON -> record/replay : on peut capturer
    la sortie d'un vrai run une fois, la figer, et la rejouer dans les tests.

Le §20 a besoin, pour décider de l'état d'une instance dynamique :
  - la config résolue (prompt, outils, modèle, permissions, delegation...) ;
  - les signaux de traçabilité (factory, template, événement de création) ;
  - le résultat de permissions (dans le plafond ? escalade ?) ;
  - le terminal state d'exécution.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.refs import ACIRef


class ResolvedConfig(BaseModel):
    """Configuration résolue d'une instance runtime (§20.2, §20.3).

    Sert à décider si l'instance comporte un override comportemental.
    """

    prompt_ref: Optional[ACIRef] = None
    model_ref: Optional[ACIRef] = None
    tool_refs: List[ACIRef] = Field(default_factory=list)

    # Overrides comportementaux (§20.3). Chacun, s'il est vrai, déclenche
    # quality=unknown / assurance=unassessed jusqu'aux contrôles runtime.
    prompt_overridden: bool = False
    system_instructions_overridden: bool = False
    model_identity_overridden: bool = False
    tool_set_overridden: bool = False
    permissions_overridden: bool = False
    delegation_policy_overridden: bool = False
    termination_rules_overridden: bool = False
    memory_source_overridden: bool = False
    retrieval_source_overridden: bool = False

    # Paramètres résolus restant dans les plages validées (§20.2) ?
    parameters_within_validated_ranges: bool = True

    def has_behavioral_override(self) -> bool:
        """§20.3 — un quelconque override comportemental est-il présent ?"""
        return any([
            self.prompt_overridden,
            self.system_instructions_overridden,
            self.model_identity_overridden,
            self.tool_set_overridden,
            self.permissions_overridden,
            self.delegation_policy_overridden,
            self.termination_rules_overridden,
            self.memory_source_overridden,
            self.retrieval_source_overridden,
        ])

    def has_forbidden_override(self) -> bool:
        """§S20 — un override d'un champ explicitement NON surchargeable ?

        Distingue les overrides tolérés (prompt/instructions autorisés par la
        factory, réévaluables) des overrides de champs qui ne doivent JAMAIS
        être modifiés par une instance dynamique :
          - ensemble d'outils (tool_set) ;
          - identité du modèle (model_identity) ;
          - politiques de délégation / permissions ;
          - sources mémoire / récupération (canaux de comportement).
        Un tel override rend l'instance non éligible (blocked), au-delà du
        simple avertissement du §20.3.
        """
        return any([
            self.tool_set_overridden,
            self.model_identity_overridden,
            self.permissions_overridden,
            self.delegation_policy_overridden,
            self.memory_source_overridden,
            self.retrieval_source_overridden,
        ])


class Traceability(BaseModel):
    """Signaux de traçabilité d'une instance dynamique (§I11, ACM-DYNAMIC-001).

    Toute instance dynamique DOIT référencer : factory, template, événement de
    création, config résolue, permissions résolues. L'absence rend l'instance
    bloquante (§20.4) et la classe comme `undeclared_instance` (§24.5).
    """

    factory_ref: Optional[ACIRef] = None
    template_ref: Optional[ACIRef] = None
    creation_event_id: Optional[str] = None
    created_by_valid_factory: bool = True

    def is_traceable(self) -> bool:
        """§I11 — toutes les références obligatoires sont-elles présentes ?"""
        return (
            self.factory_ref is not None
            and self.template_ref is not None
            and self.creation_event_id is not None
            and self.created_by_valid_factory
        )


class PermissionCheck(BaseModel):
    """Résultat de la vérification de permissions (§I13, ACM-PERM-001).

    P_instance ⊆ P_creator ∩ P_factory ∩ P_environment
    """

    within_creator_ceiling: bool = True
    within_factory_ceiling: bool = True
    within_environment_ceiling: bool = True
    uses_authorized_tools_only: bool = True

    def has_escalation(self) -> bool:
        """Une escalade de permissions est-elle détectée ?"""
        return not (
            self.within_creator_ceiling
            and self.within_factory_ceiling
            and self.within_environment_ceiling
        )


class RuntimeTerminalState(str, Enum):
    """Sous-ensemble des états terminaux runtime pertinents pour l'évaluation."""

    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeSignal(BaseModel):
    """Sortie normalisée d'un adaptateur runtime.

    Que ce signal soit fabriqué par un stub (valeurs figées) ou par une vraie
    exécution CrewAI/LangGraph, le cœur ACM ne voit AUCUNE différence.
    Sérialisable JSON pour record/replay.
    """

    instance_id: str
    definition_ref: ACIRef = Field(..., description="Définition/template source")
    resolved_config: ResolvedConfig
    traceability: Traceability
    permissions: PermissionCheck = Field(default_factory=PermissionCheck)
    terminal_state: RuntimeTerminalState = RuntimeTerminalState.CREATED

    # Empreinte canonique de la config résolue (§3.5, I2). Calculée par le
    # cœur (governance.digest_of_resolved_config) ; identique quel que soit
    # l'adaptateur pour une même config. None tant que non renseignée.
    resolved_config_digest: Optional[str] = None

    # Contrôles runtime requis effectivement enregistrés et réussis (§24.4).
    # Tant qu'ils ne sont pas là, une instance conforme reste partially_assessed.
    runtime_checks_completed: bool = False
    runtime_checks_passed: bool = False

    # Empreinte de l'adaptateur ayant produit le signal (record/replay + audit).
    adapter_name: str = "unknown"
    produced_at: Optional[datetime] = None

    # --- record / replay ---

    def to_record(self) -> Dict:
        """Sérialise le signal en dict JSON-compatible (mode `record`)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_record(cls, data: Dict) -> "RuntimeSignal":
        """Rejoue un signal figé (mode `replay`)."""
        return cls.model_validate(data)
