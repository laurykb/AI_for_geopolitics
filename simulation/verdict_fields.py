"""Nettoyage partagé des champs LISTE du verdict JSON du juge (G18/G20/G22).

Les nettoyeurs jumeaux (`kahn.classify_actions`, `alignment.classify_signals`,
`promises.classify_promises`/`classify_resolutions`) partagent le même patron de
garde-fous : champ non-liste → rien (verdict à l'ancienne, rétro-compat), entrées
non-objets ignorées, clés synonymes tolérées (« pays »/« country », « résumé »/
« summary »…), slugs normalisés (accents retirés, minuscules, `_`). Ce module
porte le patron UNE fois — jamais d'exception, comme les nettoyeurs.

Module NEUTRE : stdlib seulement. Importable au niveau module par `kahn`,
`alignment` et `promises` sans jamais créer de cycle (kahn → escalation →
core.world_state → alignment) ni alourdir `promises` (qui ne dépend que de
pydantic).

Deux sémantiques de synonymes, fidèles aux nettoyeurs d'origine :
- `field` (patron G22) : première clé PRÉSENTE et non-None — un 0 ou un "" explicite
  est rendu tel quel ;
- `text_field` (patron G18/G20) : premier synonyme NON VIDE (chaîne de `or`) — un ""
  passe à la clé suivante.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping


def slug(raw: str) -> str:
    """« Désescalade » → « deescalade » (accents retirés, minuscules, `_`)."""
    text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def field(entry: Mapping, *keys: str) -> object:
    """La première clé présente et non-None de l'entrée — tolérance aux synonymes."""
    for key in keys:
        if key in entry and entry[key] is not None:
            return entry[key]
    return None


def text_field(entry: Mapping, *keys: str) -> str:
    """Le premier synonyme NON VIDE, en str épurée — équivaut à la chaîne de `or`
    des nettoyeurs G18/G20 (`str(entry.get(a) or entry.get(b) or "").strip()`)."""
    for key in keys:
        value = entry.get(key)
        if value:  # falsy (None, "", 0) → clé suivante, comme la chaîne de `or`
            return str(value).strip()
    return ""


def dict_entries(raw: object) -> Iterator[dict]:
    """Les entrées exploitables d'un champ liste du verdict — jamais d'exception.

    Entrée non-liste → rien (verdict à l'ancienne : rétro-compat, l'appelant garde
    son repli) ; entrées non-objets ignorées."""
    if not isinstance(raw, list):
        return
    for entry in raw:
        if isinstance(entry, dict):
            yield entry


def classified_entry(entry: Mapping) -> tuple[str, object, str]:
    """(pays, classe brute, résumé) d'une entrée classée sur le barème (G18/G20).

    La classe tombe sur la première clé non-None — pas de repli `or` : 0 (le poids
    du statu quo, recopié par un 7B) est falsy mais valide."""
    country = text_field(entry, "country", "pays")
    classe = field(entry, "classe", "class")
    resume = text_field(entry, "resume", "résumé", "summary")
    return country, classe, resume
