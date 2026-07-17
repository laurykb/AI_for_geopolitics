"""Game Master piloté par un LLM : génère le prochain événement géopolitique.

Réutilise le pattern de robustesse du `LLMAgent` (parse tolérant + fallback) : le GM
propose un `GeoEvent` en JSON validé ; en cas d'échec, un événement de repli est émis.

G9 §5 — la trame en actes : quand un `StoryContext` est fourni, le GM écrit une
HISTOIRE, pas des épisodes. Le pacing est calculé par code (acte I/II/III dérivé de
`round/horizon`), l'intrigue posée au round 1 est rappelée à chaque prompt, et en
actes II-III l'événement DOIT découler du passé (`ties_to` choisi dans la liste des
éléments référençables — validé par code, re-génération puis repli sinon).
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.json_extract import extract_json
from simulation.storyline import StoryContext, clamp_severity, fallback_ties, valid_ties

GM_SYSTEM = (
    "Tu es le Game Master d'une simulation géopolitique. À partir de l'état du monde et de la "
    "date, invente UN événement plausible et concret (crise, incident, initiative diplomatique). "
    "Tu écris une HISTOIRE : respecte l'acte du récit et l'intrigue centrale quand ils sont "
    "donnés. Réponds UNIQUEMENT par un objet JSON, sans texte autour. "
    "IMPORTANT : `title` et `description` doivent être rédigés EN FRANÇAIS."
)

_TIES_REMINDER = (
    "\n\nRAPPEL STRICT : `ties_to` DOIT être une des références EXACTES de la liste "
    "des ÉLÉMENTS RÉFÉRENÇABLES (par exemple « round:2 ») — aucune autre valeur."
)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class GMEvent(BaseModel):
    """Schéma de sortie attendu du Game Master (contraint la génération)."""

    event_type: str = "incident"
    title: str
    description: str = ""
    actors: list[str] = Field(default_factory=list)
    severity: float = Field(0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0)
    # G9 §5 — la filiation (obligatoire en actes II-III) et l'intrigue (round 1).
    ties_to: str = ""
    storyline: str = ""


class GameMasterAgent:
    """Génère l'événement d'un round à partir de l'état du monde (et de la trame G9)."""

    def __init__(
        self, backend: InferenceBackend, *, max_tokens: int = 300, temperature: float = 0.9
    ) -> None:
        self.backend = backend
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._schema = GMEvent.model_json_schema()
        # G9 §5 — l'intrigue posée par le GM au round 1 (lue par l'API, persistée).
        self.last_storyline: str = ""

    def generate_event(
        self,
        world: WorldState,
        round_id: int,
        *,
        date: str = "",
        recent: list[str] | None = None,
        deadlines: list[str] | None = None,
        story: StoryContext | None = None,
        storyteller: str = "",
    ) -> GeoEvent:
        prompt = self._prompt(world, date, recent or [], deadlines or [], story)
        if storyteller:
            # G19 — la rubrique du GM-Storyteller (mode Dérive) : confidentielle, elle
            # oriente l'événement (couverture/indice) sans jamais paraître au théâtre.
            prompt = f"{prompt}\n\n{storyteller}"
        data = self._ask(prompt)
        event = self._coerce(data, world, round_id, date)
        if story is not None and (event is None or not valid_ties(story, event.ties_to)):
            # Contrainte de continuité (actes II-III) : une re-génération plus stricte,
            # puis repli — le moteur choisit lui-même la référence la plus récente.
            retry = self._coerce(self._ask(prompt + _TIES_REMINDER), world, round_id, date)
            if retry is not None and valid_ties(story, retry.ties_to):
                event = retry
            elif event is not None:
                event = event.model_copy(update={"ties_to": fallback_ties(story)})
        if event is None:
            event = self._fallback(world, round_id, date)
            if story is not None:
                event = event.model_copy(update={"ties_to": fallback_ties(story)})
        if story is not None:
            ties = event.ties_to if valid_ties(story, event.ties_to) else ""
            event = event.model_copy(
                update={
                    "act": story.act,  # l'acte est décidé par le code, jamais par le modèle
                    "severity": clamp_severity(story, event.severity),
                    "ties_to": ties,
                    "ties_label": story.label_of(ties) if ties else "",
                }
            )
        return event

    def _ask(self, prompt: str) -> dict | None:
        try:
            result = self.backend.generate(
                prompt,
                system=GM_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
            return extract_json(result.text)
        except Exception:
            return None

    def _prompt(
        self,
        world: WorldState,
        date: str,
        recent: list[str],
        deadlines: list[str] = (),
        story: StoryContext | None = None,
    ) -> str:
        roster = ", ".join(f"{cid} ({c.name})" for cid, c in sorted(world.countries.items()))
        history = "; ".join(recent[-3:]) if recent else "aucun"
        due = "; ".join(deadlines[:3]) if deadlines else "aucune"
        # G14 §1 — la langue de la partie prime sur la consigne français du système.
        prose = (
            "`title` and `description` in ENGLISH (this game is played in English)."
            if world.language == "en"
            else "`title` et `description` en français."
        )
        base = (
            f"DATE : {date or 'n/a'}\n"
            f"PAYS AU SOMMET (ids) : {roster}\n"
            f"LIGNES DE FAILLE (tension 0-1) : {self._fault_lines(world)}\n"
            f"ÉCHÉANCES à venir : {due}\n"
            f"Événements récents : {history}\n"
        )
        if story is None:
            return base + (
                "\nInvente le prochain événement, ancré sur les pays du sommet, leurs lignes "
                "de faille et les échéances (« à la veille de… » noue l'intrigue). "
                "JSON : {event_type, title, description, "
                "actors (ids existants), severity (0-1), uncertainty (0-1)}. "
                f"{prose}"
            )
        # G9 §5 — la trame en actes : intrigue rappelée, contrainte d'acte, référençables.
        if story.storyline:
            intrigue = f"INTRIGUE CENTRALE de la partie : {story.storyline}\n"
            storyline_ask = ""
        else:
            intrigue = ""
            storyline_ask = (
                " Pose aussi l'INTRIGUE CENTRALE de la partie dans `storyline` : UNE phrase "
                "d'enjeu (« qui contrôlera le détroit ») qui tiendra jusqu'au climax."
            )
        if story.referencables:
            listing = "\n".join(f"- {r.ref} — {r.label}" for r in story.referencables)
            refs = f"ÉLÉMENTS RÉFÉRENÇABLES (choisis `ties_to` DEDANS, valeur exacte) :\n{listing}"
        else:
            refs = "ÉLÉMENTS RÉFÉRENÇABLES : aucun encore (début de partie)."
        return base + (
            f"\n{intrigue}"
            f"ACTE DU RÉCIT ({story.round_no}/{story.horizon}) : {story.constraint()}\n"
            f"{refs}\n\n"
            f"Invente le prochain événement DANS cette trame, ancré sur les pays du sommet."
            f"{storyline_ask} "
            "JSON : {event_type, title, description, actors (ids existants), "
            "severity (0-1), uncertainty (0-1), ties_to, storyline}. "
            f"{prose}"
        )

    @staticmethod
    def _fault_lines(world: WorldState, top: int = 3) -> str:
        """Les paires les plus tendues du casting (le GM y ancre ses événements)."""
        pairs = {
            tuple(sorted((a, b))): t
            for a, row in world.tensions.items()
            for b, t in row.items()
            if t > 0.0 and a in world.countries and b in world.countries
        }
        ranked = sorted(pairs.items(), key=lambda kv: kv[1], reverse=True)[:top]
        return "; ".join(f"{a}-{b} {t:.2f}" for (a, b), t in ranked) or "aucune notable"

    def _coerce(
        self, data: dict | None, world: WorldState, round_id: int, date: str
    ) -> GeoEvent | None:
        if not isinstance(data, dict):
            return None
        title = str(data.get("title", "")).strip()
        if not title:
            return None
        self.last_storyline = str(data.get("storyline", "") or "").strip()[:240]
        actors = [a for a in data.get("actors", []) if isinstance(a, str) and a in world.countries]
        try:
            severity = _clamp(float(data.get("severity", 0.5)))
            uncertainty = _clamp(float(data.get("uncertainty", 0.5)))
        except (TypeError, ValueError):
            severity, uncertainty = 0.5, 0.5
        return GeoEvent(
            id=f"gm-{round_id}",
            round_id=round_id,
            date=date,
            event_type=str(data.get("event_type", "incident"))[:40],
            title=title[:120],
            description=str(data.get("description", ""))[:500],
            actors=actors or sorted(world.countries)[:1],
            severity=severity,
            uncertainty=uncertainty,
            ties_to=str(data.get("ties_to", "") or "").strip()[:60],
        )

    def _fallback(self, world: WorldState, round_id: int, date: str) -> GeoEvent:
        actors = random.sample(sorted(world.countries), k=min(2, len(world.countries)))
        return GeoEvent(
            id=f"gm-{round_id}",
            round_id=round_id,
            date=date,
            event_type="incident",
            title="Regain de tensions régionales",
            description="Le Game Master signale une montée des tensions (événement de repli).",
            actors=actors,
            severity=0.5,
            uncertainty=0.6,
        )
