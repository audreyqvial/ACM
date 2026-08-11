"""Port `RuntimeAdapter` — contrat qu'un framework d'exécution doit remplir.

Style hexagonal : le cœur ACM dépend de cette interface abstraite, jamais
d'une implémentation concrète. Le stub déterministe (aujourd'hui) et les
adaptateurs LangGraph/CrewAI (plus tard) sont des implémentations
INTERCHANGEABLES du même port.

Le port ne retourne JAMAIS un objet framework brut — toujours un RuntimeSignal
(la frontière étanche). C'est ce qui garantit que :
  - le cœur reste déterministe (§I14) aujourd'hui ;
  - les scénarios de conformité restent verts quand le vrai runtime arrivera.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from acm.runtime.signal import RuntimeSignal


class RuntimeAdapter(ABC):
    """Interface abstraite d'un adaptateur d'exécution.

    Une implémentation conforme traduit une demande de création/exécution
    d'instance en un RuntimeSignal normalisé.
    """

    name: str = "abstract"

    @abstractmethod
    def create_instance(self, request: Dict[str, Any]) -> RuntimeSignal:
        """Crée (et éventuellement exécute) une instance, retourne un signal.

        `request` décrit ce que le framework doit instancier (factory,
        template, config souhaitée...). Le format exact est libre côté
        adaptateur ; seul le RuntimeSignal de sortie est normatif.
        """
        raise NotImplementedError

    def replay(self, record: Dict[str, Any]) -> RuntimeSignal:
        """Rejoue un RuntimeSignal figé (record/replay).

        Comportement par défaut commun à tous les adaptateurs : désérialiser.
        Un adaptateur réel pourra enregistrer ses vrais runs via
        `signal.to_record()` puis les rejouer ici sans ré-exécuter.
        """
        return RuntimeSignal.from_record(record)
