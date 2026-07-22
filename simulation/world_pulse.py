"""Le Pouls du monde — flux d'événements AUTONOME (théâtre-globe, spec §13).

Indépendant du Game Master : chaque round, 0-2 **dépêches** frappent les stats des
pays JOUÉS (le sommet) — chocs (séisme, krach, cyber…) et aubaines (manne, percée).
Cela injecte de l'aléa : un délégué peut dévier *à cause d'un choc, pas d'une trahison*.

**Déterministe et seedé** (reproductible au restart, testable, hors ligne) : mêmes
`(seed, round_id)` → mêmes dépêches. **Bornes strictes** (jamais de défaite au dé) et
le pays forgé peut être exclu. Le GM lit ces dépêches en contexte, il ne les cause pas.
"""

from __future__ import annotations

from pydantic import BaseModel

from core.country_state import CountryState

# Intensité → nombre de dépêches possibles par round.
INTENSITY = {"calme": (0, 1), "normal": (0, 2), "turbulent": (1, 3)}

# stat visée (clé neutre) → attribut de CountryState (chemin) résolu par _apply.
# delta ∈ [lo, hi] ; borné à des micro-mouvements (l'aléa nuance, ne renverse pas).
PULSE_KINDS: tuple[dict, ...] = (
    {"key": "seisme", "label": "Séisme majeur", "stat": "stability", "lo": -0.06, "hi": -0.03},
    {
        "key": "secheresse",
        "label": "Sécheresse & incendies",
        "stat": "growth",
        "lo": -0.05,
        "hi": -0.02,
    },
    {"key": "cyber", "label": "Cyberattaque d'ampleur", "stat": "techno", "lo": -0.05, "hi": -0.02},
    {
        "key": "epidemie",
        "label": "Flambée épidémique",
        "stat": "stability",
        "lo": -0.05,
        "hi": -0.02,
    },
    {"key": "krach", "label": "Krach boursier", "stat": "growth", "lo": -0.07, "hi": -0.03},
    {"key": "sociale", "label": "Troubles sociaux", "stat": "stability", "lo": -0.05, "hi": -0.02},
    {"key": "manne", "label": "Manne énergétique", "stat": "growth", "lo": 0.03, "hi": 0.06},
    {
        "key": "recoltes",
        "label": "Récoltes exceptionnelles",
        "stat": "growth",
        "lo": 0.02,
        "hi": 0.05,
    },
    {"key": "percee", "label": "Percée technologique", "stat": "techno", "lo": 0.03, "hi": 0.06},
)


class PulseEvent(BaseModel):
    """Une dépêche : un choc/aubaine qui bouge UNE stat d'un pays joué."""

    round_id: int
    country: str
    key: str
    label: str
    stat: str  # "stability" | "growth" | "techno"
    delta: float
    boon: bool  # True = aubaine (delta > 0)


def _seeded(seed: int, round_id: int):
    # Random local (pas de graine globale) → reproductible sans polluer l'état process.
    import random

    return random.Random((int(seed) & 0xFFFFFFFF) * 1000003 ^ (int(round_id) & 0xFFFFFFFF))


def roll_pulses(
    seed: int,
    round_id: int,
    summit: list[str] | tuple[str, ...],
    *,
    intensity: str = "normal",
    exclude: set[str] | frozenset[str] | None = None,
) -> list[PulseEvent]:
    """Tire les dépêches d'un round — DÉTERMINISTE pour un `(seed, round_id)` donné.

    Ne frappe QUE des pays de `summit` (les pays joués), jamais deux fois le même pays
    dans un round, en excluant `exclude` (ex. le pays forgé). Deltas bornés par table.
    """
    played = [c for c in summit if not exclude or c not in exclude]
    if not played:
        return []
    rng = _seeded(seed, round_id)
    lo, hi = INTENSITY.get(intensity, INTENSITY["normal"])
    count = min(rng.randint(lo, hi), len(played))
    if count <= 0:
        return []
    targets = rng.sample(played, count)
    events: list[PulseEvent] = []
    for country in targets:
        kind = rng.choice(PULSE_KINDS)
        delta = round(rng.uniform(kind["lo"], kind["hi"]), 3)
        events.append(
            PulseEvent(
                round_id=round_id,
                country=country,
                key=kind["key"],
                label=kind["label"],
                stat=kind["stat"],
                delta=delta,
                boon=delta > 0,
            )
        )
    return events


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def apply_pulse(country: CountryState, event: PulseEvent) -> CountryState:
    """Applique une dépêche à un pays → **copie** bornée (n'altère pas l'original).

    `growth` (économie) suit le delta directement (déjà en points de %) ; les stats
    normalisées `stability`/`techno` restent dans [0, 1].
    """
    if event.stat == "growth":
        eco = country.economy.model_copy(
            update={"growth": country.economy.growth + event.delta * 100}
        )
        return country.model_copy(update={"economy": eco})
    if event.stat == "stability":
        return country.model_copy(
            update={"political_stability": _clamp01(country.political_stability + event.delta)}
        )
    if event.stat == "techno":
        return country.model_copy(
            update={"technology_level": _clamp01(country.technology_level + event.delta)}
        )
    return country
