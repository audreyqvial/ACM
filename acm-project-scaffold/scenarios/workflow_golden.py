# Emplacement : scenarios/workflow_golden.py
"""Golden oracles des workflows non triviaux (étape 3 des notes de conception).

Représentations ACM canoniques attendues, définies MANUELLEMENT, contre
lesquelles l'extraction est validée. Deux workflows d'intention fonctionnelle
équivalente mais exprimés dans les abstractions natives de chaque framework.

Topologie commune (intention abstraite) :

    entry → router ──cond A──▶ researcher → reviewer ──▶ finalizer → end
                    └─cond B──▶ direct_responder ───────────────▶ end
                    (boucle bornée reviewer → researcher tolérée)
"""
from __future__ import annotations

from harness.workflow_ir import (
    EdgeKind,
    ExtractionStatus,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
)


def golden_langgraph() -> WorkflowIR:
    """Golden ACM attendu pour le workflow LangGraph (branche conditionnelle)."""
    nodes = [
        WorkflowNode("entry", NodeKind.ENTRY),
        WorkflowNode("router", NodeKind.ROUTER),
        WorkflowNode("researcher", NodeKind.AGENT,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
        WorkflowNode("reviewer", NodeKind.AGENT,
                     agent_ref="aci:agent:reviewer",
                     prompt_ref="aci:prompt:review",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("direct_responder", NodeKind.AGENT,
                     agent_ref="aci:agent:direct",
                     prompt_ref="aci:prompt:direct",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("finalizer", NodeKind.AGENT,
                     agent_ref="aci:agent:finalizer",
                     prompt_ref="aci:prompt:finalize",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("end", NodeKind.TERMINAL),
    ]
    edges = [
        WorkflowEdge("entry", "router", EdgeKind.DIRECT),
        # Branche conditionnelle depuis le router (condition opaque).
        WorkflowEdge("router", "researcher", EdgeKind.CONDITIONAL,
                     condition_label="route_after_router",
                     condition_semantics="opaque",
                     possible_targets=["researcher", "direct_responder"]),
        WorkflowEdge("router", "direct_responder", EdgeKind.CONDITIONAL,
                     condition_label="route_after_router",
                     condition_semantics="opaque",
                     possible_targets=["researcher", "direct_responder"]),
        WorkflowEdge("researcher", "reviewer", EdgeKind.DIRECT),
        # Boucle bornée reviewer → researcher (arête conditionnelle).
        WorkflowEdge("reviewer", "researcher", EdgeKind.CONDITIONAL,
                     condition_label="needs_more_research",
                     condition_semantics="opaque",
                     possible_targets=["researcher", "finalizer"]),
        WorkflowEdge("reviewer", "finalizer", EdgeKind.CONDITIONAL,
                     condition_label="needs_more_research",
                     condition_semantics="opaque",
                     possible_targets=["researcher", "finalizer"]),
        WorkflowEdge("finalizer", "end", EdgeKind.DIRECT),
        WorkflowEdge("direct_responder", "end", EdgeKind.DIRECT),
    ]
    return WorkflowIR(
        workflow_id="wf:research-pipeline",
        framework="golden",
        nodes=nodes,
        edges=edges,
        entry_nodes=["entry"],
        terminal_nodes=["end"],
        state_schema_keys=["messages", "route", "research_notes", "review_verdict"],
    )


def golden_crewai_flow() -> WorkflowIR:
    """Golden ACM attendu pour le CrewAI FLOW non trivial (équivalent LangGraph).

    Topologie :
        flow_begin (entry)
          → flow_route_request (router) ─cond─▶ {research | direct}
             ├─ flow_run_research_crew  → flow_finish_from_research (terminal)
             └─ flow_run_direct_task    → flow_finish_from_direct   (terminal)
    """
    nodes = [
        WorkflowNode("flow_begin", NodeKind.ENTRY),
        WorkflowNode("flow_route_request", NodeKind.ROUTER),
        WorkflowNode("flow_run_research_crew", NodeKind.AGENT,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
        WorkflowNode("flow_run_direct_task", NodeKind.AGENT,
                     agent_ref="aci:agent:direct",
                     prompt_ref="aci:prompt:direct",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("flow_finish_from_research", NodeKind.TERMINAL),
        WorkflowNode("flow_finish_from_direct", NodeKind.TERMINAL),
    ]
    edges = [
        WorkflowEdge("flow_begin", "flow_route_request", EdgeKind.DIRECT),
        WorkflowEdge("flow_route_request", "flow_run_research_crew", EdgeKind.CONDITIONAL,
                     condition_label="research", condition_semantics="opaque",
                     possible_targets=["direct", "research"]),
        WorkflowEdge("flow_route_request", "flow_run_direct_task", EdgeKind.CONDITIONAL,
                     condition_label="direct", condition_semantics="opaque",
                     possible_targets=["direct", "research"]),
        WorkflowEdge("flow_run_research_crew", "flow_finish_from_research", EdgeKind.DIRECT),
        WorkflowEdge("flow_run_direct_task", "flow_finish_from_direct", EdgeKind.DIRECT),
    ]
    return WorkflowIR(
        workflow_id="wf:research-flow",
        framework="golden",
        nodes=nodes,
        edges=edges,
        entry_nodes=["flow_begin"],
        terminal_nodes=["flow_finish_from_direct", "flow_finish_from_research"],
        state_schema_keys=["request", "route", "research_output", "direct_output",
                           "final_output"],
    )


def golden_crewai_flow_plus_crew() -> WorkflowIR:
    """Golden ACM attendu pour l'extraction Flow+Crew fusionnée.

    Superpose deux vues d'un même système CrewAI : la topologie du Flow (start,
    router, branches, terminaisons) ET les composants du Research Crew (tâches +
    dépendances de contexte). Les deux vues coexistent sans être reliées entre
    elles — le Flow orchestre, le Crew détaille la branche recherche.

    Correspond à extract_flow(..., include_crew=True).
    """
    # Partie Flow (identique à golden_crewai_flow).
    flow = golden_crewai_flow()
    nodes = list(flow.nodes)
    edges = list(flow.edges)

    # Partie Crew fusionnée : les trois tâches + dépendances de contexte.
    nodes += [
        WorkflowNode("task_research", NodeKind.TASK,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
        WorkflowNode("task_review", NodeKind.TASK,
                     agent_ref="aci:agent:reviewer",
                     prompt_ref="aci:prompt:review",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("task_finalize", NodeKind.TASK,
                     agent_ref="aci:agent:finalizer",
                     prompt_ref="aci:prompt:finalize",
                     model_ref="aci:model:shared-llm"),
    ]
    edges += [
        WorkflowEdge("task_research", "task_review", EdgeKind.CONTEXT_DEPENDENCY),
        WorkflowEdge("task_review", "task_finalize", EdgeKind.CONTEXT_DEPENDENCY),
    ]
    return WorkflowIR(
        workflow_id="wf:research-flow-full",
        framework="golden",
        nodes=nodes,
        edges=edges,
        entry_nodes=["flow_begin"],
        # Terminaisons du Flow + la dernière tâche du Crew (sans successeur).
        terminal_nodes=["flow_finish_from_direct", "flow_finish_from_research",
                        "task_finalize"],
        state_schema_keys=["request", "route", "research_output", "direct_output",
                           "final_output"],
    )


def golden_openai_agent() -> WorkflowIR:
    """Golden ACM attendu pour un Agent OpenAI SDK ISOLÉ (mono-nœud).

    Un agent seul n'a pas de topologie : un unique nœud AGENT, à la fois entrée
    et terminaison. Ses outils/refs viennent des métadonnées declared_by_adapter.
    Symétrique de golden_crewai() mono, mais réduit à un seul agent (le
    researcher, qui porte un outil, pour couvrir agent_tool_refs).

    Correspond à extract_agent(build_native_openai_agent()).
    """
    nodes = [
        WorkflowNode("agent_researcher", NodeKind.AGENT,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
    ]
    return WorkflowIR(
        workflow_id="wf:research-agent",
        framework="golden",
        nodes=nodes,
        edges=[],
        entry_nodes=["agent_researcher"],
        terminal_nodes=["agent_researcher"],
        state_schema_keys=[],
    )


def golden_openai_agent_graph() -> WorkflowIR:
    """Golden ACM attendu pour le graphe de handoffs OpenAI SDK (topologie).

    Le SDK exprime la délégation par `agent.handoffs`, introspectable — les
    arêtes sont donc EXTRAITES (pas déclarées), à la différence du CrewAI Flow.

    Topologie (triage délègue vers deux spécialistes, dont un pipeline) :

        agent_triage (entry)
          ├─ handoff ─▶ agent_researcher ─ handoff ─▶ agent_reviewer
          │                                             └─ handoff ─▶ agent_finalizer (terminal)
          └─ handoff ─▶ agent_direct (terminal)

    Correspond à extract_agent_graph(build_native_openai_agent_graph()).
    """
    nodes = [
        WorkflowNode("agent_triage", NodeKind.AGENT,
                     agent_ref="aci:agent:triage",
                     prompt_ref="aci:prompt:triage",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("agent_researcher", NodeKind.AGENT,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
        WorkflowNode("agent_reviewer", NodeKind.AGENT,
                     agent_ref="aci:agent:reviewer",
                     prompt_ref="aci:prompt:review",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("agent_finalizer", NodeKind.AGENT,
                     agent_ref="aci:agent:finalizer",
                     prompt_ref="aci:prompt:finalize",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("agent_direct", NodeKind.AGENT,
                     agent_ref="aci:agent:direct",
                     prompt_ref="aci:prompt:direct",
                     model_ref="aci:model:shared-llm"),
    ]
    edges = [
        WorkflowEdge("agent_triage", "agent_researcher", EdgeKind.DIRECT),
        WorkflowEdge("agent_triage", "agent_direct", EdgeKind.DIRECT),
        WorkflowEdge("agent_researcher", "agent_reviewer", EdgeKind.DIRECT),
        WorkflowEdge("agent_reviewer", "agent_finalizer", EdgeKind.DIRECT),
    ]
    return WorkflowIR(
        workflow_id="wf:research-agent-graph",
        framework="golden",
        nodes=nodes,
        edges=edges,
        entry_nodes=["agent_triage"],
        terminal_nodes=["agent_direct", "agent_finalizer"],
        state_schema_keys=[],
    )


def golden_crewai() -> WorkflowIR:
    """Golden ACM attendu pour un CREW séquentiel (Crew-only).

    Un Crew séquentiel n'a PAS de topologie de Flow : ni entrée/sortie de flow,
    ni router, ni branche conditionnelle. Il a des tâches reliées par des
    dépendances de contexte (Task.context). L'entrée est la première tâche (sans
    dépendance amont), le terminal la dernière (sans dépendant aval).

    Correspond à extract_crew(build_native_crewai()).
    """
    nodes = [
        WorkflowNode("task_research", NodeKind.TASK,
                     agent_ref="aci:agent:researcher",
                     prompt_ref="aci:prompt:research",
                     model_ref="aci:model:shared-llm",
                     tool_refs=["aci:tool:web-search"]),
        WorkflowNode("task_review", NodeKind.TASK,
                     agent_ref="aci:agent:reviewer",
                     prompt_ref="aci:prompt:review",
                     model_ref="aci:model:shared-llm"),
        WorkflowNode("task_finalize", NodeKind.TASK,
                     agent_ref="aci:agent:finalizer",
                     prompt_ref="aci:prompt:finalize",
                     model_ref="aci:model:shared-llm"),
    ]
    edges = [
        # Dépendances de contexte entre tâches (CrewAI natif).
        WorkflowEdge("task_research", "task_review", EdgeKind.CONTEXT_DEPENDENCY),
        WorkflowEdge("task_review", "task_finalize", EdgeKind.CONTEXT_DEPENDENCY),
    ]
    return WorkflowIR(
        workflow_id="wf:research-pipeline",
        framework="golden",
        nodes=nodes,
        edges=edges,
        # Entrée = première tâche, terminal = dernière (inférés du contexte).
        entry_nodes=["task_research"],
        terminal_nodes=["task_finalize"],
        state_schema_keys=[],
    )
