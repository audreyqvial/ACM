"""AgentSpec — description neutre d'une instance à créer (entrée d'adaptateur).

Symétrique de RuntimeSignal (sortie) : l'AgentSpec est ce que le CŒUR fournit
à un adaptateur pour lui demander d'instancier un agent, sans rien savoir du
framework cible. L'adaptateur (LangGraph, CrewAI...) traduit cet AgentSpec en
construction concrète, puis produit un RuntimeSignal.

Un AgentSpec décrit la configuration RÉSOLUE souhaitée et le contexte de
gouvernance (factory, template, permissions, plafonds), pas des objets framework.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from ..models.refs import ACIRef


class PermissionCeiling(BaseModel):
    """Plafonds de permissions applicables (§I13).

    P_instance ⊆ P_creator ∩ P_factory ∩ P_environment.
    Chaque ensemble est représenté par un ensemble de capacités nommées.
    """

    creator: List[str] = Field(default_factory=list)
    factory: List[str] = Field(default_factory=list)
    environment: List[str] = Field(default_factory=list)


class AgentSpec(BaseModel):
    """Spécification neutre d'une instance dynamique à créer."""

    instance_id: str
    template_ref: ACIRef
    factory_ref: Optional[ACIRef] = None
    creation_event_id: Optional[str] = None
    created_by_valid_factory: bool = True

    # Configuration résolue souhaitée (références, pas objets framework)
    prompt_ref: Optional[ACIRef] = None
    model_ref: Optional[ACIRef] = None
    tool_refs: List[ACIRef] = Field(default_factory=list)

    # Contenu concret nécessaire à une construction/exécution réelle (couche 2).
    # Optionnel en couche 1 (construire + inspecter).
    prompt_text: Optional[str] = None
    tool_names: List[str] = Field(default_factory=list)
    model_name: Optional[str] = Field(
        default=None, description="ex. gpt-5.4 — identité du modèle à exécuter"
    )

    # Overrides comportementaux déclarés (§20.3). L'adaptateur les recopie tels
    # quels dans le RuntimeSignal ; il ne les DÉDUIT pas (la déclaration est
    # une responsabilité de gouvernance, pas d'exécution).
    prompt_overridden: bool = False
    system_instructions_overridden: bool = False
    model_identity_overridden: bool = False
    tool_set_overridden: bool = False
    permissions_overridden: bool = False
    delegation_policy_overridden: bool = False
    termination_rules_overridden: bool = False
    memory_source_overridden: bool = False
    retrieval_source_overridden: bool = False

    parameters_within_validated_ranges: bool = True

    # Permissions demandées pour l'instance + plafonds applicables.
    requested_permissions: List[str] = Field(default_factory=list)
    ceiling: PermissionCeiling = Field(default_factory=PermissionCeiling)

    # Outils autorisés par la baseline/gouvernance (pour détecter un outil interdit).
    authorized_tools: List[str] = Field(default_factory=list)

    def with_ref_digests(self) -> "AgentSpec":
        """Retourne une copie dont tous les ACIRef ont un digest canonique (§3.5).

        Renseigne les digests de template/factory/prompt/model/tools à partir de
        leur (id, revision_id). Déterministe et partagé entre adaptateurs : deux
        démos partant du même spec produisent les mêmes digests de références.
        """
        def d(ref):
            return ref.with_digest() if ref is not None else None

        return self.model_copy(update={
            "template_ref": d(self.template_ref),
            "factory_ref": d(self.factory_ref),
            "prompt_ref": d(self.prompt_ref),
            "model_ref": d(self.model_ref),
            "tool_refs": [d(t) for t in self.tool_refs],
        })
