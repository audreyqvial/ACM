"""Machines à états et validateur de transitions ACM (§5.3, §6.3, §7.2, §8.4)."""
from .machines import (
    BASELINE_MACHINE,
    LIFECYCLE_MACHINE,
    PROMOTION_MACHINE,
    RUNTIME_MACHINE,
    StateMachine,
    Verdict,
)
from .validator import (
    CODE_DUPLICATE_EVENT,
    CODE_FORBIDDEN_TRANSITION,
    CODE_SEQUENCE_GAP,
    CODE_TERMINATE_BEFORE_INSTANTIATE,
    InvalidTransitionError,
    RuntimeEvent,
    RuntimeEventType,
    SequenceProblem,
    SequenceResult,
    TransitionKind,
    TransitionValidator,
    validate_baseline,
    validate_lifecycle,
    validate_promotion,
    validate_runtime,
)

__all__ = [
    "StateMachine", "Verdict",
    "LIFECYCLE_MACHINE", "BASELINE_MACHINE", "RUNTIME_MACHINE", "PROMOTION_MACHINE",
    "TransitionValidator", "TransitionKind", "InvalidTransitionError",
    "RuntimeEvent", "RuntimeEventType", "SequenceProblem", "SequenceResult",
    "validate_lifecycle", "validate_baseline", "validate_runtime", "validate_promotion",
    "CODE_FORBIDDEN_TRANSITION", "CODE_DUPLICATE_EVENT",
    "CODE_TERMINATE_BEFORE_INSTANTIATE", "CODE_SEQUENCE_GAP",
]
