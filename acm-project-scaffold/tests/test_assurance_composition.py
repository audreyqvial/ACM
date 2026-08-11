"""Tests de la règle des trois cas d'assurance de composition (§16.2).

Ces tests verrouillent la correction clé : une composition n'hérite JAMAIS
automatiquement de l'assurance de ses enfants (non-transitivité, §10.5).
"""
from __future__ import annotations

from acm import ConfigurationGraph, PropagationContext, propagate
from acm.models.aci import AssurancePolicy
from acm.models.enums import AssuranceState, CompositionAssuranceMode
from scenarios import scenario_a

W1_KEY = "aci:workflow:report-pipeline@01JREV"


def _w1_assurance(graph, evidence) -> AssuranceState:
    report = propagate(graph, evidence, PropagationContext())
    for item in report.items.values():
        if item.ref.id == "aci:workflow:report-pipeline":
            return item.computed.effective_assurance
    raise AssertionError("W1 not found")


def test_hybrid_with_direct_evidence_is_assessed():
    """hybrid + preuve directe complète + dépendances assessed -> assessed."""
    graph, evidence = scenario_a.build()
    assert _w1_assurance(graph, evidence) == AssuranceState.ASSESSED


def test_hybrid_without_direct_evidence_is_not_assessed():
    """CŒUR DE LA CORRECTION : hybrid sans preuve directe propre, même si
    tous les enfants sont assessed, NE DOIT PAS être assessed."""
    graph, evidence = scenario_a.build()
    evidence = [e for e in evidence if e.target.id != "aci:workflow:report-pipeline"]
    result = _w1_assurance(graph, evidence)
    assert result != AssuranceState.ASSESSED
    assert result == AssuranceState.PARTIALLY_ASSESSED


def test_aggregate_only_with_deps_is_assessed():
    """aggregate_only : dépendances assessed suffisent, sans preuve directe."""
    graph, evidence = scenario_a.build()
    w1 = graph.revisions[W1_KEY]
    graph.revisions[W1_KEY] = w1.model_copy(update={"assurance_policy": AssurancePolicy(
        required_assurance_dimensions=[],
        composition_mode=CompositionAssuranceMode.AGGREGATE_ONLY,
    )})
    evidence = [e for e in evidence if e.target.id != "aci:workflow:report-pipeline"]
    assert _w1_assurance(graph, evidence) == AssuranceState.ASSESSED


def test_aggregate_only_without_deps_vacuity_guard():
    """aggregate_only sans AUCUNE dépendance -> unassessed (anti-vacuité)."""
    lone = scenario_a._validated_ok_assessed(
        "aci:workflow:empty", "workflow", CompositionAssuranceMode.AGGREGATE_ONLY
    ).model_copy(update={"assurance_policy": AssurancePolicy(
        required_assurance_dimensions=[],
        composition_mode=CompositionAssuranceMode.AGGREGATE_ONLY,
    )})
    graph = ConfigurationGraph.build([lone], [])
    report = propagate(graph, [], PropagationContext())
    item = next(iter(report.items.values()))
    assert item.computed.effective_assurance == AssuranceState.UNASSESSED


def test_vacuity_guard_can_be_explicitly_overridden():
    """allow_vacuous_assessment=True autorise l'assessment vide explicitement."""
    lone = scenario_a._validated_ok_assessed(
        "aci:workflow:empty2", "workflow", CompositionAssuranceMode.AGGREGATE_ONLY
    ).model_copy(update={"assurance_policy": AssurancePolicy(
        required_assurance_dimensions=[],
        composition_mode=CompositionAssuranceMode.AGGREGATE_ONLY,
        allow_vacuous_assessment=True,
    )})
    graph = ConfigurationGraph.build([lone], [])
    report = propagate(graph, [], PropagationContext())
    item = next(iter(report.items.values()))
    assert item.computed.effective_assurance == AssuranceState.ASSESSED


def test_partial_direct_coverage_is_partially_assessed():
    """Couverture directe incomplète -> partially_assessed."""
    graph, evidence = scenario_a.build()
    # La preuve de P1 ne couvre plus que 'functional', pas 'robustness'
    # (Evidence est immuable : on reconstruit la preuve concernée)
    evidence = [
        e.model_copy(update={"scope_dimensions": ["functional"]})
        if e.target.id == "aci:prompt:planner-system" else e
        for e in evidence
    ]
    report = propagate(graph, evidence, PropagationContext())
    p1 = next(i for i in report.items.values() if i.ref.id == "aci:prompt:planner-system")
    assert p1.computed.effective_assurance == AssuranceState.PARTIALLY_ASSESSED


if __name__ == "__main__":
    test_hybrid_with_direct_evidence_is_assessed()
    test_hybrid_without_direct_evidence_is_not_assessed()
    test_aggregate_only_with_deps_is_assessed()
    test_aggregate_only_without_deps_vacuity_guard()
    test_vacuity_guard_can_be_explicitly_overridden()
    test_partial_direct_coverage_is_partially_assessed()
    print("assurance composition: all assertions passed")
