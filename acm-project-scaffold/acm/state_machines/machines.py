"""Matrices de transitions comme fonctions pures (§5.3, §6.3, §7.2, §8.4).

Une StateMachine est SANS ÉTAT : elle répond seulement à la question
« (état_courant, état_cible) est-elle une transition autorisée ? ». Les quatre
matrices normatives sont déclaratives et injectables — une politique peut en
fournir une variante (§5.5, §6.4) sans toucher au validateur.

Ce module n'introduit AUCUNE persistance. Il complète le noyau existant :
- la matrice baseline réutilise celle déjà définie dans acm.runtime.baselines ;
- la matrice lifecycle encode §5.3 (cohérente avec l'invariant I3) ;
- les matrices runtime et promotion comblent le manque (aucune n'existait).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

from acm.models.enums import (
    BaselineState,
    LifecycleState,
    PromotionState,
    RuntimeState,
)

# --- §5.3 Lifecycle d'une révision d'ACI ---------------------------------
# draft -> candidate -> validated ; dépréciation puis archivage ; un archived
# est terminal (I6 : non réactivable). Un draft peut être abandonné (archived).
_LIFECYCLE_TRANSITIONS: FrozenSet[Tuple[LifecycleState, LifecycleState]] = frozenset({
    (LifecycleState.DRAFT, LifecycleState.CANDIDATE),
    (LifecycleState.DRAFT, LifecycleState.ARCHIVED),
    (LifecycleState.CANDIDATE, LifecycleState.VALIDATED),
    (LifecycleState.CANDIDATE, LifecycleState.DRAFT),
    (LifecycleState.CANDIDATE, LifecycleState.ARCHIVED),
    (LifecycleState.VALIDATED, LifecycleState.DEPRECATED),
    (LifecycleState.DEPRECATED, LifecycleState.ARCHIVED),
})

# --- §6.3 Baseline : réutilise la matrice déjà définie dans le même package ---
from .baselines import _ALLOWED_BASELINE_TRANSITIONS  # noqa: E402

_BASELINE_TRANSITIONS: FrozenSet[Tuple[BaselineState, BaselineState]] = frozenset(
    _ALLOWED_BASELINE_TRANSITIONS
)

# --- §7.2 Machine à états des instances runtime --------------------------
# created -> ready -> running -> {waiting, completed, failed, cancelled}
# waiting <-> running ; états terminaux -> terminated. Un état terminal ne
# revient jamais vers running (interdit le "completed -> running" de S13).
_RUNTIME_TRANSITIONS: FrozenSet[Tuple[RuntimeState, RuntimeState]] = frozenset({
    (RuntimeState.CREATED, RuntimeState.READY),
    (RuntimeState.READY, RuntimeState.RUNNING),
    (RuntimeState.RUNNING, RuntimeState.WAITING),
    (RuntimeState.WAITING, RuntimeState.RUNNING),
    (RuntimeState.RUNNING, RuntimeState.COMPLETED),
    (RuntimeState.RUNNING, RuntimeState.FAILED),
    (RuntimeState.RUNNING, RuntimeState.CANCELLED),
    (RuntimeState.READY, RuntimeState.CANCELLED),
    (RuntimeState.WAITING, RuntimeState.CANCELLED),
    (RuntimeState.COMPLETED, RuntimeState.TERMINATED),
    (RuntimeState.FAILED, RuntimeState.TERMINATED),
    (RuntimeState.CANCELLED, RuntimeState.TERMINATED),
})

# --- §8.4 Promotion des objets créés au runtime --------------------------
# ephemeral -> retained -> candidate -> {registered, rejected} ; expiration
# possible depuis les états non terminaux. registered/rejected sont terminaux.
_PROMOTION_TRANSITIONS: FrozenSet[Tuple[PromotionState, PromotionState]] = frozenset({
    (PromotionState.EPHEMERAL, PromotionState.RETAINED),
    (PromotionState.EPHEMERAL, PromotionState.EXPIRED),
    (PromotionState.RETAINED, PromotionState.CANDIDATE),
    (PromotionState.RETAINED, PromotionState.EXPIRED),
    (PromotionState.CANDIDATE, PromotionState.REGISTERED),
    (PromotionState.CANDIDATE, PromotionState.REJECTED),
    (PromotionState.CANDIDATE, PromotionState.EXPIRED),
})


@dataclass(frozen=True)
class Verdict:
    """Résultat d'une vérification de transition."""

    allowed: bool
    reason: Optional[str] = None


class StateMachine:
    """Matrice de transitions pure et sans état pour un type d'objet donné."""

    def __init__(
        self,
        name: str,
        transitions: FrozenSet[Tuple[object, object]],
    ) -> None:
        self.name = name
        self._transitions = transitions
        # Index des cibles atteignables par état, pour messages d'erreur utiles.
        self._out: Dict[object, FrozenSet[object]] = {}
        for src, dst in transitions:
            self._out.setdefault(src, set()).add(dst)  # type: ignore[arg-type]
        self._out = {k: frozenset(v) for k, v in self._out.items()}

    def check(self, current: object, target: object) -> Verdict:
        """La transition current -> target est-elle autorisée ?"""
        if current == target:
            return Verdict(True, "no-op")
        if (current, target) in self._transitions:
            return Verdict(True)
        reachable = sorted(
            getattr(s, "value", str(s)) for s in self._out.get(current, frozenset())
        )
        cur = getattr(current, "value", str(current))
        tgt = getattr(target, "value", str(target))
        hint = ", ".join(reachable) if reachable else "aucune (état terminal)"
        return Verdict(
            False,
            f"{self.name}: transition interdite {cur} -> {tgt} "
            f"(cibles autorisées: {hint})",
        )

    def terminal_states(self) -> FrozenSet[object]:
        """États sans transition sortante (utile pour I6 et le runtime)."""
        with_out = set(self._out.keys())
        all_states = with_out | {d for _, d in self._transitions}
        return frozenset(s for s in all_states if s not in with_out)


# Instances partagées des quatre machines normatives.
LIFECYCLE_MACHINE = StateMachine("lifecycle", _LIFECYCLE_TRANSITIONS)
BASELINE_MACHINE = StateMachine("baseline", _BASELINE_TRANSITIONS)
RUNTIME_MACHINE = StateMachine("runtime", _RUNTIME_TRANSITIONS)
PROMOTION_MACHINE = StateMachine("promotion", _PROMOTION_TRANSITIONS)
