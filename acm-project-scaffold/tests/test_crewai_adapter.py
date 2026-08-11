"""Tests de l'adaptateur CrewAI + équivalence inter-adaptateurs à trois voies.

Le test décisif du projet : un MÊME AgentSpec produit un verdict IDENTIQUE et
un digest IDENTIQUE via le stub déterministe, LangGraph ET CrewAI. C'est la
preuve mécanique que le paradigme ACM est indépendant du framework.
"""
from __future__ import annotations

import pytest

pytest.importorskip("crewai", reason="extra [crewai] non installé")

from acm import (
    digest_of_resolved_config,
    evaluate_runtime_instance,
    permission_check_from_spec,
    resolved_config_from_spec,
    traceability_from_spec,
)
from acm.models.enums import AssuranceState, EligibilityState, QualityState
from acm.models.refs import ACIRef
from acm.runtime.instance import DriftClassification, PermissionDrift
from acm.runtime.signal import RuntimeSignal, RuntimeTerminalState
from acm.runtime.spec import AgentSpec, PermissionCeiling
from adapters.crewai_adapter import CrewAIAdapter
from adapters.deterministic_stub import DeterministicStubAdapter
from adapters.langgraph_adapter import LangGraphAdapter


def _spec_conforming() -> AgentSpec:
    return AgentSpec(
        instance_id="rt:planner-001",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        factory_ref=ACIRef(id="aci:factory:f1", revision_id="01JF1"),
        creation_event_id="evt:001",
        prompt_ref=ACIRef(id="aci:prompt:planner", revision_id="01JR1"),
        model_ref=ACIRef(id="aci:model:gpt-5.4", revision_id="01JM1"),
        tool_refs=[ACIRef(id="aci:tool:web-search", revision_id="01JR1")],
        prompt_text="You are a planner.",
        tool_names=["web_search"],
        model_name="gpt-5.4",
        authorized_tools=["web_search"],
    )


def _spec_unauthorized() -> AgentSpec:
    return AgentSpec(
        instance_id="rt:rogue-001",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        factory_ref=None,
        creation_event_id=None,
        created_by_valid_factory=False,
        tool_names=["unauthorized_shell"],
        authorized_tools=["web_search"],
        tool_set_overridden=True,
        permissions_overridden=True,
        requested_permissions=["fs.write", "net.raw"],
        ceiling=PermissionCeiling(
            creator=["net.read"], factory=["net.read"], environment=["net.read"]
        ),
        model_name="gpt-5.4",
    )


def _stub_signal(spec: AgentSpec) -> RuntimeSignal:
    resolved = resolved_config_from_spec(spec)
    return RuntimeSignal(
        instance_id=spec.instance_id,
        definition_ref=spec.template_ref,
        resolved_config=resolved,
        resolved_config_digest=digest_of_resolved_config(resolved),
        traceability=traceability_from_spec(spec),
        permissions=permission_check_from_spec(spec),
        terminal_state=RuntimeTerminalState.CREATED,
    )


# --- Couche 1 CrewAI : construction + inspection ---

def test_crewai_builds_and_inspects_conforming():
    adapter = CrewAIAdapter(build_agent=True)
    sig = adapter.create_instance({"spec": _spec_conforming()})
    assert sig.adapter_name == "crewai"
    assert sig.traceability.is_traceable()
    assert not sig.resolved_config.has_behavioral_override()


def test_crewai_verdict_conforming():
    """§24.4 via CrewAI : partially_assessed / warning."""
    adapter = CrewAIAdapter(build_agent=True)
    sig = adapter.create_instance({"spec": _spec_conforming()})
    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.UNKNOWN
    assert v.effective_assurance == AssuranceState.PARTIALLY_ASSESSED
    assert v.eligibility_state == EligibilityState.WARNING


def test_crewai_verdict_unauthorized():
    """§24.5 via CrewAI : nok / unassessed / blocked + drifts."""
    adapter = CrewAIAdapter(build_agent=True)
    sig = adapter.create_instance({"spec": _spec_unauthorized()})
    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.NOK
    assert v.effective_assurance == AssuranceState.UNASSESSED
    assert v.eligibility_state == EligibilityState.BLOCKED
    assert v.drift_classification == DriftClassification.UNDECLARED_INSTANCE
    assert v.permission_drift == PermissionDrift.CRITICAL


def test_crewai_signal_carries_digest():
    sig = CrewAIAdapter().create_instance({"spec": _spec_conforming()})
    assert sig.resolved_config_digest is not None
    assert sig.resolved_config_digest == digest_of_resolved_config(
        resolved_config_from_spec(_spec_conforming())
    )


# --- Équivalence à TROIS voies (la thèse du projet) ---

def test_three_way_equivalence_conforming():
    """MÊME spec -> MÊME verdict via stub, LangGraph ET CrewAI."""
    spec = _spec_conforming()

    s = DeterministicStubAdapter().create_instance({"signal": _stub_signal(spec)})
    l = LangGraphAdapter().create_instance({"spec": spec})
    c = CrewAIAdapter().create_instance({"spec": spec})

    vs = evaluate_runtime_instance(s).model_dump(exclude={"instance_id"})
    vl = evaluate_runtime_instance(l).model_dump(exclude={"instance_id"})
    vc = evaluate_runtime_instance(c).model_dump(exclude={"instance_id"})

    assert vs == vl == vc


def test_three_way_equivalence_unauthorized():
    """Équivalence à trois voies sur le cas non autorisé."""
    spec = _spec_unauthorized()

    s = DeterministicStubAdapter().create_instance({"signal": _stub_signal(spec)})
    l = LangGraphAdapter().create_instance({"spec": spec})
    c = CrewAIAdapter().create_instance({"spec": spec})

    vs = evaluate_runtime_instance(s).model_dump(exclude={"instance_id"})
    vl = evaluate_runtime_instance(l).model_dump(exclude={"instance_id"})
    vc = evaluate_runtime_instance(c).model_dump(exclude={"instance_id"})

    assert vs == vl == vc


def test_three_way_digest_equality():
    """Même config résolue -> même digest, quel que soit l'adaptateur."""
    spec = _spec_conforming()

    s = DeterministicStubAdapter().create_instance({"signal": _stub_signal(spec)})
    l = LangGraphAdapter().create_instance({"spec": spec})
    c = CrewAIAdapter().create_instance({"spec": spec})

    assert s.resolved_config_digest == l.resolved_config_digest == c.resolved_config_digest


# --- Record / replay via CrewAI ---

def test_crewai_signal_record_replay():
    adapter = CrewAIAdapter()
    sig = adapter.create_instance({"spec": _spec_conforming()})
    record = sig.to_record()
    replayed = RuntimeSignal.from_record(record)
    assert evaluate_runtime_instance(replayed).eligibility_state == \
        evaluate_runtime_instance(sig).eligibility_state


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
