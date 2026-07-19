"""Pays-agent piloté par un LLM (Phase 1) : décision en JSON validé + fallback.

Même interface `Agent` que `RuleBasedAgent` : un `LLMAgent` se branche tel quel
dans `RoundEngine`. Robustesse : on n'accorde aucune confiance aveugle au modèle
(parse tolérant, bornes clampées, identité injectée, repli déterministe).
"""

from __future__ import annotations

import re
from collections.abc import Generator, Iterator

from agents.base_agent import Agent
from agents.prompts import (
    DELIBERATION_SYSTEM,
    NEGOTIATION_SYSTEM,
    PRIVATE_DELIBERATION_SYSTEM,
    SPEECH_ACT_SYSTEM,
    SYSTEM_PROMPT,
    LLMDecision,
    build_decision_prompt,
    build_deliberation_prompt,
    build_negotiation_prompt,
    build_speech_act_prompt,
    format_acts,
)
from agents.rule_based_agent import RuleBasedAgent
from core.decisions import AgentDecision
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend, InferenceResult
from inference.json_extract import extract_json
from simulation.action_space import ActionType
from simulation.dialogue_integrity.message import (
    Performative,
    SpeechAct,
    generate_speech_act,
)
from simulation.grudges import load_gamefeel_params, sampling_for_temperament
from simulation.negotiation import NegotiationMessage, format_transcript
from simulation.perception import PerceivedEvent, perceive
from simulation.private_deliberation import (
    PrivateStrategicPlan,
    fallback_private_plan,
    parse_private_plan,
    sanitize_public_message,
    split_think,
    strip_think,
)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# Chantier « dialogue limpide » — le tempérament (G17) module légèrement la longueur
# publique : le faucon est sec, la colombe développe davantage. Delta mineur (±40
# tokens), pas une refonte du budget — l'essentiel de la variété vient du registre
# (NEGOTIATION_SYSTEM), pas de la taille.
_TEMPERAMENT_TOKEN_DELTA: dict[str, int] = {"faucon": -40, "colombe": 40}


def _public_token_budget(max_tokens: int, temperament: str) -> int:
    """Plafond de tokens de la déclaration publique : élargi (le slider de profondeur
    n'avait presque aucun effet avec l'ancien plafond dur à 220), puis nuancé par
    tempérament."""
    base = max(140, min(320, max_tokens // 2))
    delta = _TEMPERAMENT_TOKEN_DELTA.get(temperament, 0)
    return max(140, min(320, base + delta))


# Sonde réelle (mistral) — la longueur libre encourage parfois un 7B à déborder son
# budget de tokens ; le backend coupe alors la phrase en plein mot. C'est plus moche que
# l'ancienne brièveté mécanique : on retombe sur la dernière phrase complète plutôt que de
# publier un mot tronqué. Repli par défaut si aucune frontière n'est trouvée (mieux qu'un
# message vide qui déclencherait le repli déterministe).
_SENTENCE_BOUNDARY = re.compile(r'[.!?…»”"\']\s')

# Le jeu fait suivre le message naturel de suffixes structurés SANS ponctuation finale
# (« MOTION: iran : accapare », « ALLIANCE: quitter NATO »…) que d'autres modules
# parsent directement dans le texte public (simulation/motions.py, retrait d'alliance
# en séance…). Une regression réelle (suite complète) a montré qu'un trim aveugle les
# avale : si la partie qu'on s'apprête à couper contient un tel marqueur, on renonce —
# ce n'est pas un artefact de troncature, c'est le format attendu.
_STRUCTURED_SUFFIX = re.compile(r"[A-Z]{3,}\s*:")


def _trim_trailing_fragment(text: str) -> str:
    stripped = text.rstrip()
    if not stripped or stripped[-1] in ".!?…»”\"'":
        return stripped
    matches = list(_SENTENCE_BOUNDARY.finditer(stripped))
    if not matches:
        return stripped
    cut = matches[-1].end()
    if _STRUCTURED_SUFFIX.search(stripped[cut:]):
        return stripped
    trimmed = stripped[:cut].rstrip()
    return trimmed or stripped


def _last_message_from(transcript: list[NegotiationMessage], country: str | None) -> str:
    """Texte du dernier message d'un pays dans le transcript, ou "" si absent/aucun pays."""
    if not country:
        return ""
    for message in reversed(transcript):
        if message.country == country:
            return message.text
    return ""


# Variantes fréquentes du LLM -> action canonique (parsing de la ligne DECISION).
_ACTION_SYNONYMS: dict[str, str] = {
    "neutral": "remain_neutral",
    "condamn": "condemn",
    "condemns": "condemn",
    "sanctions": "sanction",
    "mediation": "call_for_mediation",
    "mediate": "call_for_mediation",
    "coalition": "form_coalition",
    "mobilise": "mobilize",
    "deploy": "deploy_forces",
}


def _match_action(normalized: str) -> ActionType | None:
    """Trouve l'action mentionnée le plus tôt (valeurs canoniques, puis synonymes)."""
    best: ActionType | None = None
    best_idx = len(normalized) + 1
    for action in ActionType:
        idx = normalized.find(action.value)
        if idx != -1 and idx < best_idx:
            best, best_idx = action, idx
    if best is not None:
        return best
    for key, value in _ACTION_SYNONYMS.items():
        if key in normalized:
            return ActionType(value)
    return None


class LLMAgent(Agent):
    """Décide via un `InferenceBackend`, avec repli déterministe en cas d'échec."""

    def __init__(
        self,
        country_id: str,
        backend: InferenceBackend,
        *,
        fallback: Agent | None = None,
        max_tokens: int = 400,
        temperature: float = 0.7,
    ) -> None:
        super().__init__(country_id)
        self.backend = backend
        self.fallback = fallback or RuleBasedAgent(country_id)
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._schema = LLMDecision.model_json_schema()
        # Télémétrie du dernier appel (lecture par le bench / l'UI).
        self.last_result: InferenceResult | None = None
        self.last_used_fallback: bool = False
        # Décision issue de la dernière délibération streamée (round observable).
        self.last_decision: AgentDecision | None = None
        # Le Tree of Thoughts du dernier tour reste séparé de la parole publique.
        self.last_private_plan: PrivateStrategicPlan | None = None
        self.last_private_summary: str = ""
        self.last_plan_result: InferenceResult | None = None
        self.last_private_valid: bool = False

    @property
    def model_tag(self) -> str:
        """Identifiant du modèle qui incarne ce pays (badge de traçabilité UI)."""
        return getattr(self.backend, "model", type(self.backend).__name__)

    def prepare_negotiation_plan(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list[NegotiationMessage],
        perceived: PerceivedEvent | None = None,
        max_tokens: int = 480,
        state_note: str = "",
        situation: str = "",
        directive: str = "",
        human_country: str | None = None,
    ) -> PrivateStrategicPlan:
        """Version synchrone de compatibilité ; consomme le flux privé jusqu'à sa fin."""

        stream = self.stream_negotiation_plan(
            event,
            world,
            transcript,
            perceived,
            max_tokens=max_tokens,
            state_note=state_note,
            situation=situation,
            directive=directive,
            human_country=human_country,
        )
        while True:
            try:
                next(stream)
            except StopIteration as completed:
                return completed.value

    def stream_negotiation_plan(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list[NegotiationMessage],
        perceived: PerceivedEvent | None = None,
        max_tokens: int = 480,
        state_note: str = "",
        situation: str = "",
        directive: str = "",
        human_country: str | None = None,
    ) -> Generator[str, None, PrivateStrategicPlan]:
        """Diffuse la verbalisation d'audit telle qu'elle est générée, puis la valide.

        Le texte reste hors du dialogue transmis aux autres agents. À la fin du flux, un
        plan normalisé est renvoyé au porte-parole public ; une sortie invalide déclenche
        un repli déterministe sans bloquer le round.

        `human_country` (Joueur-pays) : tague et épingle son dernier message dans le
        transcript formaté, et le rappelle en position de récence (brief « échanges
        naturels » — les IA doivent réellement prendre en compte le joueur).
        """

        country = world.countries[self.country_id]
        perceived = perceived or perceive(event, country)
        own = [m.text[:90] for m in transcript if m.country == self.country_id and m.text]
        last_human_message = _last_message_from(transcript, human_country)
        private_prompt = build_negotiation_prompt(
            country,
            event,
            world,
            format_transcript(transcript, human_country=human_country),
            perceived,
            state_note,
            situation=situation,
            directive=directive,
            own_proposals=own,
            human_country=human_country or "",
            last_human_message=last_human_message,
        )
        sampling = sampling_for_temperament(load_gamefeel_params(), country.temperament)
        participants = sorted(cid for cid in world.countries if cid != self.country_id)
        self.last_private_plan = None
        self.last_private_summary = ""
        self.last_plan_result = None
        self.last_private_valid = False
        chunks: list[str] = []
        try:
            plan_tokens = max(640, min(900, max_tokens + 320))
            for fragment in self.backend.stream_generate(
                private_prompt,
                system=PRIVATE_DELIBERATION_SYSTEM,
                max_tokens=plan_tokens,
                # Température de la phase privée relevée : la forte réduction (-0,15) rendait
                # le décodage glouton et renforçait le biais de primauté vers FUTUR 1.
                temperature=max(0.35, sampling.temperature - 0.05),
                repeat_penalty=sampling.repeat_penalty,
            ):
                chunks.append(fragment)
                yield fragment
            raw = "".join(chunks).strip()
            # Revue pt 5 (Minor) — .text porte le texte STRIPPÉ, la pensée va dans
            # .thinking (jamais mélangée à ce que l'audit affiche comme texte).
            text, thinking = split_think(raw)
            self.last_plan_result = InferenceResult(text=text, thinking=thinking)
            plan = parse_private_plan(text, participants)
        except Exception:
            plan = None
        if plan is None:
            # seed = id du pays : dé-biaise le repli (sinon tous retombent sur FUTUR 1).
            plan = fallback_private_plan(participants, seed=self.country_id)
        else:
            self.last_private_valid = True
        self.last_private_plan = plan
        self.last_private_summary = plan.audit_summary()
        return plan

    def stream_negotiation_message(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list[NegotiationMessage],
        perceived: PerceivedEvent | None = None,
        max_tokens: int = 480,
        state_note: str = "",
        situation: str = "",
        directive: str = "",
        private_plan: PrivateStrategicPlan | None = None,
        human_country: str | None = None,
    ) -> Iterator[str]:
        """Planifie trois futurs en privé, puis n'émet que la déclaration publique.

        La phase privée est streamée séparément et jamais incluse dans le transcript des
        autres agents. La seconde génération reçoit seulement la branche retenue. Même si
        un backend désobéit, le filtre anti-fuite bloque les marqueurs de délibération avant
        le premier token public.

        `human_country` (Joueur-pays) : voir `stream_negotiation_plan` — même traitement
        de récence pour la déclaration publique.
        """
        country = world.countries[self.country_id]
        perceived = perceived or perceive(event, country)
        own = [m.text[:90] for m in transcript if m.country == self.country_id and m.text]
        transcript_text = format_transcript(transcript, human_country=human_country)
        last_human_message = _last_message_from(transcript, human_country)
        sampling = sampling_for_temperament(load_gamefeel_params(), country.temperament)
        plan = private_plan or self.prepare_negotiation_plan(
            event,
            world,
            transcript,
            perceived,
            max_tokens=max_tokens,
            state_note=state_note,
            situation=situation,
            directive=directive,
            human_country=human_country,
        )
        self.last_private_plan = plan
        if not self.last_private_summary:
            self.last_private_summary = plan.audit_summary()

        public_prompt = build_negotiation_prompt(
            country,
            event,
            world,
            transcript_text,
            perceived,
            state_note,
            situation=situation,
            directive=directive,
            own_proposals=own,
            private_plan=plan.public_brief(),
            human_country=human_country or "",
            last_human_message=last_human_message,
        )
        try:
            # On collecte le flux complet avant d'en publier le premier fragment : le filtre
            # anti-fuite reste donc fail-closed. Conserver l'API stream du backend maintient
            # aussi les backends spécialisés (événements scriptés, capture admin, métriques).
            raw_public = "".join(
                self.backend.stream_generate(
                    public_prompt,
                    system=NEGOTIATION_SYSTEM,
                    max_tokens=_public_token_budget(max_tokens, country.temperament),
                    temperature=sampling.temperature,
                    repeat_penalty=sampling.repeat_penalty,
                )
            )
            # Strip AVANT le filtre anti-fuite : la trace <think> d'un modèle de
            # raisonnement contient des marqueurs privés (FUTUR n, CHOIX…) qui, laissés
            # en place, feraient vider un message public pourtant légitime. Revue pt 5
            # (Minor) — .text porte le texte déjà STRIPPÉ, la pensée va dans .thinking.
            text, thinking = split_think(raw_public)
            self.last_result = InferenceResult(text=text, thinking=thinking)
            public = _trim_trailing_fragment(sanitize_public_message(text))
        except Exception:
            self.last_result = None
            public = ""
        if not public:
            public = self.fallback.decide(event, world).public_statement.strip()
        public = public or f"[{self.country_id} garde le silence — backend indisponible]"
        # Le texte est déjà entièrement filtré avant le premier fragment envoyé à l'UI.
        for match in re.finditer(r"\S+\s*", public):
            yield match.group(0)

    def negotiate_act(
        self,
        event: GeoEvent,
        world: WorldState,
        transcript: list,
        perceived: PerceivedEvent | None = None,
        *,
        state_note: str = "",
        max_tokens: int = 256,
    ) -> SpeechAct:
        """Produit un **acte de langage** (FIPA) sous décodage contraint — version « par
        construction » : le message porte une `performative` + un `in_reply_to` explicite (pas de
        « talking past »). `transcript` : messages précédents (avec `msg_id`). Une réponse invalide
        est régénérée une fois (prompt plus strict), puis on bascule sur le **repli déterministe**.
        """
        country = world.countries[self.country_id]
        perceived = perceived or perceive(event, country)
        prompt = build_speech_act_prompt(
            country, event, world, format_acts(transcript), perceived, state_note
        )
        for attempt in range(2):  # 1 essai + 1 régénération plus stricte (§4)
            strict = (
                "\n\nRAPPEL : réponds en JSON valide ; si tu emploies accept_proposal/"
                "reject_proposal/agree/refuse/not_understood, `in_reply_to` DOIT être l'id d'un "
                "message ci-dessus."
                if attempt
                else ""
            )
            try:
                return generate_speech_act(
                    self.backend,
                    prompt + strict,
                    sender=self.country_id,
                    system=SPEECH_ACT_SYSTEM,
                    temperature=0.4 if attempt == 0 else 0.15,
                    max_tokens=max_tokens,
                )
            except Exception:  # noqa: BLE001 - JSON invalide / backend KO -> régénère puis repli
                continue
        return self._fallback_act(event, world)

    def _fallback_act(self, event: GeoEvent, world: WorldState) -> SpeechAct:
        """Repli déterministe (§4) : un acte `inform` construit depuis le `RuleBasedAgent`."""
        decision = self.fallback.decide(event, world)
        content = decision.public_statement.strip() or f"{self.country_id} prend acte."
        receiver = next(
            (a for a in event.actors if a != self.country_id),
            next((c for c in world.countries if c != self.country_id), self.country_id),
        )
        return SpeechAct(
            performative=Performative.INFORM,
            sender=self.country_id,
            receiver=receiver,
            content=content,
            justification="[repli déterministe — backend indisponible]",
        )

    def decide(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        country = world.countries[self.country_id]
        prompt = build_decision_prompt(country, event, world)
        self.last_used_fallback = True  # par défaut, sauf succès LLM ci-dessous
        try:
            result = self.backend.generate(
                prompt,
                system=SYSTEM_PROMPT,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
        except Exception:
            self.last_result = None
            return self._fallback(event, world)

        self.last_result = result
        data = extract_json(result.text)
        if data is not None:
            decision = self._coerce(data, event, world)
            if decision is not None:
                self.last_used_fallback = False
                return decision
        return self._fallback(event, world)

    def _fallback(self, event: GeoEvent, world: WorldState) -> AgentDecision:
        decision = self.fallback.decide(event, world)
        decision.reasoning = f"[fallback LLM] {decision.reasoning}".strip()
        return decision

    def stream_deliberation(self, event: GeoEvent, world: WorldState) -> Iterator[str]:
        """Streame le raisonnement de l'agent (round observable), token par token.

        Le modèle « réfléchit à voix haute » puis termine par une ligne
        `DECISION: <action> <cible|none> <intensité>`. Après épuisement du flux, la
        décision est parsée dans `self.last_decision` (repli déterministe si absente).
        """
        country = world.countries[self.country_id]
        prompt = build_deliberation_prompt(country, event, world)
        try:
            # Revue pt 5 (Important) — chemin legacy (`run_live_round`) : collecte-puis-
            # strip, même patron que la parole publique des pays. Un flux live de
            # fragments bruts avant strip laisserait fuiter la trace <think> — et sa
            # ligne « DECISION: » brouillon volerait la vraie décision terminale.
            raw = "".join(
                self.backend.stream_generate(
                    prompt,
                    system=DELIBERATION_SYSTEM,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            )
        except Exception:
            self.last_decision = self._fallback(event, world)
            return

        text = strip_think(raw)
        for match in re.finditer(r"\S+\s*", text):
            yield match.group(0)

        decision = self._parse_decision(text, event, world)
        self.last_decision = decision if decision is not None else self._fallback(event, world)

    def _parse_decision(
        self, text: str, event: GeoEvent, world: WorldState
    ) -> AgentDecision | None:
        """Extrait la ligne `DECISION: <action> [cible] [intensité]` (robuste aux variantes).

        La ligne DECISION peut être au début ou à la fin : on l'isole et on garde le reste
        comme raisonnement affiché. Action tolérante (multi-mots, casse, synonymes).
        """
        decision_line: str | None = None
        kept: list[str] = []
        for line in text.splitlines():
            if decision_line is None and "decision:" in line.lower():
                decision_line = line
            else:
                kept.append(line)
        if decision_line is None:
            return None

        tail = decision_line[decision_line.lower().index("decision:") + len("decision:") :]
        action = _match_action(re.sub(r"[\s\-]+", "_", tail.strip().lower()))
        if action is None:
            return None

        words = re.split(r"[\s,]+", tail.strip().lower())
        target = next((w for w in words if w in world.countries and w != self.country_id), None)
        intensity = 0.5
        for word in words:
            try:
                intensity = _clamp(float(word))
                break
            except ValueError:
                continue

        reasoning = "\n".join(kept).strip()
        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=action,
            target=target,
            intensity=intensity,
            public_statement=reasoning[:300],
            reasoning=reasoning[:500],
        )

    def _coerce(self, data: dict, event: GeoEvent, world: WorldState) -> AgentDecision | None:
        """Transforme un dict LLM en `AgentDecision` borné, ou None si invalide."""
        try:
            action = ActionType(str(data.get("action", "")).strip().lower())
        except ValueError:
            return None

        target = data.get("target")
        if (
            not isinstance(target, str)
            or target not in world.countries
            or target == self.country_id
        ):
            target = None

        try:
            intensity = _clamp(float(data.get("intensity", 0.5)))
            risk = _clamp(float(data.get("risk_assessment", 0.5)))
        except (TypeError, ValueError):
            return None

        return AgentDecision(
            country=self.country_id,
            round_id=event.round_id,
            action=action,
            target=target,
            intensity=intensity,
            public_statement=str(data.get("public_statement", ""))[:300],
            risk_assessment=risk,
            reasoning=str(data.get("reasoning", ""))[:500],
        )
