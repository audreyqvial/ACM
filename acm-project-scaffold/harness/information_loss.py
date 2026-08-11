# Emplacement : harness/information_loss.py
"""Mesure de perte d'information d'une extraction (formalisme E:F→A).

Implémente la définition normative des notes de conception :

  Information loss is the inability of an ACM extraction or projection to
  preserve a property that belongs to the normative representational scope of
  the ACM metamodel.

On raisonne sur un ENSEMBLE P de propriétés que le métamodèle ACM prétend
représenter (le « périmètre normatif »). Pour chaque propriété p ∈ P, on compare
sa projection sur le workflow natif πₚ(F) à sa projection sur l'extraction
πₚ(E(F)), et on classe :

  - preserved   : πₚ(F) == πₚ(E(F))            (reconstruite sans modification) ;
  - approximated: représentée par une abstraction ACM, avec perte de précision ;
  - unsupported : aucun concept ACM correspondant.

La perte = { propriétés non préservées } restreinte au périmètre ACM. Les détails
propres au framework hors périmètre (logique Python, closures) ne comptent PAS
comme perte : ils sont hors P.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List

from .workflow_ir import EdgeKind, NodeKind, WorkflowIR


class LossStatus(str, Enum):
    PRESERVED = "preserved"
    APPROXIMATED = "approximated"
    UNSUPPORTED = "unsupported"


@dataclass
class PropertyResult:
    """Résultat de comparaison pour une propriété normative."""

    name: str
    status: LossStatus
    expected: object
    observed: object
    detail: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "property": self.name,
            "status": self.status.value,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------
# Le périmètre normatif P : ce qu'ACM prétend représenter d'un workflow.
# Chaque propriété est une fonction πₚ qui projette un WorkflowIR sur une valeur
# comparable. La perte se mesure en comparant πₚ(golden) à πₚ(extrait).
# --------------------------------------------------------------------------

def _p_agent_set(ir: WorkflowIR):
    return tuple(ir.agent_ids())

def _p_tool_set(ir: WorkflowIR):
    return tuple(ir.tool_ids())

def _p_entry_nodes(ir: WorkflowIR):
    return tuple(sorted(ir.entry_nodes))

def _p_terminal_nodes(ir: WorkflowIR):
    return tuple(sorted(ir.terminal_nodes))

def _p_node_identities(ir: WorkflowIR):
    return tuple(sorted((n.node_id, n.kind.value) for n in ir.nodes))

def _p_direct_edges(ir: WorkflowIR):
    return tuple(sorted((e.source, e.target) for e in ir.edges
                        if e.kind == EdgeKind.DIRECT))

def _p_conditional_branches(ir: WorkflowIR):
    # On projette une branche conditionnelle sur (source, cibles possibles),
    # SANS sa sémantique opaque — c'est le périmètre représentable.
    return tuple(sorted(
        (e.source, tuple(sorted(e.possible_targets)))
        for e in ir.edges if e.kind == EdgeKind.CONDITIONAL
    ))

def _p_context_dependencies(ir: WorkflowIR):
    return tuple(sorted((e.source, e.target) for e in ir.edges
                        if e.kind == EdgeKind.CONTEXT_DEPENDENCY))

def _p_agent_prompt_refs(ir: WorkflowIR):
    return tuple(sorted((n.agent_ref, n.prompt_ref) for n in ir.nodes
                        if n.agent_ref and n.prompt_ref))

def _p_agent_tool_refs(ir: WorkflowIR):
    return tuple(sorted((n.agent_ref, tuple(sorted(n.tool_refs)))
                        for n in ir.nodes if n.agent_ref and n.tool_refs))

def _p_state_schema(ir: WorkflowIR):
    return tuple(sorted(ir.state_schema_keys))


# Registre du périmètre normatif. Le flag `approximate_ok` marque les propriétés
# qui, par nature, sont représentées par une abstraction (ex. une condition
# opaque) : leur préservation topologique compte comme `approximated`, pas
# `preserved`, même si (source, cibles) coïncident.
@dataclass
class NormativeProperty:
    name: str
    project: Callable[[WorkflowIR], object]
    approximate_by_nature: bool = False


NORMATIVE_SCOPE: List[NormativeProperty] = [
    NormativeProperty("agent_set", _p_agent_set),
    NormativeProperty("tool_set", _p_tool_set),
    NormativeProperty("entry_nodes", _p_entry_nodes),
    NormativeProperty("terminal_nodes", _p_terminal_nodes),
    NormativeProperty("node_identities", _p_node_identities),
    NormativeProperty("direct_edges", _p_direct_edges),
    NormativeProperty("conditional_branches", _p_conditional_branches,
                      approximate_by_nature=True),
    NormativeProperty("context_dependencies", _p_context_dependencies),
    NormativeProperty("agent_prompt_refs", _p_agent_prompt_refs),
    NormativeProperty("agent_tool_refs", _p_agent_tool_refs),
    NormativeProperty("state_schema", _p_state_schema),
]


@dataclass
class LossReport:
    """Rapport de perte d'information entre un golden F et une extraction E(F)."""

    workflow_id: str
    framework: str
    results: List[PropertyResult] = field(default_factory=list)

    def by_status(self, status: LossStatus) -> List[PropertyResult]:
        return [r for r in self.results if r.status == status]

    @property
    def is_lossless(self) -> bool:
        """Sans perte ssi aucune propriété n'est unsupported ni divergente."""
        return all(r.status == LossStatus.PRESERVED for r in self.results)

    def to_dict(self) -> Dict[str, object]:
        counts = {s.value: len(self.by_status(s)) for s in LossStatus}
        return {
            "workflow_id": self.workflow_id,
            "framework": self.framework,
            "lossless": self.is_lossless,
            "counts": counts,
            "properties": [r.to_dict() for r in self.results],
        }


def measure_information_loss(
    golden: WorkflowIR, extracted: WorkflowIR
) -> LossReport:
    """Compare πₚ(golden) à πₚ(extracted) pour chaque propriété du périmètre ACM.

    - valeurs égales, propriété non-approximée par nature → preserved ;
    - valeurs égales, propriété approximée par nature (condition opaque)
      → approximated (la topologie est là, la sémantique non) ;
    - valeurs différentes mais projection extraite non vide → approximated ;
    - projection extraite vide alors que le golden en a → unsupported.
    """
    results: List[PropertyResult] = []
    for prop in NORMATIVE_SCOPE:
        exp = prop.project(golden)
        obs = prop.project(extracted)

        if exp == obs:
            status = (LossStatus.APPROXIMATED if prop.approximate_by_nature
                      else LossStatus.PRESERVED)
            detail = ("abstraction topologique conservée, sémantique opaque"
                      if prop.approximate_by_nature else "")
        else:
            # Différence : distinguer approximation (partiel) d'unsupported (vide).
            obs_empty = (obs == () or obs is None)
            exp_nonempty = not (exp == () or exp is None)
            if obs_empty and exp_nonempty:
                status = LossStatus.UNSUPPORTED
                detail = "aucun élément extrait pour une propriété présente au golden"
            else:
                status = LossStatus.APPROXIMATED
                detail = "projection partielle ou divergente"

        results.append(PropertyResult(
            name=prop.name, status=status, expected=exp, observed=obs, detail=detail,
        ))

    return LossReport(
        workflow_id=extracted.workflow_id,
        framework=extracted.framework,
        results=results,
    )
