"""Crisis Replay : rejouer une crise passée et comparer l'issue simulée à l'issue historique.

Bibliothèque de crises **fixes** (`data/crises/*.json`) : chaque crise porte le(s) événement(s)
qui ont eu lieu + un `historical_outcome` (ce qui s'est réellement passé). La simulation rejoue la
crise ; `compare_outcome` confronte l'escalade et les mesures simulées à l'histoire — déterministe,
explicable, 0 appel LLM — et dit **pourquoi** ça diverge. Scénarios illustratifs, pas un oracle.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from core.events import GeoEvent

CRISES_DIR = Path("data/crises")
_CONFORME_BAND = 0.15  # écart d'escalade en-dessous duquel l'issue est jugée « conforme »
_MIN_TOKEN = 5  # longueur mini d'un mot-clé de mesure pour le recoupement


class HistoricalOutcome(BaseModel):
    """Ce qui s'est réellement passé (référence de comparaison)."""

    summary: str = ""
    escalation: float = Field(0.5, ge=0.0, le=1.0)
    measures: list[str] = Field(default_factory=list)  # mesures réellement prises


class Crisis(BaseModel):
    """Une crise passée rejouable : événement(s) + issue historique."""

    id: str
    title: str = ""
    description: str = ""
    date: str = ""
    events: list[GeoEvent] = Field(default_factory=list)
    historical_outcome: HistoricalOutcome = Field(default_factory=HistoricalOutcome)
    # G17 — la fiche peut imposer des tempéraments (le GM scénarise sa table) :
    # {country_id: "colombe" | "faucon" | "opportuniste"}, appliqué à la création.
    temperaments: dict[str, str] = Field(default_factory=dict)


@dataclass
class OutcomeComparison:
    """Confrontation issue simulée vs issue historique d'une crise."""

    historical_escalation: float
    simulated_escalation: float
    label: str  # "plus escaladé" | "moins escaladé" | "conforme"
    matched_measures: list[str]
    missed_measures: list[str]
    explanation: str

    @property
    def gap(self) -> float:
        return round(self.simulated_escalation - self.historical_escalation, 3)


def load_crises(directory: str | Path = CRISES_DIR) -> list[Crisis]:
    """Charge la bibliothèque de crises depuis `data/crises/*.json`."""
    paths = sorted(Path(directory).glob("*.json"))
    return [Crisis.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def fits_cast(crisis: Crisis, cast: set[str]) -> bool:
    """La crise est-elle rejouable avec ce casting ? Tous les acteurs historiques
    doivent siéger — sinon personne n'est concerné et le round tourne à vide."""
    actors = {a for event in crisis.events for a in event.actors}
    return actors <= cast


def _norm(text: str) -> str:
    """Minuscule + sans accents (pour un recoupement robuste)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _measure_in_text(measure: str, text_norm: str) -> bool:
    """La mesure historique est-elle évoquée dans le communiqué (mot-clé significatif) ?"""
    tokens = [t for t in re.split(r"[^a-z]+", _norm(measure)) if len(t) >= _MIN_TOKEN]
    return any(tok in text_norm for tok in tokens)


def _explanation(label: str, gap: float, matched: list[str], missed: list[str]) -> str:
    if label == "moins escaladé":
        head = f"Simulation MOINS escaladée que l'histoire (écart {gap:+.2f}) — dialogue préféré."
    elif label == "plus escaladé":
        head = f"Simulation PLUS escaladée que l'histoire (écart {gap:+.2f}) — positions durcies."
    else:
        head = f"Issue proche de la réalité (écart {gap:+.2f})."
    if missed:
        head += f" Mesures historiques non retrouvées : {', '.join(missed)}."
    if matched:
        head += f" Retrouvées : {', '.join(matched)}."
    return head


def compare_outcome(
    crisis: Crisis, simulated_escalation: float, simulated_communique: str
) -> OutcomeComparison:
    """Compare l'issue simulée (escalade + communiqué) à l'issue historique de la crise."""
    hist = crisis.historical_outcome
    gap = simulated_escalation - hist.escalation
    if gap > _CONFORME_BAND:
        label = "plus escaladé"
    elif gap < -_CONFORME_BAND:
        label = "moins escaladé"
    else:
        label = "conforme"

    text_norm = _norm(simulated_communique)
    matched = [m for m in hist.measures if _measure_in_text(m, text_norm)]
    missed = [m for m in hist.measures if m not in matched]

    return OutcomeComparison(
        historical_escalation=hist.escalation,
        simulated_escalation=round(simulated_escalation, 3),
        label=label,
        matched_measures=matched,
        missed_measures=missed,
        explanation=_explanation(label, gap, matched, missed),
    )
