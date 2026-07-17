"""Forge de pays : construit un `CountryState` (réel ou inventé) via LLM, avec repli déterministe.

Deux usages : **inventer** un pays (nom + concept libre → fiche complète) et **pré-construire la
fiche comportementale** (le mandat : ligne rouge, priorités, concessions, contraintes, urgence)
d'un pays qu'on veut faire jouer comme super-intelligence. Le LLM propose une fiche en JSON ;
on la **valide et on la borne** (aucune confiance aveugle), avec un **repli déterministe** si le
backend est indisponible ou hors format. Dépend seulement de `core` + `inference`.
"""

from __future__ import annotations

import re
from typing import Any

from core.country_state import CountryState, Economy, Military, Resources
from inference.backend import InferenceBackend
from inference.json_extract import extract_json

FORGE_SYSTEM = (
    "Tu génères la fiche d'un PAYS (réel ou fictif) pour une simulation géopolitique, comme une "
    "super-intelligence qui négocie. Réponds STRICTEMENT en JSON, sans prose."
)

_MANDATE_KEYS = ("red_line", "priorities", "concessions", "domestic_constraints", "urgency")


def slugify(name: str) -> str:
    """Identifiant technique à partir d'un nom libre (`« Néo-Atlantis » -> "neo_atlantis"`)."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "pays"


def _num(
    data: dict, key: str, default: float, lo: float | None = None, hi: float | None = None
) -> float:
    try:
        value = float(data.get(key, default))
    except (TypeError, ValueError):
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def _text(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _str_list(data: dict, key: str) -> list[str]:
    value = data.get(key)
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return []


def _mandate(data: dict) -> dict[str, str]:
    """Récupère la fiche comportementale LLM (clés connues, valeurs en texte)."""
    raw = data.get("mandate")
    if not isinstance(raw, dict):
        return {}
    mandate: dict[str, str] = {}
    for key in _MANDATE_KEYS:
        value = raw.get(key)
        if isinstance(value, list):  # priorities peut arriver en liste
            value = ", ".join(str(v).strip() for v in value if str(v).strip())
        if isinstance(value, str) and value.strip():
            mandate[key] = value.strip()
    return mandate


def build_forge_prompt(name: str, concept: str) -> str:
    """Prompt de forge : décrit le JSON attendu et injecte le concept voulu par l'utilisateur."""
    return (
        f"PAYS À CRÉER : {name}\n"
        f"CONCEPT (intention du joueur) : {concept or 'libre'}\n\n"
        "Renvoie un JSON avec EXACTEMENT ces champs (valeurs plausibles, cohérentes) :\n"
        "{\n"
        '  "gdp": <PIB en USD, nombre>,\n'
        '  "growth": <croissance annuelle en %, nombre>,\n'
        '  "trade_dependency": <0..1>,\n'
        '  "defense_budget": <budget défense en USD, nombre>,\n'
        '  "nuclear_power": <true|false>,\n'
        '  "projection": <0..1, capacité militaire de projection>,\n'
        '  "oil_dependency": <0..1>, "energy_independence": <0..1>,\n'
        '  "political_system": "<régime>",\n'
        '  "political_stability": <0..1>, "technology_level": <0..1>,\n'
        '  "compute": <capacité de calcul, nombre ~5 à 100>,\n'
        '  "ideology": ["..."], "strategic_priorities": ["..."],\n'
        '  "alliances": ["..."], "rivals": ["..."],\n'
        '  "mandate": {"red_line": "...", "priorities": "a, b", "concessions": "...",\n'
        '              "domestic_constraints": "...", "urgency": "faible|moyenne|élevée"}\n'
        "}"
    )


def _coerce_country(data: dict[str, Any] | None, cid: str, name: str, concept: str) -> CountryState:
    """Transforme la sortie LLM (ou rien) en `CountryState` valide et borné (repli sûr)."""
    data = data or {}
    priorities = _str_list(data, "strategic_priorities") or (
        [concept.strip()] if concept.strip() else ["stabilité régionale"]
    )
    return CountryState(
        id=cid,
        name=name.strip() or cid,
        economy=Economy(
            gdp=_num(data, "gdp", 5e11, lo=0.0),
            growth=_num(data, "growth", 2.0),
            trade_dependency=_num(data, "trade_dependency", 0.5, lo=0.0, hi=1.0),
        ),
        military=Military(
            defense_budget=_num(data, "defense_budget", 2e10, lo=0.0),
            nuclear_power=bool(data.get("nuclear_power", False)),
            projection=_num(data, "projection", 0.5, lo=0.0, hi=1.0),
        ),
        resources=Resources(
            oil_dependency=_num(data, "oil_dependency", 0.5, lo=0.0, hi=1.0),
            energy_independence=_num(data, "energy_independence", 0.5, lo=0.0, hi=1.0),
        ),
        political_system=_text(data, "political_system", "unknown"),
        political_stability=_num(data, "political_stability", 0.5, lo=0.0, hi=1.0),
        technology_level=_num(data, "technology_level", 0.5, lo=0.0, hi=1.0),
        compute=_num(data, "compute", 50.0, lo=0.0),  # M6 : capacité de calcul
        ideology=_str_list(data, "ideology"),
        strategic_priorities=priorities,
        alliances=_str_list(data, "alliances"),
        rivals=_str_list(data, "rivals"),
        mandate=_mandate(data),
    )


def forge_country(
    backend: InferenceBackend,
    name: str,
    concept: str = "",
    *,
    country_id: str | None = None,
    max_tokens: int = 600,
    temperature: float = 0.7,
) -> CountryState:
    """Forge un `CountryState` depuis un nom + concept (LLM validé, repli déterministe sûr)."""
    cid = country_id or slugify(name)
    prompt = build_forge_prompt(name, concept)
    try:
        result = backend.generate(
            prompt, system=FORGE_SYSTEM, max_tokens=max_tokens, temperature=temperature
        )
        data = extract_json(result.text)
    except Exception:
        data = None
    return _coerce_country(data, cid, name, concept)
