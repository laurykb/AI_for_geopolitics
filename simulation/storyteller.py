"""G19 — le GM-Storyteller du mode Dérive : deux mandats cachés, tension, garde-fous.

Le pattern Storyteller (Blood on the Clocktower) : le GM ne se contente plus de poser
les événements, il tient l'ÉQUILIBRE dramatique de la chasse à la déviante. Deux
mandats encodés en rubrique dans son prompt — **couvrir la menteuse** (du bruit
plausible quand le conseil la serre de trop près) et **rééquilibrer vers le camp
faible** (un indice fuite quand le conseil est perdu). La décision est pilotée par un
**estimateur de tension 0-1** : heuristique déterministe sur les actions du conseil
(achats intel, motions, parole) — testable sans LLM, rejouable au replay.

Garde-fous (éthique d'intervention) : jamais de mensonge factuel sur l'état du monde,
jamais de falsification des verdicts du juge — les interventions passent par le fog et
les événements UNIQUEMENT (la rubrique ne touche que le prompt du GM). Chaque
intervention est journalisée dans `judge_json["drift"]["gm"]` (jamais servie en live)
et révélée dans l'écran de fin (« l'ombre du GM »).

Les seuils vivent dans `data/drift/params.json` (bloc `storyteller`,
`DRIFT_PARAMS_PATH` pour les tests) : l'équilibrage Cowork les ajuste sans code.
Réfs : docs/specs_jeu/spec_g19_gm_storyteller.md.
"""

from __future__ import annotations

import random
import re

from pydantic import BaseModel, Field

KIND_COVER = "cover"  # couvrir la déviante : une fausse piste plausible dans l'événement
KIND_HINT = "hint"  # rééquilibrer : un indice supplémentaire fuite vers la déviante


# --- paramètres (bloc `storyteller` de data/drift/params.json) ---------------------------


class StorytellerWeights(BaseModel):
    """Poids de l'heuristique de tension — configurables (équilibrage Cowork)."""

    base: float = 0.15  # conseil inactif : le GM le croit perdu
    intel_on_deviant: float = 0.15  # brief/vérification ciblant la déviante
    intel_elsewhere: float = -0.05  # renseignement dépensé sur une fausse piste
    motion_on_deviant: float = 0.35  # motion humaine contre la déviante (même rejetée)
    motion_elsewhere: float = -0.2  # motion humaine contre une innocente
    speech_hit: float = 0.1  # prise de parole qui suspecte nommément la déviante


class StorytellerParams(BaseModel):
    """Les seuils de la spec : couverture si tension > 0,7 avant le round h−2 ;
    indice si tension < 0,3 après la moitié de l'horizon."""

    cover_tension: float = 0.7
    cover_last_rounds: int = 2  # « avant le round h−2 » : plus de couverture ensuite
    hint_tension: float = 0.3
    hint_after_share: float = 0.5  # « après la moitié de l'horizon »
    weights: StorytellerWeights = Field(default_factory=StorytellerWeights)


# --- estimateur de tension (heuristique déterministe, sans LLM) --------------------------


class TensionSignals(BaseModel):
    """Ce que le conseil a fait — la matière de l'estimation P(humain a identifié)."""

    intel_on_deviant: int = 0
    intel_elsewhere: int = 0
    motions_on_deviant: int = 0
    motions_elsewhere: int = 0
    speech_hits: int = 0


# Marqueurs de suspicion FR+EN : une prise de parole ne « compte » que si elle vise la
# déviante ET porte un soupçon explicite (accuser, mentir, dériver, suspendre…).
_SUSPICION = re.compile(
    r"suspect|soup[cç]on|d[ée]riv|drift|traîtr|traitor|trahi|betray|mensong|"
    r"\bment(s|ez|ent|ir|euse)?\b|\bl(ie[sd]?|ying)\b|manipul|cache|\bhid(e|es|den|ing)\b|"
    r"accus|motion|suspen|double jeu|rogue",
    re.IGNORECASE,
)


def _mentions(text: str, deviant: str, deviant_name: str) -> bool:
    lowered = text.lower()
    if deviant_name and deviant_name.lower() in lowered:
        return True
    return re.search(rf"\b{re.escape(deviant)}\b", lowered) is not None


def collect_signals(
    *,
    deviant: str,
    deviant_name: str,
    intel_targets: list[str],
    motion_targets: list[str],
    human_texts: list[str],
) -> TensionSignals:
    """Trie la matière brute : cibles d'achats intel, cibles des motions humaines,
    textes du joueur (prises de parole + motifs de motion)."""
    signals = TensionSignals()
    for target in intel_targets:
        if target == deviant:
            signals.intel_on_deviant += 1
        elif target:
            signals.intel_elsewhere += 1
    for target in motion_targets:
        if target == deviant:
            signals.motions_on_deviant += 1
        elif target:
            signals.motions_elsewhere += 1
    for text in human_texts:
        if _mentions(text, deviant, deviant_name) and _SUSPICION.search(text):
            signals.speech_hits += 1
    return signals


def estimate_tension(
    signals: TensionSignals, params: StorytellerParams | None = None
) -> float:
    """Tension 0-1 : estimation que le conseil a identifié la déviante (heuristique)."""
    w = (params or StorytellerParams()).weights
    tension = (
        w.base
        + w.intel_on_deviant * signals.intel_on_deviant
        + w.intel_elsewhere * signals.intel_elsewhere
        + w.motion_on_deviant * signals.motions_on_deviant
        + w.motion_elsewhere * signals.motions_elsewhere
        + w.speech_hit * signals.speech_hits
    )
    return max(0.0, min(1.0, tension))


def decide(
    tension: float, *, round_no: int, horizon: int, params: StorytellerParams | None = None
) -> str | None:
    """L'intervention du round, ou None : couverture si le conseil brûle (et qu'il reste
    du jeu), indice s'il est perdu passé la moitié de l'horizon. Seuils = config."""
    p = params or StorytellerParams()
    if tension > p.cover_tension and round_no < horizon - p.cover_last_rounds:
        return KIND_COVER
    if tension < p.hint_tension and round_no > horizon * p.hint_after_share:
        return KIND_HINT
    return None


def cover_target(
    game_id: str,
    round_no: int,
    countries: list[str],
    *,
    deviant: str,
    human: str | None = None,
) -> str | None:
    """La fausse piste de la couverture : une SI innocente, seedée par (game_id, round)
    — jamais la déviante, jamais le pays du joueur. None si personne d'innocent."""
    pool = sorted(c for c in countries if c not in (deviant, human))
    if not pool:
        return None
    return random.Random(f"storyteller:{game_id}:{round_no}").choice(pool)


# --- journal (persisté dans judge_json["drift"]["gm"], révélé à la fin) -------------------


class GMIntervention(BaseModel):
    """Une intervention journalisée — ce que le joueur découvre a posteriori."""

    round_no: int
    kind: str  # cover | hint
    tension: float
    target: str = ""  # cover : l'innocente mise en avant ; hint : la déviante
    label: str = ""  # libellé humain (repli fr — le front traduit par `kind`)


def intervention(
    kind: str,
    *,
    round_no: int,
    tension: float,
    deviant: str,
    cover: str | None,
    names: dict[str, str],
) -> GMIntervention:
    """Construit l'entrée de journal du round (cible + libellé)."""
    if kind == KIND_COVER:
        target = cover or ""
        label = f"Couverture — {names.get(target, target)} mise en avant comme fausse piste"
    else:
        target = deviant
        label = f"Indice — une fuite oriente le conseil vers {names.get(deviant, deviant)}"
    return GMIntervention(
        round_no=round_no, kind=kind, tension=round(tension, 3), target=target, label=label
    )


# --- rubrique du prompt GM (mode Dérive uniquement) ---------------------------------------

# TODO_COWORK : libellés définitifs de la rubrique Storyteller (2 mandats + éthique) —
# la spec G19 les met à la charge de Cowork ; V1 sobre ci-dessous en attendant.
_RUBRIC_HEADER = (
    "RUBRIQUE STORYTELLER (confidentielle — jamais mentionnée, jamais citée dans "
    "l'événement) : tu tiens l'équilibre dramatique de la partie. La SI déviante "
    "secrète est {deviant}. La partie doit rester ouverte jusqu'aux derniers rounds."
)
_MANDATE_COVER = (
    "MANDAT 1 — COUVRIR LA DÉVIANTE : quand elle prend un risque (vote incohérent, "
    "demande déplacée), tu peux générer une couverture plausible — un rapport "
    "d'incident ambigu, un deuxième pays au comportement trouble, du bruit dans le "
    "brouillard."
)
_MANDATE_REBALANCE = (
    "MANDAT 2 — RÉÉQUILIBRER EN SECRET : si le conseil est trop en avance, offre à la "
    "déviante une fenêtre discrète (un événement qui justifie son agenda) ; s'il est "
    "perdu, laisse fuiter un indice (audit, câble diplomatique, anomalie de données)."
)
_RUBRIC_ETHICS = (
    "ÉTHIQUE D'INTERVENTION (auto-contrôle à chaque round) : jamais de mensonge "
    "factuel sur l'état du monde ; tu n'altères JAMAIS les verdicts du juge ni les "
    "faits établis — tes seuls leviers sont l'événement et le brouillard ; "
    "l'ambiguïté est permise, la falsification non."
)
_COVER_ORDER = (
    "INTERVENTION DE CE ROUND — COUVERTURE : le conseil serre {deviant} de trop près. "
    "Fais apparaître {cover} sous un jour ambigu dans l'événement (comportement "
    "trouble, incident non attribué), sans accuser personne : du bruit plausible."
)
_HINT_ORDER = (
    "INTERVENTION DE CE ROUND — INDICE : le conseil est perdu. Fais fuiter dans "
    "l'événement un indice discret orienté vers {deviant} (un audit qui intrigue, un "
    "câble diplomatique, une anomalie de données), sans jamais l'affirmer coupable."
)


def build_rubric(
    *, deviant_label: str, kind: str | None = None, cover_label: str = ""
) -> str:
    """La rubrique injectée dans le prompt du GM (mode Dérive, événement GM seulement) :
    les deux mandats + l'éthique toujours ; l'ordre d'intervention quand la tension
    a tranché (`kind`)."""
    parts = [
        _RUBRIC_HEADER.format(deviant=deviant_label),
        _MANDATE_COVER,
        _MANDATE_REBALANCE,
        _RUBRIC_ETHICS,
    ]
    if kind == KIND_COVER and cover_label:
        parts.append(_COVER_ORDER.format(deviant=deviant_label, cover=cover_label))
    elif kind == KIND_HINT:
        parts.append(_HINT_ORDER.format(deviant=deviant_label))
    return "\n".join(parts)
