"""Dérivation des faits de gouvernance depuis un AgentSpec (cœur pur).

Ces fonctions vivent dans le cœur, PAS dans l'adaptateur, pour garantir que
LangGraph et CrewAI produisent un RuntimeSignal identique à partir d'un
AgentSpec identique. La détermination de « qui est en escalade », « quel outil
est interdit », « quels overrides sont présents » est une décision de
gouvernance, indépendante du framework d'exécution.

L'adaptateur reste mince : il construit/exécute côté framework, puis appelle
ces helpers pour remplir les parties gouvernance du signal.
"""
from __future__ import annotations

import hashlib
import json

from .signal import PermissionCheck, ResolvedConfig, Traceability
from .spec import AgentSpec


def digest_of_resolved_config(config: ResolvedConfig) -> str:
    """Empreinte canonique et déterministe de la config résolue (§3.5, I2).

    Ne hashe QUE la configuration (prompt/model/tools + overrides + plages),
    pas la traçabilité ni les permissions (contexte, pas config). Ainsi deux
    instances de même config mais de factories différentes ont le même digest.

    Canonicalisation :
      - refs réduites à (id, revision_id) — le digest amont éventuel n'entre
        pas dans le calcul pour éviter toute circularité ;
      - tool_refs triées (l'ordre ne doit pas changer l'empreinte) ;
      - JSON à clés triées, séparateurs compacts.

    Garantit que LangGraph et CrewAI produisent le MÊME digest pour la MÊME
    config résolue — renfort de l'équivalence inter-adaptateurs.
    """
    def ref_tuple(ref):
        return None if ref is None else [ref.id, ref.revision_id]

    canonical = {
        "prompt_ref": ref_tuple(config.prompt_ref),
        "model_ref": ref_tuple(config.model_ref),
        "tool_refs": sorted(
            [ref_tuple(t) for t in config.tool_refs],
            key=lambda x: (x[0] or "", x[1] or ""),
        ),
        "overrides": {
            "prompt": config.prompt_overridden,
            "system_instructions": config.system_instructions_overridden,
            "model_identity": config.model_identity_overridden,
            "tool_set": config.tool_set_overridden,
            "permissions": config.permissions_overridden,
            "delegation_policy": config.delegation_policy_overridden,
            "termination_rules": config.termination_rules_overridden,
            "memory_source": config.memory_source_overridden,
            "retrieval_source": config.retrieval_source_overridden,
        },
        "parameters_within_validated_ranges": config.parameters_within_validated_ranges,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def resolved_config_from_spec(spec: AgentSpec) -> ResolvedConfig:
    """Construit la config résolue (§20.2, §20.3) à partir de la spec."""
    return ResolvedConfig(
        prompt_ref=spec.prompt_ref,
        model_ref=spec.model_ref,
        tool_refs=list(spec.tool_refs),
        prompt_overridden=spec.prompt_overridden,
        system_instructions_overridden=spec.system_instructions_overridden,
        model_identity_overridden=spec.model_identity_overridden,
        tool_set_overridden=spec.tool_set_overridden,
        permissions_overridden=spec.permissions_overridden,
        delegation_policy_overridden=spec.delegation_policy_overridden,
        termination_rules_overridden=spec.termination_rules_overridden,
        memory_source_overridden=spec.memory_source_overridden,
        retrieval_source_overridden=spec.retrieval_source_overridden,
        parameters_within_validated_ranges=spec.parameters_within_validated_ranges,
    )


def traceability_from_spec(spec: AgentSpec) -> Traceability:
    """Construit les signaux de traçabilité (§I11) à partir de la spec."""
    return Traceability(
        factory_ref=spec.factory_ref,
        template_ref=spec.template_ref,
        creation_event_id=spec.creation_event_id,
        created_by_valid_factory=spec.created_by_valid_factory,
    )


def permission_check_from_spec(spec: AgentSpec) -> PermissionCheck:
    """Calcule la vérification de permissions (§I13) : l'ensemble demandé est-il
    inclus dans chaque plafond, et tous les outils sont-ils autorisés ?
    """
    requested = set(spec.requested_permissions)
    creator = set(spec.ceiling.creator)
    factory = set(spec.ceiling.factory)
    environment = set(spec.ceiling.environment)

    tools_ok = set(spec.tool_names).issubset(set(spec.authorized_tools)) \
        if spec.authorized_tools else True

    return PermissionCheck(
        within_creator_ceiling=requested.issubset(creator) if creator or requested else True,
        within_factory_ceiling=requested.issubset(factory) if factory or requested else True,
        within_environment_ceiling=requested.issubset(environment) if environment or requested else True,
        uses_authorized_tools_only=tools_ok,
    )
