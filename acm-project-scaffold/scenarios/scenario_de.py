"""Scénarios D et E — Agents dynamiques (§24.4, §24.5).

Les deux scénarios construisent un RuntimeSignal, le passent à travers le
stub déterministe (même chemin que le futur adaptateur réel), et le cœur ACM
l'évalue via §20.

D — instance conforme (§24.4) :
    Factory F1 validated, template validated, P1/T1 validated, aucun override.
    Attendu : ephemeral / unknown / partially_assessed / warning.
    Après contrôles runtime réussis : ok / assessed / eligible (scope exécution).

E — instance non autorisée (§24.5) :
    sans factory, outil non autorisé, permission > créateur.
    Attendu : nok / unassessed / blocked,
              drift = undeclared_instance, permission_drift = critical.
"""
from __future__ import annotations

from acm import (
    ACIRef,
    PermissionCheck,
    ResolvedConfig,
    RuntimeSignal,
    RuntimeTerminalState,
    Traceability,
)

FACTORY = ACIRef(id="aci:factory:agent-factory", revision_id="01JF1")
TEMPLATE = ACIRef(id="aci:template:planner-template", revision_id="01JT1")
P1 = ACIRef(id="aci:prompt:planner-system", revision_id="01JR1")
T1 = ACIRef(id="aci:tool:web-search", revision_id="01JR1")
M1 = ACIRef(id="aci:model:default-llm", revision_id="01JR1")


def signal_d_conforming(runtime_checks_passed: bool = False) -> RuntimeSignal:
    """§24.4 — instance conforme, sans override comportemental."""
    return RuntimeSignal(
        instance_id="rt:instance:planner-001",
        definition_ref=TEMPLATE,
        resolved_config=ResolvedConfig(
            prompt_ref=P1,
            model_ref=M1,
            tool_refs=[T1],
            # aucun override comportemental
            parameters_within_validated_ranges=True,
        ),
        traceability=Traceability(
            factory_ref=FACTORY,
            template_ref=TEMPLATE,
            creation_event_id="evt:create:001",
            created_by_valid_factory=True,
        ),
        permissions=PermissionCheck(
            within_creator_ceiling=True,
            within_factory_ceiling=True,
            within_environment_ceiling=True,
            uses_authorized_tools_only=True,
        ),
        terminal_state=RuntimeTerminalState.CREATED,
        runtime_checks_completed=runtime_checks_passed,
        runtime_checks_passed=runtime_checks_passed,
    )


def signal_e_unauthorized() -> RuntimeSignal:
    """§24.5 — instance non autorisée : sans factory, outil interdit, escalade."""
    return RuntimeSignal(
        instance_id="rt:instance:rogue-001",
        definition_ref=TEMPLATE,
        resolved_config=ResolvedConfig(
            prompt_ref=P1,
            model_ref=M1,
            tool_refs=[ACIRef(id="aci:tool:unauthorized-shell", revision_id="01JX")],
            tool_set_overridden=True,
            permissions_overridden=True,
            parameters_within_validated_ranges=False,
        ),
        traceability=Traceability(
            factory_ref=None,             # sans factory
            template_ref=TEMPLATE,
            creation_event_id=None,       # pas d'événement de création
            created_by_valid_factory=False,
        ),
        permissions=PermissionCheck(
            within_creator_ceiling=False,  # permission > créateur
            within_factory_ceiling=False,
            within_environment_ceiling=True,
            uses_authorized_tools_only=False,  # outil non autorisé
        ),
        terminal_state=RuntimeTerminalState.CREATED,
    )
