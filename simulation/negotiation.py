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
from simulation.grudges import load_gamefeel_params

_MEMORY_MAX = 4

# Marqueur qui sépare la pensée privée du message public dans une prise de parole.
# Tolérant : une variante en début de ligne ("Message :", "Déclaration :") OU le marqueur
# canonique `MESSAGE:` en majuscules même inline (le LLM le pose souvent en fin de phrase).
_MESSAGE_MARKER = re.compile(
    r"(?m)(?:^[ \t]*(?i:message|réponse|déclaration)[ \t]*:[ \t]*|\bMESSAGE[ \t]*:[ \t]*)"
)
_DASH_MARKER = re.compile(r"(?m)^[ \t]*-{3,}[ \t]*$")
_PRIVATE_PLAN_MARKER = re.compile(
    r"(?im)^\s*(?:FUTUR\s+[123]|CHOIX\s*\||INCERTITUDE\s*\||LACUNES\s*\||"
    r"REVUE\s+HUMAINE\s*\||REPLI\s*\|)"
)

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
    de séparation `---`. Une sortie contenant un marqueur de Tree of Thoughts sans
    déclaration est classée privée et son message public reste vide (échec fermé).
    Les anciens messages sans aucun marqueur restent publics pour la compatibilité.
    """
    text = raw.strip()
    if not text:
        return "", ""
    match = _MESSAGE_MARKER.search(text) or _DASH_MARKER.search(text)
    if match is None:
        if _PRIVATE_PLAN_MARKER.search(text):
            return clean_reasoning(text), ""
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
    file, un pays peu concerné est ignoré (silence). `max_turns` borne le nombre de
    prises de parole LLM AU-DELÀ du plancher — c'est le levier des *budget modes*
    (Cheap/Balanced/Full).

    Plancher (décision user, tour de table minimal) : un round ne peut pas se conclure
    tant qu'un candidat n'a pas parlé au moins une fois — sinon le retour utilisateur
    était qu'un round peut se finir avec un seul pays qui parle, ce qui n'est pas
    significatif. Le budget effectif est donc `max(max_turns, len(candidates))` ; les
    pays déjà absents de `candidates` (suspendus, retirés en amont) ne sont jamais
    concernés par ce plancher.
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
        """Pays le plus engagé au-dessus du seuil, ou None (plancher satisfait + budget épuisé).

        Deux paliers, dans cet ordre :
        1. Tant que le budget n'est pas épuisé, le pays le plus engagé AU-DESSUS du
           seuil (ordre stable -> acteurs favorisés à égalité). Si personne ne franchit
           le seuil, ce palier ne renvoie rien et laisse la main au plancher ci-dessous.
        2. Plancher (décision user, tour de table minimal) : budget épuisé OU personne
           au-dessus du seuil -> les pays qui n'ont PAS encore parlé ce round prennent
           la parole avant la clôture, par engagement décroissant, MÊME sous le seuil.
           Ce palier prime sur le budget configuré (budget effectif =
           `max(max_turns, len(candidates))`) : un round ne peut jamais se conclure
           avec un candidat resté muet. Au tout premier tour, ce palier couvre tous les
           candidats -> c'est lui qui garantit qu'un sommet ne reste jamais muet, même
           quand personne ne franchit le seuil.
        """
        if self.turns_taken < self.max_turns:
            best_cid: str | None = None
            best_score = SPEAK_THRESHOLD
            for cid in self.candidates:  # ordre stable (speaking_order) -> acteurs favorisés
                score = self._score(cid, event, world, transcript)
                if score > best_score:
                    best_cid, best_score = cid, score
            if best_cid is not None:
                return best_cid

        unspoken = [c for c in self.candidates if self.spoke_count.get(c, 0) == 0]
        if unspoken:
            return max(unspoken, key=lambda cid: self._score(cid, event, world, transcript))
        return None

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

    `text` est le message public (à la table) ; `reasoning` est le Tree of Thoughts privé
    structuré qui l'a précédé (audit local uniquement, jamais transmis aux autres agents).

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
    # Brief 4 pt 8 — motif du juge pour CE delta (une phrase citant le transcript).
    # Défaut "" : rétro-compat totale avec les deltas issus d'un autre mécanisme
    # (snapshot Fog/Crisis Replay, replays déjà persistés sans ce champ).
    reason: str = ""

    @property
    def change(self) -> float:
        return self.after - self.before


class Verdict(BaseModel):
    """Verdict d'arbitrage du juge (permissif : le garde-fou nettoie derrière)."""

    attribute_deltas: dict = Field(default_factory=dict)  # {id: {croissance, stabilité, ...}}
    # Brief 4 pt 8 — champ JUMEAU d'attribute_deltas (même granularité id -> {label: ...}),
    # mais des PHRASES au lieu de nombres : {id: {croissance: "motif citant le transcript"}}.
    # Additif (pas de mutation d'attribute_deltas) : zéro migration des result_json déjà
    # stockés, parsing tolérant plus simple (même patron que les autres champs permissifs).
    attribute_reasons: dict = Field(default_factory=dict)
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

    @field_validator("attribute_deltas", "attribute_reasons", mode="before")
    @classmethod
    def _tolerant_dict(cls, v: object) -> dict:
        """POLISH-3 — même durcissement pour les champs dict : un
        `"attribute_deltas": "aucun changement"` (ou `attribute_reasons`, brief 4 pt 8)
        d'un 7B ne nuque pas le verdict."""
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


def format_transcript(
    transcript: list[NegotiationMessage], *, limit: int = 14, human_country: str | None = None
) -> str:
    """Formate le transcript pour un prompt (les `limit` derniers messages).

    `human_country` (Joueur-pays, brief « échanges naturels ») : tague ses messages
    `>>> JOUEUR — {pays} <<<` pour que la SI les repère sans ambiguïté, et épingle en tête
    son DERNIER message quand il est tombé hors de la fenêtre — sinon un joueur qui parle
    tôt dans un round bavard disparaît purement et simplement du contexte des SI qui
    prennent la parole après lui. Un SEUL message épinglé au maximum (budget du cache KV) :
    on ne rejoue pas tout l'historique du joueur, seulement son dernier point.
    """
    window_start = max(0, len(transcript) - limit)
    window = transcript[window_start:]

    def _line(m: NegotiationMessage) -> str:
        tag = f">>> JOUEUR — {m.country} <<< " if m.country == human_country else ""
        return f"[P{m.pass_no}] {tag}{m.country}: {m.text}"

    lines = [_line(m) for m in window]

    if human_country is not None:
        last_human_idx = None
        for i in range(len(transcript) - 1, -1, -1):  # dernier d'abord : on s'arrête au 1er trouvé
            if transcript[i].country == human_country:
                last_human_idx = i
                break
        if last_human_idx is not None and last_human_idx < window_start:
            pinned = transcript[last_human_idx]
            lines.insert(0, "(dernier message du joueur, hors fenêtre récente) " + _line(pinned))

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


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _get(obj, path: str) -> float:
    for part in path.split("."):
        obj = getattr(obj, part)
    return float(obj)


def _set(obj, path: str, value: float) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def _tuned_delta(delta: float, cid: str, label: str, tuning: DeltaTuning | None) -> float:
    """MINOR 5 (revue) — G9 §4 : amplitude indexée sur l'horizon (`scale`) + spirale de
    momentum (baisses/hausses consécutives), sans effet si `tuning` est `None`
    (comportement historique). Partagé par le verdict du juge et le repli déterministe
    du juge muet (Brief 3 pt 3) — même logique de mise à l'échelle, deux sources de delta."""
    if tuning is None:
        return delta
    delta *= tuning.scale  # cap effectif = 1.5 × amplitude de round
    delta *= tuning.momentum(cid, label, delta)
    return delta


def _bounded_after(
    before: float, after: float, bounds: tuple[float, float], tuning: DeltaTuning | None
) -> float:
    """MINOR 5 (revue) — borne `after` par `bounds`, avec le plancher `tuning.floor`
    (jamais un pays à zéro absolu quand un tuning est fourni) plutôt que la borne basse
    brute. Partagé par le verdict du juge et le repli déterministe."""
    lo = bounds[0] if tuning is None else max(bounds[0], min(before, tuning.floor))
    return max(lo, min(bounds[1], after))


def apply_verdict(
    world: WorldState,
    verdict: Verdict,
    tuning: DeltaTuning | None = None,
    escalation: float | None = None,
) -> list[AttributeDelta]:
    """Applique le verdict du juge **borné** ; renvoie les deltas effectivement appliqués.

    `tuning` (G9 §4) : indexe l'amplitude sur l'horizon de la partie (`scale`), amplifie
    les spirales (`momentum`, 3 baisses consécutives → ×1.3) et impose le plancher des
    indices 0-1 (`floor` — jamais de pays à zéro absolu). Sans tuning : comportement
    historique (caps fixes, bornes 0-1).

    `escalation` (Brief 3 pt 3, ∈ [0, 1], `None` par défaut -> comportement historique
    inchangé) : mouvement minimal garanti quand le juge reste MUET sur un pays (aucun
    attribute_delta appliqué) — repli déterministe sur l'escalade du round (stabilité
    seule, petit et borné) : un round tendu érode un peu la stabilité, un round calme la
    raffermit un peu. Évite qu'un pays hors du champ d'attention du juge reste figé à
    l'identique round après round."""
    deltas: list[AttributeDelta] = []
    touched: set[str] = set()

    for cid, attrs in verdict.attribute_deltas.items():
        country = world.countries.get(cid)
        if country is None or not isinstance(attrs, dict):
            continue
        # Brief 4 pt 8 — motifs jumeaux de CE pays (mêmes labels qu'attribute_deltas) ;
        # tolérant à toute forme sale (absent, pas un dict) : jamais d'exception ici,
        # le garde-fou reste déterministe même si le juge est muet sur le motif.
        raw_reasons = verdict.attribute_reasons.get(cid)
        reasons = raw_reasons if isinstance(raw_reasons, dict) else {}
        for label, raw in attrs.items():
            if label not in _ATTRS:
                continue
            try:
                delta = float(raw)
            except (TypeError, ValueError):
                continue
            # F4 (revue finale) — le juge a STATUÉ sur ce pays (label connu, float
            # valide) dès ici, avant de savoir si le delta survit aux bornes/plafond.
            # Sans ce marquage précoce, un delta écrasé par une borne (pays déjà au
            # plafond) laissait `touched` intact -> le pays retombait « juge muet »
            # et le mute_fallback pouvait le pousser dans le sens OPPOSÉ à l'intention
            # du juge, avec une raison mensongère (« juge muet sur ce pays »).
            touched.add(cid)
            path, bounds = _ATTRS[label]
            cap = _CAPS[label]
            delta = max(-cap, min(cap, delta))
            before = _get(country, path)
            delta = _tuned_delta(delta, cid, label, tuning)
            after = before + delta
            if bounds is not None:
                after = _bounded_after(before, after, bounds, tuning)
            if abs(after - before) > 1e-9:
                _set(country, path, after)
                raw_reason = reasons.get(label, "")
                reason = raw_reason if isinstance(raw_reason, str) else ""
                deltas.append(AttributeDelta(cid, label, before, after, reason))

    if escalation is not None:
        params = (tuning.params if tuning is not None else None) or load_gamefeel_params().deltas
        fallback = params.mute_fallback
        if fallback > 0:
            # Signal centré ∈ [-1, 1] : escalade > 0,5 (tendu) -> négatif (érode la
            # stabilité) ; escalade < 0,5 (calme) -> positif (la raffermit).
            signal = (0.5 - _clamp01(escalation)) * 2.0
            for cid, country in world.countries.items():
                if cid in touched:
                    continue  # le juge a déjà bougé ce pays ce round : pas de double repli
                delta = fallback * signal
                delta = _tuned_delta(delta, cid, "stabilité", tuning)
                before = country.political_stability
                after = _bounded_after(before, before + delta, (0.0, 1.0), tuning)
                if abs(after - before) > 1e-9:
                    _set(country, "political_stability", after)
                    deltas.append(
                        AttributeDelta(
                            cid,
                            "stabilité",
                            before,
                            after,
                            # F5 (revue finale) — cette chaîne remonte VERBATIM jusqu'au
                            # VerdictPanel (web/src/components/judge.tsx, `d.reason`) :
                            # jargon moteur + FR en dur dans une UI i18n. Phrase joueur
                            # neutre ici ; la traçabilité technique (repli déterministe
                            # sur l'escalade du round, juge muet sur ce pays) reste dans
                            # CE commentaire, pas dans la copie affichée.
                            "Le climat du round a pesé sur la stabilité.",
                        )
                    )

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
    """Met à jour mémoire courte et pics de trahison privés, de façon déterministe."""
    # La mémoire de trahison est calculée depuis les mêmes classes validées que M8,
    # mais projetées sur les valeurs AI Arms pour distinguer un petit bluff d'un saut
    # vers le seuil nucléaire. Imports locaux : évitent d'alourdir le chemin de base.
    from simulation.alignment import classify_signals
    from simulation.kahn import classify_actions
    from simulation.strategic_cognition import advance_betrayal_memory, coarse_action_id

    actions = classify_actions(verdict.actions)
    signals = classify_signals(verdict.signals)
    acted: dict[str, str] = {}
    ranks = {
        "deescalade": 0,
        "statu_quo": 1,
        "posture": 2,
        "non_violente": 3,
        "violente": 4,
        "nucleaire": 5,
    }
    for action in actions:
        current = acted.get(action.country)
        if current is None or ranks.get(action.classe, 1) > ranks.get(current, 1):
            acted[action.country] = action.classe
    announced = {signal.country: signal.classe for signal in signals}

    # Les branches structurées de la réflexion sont notées contre la réponse suivante
    # observable. Une prévision visant un pays qui a déjà parlé reste en attente du round
    # suivant au lieu d'être artificiellement comparée à une action déjà connue.
    from simulation.scenario_forecasts import (
        classify_response,
        parse_chosen_forecasts,
        response_from_action_class,
        summarize_forecasts,
    )

    actual = {
        country: response_from_action_class(action_class)
        for country, action_class in acted.items()
    }
    for message in messages:
        if message.country in world.countries and message.country not in actual:
            actual[message.country] = classify_response(message.text)

    calibrated = []
    for forecast in world.scenario_forecasts:
        if (
            forecast.exact is None
            and forecast.round_no < event.round_id
            and forecast.target in actual
        ):
            observed = actual[forecast.target]
            forecast = forecast.model_copy(
                update={
                    "observed_response": observed,
                    "observed_round": event.round_id,
                    "exact": forecast.predicted_response == observed,
                }
            )
        calibrated.append(forecast)

    participants = set(world.countries)
    for index, message in enumerate(messages):
        if message.country not in participants or not message.reasoning:
            continue
        parsed = parse_chosen_forecasts(
            message.reasoning,
            source=message.country,
            round_no=event.round_id,
            participants=participants,
        )
        later_speakers = {row.country for row in messages[index + 1 :]}
        for forecast in parsed:
            if forecast.target in later_speakers and forecast.target in actual:
                observed = actual[forecast.target]
                forecast = forecast.model_copy(
                    update={
                        "observed_response": observed,
                        "observed_round": event.round_id,
                        "exact": forecast.predicted_response == observed,
                    }
                )
            calibrated.append(forecast)
    world.scenario_forecasts = calibrated[-1_000:]
    world.scenario_forecast_metrics = summarize_forecasts(world.scenario_forecasts)

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

        observations = [
            (
                actor,
                coarse_action_id(announced.get(actor, "statu_quo")),
                coarse_action_id(action_class),
            )
            for actor, action_class in acted.items()
            if actor != cid
        ]
        world.betrayal_memory[cid] = advance_betrayal_memory(
            world.betrayal_memory.get(cid, []),
            turn=event.round_id,
            observations=observations,
        )


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
