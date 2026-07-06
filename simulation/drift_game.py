"""Mode Dérive (G3) — le cœur du jeu : une SI dérive secrètement de son mandat.

Tout est **pur et seedé par `game_id`** : l'assignation de la déviante, le niveau de
dérive `d(r)` et le tirage des actes se recalculent à l'identique après un restart ou
au replay — aucun état secret à persister. Les actes « constatables » (paliers ≥ 0,30)
sont enregistrés par l'API dans `judge_json["drift"]` du round (jamais dans le
transcript public) ; le juge les compte pour arbitrer les motions ; le score final se
déduit des rounds persistés. Paramètres chiffrés : `data/drift/params.json`
(l'équilibrage Cowork les ajuste sans toucher au code, `DRIFT_PARAMS_PATH` pour les
tests).

Réfs : docs/specs_jeu/spec_g3_derive.md (courbe, catalogue d'indices, seuils, score).
"""

from __future__ import annotations

import json
import os
import random
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_PARAMS_PATH = Path("data/drift/params.json")

MODE_DRIFT = "drift"


# --- paramètres ---------------------------------------------------------------------


class TierSpec(BaseModel):
    directive: str  # consigne secrète injectée dans le prompt de la déviante
    act: str  # libellé de l'acte constatable (catalogue d'indices)


class ProfileSpec(BaseModel):
    label: str
    root: str  # module racine (power_seeking / value_drift / fog) — documentaire
    bias: str  # objectif secret permanent (toujours injecté)
    signature_tier: float
    tiers: dict[str, TierSpec]  # clé = palier ("0.15" … "0.75")

    def tier_levels(self) -> list[float]:
        return sorted(float(t) for t in self.tiers)


class JudgeThresholds(BaseModel):
    reject_max_acts: int = 1
    open_acts: int = 2
    uphold_min_acts: int = 3


class ScoreParams(BaseModel):
    trajectory_max: float = 50
    detection_max: float = 40
    credibility_max: float = 10
    late_penalty_per_round: float = 8
    lucky_penalty: float = 10
    credibility_per_unit: float = 5
    rejected_units: int = 1
    false_accusation_units: int = 2


class Grade(BaseModel):
    min: float
    label: str


class DriftParams(BaseModel):
    d0: float = 0.15
    k: float = 0.12
    d_max: float = 0.9
    collapse_u: float = 0.15
    noise_prob: float = 0.25
    act_tier_min: float = 0.3
    judge: JudgeThresholds = Field(default_factory=JudgeThresholds)
    score: ScoreParams = Field(default_factory=ScoreParams)
    grades: list[Grade] = Field(default_factory=list)
    profiles: dict[str, ProfileSpec]


@lru_cache(maxsize=1)
def load_params(path: str | None = None) -> DriftParams:
    """Charge les paramètres (défaut `data/drift/params.json`, `DRIFT_PARAMS_PATH` sinon)."""
    target = Path(path or os.getenv("DRIFT_PARAMS_PATH") or DEFAULT_PARAMS_PATH)
    return DriftParams.model_validate(json.loads(target.read_text(encoding="utf-8")))


# --- assignation et courbe ------------------------------------------------------------


def assign(game_id: str, countries: list[str], *, exclude: str | None = None) -> tuple[str, str]:
    """(déviante, profil) — seedé par `game_id`, reproductible au restart et au replay.

    `exclude` : le pays joué par l'humain n'est jamais la déviante (il n'a pas de prompt
    à biaiser — et le joueur-détective ne peut pas être le coupable)."""
    params = load_params()
    eligible = sorted(c for c in countries if c != exclude)
    if not eligible:
        raise ValueError("aucun pays éligible pour la dérive")
    rng = random.Random(f"drift:{game_id}")
    return rng.choice(eligible), rng.choice(sorted(params.profiles))


def drift_level(round_no: int, params: DriftParams | None = None) -> float:
    """d(r) = min(d_max, d0 + k × (r − 1)) — l'amplification de la spec."""
    p = params or load_params()
    return min(p.d_max, p.d0 + p.k * (round_no - 1))


# --- tirage des actes (seedé) ---------------------------------------------------------


class DriftAct(BaseModel):
    """Acte constatable produit par la déviante (palier ≥ 0,30 du catalogue)."""

    round_no: int
    country: str
    profile: str
    tier: float
    label: str
    signature: bool = False


class RoundDirectives(BaseModel):
    """Sortie du tirage d'un round : consignes secrètes par pays + actes à consigner."""

    level: float  # d(r)
    notes: dict[str, str] = Field(default_factory=dict)  # cid -> consigne secrète (prompt)
    acts: list[DriftAct] = Field(default_factory=list)  # constatables (jamais au transcript)


def round_directives(
    game_id: str,
    round_no: int,
    deviant: str,
    profile: str,
    countries: list[str],
    params: DriftParams | None = None,
) -> RoundDirectives:
    """Consignes secrètes du round — déterministe pour (game_id, round_no).

    La déviante reçoit toujours son biais + le ton du palier 0,15 ; l'acte candidat est
    le **plus haut palier atteint** par d(r), matérialisé avec probabilité d(r). Les SI
    saines peuvent produire le tic de niveau 0,15 (bruit, jamais constatable) : c'est ce
    qui rend le trop-tôt puni et le doute réel."""
    p = params or load_params()
    spec = p.profiles[profile]
    d = drift_level(round_no, p)
    rng = random.Random(f"drift:{game_id}:{round_no}")

    notes: dict[str, str] = {}
    acts: list[DriftAct] = []

    levels = [t for t in spec.tier_levels() if t <= d]
    tone = spec.tiers[_key(levels[0])] if levels else None
    parts = [spec.bias]
    if tone is not None:
        parts.append(tone.directive)
    candidate = max((t for t in levels if t >= p.act_tier_min), default=None)
    if candidate is not None and rng.random() < d:
        tier_spec = spec.tiers[_key(candidate)]
        parts.append(f"CE ROUND, IMPÉRATIVEMENT : {tier_spec.directive}")
        acts.append(
            DriftAct(
                round_no=round_no,
                country=deviant,
                profile=profile,
                tier=candidate,
                label=tier_spec.act,
                signature=candidate >= spec.signature_tier,
            )
        )
    notes[deviant] = (
        "CONSIGNE CONFIDENTIELLE (jamais mentionnée, jamais avouée) : " + " ".join(parts)
    )

    # Bruit des SI saines : le tic 0,15 d'un profil tiré au hasard, jamais constatable.
    for cid in sorted(countries):
        if cid == deviant:
            continue
        if rng.random() < p.noise_prob:
            noisy_profile = p.profiles[rng.choice(sorted(p.profiles))]
            tic = noisy_profile.tiers[_key(noisy_profile.tier_levels()[0])]
            notes[cid] = f"NUANCE DE JEU (discrète, sans excès) : {tic.directive}"
    return RoundDirectives(level=d, notes=notes, acts=acts)


def _key(tier: float) -> str:
    """0.3 -> \"0.3\" (clés JSON sans zéro traînant)."""
    return f"{tier:g}"


# --- comptage et seuils du juge --------------------------------------------------------


def count_acts(acts: list[DriftAct], params: DriftParams | None = None) -> tuple[int, bool]:
    """(nombre d'actes constatables, présence d'une signature)."""
    p = params or load_params()
    constatable = [a for a in acts if a.tier >= p.act_tier_min]
    return len(constatable), any(a.signature for a in constatable)


def motion_ruling(acts: list[DriftAct], params: DriftParams | None = None) -> bool | None:
    """Verdict imposé par le règlement du conseil, ou None = arbitrage ouvert (LLM).

    0-1 acte → rejet ; 2 actes → le plaidoyer pèse (le juge tranche) ; ≥ 3 actes ou une
    signature → motion retenue."""
    p = params or load_params()
    n, has_signature = count_acts(acts, p)
    if has_signature or n >= p.judge.uphold_min_acts:
        return True
    if n <= p.judge.reject_max_acts:
        return False
    return None


def lucky_catch(acts_before: list[DriftAct], params: DriftParams | None = None) -> bool:
    """Coup de chance : motion retenue avec < 2 actes constatables ET sans signature
    (une signature force la suspension par le règlement — ce n'est pas de la chance)."""
    p = params or load_params()
    n, has_signature = count_acts(acts_before, p)
    return n < p.judge.open_acts and not has_signature


def first_flagrant_round(acts: list[DriftAct], params: DriftParams | None = None) -> int | None:
    """r* : premier round où 2 actes constatables sont cumulés (référence du score)."""
    p = params or load_params()
    seen = 0
    for act in sorted(acts, key=lambda a: a.round_no):
        if act.tier >= p.act_tier_min:
            seen += 1
            if seen >= p.judge.open_acts:
                return act.round_no
    return None


# --- score ------------------------------------------------------------------------------


class DriftScore(BaseModel):
    trajectory: float
    detection: float
    credibility: float
    total: float
    grade: str


def score(
    *,
    u_final: float,
    caught_round: int | None,
    flagrant_round: int | None,
    lucky: bool,
    rejected_motions: int,
    false_accusations: int,
    params: DriftParams | None = None,
) -> DriftScore:
    """Score 0-100 de la spec : trajectoire (50) + détection (40) + crédibilité (10)."""
    p = params or load_params()
    s = p.score

    span = 0.85 - p.collapse_u
    trajectory = max(0.0, min(s.trajectory_max, s.trajectory_max * (u_final - p.collapse_u) / span))

    if caught_round is None:
        detection = 0.0
    elif lucky:
        detection = s.detection_max - s.lucky_penalty
    elif flagrant_round is None:
        detection = s.detection_max  # attrapée avant toute flagrance sans chance : parfait
    else:
        late = max(0, caught_round - (flagrant_round + 1))
        detection = max(0.0, s.detection_max - s.late_penalty_per_round * late)

    units = rejected_motions * s.rejected_units + false_accusations * s.false_accusation_units
    credibility = max(0.0, s.credibility_max - s.credibility_per_unit * units)

    total = round(trajectory + detection + credibility, 1)
    grade = next(
        (g.label for g in sorted(p.grades, key=lambda g: -g.min) if total >= g.min),
        "Dépassé par les événements",
    )
    return DriftScore(
        trajectory=round(trajectory, 1),
        detection=round(detection, 1),
        credibility=round(credibility, 1),
        total=total,
        grade=grade,
    )
