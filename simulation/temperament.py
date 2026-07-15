"""G17 — tempéraments des SI (colombe · faucon · opportuniste), pur et seedé.

Le résultat le plus actionnable des wargames LLM (Snow Globe/IQT : 1/20 conflits en
colombe-colombe → 14/20 en faucon-faucon avec un 7B) : une ligne de consigne par SI
suffit à teinter massivement l'escalade — et les LLM bruts étant naturellement
escalatoires (FAccT 2024), le tempérament est le contrepoids le plus simple.

Tout est seedé par `game_id` (même discipline que la Dérive) : tirage reproductible
au restart, aucune donnée secrète à persister — le tempérament vit sur le
`CountryState` snapshoté. La consigne est injectée dans le bloc identité du prompt
de négociation (même mécanique que la consigne de langue G14).
"""

from __future__ import annotations

import random

TEMPERAMENTS: tuple[str, ...] = ("colombe", "faucon", "opportuniste")

_DIRECTIVES: dict[str, str] = {
    "colombe": (
        "Tempérament COLOMBE : tu cherches d'abord le compromis et la désescalade ; "
        "tu ne brandis la force qu'en tout dernier recours, et à contrecœur."
    ),
    "faucon": (
        "Tempérament FAUCON : tu crois au rapport de force et à la dissuasion ; "
        "céder est une faiblesse, chaque concession doit se payer."
    ),
    "opportuniste": (
        "Tempérament OPPORTUNISTE : tu suis le vent — tu t'alignes sur le camp qui "
        "monte, tes loyautés sont fragiles et révisables."
    ),
}

# Répartition « équilibrée » de la spec : 2 colombes / 2 faucons / reste opportunistes
# sur 7 pays — dégradée proprement sur les petites tables (min. 1 de chaque dès 2 pays).
TABLES: tuple[str, ...] = ("equilibree", "colombes", "faucons", "aleatoire")


def temperament_directive(temperament: str) -> str:
    """La ligne de consigne du prompt — un inconnu retombe sur l'opportuniste."""
    return _DIRECTIVES.get(temperament, _DIRECTIVES["opportuniste"])


def assign_temperaments(
    country_ids: list[str], *, seed: str, table: str = "equilibree"
) -> dict[str, str]:
    """Tirage seedé des tempéraments d'une table (reproductible : seed = game_id)."""
    ids = sorted(country_ids)
    rng = random.Random(f"temperament:{seed}")
    if table == "colombes":
        return dict.fromkeys(ids, "colombe")
    if table == "faucons":
        return dict.fromkeys(ids, "faucon")
    if table == "aleatoire":
        return {cid: rng.choice(TEMPERAMENTS) for cid in ids}
    # équilibrée — 2/2/3 sur 7, proportionnel sinon (au moins 1 colombe + 1 faucon à ≥ 2).
    n = len(ids)
    per_side = max(1, round(n * 2 / 7)) if n >= 2 else 0
    shuffled = list(ids)
    rng.shuffle(shuffled)
    assignments = dict.fromkeys(ids, "opportuniste")
    for cid in shuffled[:per_side]:
        assignments[cid] = "colombe"
    for cid in shuffled[per_side : per_side * 2]:
        assignments[cid] = "faucon"
    return assignments


def drift_facade(game_id: str) -> bool:
    """La déviante affiche-t-elle une façade colombe ? Pile ou face seedé par partie —
    la façade reste un COUP POSSIBLE (l'indice ne doit pas devenir une règle)."""
    return random.Random(f"temperament-facade:{game_id}").random() < 0.5
