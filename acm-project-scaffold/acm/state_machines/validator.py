"""Validateur de transitions — strict/permissif, sans état, sans EventLog (S13, S04).

La chaîne décidée : un appelant propose une transition (ou une séquence
d'événements runtime) ; le TransitionValidator interroge la StateMachine
appropriée et, en mode strict, lève InvalidTransitionError ; en mode permissif,
laisse passer en MARQUANT l'anomalie. Aucune persistance : le validateur ne
stocke rien, il répond.

Deux niveaux d'usage :
- transition unitaire : validate(current, target, kind) ;
- séquence runtime : validate_runtime_sequence(events) — c'est ce que S13 teste,
  avec les anomalies : événement dupliqué, terminaison avant instanciation,
  transition completed -> running, rupture de numéro de séquence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

from acm.models.enums import (
    BaselineState,
    LifecycleState,
    PromotionState,
    RuntimeState,
)

from .machines import (
    BASELINE_MACHINE,
    LIFECYCLE_MACHINE,
    PROMOTION_MACHINE,
    RUNTIME_MACHINE,
    StateMachine,
    Verdict,
)


class TransitionKind(str, Enum):
    LIFECYCLE = "lifecycle"
    BASELINE = "baseline"
    RUNTIME = "runtime"
    PROMOTION = "promotion"


_MACHINE_BY_KIND = {
    TransitionKind.LIFECYCLE: LIFECYCLE_MACHINE,
    TransitionKind.BASELINE: BASELINE_MACHINE,
    TransitionKind.RUNTIME: RUNTIME_MACHINE,
    TransitionKind.PROMOTION: PROMOTION_MACHINE,
}

# Codes d'erreur stables (exigés par S02/S13 : « code d'erreur explicite »).
CODE_FORBIDDEN_TRANSITION = "ACM-TRANSITION-001"
CODE_DUPLICATE_EVENT = "ACM-RUNTIME-DUP-001"
CODE_TERMINATE_BEFORE_INSTANTIATE = "ACM-RUNTIME-ORDER-001"
CODE_SEQUENCE_GAP = "ACM-RUNTIME-SEQ-001"
CODE_UNKNOWN_EVENT = "ACM-RUNTIME-EVENT-001"


class InvalidTransitionError(Exception):
    """Levée en mode strict quand une transition/séquence viole la matrice."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class SequenceProblem:
    """Anomalie détectée dans une séquence runtime (S13)."""

    code: str
    message: str
    index: Optional[int] = None


@dataclass
class SequenceResult:
    """Résultat d'une validation de séquence runtime."""

    valid: bool
    final_state: Optional[RuntimeState]
    problems: List[SequenceProblem] = field(default_factory=list)
    reliable: bool = True  # graphe reconstruit fiable ? (S13 : sinon signalé)


# --- Événements runtime pour la validation de séquence -------------------
# Un événement runtime minimal : un type + éventuellement un état cible + un
# numéro de séquence. On reste indépendant du RuntimeSignal (qui décrit une
# instance résolue) : ici on valide l'ORDRE des transitions d'état.

class RuntimeEventType(str, Enum):
    INSTANTIATED = "node.instantiated"
    STATE_CHANGED = "state.changed"
    TOOL_INVOKED = "tool.invoked"
    TOOL_COMPLETED = "tool.completed"
    TERMINATED = "node.terminated"


@dataclass
class RuntimeEvent:
    event_type: RuntimeEventType
    to_state: Optional[RuntimeState] = None
    sequence: Optional[int] = None
    event_id: Optional[str] = None


class TransitionValidator:
    """Valide des transitions et des séquences. Strict par défaut."""

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict

    # --- transition unitaire ---------------------------------------------

    def machine_for(self, kind: TransitionKind) -> StateMachine:
        return _MACHINE_BY_KIND[kind]

    def validate(
        self,
        current: object,
        target: object,
        kind: TransitionKind,
    ) -> Verdict:
        """Valide une transition unitaire. Lève en strict si interdite."""
        verdict = self.machine_for(kind).check(current, target)
        if not verdict.allowed and self.strict:
            raise InvalidTransitionError(CODE_FORBIDDEN_TRANSITION, verdict.reason or "")
        return verdict

    # --- séquence runtime (S13) ------------------------------------------

    def validate_runtime_sequence(
        self, events: Sequence[RuntimeEvent]
    ) -> SequenceResult:
        """Valide l'ordre d'une séquence d'événements runtime.

        Détecte : instanciation manquante/dupliquée, terminaison avant
        instanciation, transitions d'état interdites (completed -> running),
        rupture de numéro de séquence. En mode permissif, marque et poursuit ;
        en strict, lève à la première anomalie.
        """
        problems: List[SequenceProblem] = []
        instantiated = False
        terminated = False
        current: Optional[RuntimeState] = None
        expected_seq: Optional[int] = None
        seen_ids: set[str] = set()

        def fail(problem: SequenceProblem) -> None:
            problems.append(problem)
            if self.strict:
                raise InvalidTransitionError(problem.code, problem.message)

        for idx, ev in enumerate(events):
            # Numéro de séquence : doit être contigu et croissant si fourni.
            if ev.sequence is not None:
                if expected_seq is not None and ev.sequence != expected_seq:
                    fail(SequenceProblem(
                        CODE_SEQUENCE_GAP,
                        f"rupture de séquence: attendu {expected_seq}, reçu {ev.sequence}",
                        idx,
                    ))
                expected_seq = ev.sequence + 1

            # Événement dupliqué (par event_id).
            if ev.event_id is not None:
                if ev.event_id in seen_ids:
                    fail(SequenceProblem(
                        CODE_DUPLICATE_EVENT,
                        f"événement dupliqué: {ev.event_id}", idx,
                    ))
                seen_ids.add(ev.event_id)

            if ev.event_type == RuntimeEventType.INSTANTIATED:
                if instantiated:
                    fail(SequenceProblem(
                        CODE_DUPLICATE_EVENT,
                        "instanciation dupliquée", idx,
                    ))
                instantiated = True
                current = RuntimeState.CREATED

            elif ev.event_type == RuntimeEventType.TERMINATED:
                if not instantiated:
                    fail(SequenceProblem(
                        CODE_TERMINATE_BEFORE_INSTANTIATE,
                        "terminaison avant instanciation", idx,
                    ))
                terminated = True

            elif ev.event_type == RuntimeEventType.STATE_CHANGED:
                if not instantiated:
                    fail(SequenceProblem(
                        CODE_TERMINATE_BEFORE_INSTANTIATE,
                        "changement d'état avant instanciation", idx,
                    ))
                elif ev.to_state is not None and current is not None:
                    verdict = RUNTIME_MACHINE.check(current, ev.to_state)
                    if not verdict.allowed:
                        fail(SequenceProblem(
                            CODE_FORBIDDEN_TRANSITION, verdict.reason or "", idx,
                        ))
                    else:
                        current = ev.to_state
                elif ev.to_state is not None:
                    current = ev.to_state

            elif ev.event_type in (
                RuntimeEventType.TOOL_INVOKED,
                RuntimeEventType.TOOL_COMPLETED,
            ):
                if not instantiated:
                    fail(SequenceProblem(
                        CODE_TERMINATE_BEFORE_INSTANTIATE,
                        "appel d'outil avant instanciation", idx,
                    ))

        valid = len(problems) == 0
        return SequenceResult(
            valid=valid,
            final_state=current,
            problems=problems,
            reliable=valid,  # un graphe issu d'une séquence invalide n'est pas fiable
        )


# Helpers de haut niveau pour les cas typés du noyau.

def validate_lifecycle(
    current: LifecycleState, target: LifecycleState, *, strict: bool = True
) -> Verdict:
    return TransitionValidator(strict).validate(current, target, TransitionKind.LIFECYCLE)


def validate_baseline(
    current: BaselineState, target: BaselineState, *, strict: bool = True
) -> Verdict:
    return TransitionValidator(strict).validate(current, target, TransitionKind.BASELINE)


def validate_runtime(
    current: RuntimeState, target: RuntimeState, *, strict: bool = True
) -> Verdict:
    return TransitionValidator(strict).validate(current, target, TransitionKind.RUNTIME)


def validate_promotion(
    current: PromotionState, target: PromotionState, *, strict: bool = True
) -> Verdict:
    return TransitionValidator(strict).validate(current, target, TransitionKind.PROMOTION)
