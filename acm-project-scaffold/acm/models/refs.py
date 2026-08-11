"""Références et raisons structurées (§3.5, §4.2)."""
from __future__ import annotations

import hashlib
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def canonical_ref_digest(aci_id: str, revision_id: str) -> str:
    """Digest canonique et déterministe d'une révision exacte (§3.5).

    Dérivé de (id, revision_id) de façon reproductible : un même couple produit
    toujours le même digest, quel que soit l'adaptateur ou la démo. Permet de
    renseigner un digest cohérent quand seul le revision_id logique est connu.

    En production, ce digest serait le hash du contenu canonique de la révision ;
    ici il fournit une empreinte stable et vérifiable pour l'identité de révision.
    """
    payload = f"{aci_id}@{revision_id}".encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class ACIRef(BaseModel):
    """Référence vers une révision exacte d'ACI (§3.5).

    Une validation portant uniquement sur l'identité logique est insuffisante :
    il faut cibler un revision_id et/ou un digest.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Identité logique, ex. aci:prompt:planner-system")
    revision_id: Optional[str] = Field(default=None, description="ex. 01J...")
    digest: Optional[str] = Field(default=None, description="ex. sha256:...")

    def with_digest(self) -> "ACIRef":
        """Retourne une copie dont le digest est renseigné de façon canonique.

        Ne fait rien si le digest est déjà présent ou si le revision_id manque.
        """
        if self.digest is not None or self.revision_id is None:
            return self
        return self.model_copy(
            update={"digest": canonical_ref_digest(self.id, self.revision_id)}
        )

    def matches_revision(self, other: "ACIRef") -> bool:
        """Deux références visent la même révision exacte (§3.5, I2).

        Identité stricte : l'id DOIT correspondre, et parmi (revision_id, digest)
        toutes les composantes présentes des DEUX côtés doivent correspondre.
        Un digest divergent invalide la correspondance même si le revision_id
        coïncide (une révision modifiée a un nouveau digest). L'identité logique
        seule (id sans revision_id ni digest partagé) est insuffisante.
        """
        if self.id != other.id:
            return False

        checked_any = False

        if self.revision_id is not None and other.revision_id is not None:
            if self.revision_id != other.revision_id:
                return False
            checked_any = True

        if self.digest is not None and other.digest is not None:
            if self.digest != other.digest:
                return False
            checked_any = True

        # Au moins une composante exacte (revision_id ou digest) doit avoir été
        # comparée ET concordante. L'identité logique seule ne suffit pas.
        return checked_any

    def key(self) -> str:
        """Clé stable pour indexation dans le graphe."""
        return f"{self.id}@{self.revision_id or self.digest or 'logical'}"


class Reason(BaseModel):
    """Raison structurée accompagnant un état calculé non nominal (§4.2).

    Chaque état calculé différent de sa valeur nominale DOIT être accompagné
    d'au moins une raison structurée.
    """

    code: str = Field(..., description="Code stable, ex. ACM-PROP-QUALITY-BLOCK")
    message: str = Field(..., description="Message lisible")
    source_ref: Optional[ACIRef] = Field(default=None, description="Source du changement")
    relation_type: Optional[str] = Field(default=None, description="Relation empruntée")
    observed_state: Optional[str] = Field(default=None, description="État observé")
    rule: Optional[str] = Field(default=None, description="Règle appliquée")
    severity: Optional[str] = Field(default=None, description="Niveau de sévérité")
