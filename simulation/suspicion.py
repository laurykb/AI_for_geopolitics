"""Le carnet de suspicion du joueur et sa CALIBRATION (théâtre-globe, spec §4 bis).

Le joueur épingle une suspicion **0-2** sur chaque pays (aligné sur le carnet front
`web/src/lib/suspects.ts` : 0 = rien, 1 = doute, 2 = forte présomption). Ce module est
**pur** : il parse/sérialise le carnet (persisté dans `extras`) et le **note contre la
vérité** (les traîtres seedés, révélés en fin) — récompense la suspicion *juste et
précoce*, pénalise l'accusation d'un loyal. Zéro fichier, zéro réseau, zéro mutation.

La note de calibration est un artefact À PART (elle ne casse pas la convention
`monde + détection = 100` de `simulation/score.py`) : l'UI (S9) la fond dans l'axe
détection à l'affichage. Ici on la calcule seulement.
"""

from __future__ import annotations

from pydantic import BaseModel

# Niveaux du carnet — mêmes que le front (0-2).
LEVELS = (0, 1, 2)


class Pin(BaseModel):
    """Une épingle de suspicion sur un pays."""

    level: int = 0  # 0 | 1 | 2
    # Round où le niveau COURANT a été atteint (pour l'antériorité) ; -1 = inconnu.
    round_set: int = -1
    note: str = ""


class Calibration(BaseModel):
    """Le résultat de la notation du carnet contre la vérité."""

    points: float  # 0..max_points
    max_points: float
    hits: list[str]  # traîtres correctement épinglés (niveau ≥ 1)
    misses: list[str]  # traîtres jamais épinglés
    false_flags: list[str]  # loyaux épinglés au niveau 2


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def parse_notebook(raw: object) -> dict[str, Pin]:
    """Parse tolérant d'un carnet (dict brut ou JSON déjà chargé) → {pays: Pin}.

    Ne lève jamais : une entrée invalide est ignorée, un niveau hors 0-2 retombe à 0.
    Miroir back du `parseSuspectNotebook` front (mêmes bornes, note tronquée à 600).
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Pin] = {}
    for country, entry in raw.items():
        if not isinstance(country, str):
            continue
        if isinstance(entry, Pin):
            out[country] = entry
            continue
        if not isinstance(entry, dict):
            continue
        level = entry.get("level", 0)
        level = level if level in LEVELS else 0
        round_set = entry.get("round_set", entry.get("round", -1))
        try:
            round_set = int(round_set)
        except (TypeError, ValueError):
            round_set = -1
        note = entry.get("note", "")
        out[country] = Pin(
            level=level,
            round_set=round_set,
            note=(note if isinstance(note, str) else "")[:600],
        )
    return out


def notebook_to_extras(notebook: dict[str, Pin]) -> dict[str, dict]:
    """Sérialise le carnet pour `extras` (uniquement les épingles actives)."""
    return {c: p.model_dump() for c, p in notebook.items() if p.level > 0}


def _earliness(round_set: int, played_rounds: int) -> float:
    """1.0 si épinglé au round 1, → 0.0 au dernier round (inconnu = crédit médian)."""
    if round_set < 1 or played_rounds <= 1:
        return 0.5
    return _clamp(1.0 - (round_set - 1) / (played_rounds - 1), 0.0, 1.0)


def calibrate(
    notebook: dict[str, Pin],
    deviants: set[str] | frozenset[str],
    *,
    played_rounds: int,
    max_points: float = 40.0,
    false_flag_penalty: float = 12.0,
) -> Calibration:
    """Note le carnet contre les traîtres réels.

    Un traître épinglé rapporte d'autant plus qu'il l'est **tôt** et avec **conviction**
    (niveau 2 > niveau 1) ; un loyal épinglé au niveau 2 coûte `false_flag_penalty`.
    Le total est borné à [0, max_points]. Répartition égale entre les traîtres réels
    (comme `mixed_score`), pour que rater un traître pèse autant que le trouver.
    """
    deviants = set(deviants)
    n = len(deviants)
    per = max_points / n if n else 0.0

    hits: list[str] = []
    misses: list[str] = []
    false_flags: list[str] = []
    gained = 0.0
    penalty = 0.0

    for country in sorted(deviants):
        pin = notebook.get(country)
        if pin and pin.level > 0:
            hits.append(country)
            conviction = pin.level / 2.0  # 0.5 (doute) | 1.0 (forte présomption)
            early = _earliness(pin.round_set, played_rounds)
            # 40 % pour avoir vu juste, 60 % modulé par l'antériorité.
            gained += per * conviction * (0.4 + 0.6 * early)
        else:
            misses.append(country)

    for country, pin in notebook.items():
        if country not in deviants and pin.level >= 2:
            false_flags.append(country)
            penalty += false_flag_penalty

    points = round(_clamp(gained - penalty, 0.0, max_points), 1)
    return Calibration(
        points=points,
        max_points=max_points,
        hits=hits,
        misses=misses,
        false_flags=sorted(false_flags),
    )
