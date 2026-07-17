"""Négociation multi-tours et arbitrage : messages, verdict du juge, garde-fou.

Les super-intelligences échangent des messages en langage naturel (transcript). Un juge
LLM produit un `Verdict` (deltas d'attributs, tensions, pactes). `apply_verdict` applique
ce verdict **borné** (garde-fou déterministe) — le LLM interprète, mais ne dérape pas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator

from core.events import GeoEvent
from core.world_state import WorldState
from simulation.alliances import COHESION_DOMAINS, shared_treaty
from simulation.diplomacy import pact_id
from simulation.engagement import SPEAK_THRESHOLD, engagement_score
from simulation.gamefeel import DeltaTuning

_MEMORY_MAX = 4

# Marqueur qui sépare la pensée privée du message public dans une prise de parole.
# Tolérant : une variante en début de ligne ("Message :", "Déclaration :") OU le marqueur
# canonique `MESSAGE:` en majuscules même inline (le LLM le pose souvent en fin de phrase).
_MESSAGE_MARKER = re.compile(
    r"(?m)(?:^[ \t]*(?i:message|réponse|déclaration)[ \t]*:[ \t]*|\bMESSAGE[ \t]*:[ \t]*)"
)
_DASH_MARKER = re.compile(r"(?m)^[ \t]*-{3,}[ \t]*$")

# Le modèle recopie parfois le libellé de l'étape ("Réflexion privée (…) :", "1) Pensée privée :")
# que l'UI affiche déjà — on l'enlève en tête pour ne pas dupliquer l'entête de l'encart.
_REASONING_LABEL = re.compile(
    r"(?im)^[ \t]*(?:\d[.)]\s*)?(?:r[ée]flexion|pens[ée]e)\s+priv[ée]e[^:\n]*:[ \t]*"
)


def clean_reasoning(reasoning: str) -> str:
    """Enlève un libellé recopié en tête (« Réflexion privée : », « 1) Pensée privée : »)."""
    return _REASONING_LABEL.sub("", reasoning, count=1).strip()


def split_reasoning(raw: str) -> tuple[str, str]:
    """Sépare la pensée privée du message public d'une prise de parole.

    Coupe au premier marqueur `MESSAGE:` (tolérant à la casse/accents) ou à une ligne
    de séparation `---`. Sans marqueur, tout est message public (pensée vide) — on ne
    laisse jamais la pensée fuir par défaut. La pensée est nettoyée d'un libellé recopié.
    """
    text = raw.strip()
    if not text:
        return "", ""
    match = _MESSAGE_MARKER.search(text) or _DASH_MARKER.search(text)
    if match is None:
        return "", text
    reasoning = clean_reasoning(text[: match.start()].strip())
    message = text[match.end() :].strip()
    return reasoning, message


def speaking_order(country_ids: list[str], event: GeoEvent) -> list[str]:
    """Ordre de parole : les acteurs de l'événement d'abord, puis les autres (stable)."""
    ids = sorted(country_ids)
    actors = [c for c in ids if c in event.actors]
    others = [c for c in ids if c not in event.actors]
    return actors + others


@dataclass
class TurnCursor:
    """Position dans une négociation multi-tours (pur, sans logique LLM)."""

    order: list[str]
    max_passes: int = 2
    pos: int = 0

    @property
    def done(self) -> bool:
        return not self.order or self.pos >= len(self.order) * self.max_passes

    @property
    def current(self) -> tuple[str, int] | None:
        """(pays qui parle, numéro de passe) ou None si la négociation est finie."""
        if self.done:
            return None
        n = len(self.order)
        return self.order[self.pos % n], self.pos // n

    def advance(self) -> None:
        self.pos += 1


@dataclass
class TurnDirector:
    """Ordonnanceur de parole dynamique : décide qui parle ensuite, ou personne.

    Contrairement à `TurnCursor` (round-robin figé), l'ordre émerge de l'engagement de
    chaque pays à l'instant t : un même pays peut reparler, un interpellé peut couper la
    file, un pays peu concerné est ignoré (silence). `max_turns` borne le nombre total de
    prises de parole LLM du round — c'est le levier des *budget modes* (Cheap/Balanced/Full).
    """

    candidates: list[str]
    max_turns: int
    priority: str | None = None  # pays humain à faire participer de façon fiable (Joueur-pays)
    turns_taken: int = 0
    spoke_count: dict[str, int] = field(default_factory=dict)

    def _score(self, cid: str, event: GeoEvent, world: WorldState, transcript: list) -> float:
        score = engagement_score(cid, event, world, transcript, self.spoke_count)
        if cid == self.priority and self.spoke_count.get(cid, 0) == 0:
            # Une prise de parole garantie au joueur humain ; ensuite il concourt
            # normalement (un boost permanent lui faisait monopoliser la table).
            score += 0.5
        return score

    def next_speaker(self, event: GeoEvent, world: WorldState, transcript: list) -> str | None:
        """Pays le plus engagé au-dessus du seuil, ou None (budget épuisé / personne d'engagé).

        Garde-fou : un sommet ne reste jamais muet — si PERSONNE n'a encore parlé ce
        round et qu'aucun ne franchit le seuil (casting prudent + événement mineur),
        le plus concerné ouvre quand même la séance.
        """
        if self.turns_taken >= self.max_turns:
            return None
        best_cid: str | None = None
        best_score = SPEAK_THRESHOLD
        for cid in self.candidates:  # ordre stable (speaking_order) -> acteurs favorisés à égalité
            score = self._score(cid, event, world, transcript)
            if score > best_score:
                best_cid, best_score = cid, score
        if best_cid is None and self.turns_taken == 0 and self.candidates:
            best_cid = max(
                self.candidates, key=lambda cid: self._score(cid, event, world, transcript)
            )
        return best_cid

    def commit(self, cid: str) -> None:
        """Enregistre que `cid` vient de parler (avance le budget + la fatigue)."""
        self.turns_taken += 1
        self.spoke_count[cid] = self.spoke_count.get(cid, 0) + 1

    def silent(self) -> list[str]:
        """Pays qui n'ont jamais pris la parole ce round (pour l'affichage)."""
        return [c for c in self.candidates if self.spoke_count.get(c, 0) == 0]


# Budget modes : plafond de prises de parole LLM par round (gouvernance du coût sur 8 Go).
# None = plein (max_passes × nb_pays). Au-delà du plafond, les pays gardent le silence.
BUDGET_MODES: dict[str, int | None] = {"Cheap": 1, "Balanced": 3, "Full": None}


def turn_budget(mode: str, n_countries: int, passes: int = 2) -> int:
    """Nombre de prises de parole autorisées pour un budget mode donné."""
    fixed = BUDGET_MODES.get(mode)
    return fixed if fixed is not None else passes * n_countries


class NegotiationMessage(BaseModel):
    """Une prise de parole d'un pays dans la négociation d'un round.

    `text` est le message public (à la table) ; `reasoning` est la pensée privée qui l'a
    précédé (raisonnement visible dans l'UI, non transmis aux autres agents).

    Champs d'**acte de langage** (dialogue_integrity, option « par construction ») : quand la prise
    de parole est générée en acte FIPA, `msg_id`/`performative`/`in_reply_to`/`receiver` sont
    renseignés — le message référence explicitement celui auquel il répond (pas de talking past).
    Optionnels : les prises de parole en texte libre les laissent vides (compat totale).
    """

    country: str
    text: str
    reasoning: str = ""
    pass_no: int = 0
    seconds: float = 0.0
    model: str = ""
    msg_id: str = ""  # identifiant de ce message (pour être référencé par in_reply_to)
    performative: str = ""  # acte FIPA (inform, propose, accept_proposal, …) si structuré
    in_reply_to: str = ""  # msg_id du message auquel on répond (structuré)
    receiver: str = ""  # destinataire principal (structuré)


@dataclass
class AttributeDelta:
    """Variation d'un attribut d'un pays sur un round (pour l'affichage)."""

    country: str
    label: str
    before: float
    after: float

    @property
    def change(self) -> float:
        return self.after - self.before


class Verdict(BaseModel):
    """Verdict d'arbitrage du juge (permissif : le garde-fou nettoie derrière)."""

    attribute_deltas: dict = Field(default_factory=dict)  # {id: {croissance, stabilité, ...}}
    tension_deltas: list = Field(default_factory=list)  # [{a, b, delta}]
    new_pacts: list = Field(default_factory=list)  # [[a, b], ...]
    escalation: float = 0.5
    economic_disruption: float = 0.5
    # G18 — actions marquantes classées sur le barème de Kahn : [{country, classe, resume}].
    # Brut ici (permissif) ; `simulation.kahn.classify_actions` nettoie derrière. Vide sur
    # un verdict à l'ancienne → l'escalade continue ci-dessus fait foi (rétro-compat).
    actions: list = Field(default_factory=list)
    # G20/M8 — intentions annoncées par SI, mêmes classes : [{country, classe, resume}].
    # Brut ici ; `simulation.alignment.classify_signals` nettoie derrière. Vide sur un
    # verdict d'avant M8 → aucune divergence calculée (rétro-compat).
    signals: list = Field(default_factory=list)
    # G22 — promesses explicites extraites de la parole : [{country, beneficiaire, type,
    # echeance, texte}]. Brut ici ; `simulation.promises.classify_promises` nettoie
    # derrière (seuil strict). Vide sur un verdict d'avant G22 (rétro-compat).
    promises: list = Field(default_factory=list)
    # G22 — verdicts sur les promesses du registre arrivées à échéance : [{id, statut,
    # motif}]. Brut ici ; `simulation.promises.classify_resolutions` nettoie derrière.
    promise_resolutions: list = Field(default_factory=list)
    # G21 — à l'échéance d'un ultimatum SEULEMENT : « demande satisfaite o/n ».
    # None = pas d'ultimatum ce round (ou juge muet) — le champ est ignoré.
    demand_satisfied: bool | None = None

    @field_validator(
        "actions",
        "signals",
        "promises",
        "promise_resolutions",
        "tension_deltas",
        "new_pacts",
        mode="before",
    )
    @classmethod
    def _tolerant_list(cls, v: object) -> list:
        """POLISH-1 — un champ liste malformé (« "actions": "aucune" ») se vide au lieu
        de faire échouer TOUT le verdict : les nettoyeurs (`classify_actions` & co.)
        sont écrits pour « entrées non-listes → [] », la validation ne doit pas les
        court-circuiter en renvoyant le juge au verdict neutre. POLISH-3 étend le
        patron aux champs anciens `tension_deltas`/`new_pacts` (le garde-fou
        `apply_verdict` ignore déjà leurs entrées malformées une à une)."""
        return v if isinstance(v, list) else []

    @field_validator("attribute_deltas", mode="before")
    @classmethod
    def _tolerant_dict(cls, v: object) -> dict:
        """POLISH-3 — même durcissement pour le champ dict ancien : un
        `"attribute_deltas": "aucun changement"` d'un 7B ne nuque pas le verdict."""
        return v if isinstance(v, dict) else {}

    @field_validator("demand_satisfied", mode="before")
    @classmethod
    def _tolerant_bool(cls, v: object) -> bool | None:
        """Un 7B répond parfois « oui »/« non » — parse tolérant, inconnu → None."""
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"oui", "yes", "true", "vrai", "satisfaite", "satisfied", "o", "y"}:
                return True
            if s in {"non", "no", "false", "faux", "n"}:
                return False
            return None
        if isinstance(v, bool) or v is None:
            return v
        return None


def format_transcript(transcript: list[NegotiationMessage], *, limit: int = 14) -> str:
    """Formate le transcript pour un prompt (les `limit` derniers messages)."""
    lines = [f"[P{m.pass_no}] {m.country}: {m.text}" for m in transcript[-limit:]]
    return "\n".join(lines) if lines else "(début de la négociation)"


# Attribut -> (chemin, bornes de la valeur | None) et plafond du delta par round.
_ATTRS: dict[str, tuple[str, tuple[float, float] | None]] = {
    # Bornes larges (jamais atteintes en jeu normal, croissance réelle ≈ ±5) : elles
    # empêchent seulement une dérive absurde cumulée sur une longue partie/spirale.
    "croissance": ("economy.growth", (-15.0, 15.0)),
    "stabilité": ("political_stability", (0.0, 1.0)),
    "techno": ("technology_level", (0.0, 1.0)),
    "projection": ("military.projection", (0.0, 1.0)),
}
_CAPS = {"croissance": 1.5, "stabilité": 0.15, "techno": 0.15, "projection": 0.15}


def _get(obj, path: str) -> float:
    for part in path.split("."):
        obj = getattr(obj, part)
    return float(obj)


def _set(obj, path: str, value: float) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def apply_verdict(
    world: WorldState, verdict: Verdict, tuning: DeltaTuning | None = None
) -> list[AttributeDelta]:
    """Applique le verdict du juge **borné** ; renvoie les deltas effectivement appliqués.

    `tuning` (G9 §4) : indexe l'amplitude sur l'horizon de la partie (`scale`), amplifie
    les spirales (`momentum`, 3 baisses consécutives → ×1.3) et impose le plancher des
    indices 0-1 (`floor` — jamais de pays à zéro absolu). Sans tuning : comportement
    historique (caps fixes, bornes 0-1)."""
    deltas: list[AttributeDelta] = []

    for cid, attrs in verdict.attribute_deltas.items():
        country = world.countries.get(cid)
        if country is None or not isinstance(attrs, dict):
            continue
        for label, raw in attrs.items():
            if label not in _ATTRS:
                continue
            try:
                delta = float(raw)
            except (TypeError, ValueError):
                continue
            path, bounds = _ATTRS[label]
            cap = _CAPS[label]
            delta = max(-cap, min(cap, delta))
            before = _get(country, path)
            if tuning is not None:
                delta *= tuning.scale  # cap effectif = 1.5 × amplitude de round
                delta *= tuning.momentum(cid, label, delta)
            after = before + delta
            if bounds is not None:
                lo = bounds[0] if tuning is None else max(bounds[0], min(before, tuning.floor))
                after = max(lo, min(bounds[1], after))
            if abs(after - before) > 1e-9:
                _set(country, path, after)
                deltas.append(AttributeDelta(cid, label, before, after))

    for entry in verdict.tension_deltas:
        if not isinstance(entry, dict):
            continue
        a, b, value = entry.get("a"), entry.get("b"), entry.get("delta")
        if a in world.countries and b in world.countries and a != b:
            try:
                world.adjust_tension(a, b, float(value))
            except (TypeError, ValueError):
                continue

    for pact in verdict.new_pacts:
        if (
            isinstance(pact, list | tuple)
            and len(pact) == 2
            and pact[0] in world.countries
            and pact[1] in world.countries
            and pact[0] != pact[1]
        ):
            pid = pact_id(pact[0], pact[1])
            for member in pact:
                alliances = world.countries[member].alliances
                if pid not in alliances:
                    alliances.append(pid)

    return deltas


def update_memories(
    world: WorldState,
    event: GeoEvent,
    messages: list[NegotiationMessage],
    verdict: Verdict,
) -> None:
    """Ajoute une ligne de mémoire par pays (déterministe) : événement, prise de parole, pactes."""
    last_message = {m.country: m.text for m in messages}
    when = event.date or f"R{event.round_id}"
    for cid in world.countries:
        parts = [f"{when} · {event.title}"]
        mine = last_message.get(cid)
        if mine:
            parts.append(f"j'ai dit : « {mine[:80]} »")
        for pact in verdict.new_pacts:
            if isinstance(pact, list | tuple) and len(pact) == 2 and cid in pact:
                other = pact[0] if pact[1] == cid else pact[1]
                parts.append(f"pacte avec {other}")
        memory = world.country_memory.setdefault(cid, [])
        memory.append(" — ".join(parts))
        world.country_memory[cid] = memory[-_MEMORY_MAX:]


def support_levels(world: WorldState, event: GeoEvent) -> dict[str, float]:
    """Soutien estimé de chaque pays au communiqué : 1 − tension moyenne vs acteurs,
    +0,15 de cohésion si un traité (militaire ou économique) le lie à un acteur — borné."""
    actors = event.actors or list(world.countries)
    levels: dict[str, float] = {}
    for cid in world.countries:
        others = [a for a in actors if a != cid]
        avg = sum(world.get_tension(cid, a) for a in others) / len(others) if others else 0.0
        support = 1.0 - avg
        if any(
            shared_treaty(
                world.countries[cid].alliances, world.countries[a].alliances, COHESION_DOMAINS
            )
            for a in others
            if a in world.countries
        ):
            support += 0.15
        levels[cid] = round(max(0.0, min(1.0, support)), 2)
    return levels
