# Emplacement : harness/extraction_oracle.py
"""Oracle d'extraction : métriques de fidélité extraction vs golden (étape 3).

Compare une extraction E(F) à sa représentation golden et produit les métriques
des notes de conception :
  - couverture des nœuds / relations ;
  - préservation entry / terminal / branches ;
  - préservation des références agent–prompt–outil ;
  - nombre d'éléments unresolved ;
  - stabilité du digest (via extractions répétées, testée ailleurs).

Combine les métriques de couverture avec le rapport de perte d'information pour
donner une vue complète de la qualité d'extraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .information_loss import LossReport, LossStatus, measure_information_loss
from .workflow_ir import EdgeKind, ExtractionStatus, NodeKind, WorkflowIR


def _coverage(expected: set, observed: set) -> float:
    if not expected:
        return 1.0
    return len(expected & observed) / len(expected)


@dataclass
class ExtractionMetrics:
    """Métriques de fidélité d'une extraction vis-à-vis du golden."""

    workflow_id: str
    framework: str
    node_coverage: float
    relation_coverage: float
    entry_preserved: bool
    terminal_preserved: bool
    branch_coverage: float
    agent_prompt_ref_coverage: float
    agent_tool_ref_coverage: float
    unresolved_count: int
    # comptage par statut d'extraction des nœuds
    extraction_status_counts: Dict[str, int] = field(default_factory=dict)
    loss: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "workflow_id": self.workflow_id,
            "framework": self.framework,
            "node_coverage": round(self.node_coverage, 4),
            "relation_coverage": round(self.relation_coverage, 4),
            "entry_preserved": self.entry_preserved,
            "terminal_preserved": self.terminal_preserved,
            "branch_coverage": round(self.branch_coverage, 4),
            "agent_prompt_ref_coverage": round(self.agent_prompt_ref_coverage, 4),
            "agent_tool_ref_coverage": round(self.agent_tool_ref_coverage, 4),
            "unresolved_count": self.unresolved_count,
            "extraction_status_counts": self.extraction_status_counts,
            "loss": self.loss,
        }


def _node_key_set(ir: WorkflowIR) -> set:
    return {(n.node_id, n.kind.value) for n in ir.nodes}


def _edge_key_set(ir: WorkflowIR, kind: EdgeKind) -> set:
    return {(e.source, e.target) for e in ir.edges if e.kind == kind}


def _branch_set(ir: WorkflowIR) -> set:
    return {(e.source, tuple(sorted(e.possible_targets)))
            for e in ir.edges if e.kind == EdgeKind.CONDITIONAL}


def _agent_prompt_set(ir: WorkflowIR) -> set:
    return {(n.agent_ref, n.prompt_ref) for n in ir.nodes
            if n.agent_ref and n.prompt_ref}


def _agent_tool_set(ir: WorkflowIR) -> set:
    return {(n.agent_ref, tuple(sorted(n.tool_refs))) for n in ir.nodes
            if n.agent_ref and n.tool_refs}


def evaluate_extraction(golden: WorkflowIR, extracted: WorkflowIR) -> ExtractionMetrics:
    """Calcule les métriques de fidélité + le rapport de perte."""
    all_edges_golden = {(e.source, e.target) for e in golden.edges}
    all_edges_extracted = {(e.source, e.target) for e in extracted.edges}

    status_counts: Dict[str, int] = {s.value: 0 for s in ExtractionStatus}
    for n in extracted.nodes:
        status_counts[n.status.value] += 1

    loss_report = measure_information_loss(golden, extracted)

    return ExtractionMetrics(
        workflow_id=extracted.workflow_id,
        framework=extracted.framework,
        node_coverage=_coverage(_node_key_set(golden), _node_key_set(extracted)),
        relation_coverage=_coverage(all_edges_golden, all_edges_extracted),
        entry_preserved=sorted(golden.entry_nodes) == sorted(extracted.entry_nodes),
        terminal_preserved=sorted(golden.terminal_nodes) == sorted(extracted.terminal_nodes),
        branch_coverage=_coverage(_branch_set(golden), _branch_set(extracted)),
        agent_prompt_ref_coverage=_coverage(_agent_prompt_set(golden), _agent_prompt_set(extracted)),
        agent_tool_ref_coverage=_coverage(_agent_tool_set(golden), _agent_tool_set(extracted)),
        unresolved_count=len(extracted.unresolved_elements),
        extraction_status_counts=status_counts,
        loss=loss_report.to_dict(),
    )
