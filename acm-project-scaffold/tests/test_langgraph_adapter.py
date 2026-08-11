"""Tests de l'adaptateur LangGraph — couche 1 (construire + inspecter).

Point clé : le MÊME AgentSpec, passé au stub déterministe et à l'adaptateur
LangGraph, produit un verdict de gouvernance IDENTIQUE. C'est la démonstration
que le paradigme ACM est indépendant du framework — la thèse du projet.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langgraph", reason="extra [langgraph] non installé")

from acm import evaluate_runtime_instance
from acm.models.enums import (
    AssuranceState,
    EligibilityState,
    QualityState,
)
from acm.runtime.governance import (
    permission_check_from_spec,
    resolved_config_from_spec,
    traceability_from_spec,
)
from acm.runtime.instance import DriftClassification, PermissionDrift
from acm.runtime.signal import RuntimeSignal, RuntimeTerminalState
from acm.runtime.spec import AgentSpec, PermissionCeiling
from acm.models.refs import ACIRef
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


def _spec_to_stub_signal(spec: AgentSpec) -> RuntimeSignal:
    """Traduit un AgentSpec en RuntimeSignal via les helpers de gouvernance,
    tel que le stub le recevrait (référence pour l'équivalence)."""
    from acm.runtime.governance import digest_of_resolved_config
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


# --- Couche 1 : construction + inspection ---

def test_langgraph_builds_and_inspects_conforming():
    adapter = LangGraphAdapter(build_graph=True)
    sig = adapter.create_instance({"spec": _spec_conforming()})
    # La construction ne doit PAS avoir échoué
    assert sig.adapter_name == "langgraph"
    assert sig.traceability.is_traceable()
    assert not sig.resolved_config.has_behavioral_override()


def test_langgraph_verdict_conforming():
    """§24.4 via LangGraph : partially_assessed / warning."""
    adapter = LangGraphAdapter(build_graph=True)
    sig = adapter.create_instance({"spec": _spec_conforming()})
    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.UNKNOWN
    assert v.effective_assurance == AssuranceState.PARTIALLY_ASSESSED
    assert v.eligibility_state == EligibilityState.WARNING


def test_langgraph_verdict_unauthorized():
    """§24.5 via LangGraph : nok / unassessed / blocked + drifts."""
    adapter = LangGraphAdapter(build_graph=True)
    sig = adapter.create_instance({"spec": _spec_unauthorized()})
    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.NOK
    assert v.effective_assurance == AssuranceState.UNASSESSED
    assert v.eligibility_state == EligibilityState.BLOCKED
    assert v.drift_classification == DriftClassification.UNDECLARED_INSTANCE
    assert v.permission_drift == PermissionDrift.CRITICAL


def test_build_graph_false_still_produces_signal():
    """Sans construire le graphe, le signal de gouvernance reste produit."""
    adapter = LangGraphAdapter(build_graph=False)
    sig = adapter.create_instance({"spec": _spec_conforming()})
    v = evaluate_runtime_instance(sig)
    assert v.eligibility_state == EligibilityState.WARNING


# --- Équivalence inter-adaptateurs (la thèse du projet) ---

def test_stub_and_langgraph_equivalent_conforming():
    """MÊME spec -> MÊME verdict, via stub et via LangGraph."""
    spec = _spec_conforming()

    stub_sig = DeterministicStubAdapter().create_instance(
        {"signal": _spec_to_stub_signal(spec)}
    )
    lg_sig = LangGraphAdapter().create_instance({"spec": spec})

    v_stub = evaluate_runtime_instance(stub_sig)
    v_lg = evaluate_runtime_instance(lg_sig)

    assert v_stub.quality_state == v_lg.quality_state
    assert v_stub.effective_assurance == v_lg.effective_assurance
    assert v_stub.eligibility_state == v_lg.eligibility_state
    assert v_stub.drift_classification == v_lg.drift_classification
    # Même config -> même digest, quel que soit l'adaptateur
    assert stub_sig.resolved_config_digest == lg_sig.resolved_config_digest


def test_stub_and_langgraph_equivalent_unauthorized():
    """Équivalence aussi sur le cas non autorisé."""
    spec = _spec_unauthorized()

    stub_sig = DeterministicStubAdapter().create_instance(
        {"signal": _spec_to_stub_signal(spec)}
    )
    lg_sig = LangGraphAdapter().create_instance({"spec": spec})

    v_stub = evaluate_runtime_instance(stub_sig)
    v_lg = evaluate_runtime_instance(lg_sig)

    assert v_stub.model_dump(exclude={"instance_id"}) == \
        v_lg.model_dump(exclude={"instance_id"})


# --- Record / replay via l'adaptateur LangGraph ---

def test_langgraph_signal_record_replay():
    """Le signal produit par LangGraph est enregistrable et rejouable."""
    adapter = LangGraphAdapter()
    sig = adapter.create_instance({"spec": _spec_conforming()})

    record = sig.to_record()
    replayed = RuntimeSignal.from_record(record)

    assert evaluate_runtime_instance(replayed).eligibility_state == \
        evaluate_runtime_instance(sig).eligibility_state


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
