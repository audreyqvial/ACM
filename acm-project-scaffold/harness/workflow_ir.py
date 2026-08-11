# Emplacement : harness/workflow_ir.py
"""Représentation intermédiaire canonique d'un workflow (l'objet A de E:F→A).

C'est la cible de l'extraction : une forme ACM canonique, framework-indépendante,
d'un workflow natif. Elle capture ce qui appartient au PÉRIMÈTRE NORMATIF d'ACM —
topologie, identité des composants, dépendances, références, provenance, limites
d'extraction — sans prétendre représenter la logique Python arbitraire.

Chaque élément porte un `extraction_status` (§ notes de conception) :
  - extracted          : lu directement depuis l'objet natif ;
  - declared_by_adapter: fourni par métadonnées explicites (non introspectable) ;
  - unresolved         : présent mais non reconstructible (closure, condition
                         opaque, prompt dynamique…).

La représentation est CANONIQUE : sérialisation triée, indépendante des UUID et
timestamps, pour permettre la comparaison à un golden oracle.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExtractionStatus(str, Enum):
    EXTRACTED = "extracted"
    DECLARED_BY_ADAPTER = "declared_by_adapter"
    UNRESOLVED = "unresolved"


class NodeKind(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    ROUTER = "router"          # nœud de branchement conditionnel
    TERMINAL = "terminal"
    ENTRY = "entry"
    TASK = "task"              # CrewAI : une Task
    OTHER = "other"


class EdgeKind(str, Enum):
    DIRECT = "direct"                  # arête inconditionnelle
    CONDITIONAL = "conditional"        # arête conditionnelle (branche)
    CONTEXT_DEPENDENCY = "context"     # CrewAI : dépendance de contexte entre tâches


@dataclass
class WorkflowNode:
    node_id: str
    kind: NodeKind
    status: ExtractionStatus = ExtractionStatus.EXTRACTED
    # Références vers des ACI (par id logique) — agent, prompt, model, tools.
    agent_ref: Optional[str] = None
    prompt_ref: Optional[str] = None
    model_ref: Optional[str] = None
    tool_refs: List[str] = field(default_factory=list)
    # Métadonnées libres (rôle, goal…), non normatives mais utiles au diagnostic.
    meta: Dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "agent_ref": self.agent_ref,
            "prompt_ref": self.prompt_ref,
            "model_ref": self.model_ref,
            "tool_refs": sorted(self.tool_refs),
        }


@dataclass
class WorkflowEdge:
    source: str
    target: str
    kind: EdgeKind = EdgeKind.DIRECT
    status: ExtractionStatus = ExtractionStatus.EXTRACTED
    # Pour une arête conditionnelle : la condition est souvent OPAQUE (on garde
    # sa représentation nominale et les cibles possibles, pas sa sémantique).
    condition_label: Optional[str] = None
    condition_semantics: str = "n/a"   # "opaque" pour une condition non introspectée
    possible_targets: List[str] = field(default_factory=list)

    def canonical(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind.value,
            "status": self.status.value,
            "condition_label": self.condition_label,
            "condition_semantics": self.condition_semantics,
            "possible_targets": sorted(self.possible_targets),
        }


@dataclass
class WorkflowIR:
    """Représentation intermédiaire canonique d'un workflow (objet A)."""

    workflow_id: str
    framework: str                       # "langgraph" | "crewai" | "openai_agents" | "golden"
    nodes: List[WorkflowNode] = field(default_factory=list)
    edges: List[WorkflowEdge] = field(default_factory=list)
    entry_nodes: List[str] = field(default_factory=list)
    terminal_nodes: List[str] = field(default_factory=list)
    # État partagé / schéma d'état, si extractible (nom des clés, pas les valeurs).
    state_schema_keys: List[str] = field(default_factory=list)
    # Éléments présents mais non reconstructibles (diagnostic d'extraction).
    unresolved_elements: List[Dict[str, Any]] = field(default_factory=list)

    # -- helpers d'accès -----------------------------------------------------

    def node(self, node_id: str) -> Optional[WorkflowNode]:
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def nodes_by_kind(self, kind: NodeKind) -> List[WorkflowNode]:
        return [n for n in self.nodes if n.kind == kind]

    def conditional_edges(self) -> List[WorkflowEdge]:
        return [e for e in self.edges if e.kind == EdgeKind.CONDITIONAL]

    def agent_ids(self) -> List[str]:
        return sorted(n.agent_ref for n in self.nodes if n.agent_ref)

    def tool_ids(self) -> List[str]:
        tools: set[str] = set()
        for n in self.nodes:
            tools.update(n.tool_refs)
        return sorted(tools)

    # -- forme canonique -----------------------------------------------------

    def canonical(self) -> Dict[str, Any]:
        """Forme canonique, indépendante des UUID/timestamps, pour comparaison."""
        return {
            "workflow_id": self.workflow_id,
            "framework": self.framework,
            "nodes": sorted((n.canonical() for n in self.nodes),
                            key=lambda d: d["node_id"]),
            "edges": sorted((e.canonical() for e in self.edges),
                            key=lambda d: (d["source"], d["target"], d["kind"])),
            "entry_nodes": sorted(self.entry_nodes),
            "terminal_nodes": sorted(self.terminal_nodes),
            "state_schema_keys": sorted(self.state_schema_keys),
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical(), sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))

    def digest(self) -> str:
        """Digest canonique : stable après extraction répétée (métrique oracle)."""
        return "sha256:" + hashlib.sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()
