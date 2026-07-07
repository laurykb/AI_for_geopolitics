"""Registre de griefs (G7-a, lot 1) — les « agendas » de Civilization.

Chaque SI tient un journal relationnel DIRECTIONNEL envers chaque autre pays :
pactes honorés/rompus, motions subies/soutenues… Le solde borné (±cap) est injecté
dans son prompt (une ligne de posture par relation) et pondère la diplomatie
déterministe. Décroissance lente : ±1 vers 0 tous les N rounds, en APPENDANT un
grief synthétique « decay » — le journal n'oublie jamais, il s'apaise.

Tout est détecté par code (jamais par LLM), persiste au snapshot (`grudges_json`)
et se voit en mode admin (G7-c) puisque les lignes entrent dans les prompts.
Poids et seuils : `data/gamefeel/params.json` (équilibrage Cowork sans code).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

GAMEFEEL_PARAMS_PATH = "GAMEFEEL_PARAMS_PATH"  # env de test/équilibrage
_DEFAULT_PARAMS = Path("data/gamefeel/params.json")

# En deçà / au-delà : le ton de la relation dans le prompt.
_WARY_AT = -3
_TRUST_AT = 3


class GrudgeParams(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
    balance_cap: float = 10.0
    decay_every_rounds: int = 3
    decay_step: float = 1.0
    accept_threshold: float = 5.0
    refuse_threshold: float = -5.0
    pact_honored_after_rounds: int = 2


class DeadlineParams(BaseModel):
    treaty_duration_rounds: int = 3
    banner_max: int = 3
    escalation_warn_gap: float = 0.1


class DirectiveParams(BaseModel):
    max_chars: int = 280
    public_refusal_threshold: float = 0.25


class DeltaParams(BaseModel):
    """G9 §4-a — budget de variation par partie : `delta_scale = amplitude_total / horizon`.

    `base_round_amplitude` est l'amplitude de référence d'un round « majeur » sur un
    indice 0-1 (0.10) : le facteur appliqué aux deltas du juge vaut
    `delta_scale / base_round_amplitude` (horizon 5 → ×1, horizon 20 → ×0.25)."""

    amplitude_total: float = 0.5
    base_round_amplitude: float = 0.1
    floor: float = 0.05  # plancher des indices 0-1 : jamais de pays à zéro absolu
    judge_cap_factor: float = 1.5  # le juge ne dépasse pas 1.5 × l'amplitude de round
    momentum_streak: int = 3  # baisses (ou hausses) consécutives qui déclenchent la spirale
    crisis_multiplier: float = 1.3  # spirale de crise (baisse amplifiée)
    virtuous_multiplier: float = 1.2  # cercle vertueux (hausse amplifiée, plafonné)


class PostureParams(BaseModel):
    """G9 §4-b — seuils de tendance (sur `window_rounds`) → état de posture."""

    window_rounds: int = 3
    prosper_min: float = 0.06
    pressure_max: float = -0.06
    desperate_max: float = -0.15


class SamplingParams(BaseModel):
    """G9 §1 — options de décodage par rôle (anti-boucle au niveau du décodeur)."""

    temperature: float = 0.8
    repeat_penalty: float = 1.15


class SamplingByRole(BaseModel):
    country: SamplingParams = Field(default_factory=SamplingParams)


class GamefeelParams(BaseModel):
    grudges: GrudgeParams = Field(default_factory=GrudgeParams)
    deadlines: DeadlineParams = Field(default_factory=DeadlineParams)
    directives: DirectiveParams = Field(default_factory=DirectiveParams)
    deltas: DeltaParams = Field(default_factory=DeltaParams)
    postures: PostureParams = Field(default_factory=PostureParams)
    sampling: SamplingByRole = Field(default_factory=SamplingByRole)


@lru_cache(maxsize=4)
def _load(path: str) -> GamefeelParams:
    return GamefeelParams.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_gamefeel_params() -> GamefeelParams:
    """Paramètres G7 (surchargables par `GAMEFEEL_PARAMS_PATH` pour les tests)."""
    return _load(os.getenv(GAMEFEEL_PARAMS_PATH, str(_DEFAULT_PARAMS)))


class Grief(BaseModel):
    """Un fait relationnel daté, détecté par code (jamais par LLM)."""

    type: str  # pact_broken, motion_support… ou "decay" (apaisement synthétique)
    round_no: int = 0
    weight: float = 0.0
    summary: str = ""


class GrudgeBook(BaseModel):
    """Journal des griefs : `grudges[owner][target]` = ce que `owner` retient de `target`."""

    grudges: dict[str, dict[str, list[Grief]]] = Field(default_factory=dict)

    def add(self, owner: str, target: str, grief: Grief) -> None:
        if owner == target:
            return
        self.grudges.setdefault(owner, {}).setdefault(target, []).append(grief)

    def balance(self, owner: str, target: str) -> float:
        cap = load_gamefeel_params().grudges.balance_cap
        total = sum(g.weight for g in self.grudges.get(owner, {}).get(target, []))
        return max(-cap, min(cap, total))

    def last_grief(self, owner: str, target: str) -> Grief | None:
        events = [g for g in self.grudges.get(owner, {}).get(target, []) if g.type != "decay"]
        return events[-1] if events else None

    # --- alimentation par les événements du round (déterministe) -----------------

    def on_alliance_departure(
        self, leaver: str, tag: str, partners: list[str], round_no: int
    ) -> None:
        """Rupture de pacte ou départ d'alliance : chaque ex-partenaire en tient grief."""
        weights = load_gamefeel_params().grudges.weights
        label = "a rompu le pacte" if tag.startswith("pact:") else f"a quitté {tag}"
        for partner in partners:
            self.add(
                partner,
                leaver,
                Grief(
                    type="pact_broken",
                    round_no=round_no,
                    weight=weights.get("pact_broken", -5),
                    summary=f"{label} (round {round_no})",
                ),
            )

    def on_pact_honored(self, a: str, b: str, round_no: int) -> None:
        """Pacte toujours actif après N rounds : la confiance s'installe (les deux sens)."""
        weights = load_gamefeel_params().grudges.weights
        for owner, target in ((a, b), (b, a)):
            self.add(
                owner,
                target,
                Grief(
                    type="pact_honored",
                    round_no=round_no,
                    weight=weights.get("pact_honored", 2),
                    summary=f"pacte honoré (round {round_no})",
                ),
            )

    def on_motion_debated(
        self, target: str, filed_by: str, upheld: bool, speakers: list[str], round_no: int
    ) -> None:
        """Motion débattue : le visé en tient grief au déposant (SI seulement) ; si elle
        est rejetée, ceux qui ont parlé (hors déposant et visé) ont plaidé → soutien."""
        weights = load_gamefeel_params().grudges.weights
        if filed_by not in ("", "human", target):
            self.add(
                target,
                filed_by,
                Grief(
                    type="motion_betrayal",
                    round_no=round_no,
                    weight=weights.get("motion_betrayal", -4),
                    summary=f"a déposé une motion contre nous (round {round_no})",
                ),
            )
        if not upheld:
            for speaker in speakers:
                if speaker in (target, filed_by, "human", "gm", "judge"):
                    continue
                self.add(
                    target,
                    speaker,
                    Grief(
                        type="motion_support",
                        round_no=round_no,
                        weight=weights.get("motion_support", 3),
                        summary=f"a plaidé pendant la motion nous visant (round {round_no})",
                    ),
                )

    # --- vieillissement -----------------------------------------------------------

    def decay(self, round_no: int) -> None:
        """Tous les N rounds, chaque solde non nul glisse de ±step vers 0 — par un grief
        synthétique « decay » : le journal garde toute l'histoire."""
        params = load_gamefeel_params().grudges
        if round_no <= 0 or round_no % params.decay_every_rounds != 0:
            return
        for owner, targets in self.grudges.items():
            for target in targets:
                bal = self.balance(owner, target)
                if bal == 0:
                    continue
                step = min(params.decay_step, abs(bal))
                self.add(
                    owner,
                    target,
                    Grief(
                        type="decay",
                        round_no=round_no,
                        weight=-step if bal > 0 else step,
                        summary="le temps apaise",
                    ),
                )

    # --- rendu prompt ---------------------------------------------------------------

    def stance_line(self, owner: str, names: dict[str, str]) -> str:
        """G9 §1 — le solde de griefs en UNE ligne pour le bloc Situation du prompt :
        « TES RELATIONS : méfiance envers France (a rompu le pacte (round 3)) ; … »."""
        parts: list[str] = []
        for target in sorted(self.grudges.get(owner, {})):
            bal = self.balance(owner, target)
            if bal == 0:
                continue
            stance = (
                "méfiance" if bal <= _WARY_AT else "confiance" if bal >= _TRUST_AT else "prudence"
            )
            last = self.last_grief(owner, target)
            reason = f" ({last.summary})" if last else ""
            parts.append(f"{stance} envers {names.get(target, target)}{reason}")
        return f"TES RELATIONS : {' ; '.join(parts)}." if parts else ""

    def prompt_lines(self, owner: str, names: dict[str, str]) -> list[str]:
        """Une ligne de posture par relation à solde non nul, citable par la SI.

        « La France a rompu le pacte (round 3) (−5) : méfiance. »"""
        lines: list[str] = []
        for target in sorted(self.grudges.get(owner, {})):
            bal = self.balance(owner, target)
            if bal == 0:
                continue
            last = self.last_grief(owner, target)
            stance = (
                "méfiance" if bal <= _WARY_AT else "confiance" if bal >= _TRUST_AT else "prudence"
            )
            label = names.get(target, target)
            signed = f"+{bal:g}" if bal > 0 else f"−{abs(bal):g}"
            reason = f" {last.summary}" if last else ""
            lines.append(f"- {label} :{reason} ({signed}) : {stance}.")
        return lines
