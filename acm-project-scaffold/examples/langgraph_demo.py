"""Démo — exécution réelle du pipeline via l'adaptateur LangGraph + gpt-5.4.

Usage :
    export OPENAI_API_KEY=sk-...
    PYTHONPATH=. python examples/langgraph_demo.py

Cette démo construit un AgentSpec conforme (le planner du use case), l'exécute
réellement avec gpt-5.4 via LangGraph, enregistre le RuntimeSignal en JSON
(record), puis fait évaluer ce signal par le cœur ACM.

Le même signal figé pourra ensuite être rejoué dans les tests SANS clé API.
"""
from __future__ import annotations

import os

from langchain_core.messages import HumanMessage

from acm import evaluate_runtime_instance
from acm.models.refs import ACIRef
from acm.runtime.signal import RuntimeSignal
from acm.runtime.spec import AgentSpec
from adapters.langgraph_adapter import LangGraphAdapter

RECORD_PATH = "examples/records/recorded_run_langgraph.json"


def build_spec() -> AgentSpec:
    return AgentSpec(
        instance_id="rt:planner-demo-001",
        template_ref=ACIRef(id="aci:template:planner", revision_id="01JT1"),
        factory_ref=ACIRef(id="aci:factory:agent-factory", revision_id="01JF1"),
        creation_event_id="evt:demo:001",
        prompt_ref=ACIRef(id="aci:prompt:planner-system", revision_id="01JR1"),
        model_ref=ACIRef(id="aci:model:gpt-5.4", revision_id="01JM1"),
        prompt_text="You are a concise trip planner. Answer in one sentence.",
        model_name="gpt-5.4",
        authorized_tools=[],
    ).with_ref_digests()


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Definir OPENAI_API_KEY pour lancer la demo reelle.")

    adapter = LangGraphAdapter()  # modele OpenAI par defaut (gpt-5.4)
    spec = build_spec()
    os.makedirs(os.path.dirname(RECORD_PATH), exist_ok=True)

    print(">> Execution reelle via LangGraph + gpt-5.4 ...")
    signal = adapter.execute(
        {"spec": spec},
        inputs={"messages": [HumanMessage(content="Plan a 2-day trip to Lisbon.")]},
        record_path=RECORD_PATH,
    )
    print(f"   terminal_state = {signal.terminal_state.value}")
    print(f"   signal enregistre -> {RECORD_PATH}")

    verdict = evaluate_runtime_instance(signal)
    print("\n>> Verdict de gouvernance (cceur ACM) :")
    print(f"   promotion   = {verdict.promotion_state.value}")
    print(f"   quality     = {verdict.quality_state.value}")
    print(f"   assurance   = {verdict.effective_assurance.value}")
    print(f"   eligibility = {verdict.eligibility_state.value}")

    print("\n>> Rejeu du signal fige (sans reexecution) :")
    import json
    with open(RECORD_PATH, encoding="utf-8") as fh:
        replayed = RuntimeSignal.from_record(json.load(fh))
    v2 = evaluate_runtime_instance(replayed)
    print(f"   eligibility (rejeu) = {v2.eligibility_state.value}")


if __name__ == "__main__":
    main()
