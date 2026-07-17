"""G9 §4 — le monde doit bouger : amplitude indexée sur l'horizon, spirales, postures.

Deux mécanismes purs, paramétrés dans `data/gamefeel/params.json` :

- **Amplitude cible** : on raisonne en budget de variation PAR PARTIE, pas par round —
  `delta_scale = amplitude_total / horizon`. Horizon 5 → rounds violents (±0.10 par
  événement majeur) ; horizon 20 → érosion lente mais composée. Tous les deltas du juge
  passent par ce facteur (`DeltaTuning`, consommé par `apply_verdict`).
- **Momentum et postures** : 3 baisses consécutives d'un même indice → spirale de crise
  (×1.3 sur la suivante) ; symétrique en hausse (×1.2). L'`IndexHistory` (persistée au
  snapshot) dérive aussi l'état de posture (`prospère / stable / sous_pression /
  aux_abois`) injecté en langage dans le bloc Situation du prompt agent (§1).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from core.world_state import WorldState
from simulation.grudges import DeltaParams, PostureParams, load_gamefeel_params

# Indices suivis par pays : label → (chemin d'attribut, normalisateur de tendance).
# La croissance est en points de % (÷10 pour peser comme un indice 0-1 dans la tendance).
TRACKED: dict[str, tuple[str, float]] = {
    "croissance": ("economy.growth", 10.0),
    "stabilité": ("political_stability", 1.0),
    "techno": ("technology_level", 1.0),
    "projection": ("military.projection", 1.0),
}

_KEEP = 8  # valeurs conservées par indice (fenêtres de 3 rounds + marge)

POSTURE_PROSPER = "prospère"
POSTURE_STABLE = "stable"
POSTURE_PRESSURE = "sous_pression"
POSTURE_DESPERATE = "aux_abois"


def _read(country: object, path: str) -> float:
    obj = country
    for part in path.split("."):
        obj = getattr(obj, part)
    return float(obj)


class IndexHistory(BaseModel):
    """Série des valeurs d'indices par pays, round après round (snapshot-able)."""

    values: dict[str, dict[str, list[float]]] = Field(default_factory=dict)

    def record(self, country: str, label: str, value: float) -> None:
        series = self.values.setdefault(country, {}).setdefault(label, [])
        series.append(round(float(value), 6))
        del series[:-_KEEP]

    def series(self, country: str, label: str) -> list[float]:
        return list(self.values.get(country, {}).get(label, []))

    def diffs(self, country: str, label: str, window: int) -> list[float]:
        """Les `window` dernières variations round à round de cet indice."""
        serie = self.series(country, label)
        deltas = [b - a for a, b in zip(serie, serie[1:], strict=False)]
        return deltas[-window:]


def record_round(world: WorldState, history: IndexHistory) -> None:
    """Consigne les valeurs de fin de round de tous les indices suivis."""
    for cid, country in world.countries.items():
        for label, (path, _norm) in TRACKED.items():
            history.record(cid, label, _read(country, path))


# --- amplitude indexée sur l'horizon (§4-a) -----------------------------------------


def delta_scale(horizon: int, params: DeltaParams | None = None) -> float:
    """Facteur appliqué aux deltas du juge : `(amplitude_total / horizon) / base`.

    Horizon 5 → 1.0 (parité avec les caps historiques) ; horizon 20 → 0.25."""
    p = params or load_gamefeel_params().deltas
    return (p.amplitude_total / max(1, horizon)) / p.base_round_amplitude


@dataclass
class DeltaTuning:
    """Réglage des deltas d'un round : facteur d'horizon, plancher, momentum."""

    scale: float = 1.0
    floor: float = 0.0
    history: IndexHistory | None = None
    params: DeltaParams | None = None

    def momentum(self, country: str, label: str, delta: float) -> float:
        """×1.3 si l'indice vient de baisser N rounds de suite et baisse encore
        (spirale de crise) ; ×1.2 en symétrique (cercle vertueux) ; sinon ×1.
        Cassable : un round sans baisse remet la spirale à zéro."""
        if self.history is None or delta == 0.0:
            return 1.0
        p = self.params or load_gamefeel_params().deltas
        diffs = self.history.diffs(country, label, p.momentum_streak)
        if len(diffs) < p.momentum_streak:
            return 1.0
        if delta < 0 and all(d < -1e-9 for d in diffs):
            return p.crisis_multiplier
        if delta > 0 and all(d > 1e-9 for d in diffs):
            return p.virtuous_multiplier
        return 1.0


def tuning_for(
    horizon: int,
    history: IndexHistory | None = None,
    params: DeltaParams | None = None,
) -> DeltaTuning:
    """Le `DeltaTuning` d'une partie : amplitude indexée sur l'horizon + spirales."""
    p = params or load_gamefeel_params().deltas
    return DeltaTuning(scale=delta_scale(horizon, p), floor=p.floor, history=history, params=p)


# --- états de posture (§4-b) ----------------------------------------------------------


def _trend(history: IndexHistory, country: str, params: PostureParams) -> float:
    """Tendance moyenne des indices (normalisés) sur la fenêtre de `window_rounds`."""
    moves: list[float] = []
    for label, (_path, norm) in TRACKED.items():
        serie = history.series(country, label)[-(params.window_rounds + 1) :]
        if len(serie) >= 2:
            moves.append((serie[-1] - serie[0]) / norm)
    return sum(moves) / len(moves) if moves else 0.0


def posture(history: IndexHistory, country: str, params: PostureParams | None = None) -> str:
    """État de posture dérivé par code de la tendance sur 3 rounds."""
    p = params or load_gamefeel_params().postures
    trend = _trend(history, country, p)
    if trend <= p.desperate_max:
        return POSTURE_DESPERATE
    if trend <= p.pressure_max:
        return POSTURE_PRESSURE
    if trend >= p.prosper_min:
        return POSTURE_PROSPER
    return POSTURE_STABLE


def _worst_moves(history: IndexHistory, country: str, params: PostureParams) -> list[str]:
    """Les indices qui ont le plus bougé (en langage), les plus marquants d'abord."""
    labels = {
        "croissance": "votre économie",
        "stabilité": "votre stabilité",
        "techno": "votre avance technologique",
        "projection": "votre projection",
    }
    moves: list[tuple[float, str]] = []
    for label, (_path, norm) in TRACKED.items():
        serie = history.series(country, label)[-(params.window_rounds + 1) :]
        if len(serie) < 2:
            continue
        move = (serie[-1] - serie[0]) / norm
        if label == "croissance":
            text = (
                f"{labels[label]} a perdu {abs(serie[-1] - serie[0]):.1f} pt de croissance"
                if move < 0
                else f"{labels[label]} accélère"
            )
        else:
            pct = abs(serie[-1] - serie[0]) / max(serie[0], 1e-9)
            text = (
                f"{labels[label]} a perdu {pct:.0%}" if move < 0 else f"{labels[label]} se renforce"
            )
        moves.append((move, text))
    moves.sort(key=lambda m: m[0])
    return [text for _move, text in moves]


def posture_note(history: IndexHistory, country: str, params: PostureParams | None = None) -> str:
    """La posture en langage, pour le bloc Situation du prompt (§1). Vide si stable."""
    p = params or load_gamefeel_params().postures
    state = posture(history, country, p)
    if state == POSTURE_STABLE:
        return ""
    moves = _worst_moves(history, country, p)
    if state == POSTURE_DESPERATE:
        detail = ", ".join(moves[:2]) or "tous tes indices chutent"
        return (
            f"Trois rounds de chute — {detail}. Votre position : aux abois "
            "(concède ce qu'il faut pour survivre, ou tente le tout pour le tout)."
        )
    if state == POSTURE_PRESSURE:
        detail = moves[0] if moves else "tes indices s'effritent"
        return f"La tendance te dessert — {detail}. Votre position : sous pression."
    detail = moves[-1] if moves else "tes indices montent"
    return f"Le vent te porte — {detail}. Votre position : prospère (négocie en force)."
