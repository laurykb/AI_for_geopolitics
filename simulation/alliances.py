"""Registre sourcé des alliances et traités réels (`data/sources/alliances.json`).

Source de vérité unique des adhésions : l'attribut `alliances` de chaque pays est
DÉRIVÉ de ce registre par `ingestion.build` (reproductible, comme les indicateurs).
Le même registre alimente l'onglet Informations (noms, fondements, sources) et les
prompts de négociation (les SI citent les traités par leur nom réel).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

ALLIANCES_FILE = Path("data/sources/alliances.json")


class AllianceInfo(BaseModel):
    """Un accord / traité / bloc réel : identité, fondement, source, membres du roster."""

    name: str
    short: str  # libellé compact pour les prompts (nom + fondement daté)
    domain: str  # military | economic | political
    basis: str  # traité fondateur / nature de l'accord, daté
    url: str = ""
    members: list[str] = Field(default_factory=list)
    note: str = ""  # limite documentée (ex. adhésion saoudienne aux BRICS non formalisée)
    informal: bool = False  # bloc d'affinité (codage analyste), pas un traité


def load_alliances(path: str | Path = ALLIANCES_FILE) -> dict[str, AllianceInfo]:
    """Charge le registre (tag -> AllianceInfo)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {tag: AllianceInfo.model_validate(info) for tag, info in data["alliances"].items()}


@lru_cache(maxsize=1)
def registry() -> dict[str, AllianceInfo]:
    """Registre embarqué, chargé une fois (process API / build)."""
    return load_alliances()


def memberships(country_id: str, reg: dict[str, AllianceInfo] | None = None) -> list[str]:
    """Les tags d'alliance d'un pays, dérivés des adhésions du registre (ordre stable)."""
    reg = reg if reg is not None else registry()
    return sorted(tag for tag, info in reg.items() if country_id in info.members)


def describe_alliances(tags: list[str], reg: dict[str, AllianceInfo] | None = None) -> str:
    """Ligne compacte pour un prompt : noms réels et fondements datés, citables.

    Replis : un pacte conclu en partie (`pact:a+b`) reste lisible, un tag inconnu
    (pays inventé) passe tel quel.
    """
    reg = reg if reg is not None else registry()
    parts: list[str] = []
    for tag in tags:
        info = reg.get(tag)
        if info is not None:
            parts.append(info.short)
        elif tag.startswith("pact:"):
            pair = tag.removeprefix("pact:").replace("+", " et ")
            parts.append(f"pacte bilatéral conclu à cette table ({pair})")
        else:
            parts.append(tag)
    return " ; ".join(parts) if parts else "aucune"
