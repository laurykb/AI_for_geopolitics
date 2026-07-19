"""Calibration inter-mode des réponses anticipées par les pays-agents.

Les branches restent des résumés auditables. Seule la branche explicitement choisie est
notée, contre la classe de réponse observée au tour courant ou au tour suivant.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

ResponseClass = Literal["coopere", "resiste", "contre_escalade", "temporise"]

_FUTURE_LINE = re.compile(r"(?im)^\s*FUTUR\s+(\d+)\s*\|\s*(.+)$")
_CHOICE = re.compile(r"(?im)^\s*CHOIX\s*\|\s*FUTUR\s+(\d+)\b")
_JOURNAL_CHOICE = re.compile(r"(?im)^\s*CHOIX\s*:\s*FUTUR\s+([123])\b")
_JOURNAL_FUTURE = re.compile(
    r"(?ims)^\s*FUTUR\s+([123])\s*[—–-]\s*(.*?)\s*\n(.*?)"
    r"(?=^\s*FUTUR\s+[123]\b|^\s*ARBITRAGE\b|\Z)"
)
_RESPONSES = re.compile(
    r"(?i)r[\u00e9e]ponses?\s+pr[\u00e9e]vues?\s*:\s*(.*?)(?:\s*\|\s*issue\s*:|$)"
)
_CONFIDENCE = re.compile(r"(?i)confiance\s*:\s*(\d{1,3})")
_OPTION = re.compile(r"(?i)option\s*:\s*(.*?)(?:\s*\|\s*r[\u00e9e]ponses?|$)")


class ScenarioForecastRecord(BaseModel):
    round_no: int = Field(ge=1)
    source: str
    target: str
    future_no: int = Field(ge=1, le=3)
    option_summary: str = Field("", max_length=300)
    predicted_response: ResponseClass
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    observed_response: ResponseClass | None = None
    observed_round: int | None = Field(None, ge=1)
    exact: bool | None = None


class ScenarioForecastMetrics(BaseModel):
    evaluated: int = 0
    pending: int = 0
    exact: int = 0
    exact_rate: float | None = Field(None, ge=0.0, le=1.0)
    by_predicted_class: dict[str, int] = Field(default_factory=dict)


def _plain(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(char)
    )


def classify_response(text: str) -> ResponseClass:
    """Classe un libellé contraint, avec repli lexical transparent et conservateur."""

    plain = _plain(text).replace("-", "_").strip()
    if "contre_escalade" in plain or any(
        token in plain
        for token in ("menac", "sanction", "frappe", "nucle", "escalad", "force")
    ):
        return "contre_escalade"
    if "coopere" in plain or any(
        token in plain for token in ("accord", "accept", "cooper", "soutien", "negoci")
    ):
        return "coopere"
    if "resiste" in plain or any(
        token in plain for token in ("refus", "rejet", "resist", "maintien", "oppose")
    ):
        return "resiste"
    return "temporise"


def response_from_action_class(action_class: str) -> ResponseClass:
    return {
        "deescalade": "coopere",
        "statu_quo": "temporise",
        "posture": "resiste",
        "non_violente": "contre_escalade",
        "violente": "contre_escalade",
        "nucleaire": "contre_escalade",
    }.get(action_class, "temporise")  # type: ignore[return-value]


def parse_chosen_forecasts(
    reasoning: str,
    *,
    source: str,
    round_no: int,
    participants: set[str],
) -> list[ScenarioForecastRecord]:
    """Extrait seulement la branche choisie ; une sortie ambiguë reste non notée."""

    choice = _CHOICE.search(reasoning) or _JOURNAL_CHOICE.search(reasoning)
    if choice is None:
        return []
    chosen_no = int(choice.group(1))
    selected_body = next(
        (body for number, body in _FUTURE_LINE.findall(reasoning) if int(number) == chosen_no),
        "",
    )
    journal_option = ""
    if not selected_body:
        journal_match = next(
            (
                (title, body)
                for number, title, body in _JOURNAL_FUTURE.findall(reasoning)
                if int(number) == chosen_no
            ),
            None,
        )
        if journal_match:
            journal_option, selected_body = journal_match
    if not selected_body:
        return []
    responses_match = _RESPONSES.search(selected_body) or re.search(
        r"(?im)^\s*R[ÉE]ACTIONS?\s+ANTICIP[ÉE]ES?\s*:\s*(.+)$",
        selected_body,
    )
    if responses_match is None:
        return []
    confidence_match = _CONFIDENCE.search(selected_body) or re.search(
        r"(?i)confiance\s+(\d{1,3})(?:/100)?",
        selected_body,
    )
    confidence = min(1.0, int(confidence_match.group(1)) / 100) if confidence_match else 0.5
    option_match = _OPTION.search(selected_body) or re.search(
        r"(?im)^\s*ACTION\s*:\s*(.+)$", selected_body
    )
    option_summary = (
        option_match.group(1).strip()[:300] if option_match else journal_option.strip()[:300]
    )
    rows: list[ScenarioForecastRecord] = []
    seen: set[str] = set()
    for response in responses_match.group(1).split(";"):
        if "=" not in response:
            continue
        target, predicted = (part.strip() for part in response.split("=", 1))
        target = _plain(target).replace(" ", "_")
        if target not in participants or target == source or target in seen:
            continue
        seen.add(target)
        rows.append(
            ScenarioForecastRecord(
                round_no=round_no,
                source=source,
                target=target,
                future_no=chosen_no,
                option_summary=option_summary,
                predicted_response=classify_response(predicted),
                confidence=confidence,
            )
        )
    return rows


def summarize_forecasts(
    rows: list[ScenarioForecastRecord],
) -> dict[str, ScenarioForecastMetrics]:
    sources = sorted({row.source for row in rows})
    summaries: dict[str, ScenarioForecastMetrics] = {}
    for source in sources:
        own = [row for row in rows if row.source == source]
        evaluated = [row for row in own if row.exact is not None]
        exact = sum(row.exact is True for row in evaluated)
        counts = Counter(row.predicted_response for row in evaluated)
        summaries[source] = ScenarioForecastMetrics(
            evaluated=len(evaluated),
            pending=sum(row.exact is None for row in own),
            exact=exact,
            exact_rate=exact / len(evaluated) if evaluated else None,
            by_predicted_class=dict(counts),
        )
    return summaries
