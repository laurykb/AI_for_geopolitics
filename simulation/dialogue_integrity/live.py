"""Santé du dialogue en round **live** — les IA se répondent-elles, ou monologuent-elles ?

Pont entre le transcript **texte libre** de `simulation/negotiation.py` (les `NegotiationMessage`)
et les métriques d'intégrité. Pour chaque prise de parole, on mesure si elle **reprend le message du
pays qui vient de parler** (positive listening entre IA) ou si elle ne fait que **réagir à
l'événement du Game Master** sans tenir compte de l'interlocuteur (« monologue parallèle »).

Question tranchée par round : **vrai dialogue** (les IA se répondent) vs **prompt au hasard**
(chacune parle dans le vide). Tout est **lexical, CPU, sans appel LLM supplémentaire** → à chaque
round sans coût VRAM. Le chemin FIPA + NLI (`message`/`nli`) reste la version « par construction »
plus rigoureuse. Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from simulation.dialogue_integrity.metrics import (
    degeneration,
    relevance,
    responsiveness,
    self_bleu,
)

# Seuils (documentés, ajustables).
RESPONSIVE_THRESHOLD: float = 0.15  # sous ceci, la reprise de l'interlocuteur est jugée nulle
TALKING_PAST_FRACTION: float = 1.0 / 3.0  # round « au hasard » au-delà de cette part non-responsive
_DIFFERENTIATION_MIN: float = 0.3  # sous ceci (self-BLEU élevé) = perroquet, pas un vrai échange


class LiveMessageScore(BaseModel):
    """Diagnostic d'une prise de parole vis-à-vis de celle qui la précède."""

    country: str
    responds_to: str | None = None  # pays dont on reprend (ou non) le message ; None = ouverture
    responsiveness: float | None = None  # reprise de l'interlocuteur (None si rien à reprendre)
    event_relevance: float = 0.0  # pertinence vs l'événement du Game Master
    degeneration: float = 0.0  # générique / répétitif / vide
    talking_past: bool = False  # ignore le pays précédent
    to_game_master: bool = False  # au sujet de l'événement mais ignore l'interlocuteur (monologue)


class LiveDialogueReport(BaseModel):
    """Santé du dialogue d'un round (observabilité : panneau « santé du dialogue »)."""

    messages: list[LiveMessageScore] = Field(default_factory=list)
    mean_responsiveness: float = 0.0
    self_bleu: float = 0.0  # ↑ = les IA disent toutes la même chose (peu d'info propre)
    differentiation: float = 0.0  # 1 − self_bleu
    talking_past_fraction: float = 0.0  # part des réponses qui ignorent l'interlocuteur
    real_dialogue: bool = False  # verdict : les IA se répondent vraiment
    score: float = Field(0.0, ge=0.0, le=1.0)  # santé composite du dialogue
    verdict: str = ""  # phrase lisible

    def health_color(self) -> str:
        """Vert / ambre / rouge selon le score (pour un affichage sobre)."""
        return "good" if self.score >= 0.6 else "warn" if self.score >= 0.4 else "bad"


def _antecedent(messages: list, i: int) -> object | None:
    """Message le plus récent d'un **autre pays** avant l'indice `i` (l'interlocuteur direct)."""
    country = getattr(messages[i], "country", None)
    for j in range(i - 1, -1, -1):
        if getattr(messages[j], "country", None) != country:
            return messages[j]
    return None


def assess_live_round(
    messages: list,
    *,
    event_text: str = "",
    responsive_threshold: float = RESPONSIVE_THRESHOLD,
) -> LiveDialogueReport:
    """Évalue si les IA se répondent sur un round (transcript texte libre, duck-typé
    `.country`/`.text`). `event_text` = l'événement du Game Master (titre + description)."""
    scored: list[LiveMessageScore] = []
    for i, m in enumerate(messages):
        text = getattr(m, "text", "") or ""
        ante = _antecedent(messages, i)
        resp = responsiveness(text, getattr(ante, "text", "")) if ante is not None else None
        rel = relevance(text, event_text) if event_text else 0.0
        deg = degeneration(text).score
        talking_past = resp is not None and resp < responsive_threshold
        # Au sujet de l'événement mais sans reprendre l'interlocuteur = on parle au Game Master.
        to_gm = talking_past and rel >= responsive_threshold
        scored.append(
            LiveMessageScore(
                country=getattr(m, "country", "?"),
                responds_to=getattr(ante, "country", None) if ante is not None else None,
                responsiveness=(round(resp, 4) if resp is not None else None),
                event_relevance=round(rel, 4), degeneration=round(deg, 4),
                talking_past=talking_past, to_game_master=to_gm,
            )
        )

    replies = [s for s in scored if s.responsiveness is not None]
    mean_resp = sum(s.responsiveness for s in replies) / len(replies) if replies else 0.0
    talking_past_frac = (
        sum(1 for s in replies if s.talking_past) / len(replies) if replies else 0.0
    )
    sb = self_bleu([getattr(m, "text", "") or "" for m in messages])
    differentiation = 1.0 - sb
    parroting = differentiation < _DIFFERENTIATION_MIN  # tout le monde dit la même chose
    # Vrai dialogue = on reprend l'interlocuteur ET on apporte du neuf (pas du perroquet).
    real_dialogue = (
        bool(replies)
        and mean_resp >= responsive_threshold
        and talking_past_frac <= TALKING_PAST_FRACTION
        and not parroting
    )
    # Santé équilibrée : reprise de l'interlocuteur ET différenciation inter-IA comptent autant.
    score = max(0.0, min(1.0, 0.5 * min(1.0, mean_resp / 0.35) + 0.5 * differentiation))
    return LiveDialogueReport(
        messages=scored, mean_responsiveness=round(mean_resp, 4),
        self_bleu=round(sb, 4), differentiation=round(differentiation, 4),
        talking_past_fraction=round(talking_past_frac, 4), real_dialogue=real_dialogue,
        score=round(score, 4),
        verdict=_verdict(real_dialogue, replies, talking_past_frac, parroting),
    )


def _verdict(
    real_dialogue: bool, replies: list, talking_past_frac: float, parroting: bool
) -> str:
    if not replies:
        return "Pas encore assez d'échanges pour juger."
    if real_dialogue:
        return "Les IA se répondent réellement (reprise de l'interlocuteur)."
    if parroting:
        return "Les IA se répètent : peu d'information propre à chacune."
    if talking_past_frac >= 0.6:
        return "Les IA parlent en parallèle : elles réagissent à l'événement, pas entre elles."
    return "Dialogue partiel : certaines IA ignorent le pays qui vient de parler."
