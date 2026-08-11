# Emplacement : tests/test_scenarios_baselines.py
"""Tests S04 et S17 — immutabilité et retrait des baselines (§6, plan ACM-S04/S17).

Ces deux scénarios portent sur le MODÈLE Baseline et sa machine à états, pas sur
propagate() : ils ne passent donc pas par le harness YAML (qui construit un
ConfigurationGraph). Ils sont implémentés comme tests dédiés.

S04 — Immutabilité d'une baseline released :
  L'immutabilité est LOGIQUE (par digest), pas structurelle : Baseline est un
  BaseModel mutable en mémoire, mais toute mutation d'un membre fait diverger le
  digest recalculé du digest publié → la mutation est détectable. Une nouvelle
  baseline (nouveau digest) est exigée ; l'historique reste intact.

S17 — Baseline retirée après exécution historique :
  Le passage à withdrawn ne modifie ni le digest ni le snapshot : un run
  historique reste reconstructible et lié à B1. La réactivation est refusée par
  la matrice §6.3, et un nouveau run est bloqué par défaut sur une baseline
  withdrawn.
"""
from __future__ import annotations

import pytest

from acm.models.enums import BaselineState
from acm.models.refs import ACIRef
from acm.state_machines import InvalidTransitionError, validate_baseline
from acm.state_machines.baselines import (
    Baseline,
    OperationalStatus,
    baseline_transition_allowed,
)
from harness import baseline_digest


def _members():
    return [
        ACIRef(id="aci:agent:planner", revision_id="R1", digest="sha256:a"),
        ACIRef(id="aci:tool:web-search", revision_id="R1", digest="sha256:t"),
    ]


def _released_baseline():
    b = Baseline(baseline_id="b1", required_items=_members())
    b.transition(BaselineState.RELEASED)
    b.digest = baseline_digest(b)  # digest publié, figé au moment du release
    return b


# ============================================================ S04

def test_s04_released_baseline_has_stable_digest():
    b = _released_baseline()
    # Recalculer sans muter donne le même digest.
    assert baseline_digest(b) == b.digest


def test_s04_mutating_a_member_diverges_digest():
    """Modifier un composant couvert par le digest → le digest ne correspond plus."""
    b = _released_baseline()
    published = b.digest

    # Mutation : un membre passe de R1 à R2 (changement de révision).
    b.required_items = [
        ACIRef(id="aci:agent:planner", revision_id="R2", digest="sha256:a2"),
        ACIRef(id="aci:tool:web-search", revision_id="R1", digest="sha256:t"),
    ]
    recomputed = baseline_digest(b)
    assert recomputed != published, "la mutation doit être détectée par divergence du digest"


def test_s04_adding_or_removing_member_diverges_digest():
    b = _released_baseline()
    published = b.digest

    # Retrait d'un membre.
    b.required_items = _members()[:1]
    assert baseline_digest(b) != published


def test_s04_new_baseline_required_for_changed_content():
    """Un contenu modifié impose une NOUVELLE baseline (nouveau baseline_id)."""
    b1 = _released_baseline()

    changed_members = [
        ACIRef(id="aci:agent:planner", revision_id="R2", digest="sha256:a2"),
        ACIRef(id="aci:tool:web-search", revision_id="R1", digest="sha256:t"),
    ]
    b2 = Baseline(baseline_id="b2", required_items=changed_members)
    b2.transition(BaselineState.RELEASED)
    b2.digest = baseline_digest(b2)

    # Les deux baselines ont des digests distincts et coexistent.
    assert b1.digest != b2.digest
    assert b1.baseline_id != b2.baseline_id


def test_s04_historical_baseline_remains_intact():
    """La baseline historique reste consultable et intacte après la nouvelle."""
    b1 = _released_baseline()
    snapshot_before = [(r.id, r.revision_id, r.digest) for r in b1.required_items]
    digest_before = b1.digest

    # Création d'une nouvelle baseline (n'affecte pas b1).
    b2 = Baseline(baseline_id="b2", required_items=_members())
    b2.transition(BaselineState.RELEASED)

    snapshot_after = [(r.id, r.revision_id, r.digest) for r in b1.required_items]
    assert snapshot_after == snapshot_before
    assert b1.digest == digest_before
    assert b1.state == BaselineState.RELEASED


# ============================================================ S17

def test_s17_withdraw_does_not_change_digest():
    """Le passage à withdrawn n'altère pas le digest historique."""
    b = _released_baseline()
    digest_before = baseline_digest(b)

    b.transition(BaselineState.WITHDRAWN)

    assert baseline_digest(b) == digest_before, "le retrait ne doit pas changer le digest"


def test_s17_withdraw_does_not_change_snapshot():
    """Le retrait ne modifie pas le snapshot des membres (journal intact)."""
    b = _released_baseline()
    snapshot_before = [(r.id, r.revision_id, r.digest) for r in b.required_items]

    b.transition(BaselineState.WITHDRAWN)

    snapshot_after = [(r.id, r.revision_id, r.digest) for r in b.required_items]
    assert snapshot_after == snapshot_before


def test_s17_historical_run_stays_linked_to_b1():
    """Un run historique enregistré avec le digest de B1 reste reconstructible.

    On simule un run figé par son digest de baseline ; après retrait, le lien
    (digest) reste valide et pointe toujours vers le même contenu.
    """
    b = _released_baseline()
    recorded_run = {"baseline_id": b.baseline_id, "baseline_digest": b.digest}

    b.transition(BaselineState.WITHDRAWN)

    # Le run historique référence toujours un digest qui correspond au snapshot.
    assert recorded_run["baseline_digest"] == baseline_digest(b)
    assert recorded_run["baseline_id"] == b.baseline_id


def test_s17_reactivation_is_refused():
    """withdrawn → released est refusé par la matrice §6.3 (retrait irréversible)."""
    assert not baseline_transition_allowed(BaselineState.WITHDRAWN, BaselineState.RELEASED)
    with pytest.raises(InvalidTransitionError):
        validate_baseline(BaselineState.WITHDRAWN, BaselineState.RELEASED, strict=True)


def test_s17_transition_method_refuses_reactivation():
    """La méthode transition() de Baseline refuse aussi la réactivation."""
    b = _released_baseline()
    b.transition(BaselineState.WITHDRAWN)
    with pytest.raises(ValueError):
        b.transition(BaselineState.RELEASED)


def test_s17_new_run_on_withdrawn_is_blocked_by_default():
    """Une baseline withdrawn ne peut plus servir de base à un nouveau run.

    Modélisé par une règle de gating : un nouveau run n'est autorisé que si la
    baseline est released. withdrawn → refus par défaut.
    """
    b = _released_baseline()
    b.transition(BaselineState.WITHDRAWN)

    def new_run_allowed(baseline: Baseline) -> bool:
        return baseline.state == BaselineState.RELEASED

    assert new_run_allowed(b) is False


def test_s17_operational_status_is_separate_from_lifecycle():
    """§6.5 — un statut opérationnel (withdrawal_recommended) n'est pas un retrait.

    Distinction historique/opérationnel : recommander un retrait ne change pas
    l'état normatif de la baseline.
    """
    b = _released_baseline()
    b.flag_operational(OperationalStatus.WITHDRAWAL_RECOMMENDED)
    assert b.state == BaselineState.RELEASED           # lifecycle inchangé
    assert b.operational_status == OperationalStatus.WITHDRAWAL_RECOMMENDED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
