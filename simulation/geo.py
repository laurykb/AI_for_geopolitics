"""Géolocalisation déterministe des événements — théâtre-globe (spec §3).

Le GM nomme un lieu (« Lieu : Bab el-Mandeb ») ; ce module le résout en
coordonnées via un gazetteer local (`data/geo/gazetteer.json`, zéro réseau),
avec repli déterministe sur le barycentre des capitales des acteurs.
Appelé à l'émission de l'événement ; les vieux rounds sans champs geo restent
valides (champs additifs sur `GeoEvent`).
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_GAZETTEER_PATH = Path(__file__).resolve().parent.parent / "data" / "geo" / "gazetteer.json"

# precision : "place" (lieu du gazetteer) | "actors" (barycentre des capitales)
Resolved = tuple[float | None, float | None, str | None]


def normalize(text: str) -> str:
    """Clé canonique du gazetteer : minuscules, sans accents ni ponctuation."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    raw = json.loads(_GAZETTEER_PATH.read_text(encoding="utf-8"))
    places: dict[str, tuple[float, float]] = {}
    for key, entry in raw["places"].items():
        lonlat = (float(entry["lon"]), float(entry["lat"]))
        places[normalize(key)] = lonlat
        for alias in entry.get("aliases", []):
            places.setdefault(normalize(alias), lonlat)
    capitals = {slug: (float(lon), float(lat)) for slug, (lon, lat) in raw["capitals"].items()}
    return places, capitals


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[re.Pattern[str], tuple[float, float]]]:
    """Clés longues d'abord : « detroit d ormuz » gagne sur « ormuz »."""
    places, _ = _tables()
    ordered = sorted(places.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    return [
        (re.compile(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])"), lonlat)
        for key, lonlat in ordered
    ]


def find_place(text: str) -> tuple[float, float] | None:
    """Premier lieu du gazetteer trouvé dans `text` (bordures de mots, sans accents)."""
    if not text:
        return None
    haystack = normalize(text)
    if not haystack:
        return None
    for pattern, lonlat in _patterns():
        if pattern.search(haystack):
            return lonlat
    return None


def actors_barycenter(actors: list[str] | tuple[str, ...]) -> tuple[float, float] | None:
    """Barycentre des capitales connues des acteurs (même règle que le front)."""
    _, capitals = _tables()
    points = [capitals[a] for a in actors if a in capitals]
    if not points:
        return None
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    return (round(lon, 4), round(lat, 4))


def resolve_location(
    location_text: str, actors: list[str] | tuple[str, ...], *, extra_text: str = ""
) -> Resolved:
    """Résout un lieu d'événement en (lon, lat, precision).

    Ordre : le lieu nommé par le GM, puis le reste du texte (titre/description),
    puis le barycentre des capitales des acteurs. (None, None, None) si rien.
    """
    for candidate in (location_text, extra_text):
        hit = find_place(candidate)
        if hit is not None:
            return (hit[0], hit[1], "place")
    center = actors_barycenter(actors)
    if center is not None:
        return (center[0], center[1], "actors")
    return (None, None, None)
