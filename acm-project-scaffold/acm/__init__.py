"""ACM — Agentic Configuration Management, cœur normatif v0.1.

Package sans aucune dépendance à un framework agentique (LangGraph, CrewAI).
Point d'entrée principal : `propagate()`.
"""
from .models.aci import (
    ACIRevision,
    ConfigurationGraph,
    DeclaredStatus,
    Evidence,
    Relation,
)
from .models.enums import (
    ACIType,
    AssuranceState,
    BaselineState,
    CompositionAssuranceMode,
    EligibilityState,
    EvidenceResult,
    ImpactState,
    LifecycleState,
    PromotionState,
    PropagationPolicy,
    QualityState,
    RelationType,
    RuntimeState,
)
from .models.refs import ACIRef, Reason
from .models.status import ComputedStatus, ItemStatus, PropagationReport
from .policy import (
    DEFAULT_POLICY,
    EligibilityContext,
    Policy,
    PropagationContext,
    ReleaseRules,
)
from .propagation.engine import propagate
from .propagation.assurance import (
    EvidenceApplicability,
    applicable_evidence,
    classify_evidence,
    covered_dimensions,
    evidence_applicability,
)
from .propagation.quality import quality_from_evidence
from .invariants import (
    InvariantViolation,
    InvariantViolationError,
    check_report_invariants,
)
from .runtime.evaluator import evaluate_runtime_instance
from .runtime.instance import (
    DriftClassification,
    PermissionDrift,
    RuntimeInstanceStatus,
)
from .runtime.governance import (
    digest_of_resolved_config,
    permission_check_from_spec,
    resolved_config_from_spec,
    traceability_from_spec,
)
from .runtime.spec import AgentSpec, PermissionCeiling
from .runtime.signal import (
    PermissionCheck,
    ResolvedConfig,
    RuntimeSignal,
    RuntimeTerminalState,
    Traceability,
)

__all__ = [
    "ACIRevision", "ConfigurationGraph", "DeclaredStatus", "Evidence", "Relation",
    "AssuranceState", "BaselineState", "EligibilityState", "ImpactState",
    "LifecycleState", "PromotionState", "PropagationPolicy", "QualityState",
    "RelationType", "RuntimeState", "ACIType", "EvidenceResult",
    "CompositionAssuranceMode",
    "EvidenceApplicability", "classify_evidence", "evidence_applicability",
    "applicable_evidence", "covered_dimensions",
    "quality_from_evidence",
    "ACIRef", "Reason",
    "ComputedStatus", "ItemStatus", "PropagationReport",
    "DEFAULT_POLICY", "EligibilityContext", "Policy", "PropagationContext",
    "ReleaseRules",
    "propagate",
    "InvariantViolation", "InvariantViolationError", "check_report_invariants",
    "evaluate_runtime_instance", "RuntimeInstanceStatus",
    "DriftClassification", "PermissionDrift",
    "RuntimeSignal", "ResolvedConfig", "Traceability", "PermissionCheck",
    "RuntimeTerminalState",
    "AgentSpec", "PermissionCeiling",
    "digest_of_resolved_config", "resolved_config_from_spec",
    "traceability_from_spec", "permission_check_from_spec",
]

__version__ = "0.1.0"
