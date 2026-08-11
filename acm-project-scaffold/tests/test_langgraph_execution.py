"""Tests couche 2 de l'adaptateur LangGraph — exécution + record/replay.

Utilise un model_factory mock (FakeListChatModel) : aucune clé API requise,
donc exécutable en CI. Le chemin d'exécution réel avec gpt-5.4 est identique ;
seul le modèle injecté change (démo dans examples/langgraph_demo.py).
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain_core", reason="extra [langgraph] non installé")

import json
import os
import tempfile

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from acm import evaluate_runtime_instance
from acm.models.enums import AssuranceState, EligibilityState, QualityState
from acm.models.refs import ACIRef
from acm.runtime.signal import RuntimeSignal, RuntimeTerminalState
from acm.runtime.spec import AgentSpec
from adapters.langgraph_adapter import LangGraphAdapter


def _mock_factory(name: str):
    return FakeListChatModel(responses=["Plan: step 1, step 2."])


def _spec() -> AgentSpec:
    return AgentSpec(
        instance_id="rt:planner-exec-001",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        factory_ref=ACIRef(id="aci:factory:f1", revision_id="01JF1"),
        creation_event_id="evt:exec:001",
        prompt_ref=ACIRef(id="aci:prompt:planner", revision_id="01JR1"),
        model_ref=ACIRef(id="aci:model:gpt-5.4", revision_id="01JM1"),
        prompt_text="You are a planner.",
        model_name="gpt-5.4",
    )


def test_execute_completes_and_elevates():
    """Exécution réussie -> terminal completed, instance conforme élevée."""
    adapter = LangGraphAdapter(model_factory=_mock_factory)
    sig = adapter.execute(
        {"spec": _spec()},
        inputs={"messages": [HumanMessage(content="Plan a trip.")]},
    )
    assert sig.terminal_state == RuntimeTerminalState.COMPLETED
    assert sig.runtime_checks_completed and sig.runtime_checks_passed

    v = evaluate_runtime_instance(sig)
    assert v.quality_state == QualityState.OK
    assert v.effective_assurance == AssuranceState.ASSESSED
    assert v.eligibility_state == EligibilityState.ELIGIBLE


def test_execute_failure_marks_failed():
    """Un modèle qui lève -> terminal failed, pas d'élévation."""
    def broken_factory(name: str):
        class _Broken:
            def invoke(self, *a, **k):
                raise RuntimeError("boom")
        return _Broken()

    adapter = LangGraphAdapter(model_factory=broken_factory)
    sig = adapter.execute({"spec": _spec()}, inputs={"messages": []})
    assert sig.terminal_state == RuntimeTerminalState.FAILED
    assert not sig.runtime_checks_passed


def test_record_then_replay_identical():
    """Un run figé en JSON se rejoue à l'identique (record/replay)."""
    adapter = LangGraphAdapter(model_factory=_mock_factory)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "run.json")
        sig = adapter.execute(
            {"spec": _spec()},
            inputs={"messages": [HumanMessage(content="Plan.")]},
            record_path=path,
        )
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as fh:
            replayed = RuntimeSignal.from_record(json.load(fh))

    assert evaluate_runtime_instance(replayed).eligibility_state == \
        evaluate_runtime_instance(sig).eligibility_state


def test_llm_content_does_not_leak_into_signal():
    """La réponse LLM ne traverse PAS la frontière : le signal ne contient
    aucun champ de contenu métier, seulement la gouvernance."""
    adapter = LangGraphAdapter(model_factory=_mock_factory)
    sig = adapter.execute({"spec": _spec()}, inputs={"messages": []})
    dumped = sig.model_dump_json()
    assert "step 1" not in dumped  # la réponse du modèle n'est pas dans le signal


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
