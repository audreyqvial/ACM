"""Adaptateur stub déterministe.

Produit des RuntimeSignal figés, sans exécuter aucun agent réel. Sert aux
scénarios D et E : les états runtime sont testables et reproductibles au même
titre que A/B/C.

Plus tard, `LangGraphAdapter` et `CrewAIAdapter` implémenteront le même port
`RuntimeAdapter` en exécutant réellement, puis en produisant un RuntimeSignal
identique en structure. Le cœur ACM ne verra aucune différence.
"""
from __future__ import annotations

from typing import Any, Dict

from ports.runtime_adapter import RuntimeAdapter

from acm.runtime.signal import RuntimeSignal


class DeterministicStubAdapter(RuntimeAdapter):
    """Retourne le RuntimeSignal fourni tel quel (déterminisme total)."""

    name = "deterministic-stub"

    def create_instance(self, request: Dict[str, Any]) -> RuntimeSignal:
        """`request` doit contenir une clé `signal` : soit un RuntimeSignal,
        soit un dict record à rejouer. Aucune exécution réelle.
        """
        payload = request["signal"]
        if isinstance(payload, RuntimeSignal):
            signal = payload
        else:
            signal = RuntimeSignal.from_record(payload)
        # Empreinte de l'adaptateur, pour audit/record.
        signal.adapter_name = self.name
        return signal
