# Emplacement : scenarios/native_workflows.py
"""Constructeurs de workflows natifs LangGraph/CrewAI non triviaux (vague 1.b).

Factorise la construction des vrais workflows framework pour qu'ils soient
partagés entre les tests (tests/test_workflow_extractors_native.py) et le
générateur d'Information Preservation Report (generate_preservation_report.py).

À N'UTILISER que dans un environnement où les frameworks sont installés :
chaque fonction importe son framework à l'appel et lève ImportError sinon.

IMPORTANT — WorkflowState est défini au niveau MODULE, sans
`from __future__ import annotations`, pour que get_type_hints() de LangGraph
résolve correctement l'annotation Annotated (piège des annotations différées).
"""
from typing import Annotated, TypedDict


def _merge_lists(a, b):
    return a + b


class WorkflowState(TypedDict):
    messages: Annotated[list, _merge_lists]
    route: str
    research_notes: str
    review_verdict: str


# Mapping node → références ACM (non introspectable : declared_by_adapter).
LANGGRAPH_METADATA = {
    "researcher": {"agent_ref": "aci:agent:researcher", "prompt_ref": "aci:prompt:research",
                   "model_ref": "aci:model:shared-llm", "tool_refs": ["aci:tool:web-search"]},
    "reviewer": {"agent_ref": "aci:agent:reviewer", "prompt_ref": "aci:prompt:review",
                 "model_ref": "aci:model:shared-llm"},
    "direct_responder": {"agent_ref": "aci:agent:direct", "prompt_ref": "aci:prompt:direct",
                         "model_ref": "aci:model:shared-llm"},
    "finalizer": {"agent_ref": "aci:agent:finalizer", "prompt_ref": "aci:prompt:finalize",
                  "model_ref": "aci:model:shared-llm"},
}

CREWAI_METADATA = {
    "researcher": {"agent_ref": "aci:agent:researcher", "prompt_ref": "aci:prompt:research",
                   "model_ref": "aci:model:shared-llm", "tool_refs": ["aci:tool:web-search"]},
    "reviewer": {"agent_ref": "aci:agent:reviewer", "prompt_ref": "aci:prompt:review",
                 "model_ref": "aci:model:shared-llm"},
    "finalizer": {"agent_ref": "aci:agent:finalizer", "prompt_ref": "aci:prompt:finalize",
                  "model_ref": "aci:model:shared-llm"},
}

LANGGRAPH_STATE_KEYS = ["messages", "route", "research_notes", "review_verdict"]


def build_native_langgraph():
    """Construit un vrai StateGraph LangGraph non trivial (branche conditionnelle).

    Topologie : entry → router ─cond─▶ {researcher→reviewer→finalizer | direct} → end
    avec boucle bornée reviewer → researcher. Lève ImportError si langgraph absent.
    """
    from langgraph.graph import END, START, StateGraph

    def router(state): return state
    def researcher(state): return state
    def reviewer(state): return state
    def direct_responder(state): return state
    def finalizer(state): return state

    def route_after_router(state) -> str:
        return "researcher" if state.get("route") == "deep" else "direct_responder"

    def needs_more_research(state) -> str:
        return "researcher" if state.get("review_verdict") == "insufficient" else "finalizer"

    builder = StateGraph(WorkflowState)
    builder.add_node("router", router)
    builder.add_node("researcher", researcher)
    builder.add_node("reviewer", reviewer)
    builder.add_node("direct_responder", direct_responder)
    builder.add_node("finalizer", finalizer)

    builder.add_edge(START, "router")
    builder.add_conditional_edges("router", route_after_router,
                                  {"researcher": "researcher",
                                   "direct_responder": "direct_responder"})
    builder.add_edge("researcher", "reviewer")
    builder.add_conditional_edges("reviewer", needs_more_research,
                                  {"researcher": "researcher",
                                   "finalizer": "finalizer"})
    builder.add_edge("finalizer", END)
    builder.add_edge("direct_responder", END)
    return builder.compile()


def build_native_crewai():
    """Construit un vrai Crew CrewAI non trivial (dépendances de tâches).

    Lève ImportError si crewai absent.
    """
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(role="researcher", goal="Research the topic",
                       backstory="Expert researcher", allow_delegation=False)
    reviewer = Agent(role="reviewer", goal="Review the research",
                     backstory="Critical reviewer", allow_delegation=False)
    finalizer = Agent(role="finalizer", goal="Finalize the output",
                      backstory="Editor", allow_delegation=False)

    t_research = Task(description="Research", expected_output="Notes", agent=researcher)
    t_review = Task(description="Review", expected_output="Verdict", agent=reviewer,
                    context=[t_research])
    t_finalize = Task(description="Finalize", expected_output="Report", agent=finalizer,
                      context=[t_review])

    return Crew(agents=[researcher, reviewer, finalizer],
                tasks=[t_research, t_review, t_finalize],
                process=Process.sequential)


def build_research_crew():
    """Le Research Crew réutilisé par le Flow (researcher → reviewer → finalizer)."""
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(role="researcher", goal="Research the topic",
                       backstory="Expert researcher", allow_delegation=False)
    reviewer = Agent(role="reviewer", goal="Review the research",
                     backstory="Critical reviewer", allow_delegation=False)
    finalizer = Agent(role="finalizer", goal="Finalize the output",
                      backstory="Editor", allow_delegation=False)

    t_research = Task(description="Research", expected_output="Notes", agent=researcher)
    t_review = Task(description="Review", expected_output="Verdict", agent=reviewer,
                    context=[t_research])
    t_finalize = Task(description="Finalize", expected_output="Report", agent=finalizer,
                      context=[t_review])

    return Crew(agents=[researcher, reviewer, finalizer],
                tasks=[t_research, t_review, t_finalize],
                process=Process.sequential)


def build_native_crewai_flow():
    """Construit un vrai CrewAI Flow non trivial, équivalent au LangGraph.

    Topologie :
        start (begin)
          → router (route_request) ── "research" / "direct"
             ├─ research crew (researcher → reviewer → finalizer)   [branche A]
             └─ direct task                                          [branche B]
          → end (finish)

    Idiome standard et introspectable : @start → @router (retourne un label) →
    @listen(label) sur chaque branche, convergence via @listen sur les deux
    branches. Lève ImportError si crewai absent.
    """
    from crewai import Agent, Task
    from crewai.flow.flow import Flow, listen, router, start
    from pydantic import BaseModel

    class ResearchFlowState(BaseModel):
        request: str = ""
        route: str = ""
        research_output: str = ""
        direct_output: str = ""
        final_output: str = ""

    class ResearchFlow(Flow[ResearchFlowState]):

        def __init__(self):
            super().__init__()
            # Le Research Crew est stocké comme attribut d'instance (idiome
            # CrewAI courant) → introspectable par l'extracteur (status=extracted).
            self.research_crew = build_research_crew()

        @start()
        def begin(self):
            # Point d'entrée : prépare la requête.
            return self.state.request

        @router(begin)
        def route_request(self):
            # Décision de routage (sémantique opaque du point de vue ACM).
            return "research" if self.state.route == "deep" else "direct"

        @listen("research")
        def run_research_crew(self):
            # Branche A : le Research Crew (researcher → reviewer → finalizer).
            self.state.research_output = "research-done"
            return "research-done"

        @listen("direct")
        def run_direct_task(self):
            # Branche B : réponse directe (un seul agent).
            direct_agent = Agent(role="direct", goal="Answer directly",
                                 backstory="Fast responder", allow_delegation=False)
            self.state.direct_output = "direct-done"
            return "direct-done"

        @listen(run_research_crew)
        def finish_from_research(self):
            # Terminaison identifiable depuis la branche recherche.
            self.state.final_output = self.state.research_output
            return self.state.final_output

        @listen(run_direct_task)
        def finish_from_direct(self):
            # Terminaison identifiable depuis la branche directe.
            self.state.final_output = self.state.direct_output
            return self.state.final_output

    return ResearchFlow()


# --------------------------------------------------------------------------
# OpenAI Agents SDK — Agent seul et graphe de handoffs.
# --------------------------------------------------------------------------

# Mapping agent.name → références ACM (non introspectable : declared_by_adapter).
OPENAI_AGENTS_METADATA = {
    "triage": {"agent_ref": "aci:agent:triage", "prompt_ref": "aci:prompt:triage",
               "model_ref": "aci:model:shared-llm"},
    "researcher": {"agent_ref": "aci:agent:researcher", "prompt_ref": "aci:prompt:research",
                   "model_ref": "aci:model:shared-llm", "tool_refs": ["aci:tool:web-search"]},
    "reviewer": {"agent_ref": "aci:agent:reviewer", "prompt_ref": "aci:prompt:review",
                 "model_ref": "aci:model:shared-llm"},
    "finalizer": {"agent_ref": "aci:agent:finalizer", "prompt_ref": "aci:prompt:finalize",
                  "model_ref": "aci:model:shared-llm"},
    "direct": {"agent_ref": "aci:agent:direct", "prompt_ref": "aci:prompt:direct",
               "model_ref": "aci:model:shared-llm"},
}


def _stub_web_search(query: str) -> str:
    """Outil-fonction minimal pour peupler agent.tools (non exécuté en extraction)."""
    return "results"


def build_native_openai_agent():
    """Construit un `agents.Agent` OpenAI SDK ISOLÉ (researcher avec un outil).

    Un seul agent, un outil attaché (web_search), pas de handoff. Symétrique
    mono-agent. Lève ImportError si openai-agents absent.
    """
    from agents import Agent, function_tool

    web_search = function_tool(_stub_web_search)
    return Agent(
        name="researcher",
        instructions="Research the topic thoroughly.",
        model="gpt-5.4",
        tools=[web_search],
    )


def build_native_openai_agent_graph():
    """Construit un graphe de handoffs OpenAI SDK non trivial.

    Topologie (introspectable via agent.handoffs) :
        triage → {researcher → reviewer → finalizer | direct}

    Le triage délègue soit vers le pipeline de recherche (researcher, qui
    délègue au reviewer, qui délègue au finalizer), soit vers l'agent direct.
    Lève ImportError si openai-agents absent.
    """
    from agents import Agent, function_tool

    web_search = function_tool(_stub_web_search)

    finalizer = Agent(name="finalizer",
                      instructions="Finalize the output.", model="gpt-5.4")
    reviewer = Agent(name="reviewer", instructions="Review the research.",
                     model="gpt-5.4", handoffs=[finalizer])
    researcher = Agent(name="researcher", instructions="Research the topic.",
                       model="gpt-5.4", tools=[web_search], handoffs=[reviewer])
    direct = Agent(name="direct", instructions="Answer directly.", model="gpt-5.4")
    triage = Agent(name="triage", instructions="Route the request.",
                   model="gpt-5.4", handoffs=[researcher, direct])
    return triage


# Métadonnées ACM pour le Flow : mapping method/branche → références ACI.
# Non introspectable (le Flow ne connaît que des méthodes Python) →
# declared_by_adapter.
CREWAI_FLOW_METADATA = {
    "run_research_crew": {"agent_ref": "aci:agent:researcher",
                          "prompt_ref": "aci:prompt:research",
                          "model_ref": "aci:model:shared-llm",
                          "tool_refs": ["aci:tool:web-search"]},
    "run_direct_task": {"agent_ref": "aci:agent:direct",
                        "prompt_ref": "aci:prompt:direct",
                        "model_ref": "aci:model:shared-llm"},
}

# Arêtes du Flow DÉCLARÉES : la topologie (@router/@listen) n'étant pas
# introspectable statiquement dans les versions récentes de CrewAI (résolue à
# l'exécution), les connexions sont fournies explicitement. Marquées
# declared_by_adapter par l'extracteur. Reflète la structure de
# build_native_crewai_flow().
CREWAI_FLOW_EDGES = [
    {"source": "flow_begin", "target": "flow_route_request", "kind": "direct"},
    {"source": "flow_route_request", "target": "flow_run_research_crew",
     "kind": "conditional", "condition_label": "research",
     "possible_targets": ["research", "direct"]},
    {"source": "flow_route_request", "target": "flow_run_direct_task",
     "kind": "conditional", "condition_label": "direct",
     "possible_targets": ["research", "direct"]},
    {"source": "flow_run_research_crew", "target": "flow_finish_from_research",
     "kind": "direct"},
    {"source": "flow_run_direct_task", "target": "flow_finish_from_direct",
     "kind": "direct"},
]
