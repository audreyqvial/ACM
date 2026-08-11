"""Tests du validateur de transitions et des matrices (§5.3, §6.3, §7.2, §8.4)."""
from __future__ import annotations

import pytest

from acm.models.enums import (
    BaselineState,
    LifecycleState,
    PromotionState,
    RuntimeState,
)
from acm.state_machines import (
    CODE_DUPLICATE_EVENT,
    CODE_FORBIDDEN_TRANSITION,
    CODE_SEQUENCE_GAP,
    CODE_TERMINATE_BEFORE_INSTANTIATE,
    InvalidTransitionError,
    RuntimeEvent,
    RuntimeEventType,
    TransitionValidator,
    validate_baseline,
    validate_lifecycle,
    validate_runtime,
)


# --- transitions unitaires -------------------------------------------------

@pytest.mark.parametrize("current,target,ok", [
    (BaselineState.CANDIDATE, BaselineState.RELEASED, True),
    (BaselineState.RELEASED, BaselineState.SUPERSEDED, True),
    (BaselineState.RELEASED, BaselineState.WITHDRAWN, True),
    (BaselineState.RELEASED, BaselineState.CANDIDATE, False),
    (BaselineState.WITHDRAWN, BaselineState.RELEASED, False),
])
def test_baseline_matrix(current, target, ok):
    assert validate_baseline(current, target, strict=False).allowed is ok


def test_lifecycle_archived_is_terminal_I6():
    # I6 : un archived n'est jamais réactivable.
    for target in LifecycleState:
        if target is LifecycleState.ARCHIVED:
            continue
        assert validate_lifecycle(
            LifecycleState.ARCHIVED, target, strict=False
        ).allowed is False


def test_runtime_completed_cannot_return_to_running():
    assert validate_runtime(
        RuntimeState.COMPLETED, RuntimeState.RUNNING, strict=False
    ).allowed is False


def test_strict_raises_on_forbidden():
    with pytest.raises(InvalidTransitionError) as exc:
        validate_runtime(RuntimeState.COMPLETED, RuntimeState.RUNNING, strict=True)
    assert exc.value.code == CODE_FORBIDDEN_TRANSITION


def test_permissive_never_raises():
    v = validate_runtime(RuntimeState.COMPLETED, RuntimeState.RUNNING, strict=False)
    assert v.allowed is False and v.reason


# --- séquences runtime (S13) ----------------------------------------------

def _nominal():
    E, T, S = RuntimeEvent, RuntimeEventType, RuntimeState
    return [
        E(T.INSTANTIATED, event_id="e1", sequence=0),
        E(T.STATE_CHANGED, to_state=S.READY, event_id="e2", sequence=1),
        E(T.STATE_CHANGED, to_state=S.RUNNING, event_id="e3", sequence=2),
        E(T.STATE_CHANGED, to_state=S.COMPLETED, event_id="e4", sequence=3),
        E(T.TERMINATED, event_id="e5", sequence=4),
    ]


def test_nominal_sequence_is_valid_S12():
    r = TransitionValidator(strict=False).validate_runtime_sequence(_nominal())
    assert r.valid and r.reliable
    assert r.final_state is RuntimeState.COMPLETED


def test_sequence_completed_to_running_detected():
    E, T, S = RuntimeEvent, RuntimeEventType, RuntimeState
    bad = _nominal() + [E(T.STATE_CHANGED, to_state=S.RUNNING, event_id="e6", sequence=5)]
    r = TransitionValidator(strict=False).validate_runtime_sequence(bad)
    assert not r.valid and not r.reliable
    assert CODE_FORBIDDEN_TRANSITION in {p.code for p in r.problems}


def test_sequence_terminate_before_instantiate():
    E, T = RuntimeEvent, RuntimeEventType
    r = TransitionValidator(strict=False).validate_runtime_sequence(
        [E(T.TERMINATED, event_id="x", sequence=0)]
    )
    assert CODE_TERMINATE_BEFORE_INSTANTIATE in {p.code for p in r.problems}


def test_sequence_duplicate_event():
    E, T, S = RuntimeEvent, RuntimeEventType, RuntimeState
    bad = _nominal() + [E(T.STATE_CHANGED, to_state=S.WAITING, event_id="e3", sequence=5)]
    r = TransitionValidator(strict=False).validate_runtime_sequence(bad)
    assert CODE_DUPLICATE_EVENT in {p.code for p in r.problems}


def test_sequence_gap():
    E, T, S = RuntimeEvent, RuntimeEventType, RuntimeState
    bad = [
        E(T.INSTANTIATED, event_id="a", sequence=0),
        E(T.STATE_CHANGED, to_state=S.READY, event_id="b", sequence=5),
    ]
    r = TransitionValidator(strict=False).validate_runtime_sequence(bad)
    assert CODE_SEQUENCE_GAP in {p.code for p in r.problems}


def test_strict_sequence_raises_first_anomaly():
    E, T, S = RuntimeEvent, RuntimeEventType, RuntimeState
    bad = _nominal() + [E(T.STATE_CHANGED, to_state=S.RUNNING, event_id="e6", sequence=5)]
    with pytest.raises(InvalidTransitionError):
        TransitionValidator(strict=True).validate_runtime_sequence(bad)


# --- cohérence avec les sources natives (anti-divergence) ------------------

def test_baseline_machine_matches_native_function():
    """BASELINE_MACHINE ne doit jamais diverger de baseline_transition_allowed."""
    import itertools

    from acm.models.enums import BaselineState
    from acm.state_machines.baselines import baseline_transition_allowed
    from acm.state_machines.machines import BASELINE_MACHINE

    for a, b in itertools.product(BaselineState, BaselineState):
        if a == b:
            continue
        assert baseline_transition_allowed(a, b) == BASELINE_MACHINE.check(a, b).allowed, (a, b)


def test_lifecycle_machine_matches_invariant_i3():
    """LIFECYCLE_MACHINE ne doit jamais diverger de i3_transition_in_matrix."""
    import itertools

    from acm.invariants import i3_transition_in_matrix
    from acm.models.enums import LifecycleState
    from acm.state_machines.machines import LIFECYCLE_MACHINE

    for a, b in itertools.product(LifecycleState, LifecycleState):
        if a == b:
            continue
        native_ok = i3_transition_in_matrix(a, b) == []
        assert native_ok == LIFECYCLE_MACHINE.check(a, b).allowed, (a, b)
