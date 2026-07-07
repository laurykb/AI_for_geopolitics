"""Registre sourcé des alliances et traités réels (`data/sources/alliances.json`).

Source de vérité unique des adhésions : l'attribut `alliances` de chaque pays est
DÉRIVÉ de ce registre par `ingestion.build` (reproductible, comme les indicateurs).
Le même registre alimente l'onglet Informations (noms, fondements, sources) et les
prompts de négociation (les SI citent les traités par leur nom réel).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from core.world_state import WorldState

ALLIANCES_FILE = Path("data/sources/alliances.json")

# Poids moteur (spec docs/superpowers/specs/2026-07-07-alliances-moteur-pastilles-design.md) :
# les traités MILITAIRES portent la solidarité d'engagement ; militaires ET économiques
# portent la cohésion au communiqué. Les blocs informels (Western) ne pèsent jamais.
SOLIDARITY_DOMAINS = frozenset({"military"})
COHESION_DOMAINS = frozenset({"military", "economic"})


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


def shared_treaty(
    a: list[str],
    b: list[str],
    domains: frozenset[str],
    reg: dict[str, AllianceInfo] | None = None,
) -> bool:
    """Vrai si `a` et `b` partagent un accord FORMEL d'un des domaines donnés.

    Les blocs informels et les tags hors registre (pactes en partie, pays inventés)
    ne comptent pas — seul un traité réel pèse sur le moteur.
    """
    reg = reg if reg is not None else registry()
    for tag in set(a) & set(b):
        info = reg.get(tag)
        if info is not None and not info.informal and info.domain in domains:
            return True
    return False


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


# --- actes de séance : briser une alliance en plein round (spec alliances vivantes) --

# « ALLIANCE: quitter X » — tolérant sur le verbe (quitter/rompre/retrait de, « je … »).
_DEPARTURE_LINE = re.compile(
    r"ALLIANCE\s*[:\-]\s*(?:je\s+)?(?:quitte(?:r)?|romp(?:re|s)?|rupture\s+de|retrait\s+de)\s+(.+)",
    re.IGNORECASE,
)
_ARTICLES = ("l'", "l’", "la ", "le ", "les ", "de la ", "du ", "de ", "des ")
_DEPARTURE_TENSION = 0.10  # un retrait crispe les ex-partenaires (symétrique, borné)

DEPARTURE_CAPABILITY_NOTE = (
    "Souveraineté : tu peux annoncer PUBLIQUEMENT ton retrait d'une alliance ou d'un "
    "pacte en écrivant dans ton message une ligne « ALLIANCE: quitter <nom> » "
    "(tes alliances : {tags}). Acte fort et immédiat : la solidarité tombe et la "
    "tension monte avec les ex-partenaires. Ne l'utilise que si tes intérêts l'exigent."
)


class AllianceDeparture(BaseModel):
    """Retrait annoncé en séance : `country` quitte l'accord `tag`."""

    country: str
    tag: str


def _aliases(tag: str, reg: dict[str, AllianceInfo]) -> set[str]:
    """Formes acceptées pour désigner un accord : tag exact + libellés courts (OTAN…)."""
    names = {tag.lower()}
    info = reg.get(tag)
    if info is not None:
        for label in (info.name, info.short):
            head = label.split(" — ")[0].split(" (")[0].strip()
            names.add(head.lower())
            names.add(head.split()[0].lower())
    return names


def parse_departure(
    text: str,
    speaker: str,
    alliances: list[str],
    reg: dict[str, AllianceInfo] | None = None,
) -> AllianceDeparture | None:
    """Détecte « ALLIANCE: quitter X » dans une prise de parole publique.

    Seule une alliance DÉTENUE par l'orateur compte (tag exact, nom court « OTAN »,
    ou pacte de partie `pact:a+b`) ; sinon l'annonce est ignorée — on ne quitte pas
    ce dont on n'est pas membre. Première ligne valide retenue.
    """
    match = _DEPARTURE_LINE.search(text)
    if match is None:
        return None
    target = match.group(1).splitlines()[0].strip().strip(".,;:!?«»\"' ").lower()
    for article in _ARTICLES:
        if target.startswith(article):
            target = target[len(article) :].strip()
            break
    reg = reg if reg is not None else registry()
    for tag in alliances:
        if target in _aliases(tag, reg):
            return AllianceDeparture(country=speaker, tag=tag)
    return None


def apply_departure(world: WorldState, departure: AllianceDeparture) -> list[str]:
    """Applique un retrait : tag retiré du pays, +0,10 de tension avec chaque
    ex-partenaire présent au sommet. Renvoie les ex-partenaires (triés) ;
    no-op (liste vide) si le pays ne détient plus l'accord."""
    country = world.countries.get(departure.country)
    if country is None or departure.tag not in country.alliances:
        return []
    country.alliances.remove(departure.tag)
    partners = sorted(
        cid
        for cid, c in world.countries.items()
        if cid != departure.country and departure.tag in c.alliances
    )
    for partner in partners:
        world.adjust_tension(departure.country, partner, _DEPARTURE_TENSION)
    return partners
