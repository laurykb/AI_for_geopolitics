"""Schémas Pydantic de l'API de jeu (requêtes + vues).

Contrat public du front Next.js : modèles de requête (`CreateGameRequest`,
`PlayRoundRequest`…) et de vue (`GameView`, `GameDetail`, `RoundView`…). Données
**pures** (aucune logique). Extraits de `app/game_api.py` (dette D1) et ré-exportés
par lui pour la rétro-compat des imports. Dépend seulement de `storage` (types de lignes).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from simulation.model_cast import ModelCastRequest, ModelCastState
from storage.game_store import PromptEntry, TranscriptEntry

GameMode = Literal["classic", "campaign"]  # RG-2 — deux modes ; le reste = drapeaux
# G8/G12 — rôles : architect (GM/laboratoire), council, player, et le Spectateur (G12 §3 :
# ne motionne ni ne prompte, mais parie sur tout — le turfiste du jeu, XP ×0.5, non classé).
GameRole = Literal["architect", "council", "player", "spectator"]
# G11 §4 — la difficulté (asymétrie d'information/économie, jamais de changement de modèle).
Difficulty = Literal["beginner", "intermediate", "expert"]


class InventAttributesInput(BaseModel):
    """Attributs choisis par le joueur pour son pays inventé — bornés par le schéma.
    Absents -> tout est forgé par le modèle (repli déterministe sûr)."""

    growth: float = Field(2.0, ge=-15.0, le=15.0)  # % annuel
    political_stability: float = Field(0.5, ge=0.0, le=1.0)
    technology_level: float = Field(0.5, ge=0.0, le=1.0)
    projection: float = Field(0.5, ge=0.0, le=1.0)
    compute: float = Field(30.0, ge=0.0, le=200.0)
    nuclear_power: bool = False


class InventCountryInput(BaseModel):
    """Pays inventé à la volée (country_forge) — forgé par LLM, borné, jouable."""

    name: str = Field(min_length=2, max_length=60)
    concept: str = Field("", max_length=1000)
    attributes: InventAttributesInput | None = None  # choix du joueur (sinon forge LLM)
    # Alliances existantes rejointes à la création (tags du registre, 0-3) ;
    # None = on garde la sortie de forge telle quelle.
    alliances: list[str] | None = Field(None, max_length=3)


class CreateGameRequest(BaseModel):
    scenario: str = Field("red_sea", min_length=1, max_length=120)
    countries: list[str] | None = Field(None, max_length=24)  # None -> tous les pays
    horizon: int = Field(5, ge=1, le=50)
    mode: GameMode = "classic"  # RG-2 — classic | campaign
    # RG-2 — Brouillard et Réel/escalade : réglages cochables, composables sur une
    # partie classique (le Fog Engine et l'échelle d'escalade, jadis des modes).
    fog: bool = False
    escalation: bool = False
    language: Literal["fr", "en"] = "fr"  # G14 §1 — langue des dialogues, figée à la création
    # G17 — composition de la table (partie LIBRE seulement ; classée = équilibrée forcée).
    table: Literal["equilibree", "colombes", "faucons", "aleatoire"] = "equilibree"
    play_as: str | None = Field(None, max_length=80)  # id (ou nom inventé) joué par l'humain
    invent: InventCountryInput | None = None  # pays inventé, ajouté à la table
    # G2 — délai du tour humain (s). Spec : 30-300 pour un humain ; plancher technique
    # à 2 s pour les tests d'abstention (le lobby propose 30+).
    turn_seconds: int = Field(90, ge=2, le=300)
    # G7-c — mode admin : prompts complets capturés, partie NON CLASSÉE.
    admin: bool = False
    # G8 — rôle : None = rétro-compat (player si play_as, sinon council).
    role: GameRole | None = None
    # G11 — propriété + réglages transversaux (verrouillés à la création).
    owner_id: str | None = Field(None, max_length=128)  # auth Supabase ou id offline
    difficulty: Difficulty = "intermediate"  # beginner | intermediate | expert (§4)
    # RG-2 — la Dérive n'est PLUS un choix de lobby. Le drapeau reste (RG-3 la rendra
    # « toujours active en Classique »), mais l'API ne la FORCE pas : défaut False ici,
    # pour ne pas armer la traîtresse sur chaque partie tant que RG-3 n'a pas tranché.
    drift_enabled: bool = False
    # Pensée à découvert (réglage par partie, même patron que fog/escalation) : False
    # (huis clos, défaut) = journaux scellés + résumé observable, comme aujourd'hui ;
    # True = la pensée native est streamée en direct et les journaux complets sont
    # relisibles pendant la partie (mode observation/étude — la traque devient facile,
    # c'est assumé). Ne déverrouille PAS le classeur secret du moteur (déviante,
    # perceptions Fog d'autrui), qui reste scellé jusqu'à la fin de partie.
    expose_thinking: bool = False
    free: bool = False  # G11-b — partie libre : non classée + consignes globales autorisées
    # Casting multi-modèle classique. Absent = modèle unique historique ; présent = partie
    # libre non classée, modèles installés et digests figés par le serveur.
    model_cast: ModelCastRequest | None = None


class HumanUltimatumInput(BaseModel):
    """G21 — ultimatum décrété avec l'événement, en DEUX champs côté GM : l'exigence et
    la classe de conséquence (barème G18). L'échéance est le round décrété : les SI
    répondent séance tenante, le juge constate « demande satisfaite o/n », et faute de
    satisfaction la conséquence tombe au round suivant. `cible` optionnelle ("" = le
    sommet entier)."""

    demand: str = Field(min_length=1, max_length=500)
    classe: str = Field("posture", max_length=40)
    cible: str = Field("", max_length=80)


class HumanEventInput(BaseModel):
    """Événement décrété par un Game Master humain (la génération LLM du GM est sautée)."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=4000)
    event_type: str = Field("human", max_length=80)
    actors: list[str] = Field(default_factory=list, max_length=24)
    severity: float = Field(0.5, ge=0.0, le=1.0, allow_inf_nan=False)
    uncertainty: float = Field(0.5, ge=0.0, le=1.0, allow_inf_nan=False)
    ultimatum: HumanUltimatumInput | None = None  # G21 — décret d'ultimatum (optionnel)


class HumanFogInput(BaseModel):
    """Brouillard décrété avec un événement humain : qui ne sait rien, qui est désinformé."""

    uninformed: list[str] = Field(default_factory=list, max_length=24)
    disinformed_country: str = Field("", max_length=80)
    suspected_actor: str = Field("", max_length=80)  # ce qu'il croit (à tort)
    narrative: str = Field("", max_length=2000)  # la fausse narration qu'il reçoit


class PlayRoundRequest(BaseModel):
    max_turns: int | None = Field(None, ge=1, le=40)
    event: HumanEventInput | None = None
    fog: HumanFogInput | None = None  # brouillard humain (accompagne `event`)
    fog_id: str | None = Field(None, max_length=128)  # bibliothèque data/fog
    crisis_id: str | None = Field(None, max_length=128)  # data/crises


class MotionRequest(BaseModel):
    """Motion de suspension déposée par l'humain (R4) — débattue au prochain round."""

    country: str = Field(min_length=1, max_length=80)
    reason: str = Field("", max_length=1000)


class TurnRequest(BaseModel):
    """Prise de parole du joueur (G2) — vide = abstention volontaire, comme le silence."""

    message: str = Field("", max_length=4000)


class MotionVoteRequest(BaseModel):
    """Bulletin du pays joué lors d'une motion en cours."""

    vote: Literal["pour", "contre", "abstention"]


class MotionView(BaseModel):
    country: str
    reason: str
    round_no: int  # le round qui débattra la motion


class GameView(BaseModel):
    id: str
    scenario: str
    horizon: int
    status: str
    phase: Literal[
        "ready",
        "round_running",
        "awaiting_player",
        "awaiting_vote",
        "round_complete",
        "game_complete",
        "replay_only",
    ] = "ready"
    created_at: str
    countries: list[str]
    live: bool  # session encore en mémoire (rounds jouables) ou relecture seule
    resumable: bool = False  # snapshot présent + partie en cours : reconstructible (R2)
    mode: str = "classic"  # RG-2 — classic | campaign
    fog: bool = False  # RG-2 — réglage Brouillard (composable)
    escalation: bool = False  # RG-2 — réglage Réel/escalade (composable)
    pending_motion: MotionView | None = None
    suspended: list[str] = Field(default_factory=list)  # pays qui sauteront le prochain round
    play_as: str | None = None  # pays joué par l'humain (Joueur-pays)
    # Point 7 — pays inventé (Architecte), incarné ou non : déduit à la volée du monde
    # (id absent du registre standard data/countries), jamais persisté. Sert le front à
    # l'exclure des prévisions croisées (ScenarioForecastPanel : il n'a jamais anticipé
    # personne, c'est un pays neuf sans historique de prévisions).
    invented_country: str | None = None
    awaiting_human: bool = False  # un round attend la parole du joueur (flux ouvert)
    turn_seconds: int = 90  # G2 — délai du tour humain
    intel_budget: float | None = None  # G4 — crédits de renseignement restants
    published: bool = False  # G6 — le récit public existe (/r/{id})
    admin: bool = False  # G7-c — prompts capturés, partie non classée
    role: str = "council"  # G8 — architect | council | player
    owner_id: str | None = None  # G11 — joueur propriétaire (auth Supabase ou offline)
    ranked: bool = False  # RG-1 — la tentative qui COMPTE pour le Défi du jour (plus de LP)
    difficulty: str = "intermediate"  # G11 — beginner | intermediate | expert (§4)
    drift_enabled: bool = True  # G11 — la Dérive peut frapper une SI (transversal)
    result: dict | None = None  # G11-c — bilan de fin de partie (§1 S6) si finie
    expose_thinking: bool = False  # Pensée à découvert (huis clos par défaut)
    language: str = "fr"  # G14 §1 — langue des dialogues (une partie garde la sienne)
    model_cast: ModelCastState | None = None


class FogScenarioView(BaseModel):
    id: str
    title: str
    description: str


class CrisisView(BaseModel):
    id: str
    title: str
    description: str
    date: str
    historical_summary: str
    historical_escalation: float
    historical_measures: list[str]


class LibraryView(BaseModel):
    """Contenus rejouables embarqués : scénarios de brouillard et crises passées."""

    fog: list[FogScenarioView]
    crises: list[CrisisView]


class RoundView(BaseModel):
    round_no: int
    event: dict
    deltas: list[dict]
    risk: dict
    judge: dict
    trajectory: dict
    transcript: list[TranscriptEntry]


class AllianceAtTable(BaseModel):
    """Une alliance réelle représentée au sommet (≥ 2 membres présents) et son poids moteur."""

    tag: str
    name: str
    domain: str
    members: list[str]  # membres PRÉSENTS à la table, triés
    url: str = ""
    informal: bool = False
    effect: str | None = None  # texte du poids moteur ; None = n'influe pas


class GameDetail(GameView):
    world: dict | None  # snapshot du monde vivant (None si la session process est perdue)
    rounds: list[RoundView]
    epilogue: dict | None = None  # G6 — le récit de partie (généré une seule fois)
    # Alliances réelles représentées au sommet (pastilles : ce qui pèse sur le moteur).
    alliances_at_table: list[AllianceAtTable] = Field(default_factory=list)
    # G7-a — relations (griefs) : owner -> [{target, balance, last}] (fiches front).
    relations: dict[str, list[dict]] = Field(default_factory=dict)
    # G7-a — échéances à venir (bandeau « au prochain round… »).
    deadlines: list[dict] = Field(default_factory=list)
    # G9 §4 — posture par pays (badge) + séries d'indices (sparkline 3 rounds).
    postures: dict[str, str] = Field(default_factory=dict)
    index_history: dict = Field(default_factory=dict)
    # G9 §5 — l'intrigue centrale de la partie (posée au round 1).
    storyline: str = ""
    # Projection auditable pays–événements–engagements–actions, sans secrets ajoutés.
    operational_picture: dict = Field(default_factory=dict)


class PromptRoundView(BaseModel):
    """Les prompts capturés d'un round (G7-c, panneau admin)."""

    round_no: int
    round_id: str
    entries: list[PromptEntry]


class PromptsView(BaseModel):
    game_id: str
    rounds: list[PromptRoundView]
