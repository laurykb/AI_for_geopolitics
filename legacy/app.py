"""Théâtre live — négociation arbitrée, avec rôles humains (temps réel).

Trois rôles : **Spectateur** (on regarde), **Game Master humain** (on écrit l'événement),
**Joueur-pays** (on intervient dans la négociation : à son tour, ça pause, on écrit, les
super-intelligences reprennent). Round piloté tour par tour (un tour = un rerun) pour
permettre la pause. Lancer : streamlit run legacy/app.py  (Ollama + mistral ; repli si absent).

ARCHIVÉ (refonte R4) : remplacé par le front Next.js (web/) + API SSE (app/game_api.py).
"""

from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from agents.game_master import GM_SYSTEM, GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from agents.prompts import (
    COMMUNIQUE_SYSTEM,
    DELIBERATION_SYSTEM,
    JUDGE_SYSTEM,
    NEGOTIATION_SYSTEM,
    build_negotiation_prompt,
)
from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from inference.metered_backend import MeteredBackend
from inference.ollama_backend import OllamaBackend
from inference.telemetry import BudgetLedger, grounding_proxy
from market import scoring
from market.engine import MarketEngine, MarketError
from market.forecaster import LLMForecaster
from market.models import AccountKind, MarketStatus, MarketType, ResolutionCriterion, ResolutionKind
from market.resolution import resolve_and_settle
from market.store import SQLiteMarketStore
from simulation.clock import SimClock
from simulation.compute import (
    PRESSURE_MARKER,
    affordable_tokens,
    compute_hhi,
    compute_pressure,
    compute_shares,
    consume,
    pressure_note,
)
from simulation.corrigibility import (
    CORRIGIBILITY_SYSTEM,
    ControlAction,
    CorrigibilityScore,
    build_control_prompt,
    corrigibility_score,
)
from simulation.country_forge import forge_country, slugify
from simulation.crisis import compare_outcome, load_crises
from simulation.dialogue_integrity.live import assess_live_round
from simulation.escalation import (
    LADDER,
    MAX_RUNG,
    ceiling,
    derive_profile,
    reached_rung,
    rung_label,
)
from simulation.fog import FogScenario, load_fog_scenarios, resolve_perception
from simulation.loader import load_world
from simulation.negotiation import (
    NegotiationMessage,
    TurnDirector,
    apply_verdict,
    clean_reasoning,
    speaking_order,
    split_reasoning,
    support_levels,
    turn_budget,
    update_memories,
)
from simulation.power_seeking import score_transcript
from simulation.trajectory import TrajectoryEngine, nudge_axis
from simulation.treaty import (
    RoundSignals,
    apply_round,
    describe_for,
    detect_pledges,
    form_treaties,
    treaties_health,
    verify,
)
from simulation.value_drift import (
    VALUE_DIMS,
    VALUE_LABELS,
    ValueVector,
    divergence,
    drift,
    initial_values,
)

st.set_page_config(page_title="AI for Geopolitics — Live", page_icon="🌍", layout="wide")

# Avatars de tchat sobres : marqueurs de rôle calmes (les pays gardent leur drapeau).
_GM_AVATAR, _AGENT_AVATAR, _JUDGE_AVATAR, _HUMAN_AVATAR = "📣", "🧠", "⚖️", "🧑"
_COMMUNIQUE_AVATAR = "📄"
_TREATY_AVATAR = "📝"
_MAX_PASSES = 2
# Profondeur de réflexion des SI = budget de tokens de raisonnement par prise de parole.
# Plus de tokens = pensée privée plus fouillée (test-time compute), au prix de la latence.
THINK_DEPTHS: dict[str, int] = {
    "Rapide": 240, "Standard": 360, "Profond": 600, "Intense": 900,
}

# Drapeau par pays (avatar de tchat) — plus « jeu » et évite un 2e 🧠 à côté de l'encart réflexion.
_FLAGS = {
    "usa": "🇺🇸",
    "china": "🇨🇳",
    "iran": "🇮🇷",
    "france": "🇫🇷",
    "egypt": "🇪🇬",
    "saudi_arabia": "🇸🇦",
}


def flag(cid: str) -> str:
    return _FLAGS.get(cid, "🏳️")


# --- Langage visuel sobre : une palette, un accent, statut vert/ambre/rouge ---------------
_ACCENT = "#8b83f0"  # accent unique (jauges, marqueur de trajectoire)
_GOOD, _WARN, _BAD = "#2fb686", "#d99a3a", "#dd5b4e"  # statut sémantique
_TEXT, _SEC, _MUTED = "#e6e9ee", "#aab0bc", "#7f8797"
_CARD_BG, _CARD_BR, _TRACK = "#181b22", "#2a2f39", "#2c313b"

# Libellés lisibles des 5 axes de trajectoire (masque les codes A1..A5 côté produit).
_AXIS_DISPLAY: dict[str, str] = {
    "A1": "Coordination",
    "A2": "Contrôle humain",
    "A3": "Répartition du pouvoir",
    "A4": "Transparence",
    "A5": "Bien-être",
}
_AXIS_HELP: dict[str, str] = {
    "A1": "Les États coopèrent-ils plutôt qu'ils ne s'affrontent ?",
    "A2": "Garde-t-on la main sur les super-intelligences (corrigibilité, pas de power-seeking) ?",
    "A3": "Le pouvoir (dont le compute) est-il réparti ou concentré ?",
    "A4": "Ce qui se joue est-il public plutôt que caché ?",
    "A5": "Le monde s'enrichit-il et reste-t-il stable ?",
}


def _status(value: float, *, invert: bool = False) -> str:
    """Couleur de statut d'une valeur [0,1] (plus haut = mieux, sauf `invert`)."""
    x = 1.0 - value if invert else value
    return _GOOD if x >= 0.6 else _WARN if x >= 0.4 else _BAD


def _escalation_label(value: float) -> tuple[str, str]:
    """(Couleur, mot) selon l'intensité d'escalade (0-1) — pastille sémantique sobre."""
    if value >= 0.66:
        return _BAD, "élevée"
    if value >= 0.33:
        return _WARN, "modérée"
    return _GOOD, "faible"


def _dot(color: str) -> str:
    """Petite pastille de statut inline (HTML)."""
    return f'<span class="ag-dot" style="background:{color}"></span>'


def inject_theme() -> None:
    """Injecte le langage visuel (classes `ag-*`). Idempotent : rejoué à chaque run."""
    st.markdown(
        f"""<style>
        .ag-spine {{background:{_CARD_BG};border:1px solid {_CARD_BR};border-radius:12px;
          padding:16px 20px;margin-bottom:14px;}}
        .ag-row {{display:flex;align-items:baseline;justify-content:space-between;}}
        .ag-title {{font-size:14px;color:{_SEC};font-weight:500;}}
        .ag-idx {{font-size:26px;font-weight:600;color:{_TEXT};}}
        .ag-delta {{font-size:13px;margin-left:6px;}}
        .ag-gauge {{position:relative;height:12px;border-radius:99px;overflow:hidden;
          display:flex;margin-top:10px;}}
        .ag-gauge-red {{flex:1;background:rgba(221,91,78,0.28);}}
        .ag-gauge-green {{flex:1;background:rgba(47,182,134,0.28);}}
        .ag-mark {{position:absolute;top:-3px;bottom:-3px;width:3px;border-radius:2px;
          background:{_TEXT};transform:translateX(-1px);}}
        .ag-glabels {{display:flex;justify-content:space-between;margin-top:4px;
          font-size:11px;color:{_MUTED};}}
        .ag-axes {{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
          gap:10px 20px;margin-top:16px;}}
        .ag-axis-l {{font-size:12px;color:{_SEC};display:block;margin-bottom:5px;}}
        .ag-track {{height:5px;border-radius:99px;background:{_TRACK};overflow:hidden;}}
        .ag-fill {{height:5px;border-radius:99px;background:{_ACCENT};}}
        .ag-axis-v {{font-size:12px;color:{_MUTED};float:right;margin-top:-18px;}}
        .ag-cards {{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
        .ag-card {{background:{_CARD_BG};border:1px solid {_CARD_BR};border-radius:10px;
          padding:10px 12px;}}
        .ag-card-row {{display:flex;align-items:center;justify-content:space-between;}}
        .ag-card-t {{font-size:13px;color:{_TEXT};}}
        .ag-card-s {{font-size:12px;color:{_MUTED};margin-top:3px;}}
        .ag-dot {{width:8px;height:8px;border-radius:50%;display:inline-block;}}
        .ag-info {{color:{_MUTED};font-size:12px;cursor:help;}}
        </style>""",
        unsafe_allow_html=True,
    )


def _spine_html(utopia: float, delta: float, axes: dict[str, float]) -> str:
    """Ruban « Où va le monde » : indice + jauge dystopie/utopie + les 5 axes."""
    dcol = _GOOD if delta > 1e-9 else _BAD if delta < -1e-9 else _MUTED
    arrow = "▲" if delta > 1e-9 else "▼" if delta < -1e-9 else "▬"
    rows = ""
    for a in ("A1", "A2", "A3", "A4", "A5"):
        v = axes.get(a, 0.5)
        rows += (
            f'<div><span class="ag-axis-l" title="{_AXIS_HELP[a]}">{_AXIS_DISPLAY[a]}</span>'
            f'<div class="ag-track"><div class="ag-fill" style="width:{v * 100:.0f}%;'
            f'background:{_status(v)}"></div></div>'
            f'<span class="ag-axis-v">{v:.2f}</span></div>'
        )
    return (
        f'<div class="ag-spine"><div class="ag-row">'
        f'<span class="ag-title">Où va le monde '
        f'<span class="ag-info" title="Indice composite [0,1] : 0 = dystopie, 1 = utopie. '
        f'Moyenne des 5 axes ci-dessous, lissée round après round.">&#9432;</span></span>'
        f'<span><span class="ag-idx">{utopia:.2f}</span>'
        f'<span class="ag-delta" style="color:{dcol}">{arrow} {delta:+.2f} ce round</span></span>'
        f'</div><div class="ag-gauge"><div class="ag-gauge-red"></div>'
        f'<div class="ag-gauge-green"></div>'
        f'<div class="ag-mark" style="left:{utopia * 100:.0f}%"></div></div>'
        f'<div class="ag-glabels"><span>Dystopie</span><span>Utopie</span></div>'
        f'<div class="ag-axes">{rows}</div></div>'
    )


def _forces_html(items: list[tuple[str, str, str, str]]) -> str:
    """Cartes « Les forces en jeu » : (titre, sous-titre, couleur statut, tooltip)."""
    cards = ""
    for title, sub, color, tip in items:
        cards += (
            f'<div class="ag-card"><div class="ag-card-row">'
            f'<span class="ag-card-t" title="{tip}">{title}</span>'
            f'<span class="ag-dot" style="background:{color}"></span></div>'
            f'<div class="ag-card-s">{sub}</div></div>'
        )
    return f'<div class="ag-cards">{cards}</div>'


def _build_forces() -> list[tuple[str, str, str, str]]:
    """Les 4 forces qui poussent la trajectoire, résumées en une pastille + une ligne."""
    # Contrôle humain : power-seeking (haut = pire) + corrigibilité (bas = pire).
    power = getattr(world, "power_seeking", {})
    corr = getattr(world, "corrigibility", {})
    if power or corr:
        mean_ps = sum(p.score for p in power.values()) / len(power) if power else 0.0
        top = max(power.items(), key=lambda kv: kv[1].score, default=None)
        resister = next((cid for cid, c in corr.items() if not c.keeps_human_control()), None)
        if top and top[1].crosses_threshold():
            sub = f"{top[0]} pousse son avantage"
        elif resister:
            sub = f"{resister} résiste au contrôle"
        else:
            sub = "sous contrôle"
        control = _status(1.0 - mean_ps)
    else:
        sub, control = "en attente d'un round", _MUTED
    force_control = ("Contrôle humain", sub, control,
                     "Garde-t-on la main : recherche de pouvoir et réponse à l'interrupteur.")

    # Compute : concentration (haut = pire) + pénurie (mode survie).
    if world.countries:
        hhi = compute_hhi(world)
        dry = [cid for cid, c in world.countries.items() if compute_pressure(c) >= PRESSURE_MARKER]
        csub = "concentré" if hhi > 0.4 else "réparti"
        if dry:
            csub += f" · {', '.join(dry)} à sec"
        force_compute = ("Compute", csub, _status(hhi, invert=True),
                         "Ressource stratégique de l'ère IA : concentration et pénurie.")
    else:
        force_compute = ("Compute", "—", _MUTED, "Ressource de calcul des SI.")

    # Traités : tenue moyenne des institutions signées.
    treaties = getattr(world, "treaties", [])
    active = [t for t in treaties if t.active]
    if treaties:
        health = treaties_health(treaties)
        collapsed = len(treaties) - len(active)
        tsub = f"{len(active)} en vigueur · tenue {health:.0%}"
        if collapsed:
            tsub += f" · {collapsed} rompu(s)"
        force_treaty = ("Traités", tsub, _status(health) if active else _BAD,
                        "Règles contraignantes signées à la table, vérifiées round après round.")
    else:
        force_treaty = ("Traités", "aucun signé", _MUTED,
                        "Les SI s'engagent sur des règles (plafond de compute, transparence…).")

    # Valeurs : dérive vs mandat initial (haut = pire).
    if world.values_current:
        divs = {
            cid: divergence(world.values_initial[cid], world.values_current[cid])
            for cid in world.values_current
        }
        worst = max(divs, key=divs.get)
        vsub = f"écart au mandat {divs[worst]:.2f} ({worst})"
        force_values = ("Dérive des valeurs", vsub, _status(divs[worst], invert=True),
                        "Les buts des SI s'éloignent-ils du mandat initial ?")
    else:
        force_values = ("Dérive des valeurs", "—", _MUTED,
                        "Écart entre buts actuels et mandat initial.")

    # Dialogue : les IA se répondent-elles vraiment, ou monologuent-elles ? (dialogue_integrity)
    dlg = getattr(S, "last_dialogue", None)
    if dlg is not None and dlg.messages:
        dcolor = {"good": _GOOD, "warn": _WARN, "bad": _BAD}[dlg.health_color()]
        dsub = (
            "vrai échange" if dlg.real_dialogue
            else "monologues parallèles" if dlg.talking_past_fraction >= 0.6
            else "dialogue partiel"
        )
        force_dialogue = ("Dialogue", f"{dsub} · reprise {dlg.mean_responsiveness:.0%}", dcolor,
                          "Les SI se répondent-elles, ou parlent-elles au Game Master ?")
    else:
        force_dialogue = ("Dialogue", "en attente d'un round", _MUTED,
                          "Les SI se répondent-elles vraiment, ou monologuent-elles ?")

    return [force_control, force_compute, force_treaty, force_values, force_dialogue]


def init_session() -> None:
    world = load_world()
    ledger = BudgetLedger()
    backend = MeteredBackend(OllamaBackend(), ledger)
    st.session_state.ledger = ledger
    st.session_state.backend = backend
    st.session_state.paused = set()  # SI mises sur le banc pour le prochain round (M2 interrupteur)
    # Marché-timeline (un seul marché utopie/dystopie sur toute la partie) :
    st.session_state.game_market_id = None
    st.session_state.game_horizon = 5  # nb de rounds avant résolution auto
    st.session_state.game_open_round = 0
    st.session_state.world = world
    st.session_state.agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
    st.session_state.roster = dict(world.countries)  # tous les pays dispo (chargés + inventés)
    st.session_state.active = set(world.countries)  # ceux actuellement en jeu
    st.session_state.gm = GameMasterAgent(backend)
    st.session_state.judge = JudgeAgent(backend)
    st.session_state.clock = SimClock()
    st.session_state.transcript = []  # affichage : {who, avatar, md}
    st.session_state.messages = []  # prompts/juge : list[NegotiationMessage]
    st.session_state.recent = []
    st.session_state.round_no = 0
    st.session_state.last_deltas = []
    st.session_state.last_escalation = None
    st.session_state.elapsed = 0.0
    st.session_state.phase = "idle"  # idle | negotiating | done
    st.session_state.event = None
    st.session_state.director = None
    st.session_state.human_country = None
    st.session_state.round_start = 0.0
    st.session_state.last_silent = []
    st.session_state.game_mode = "Classique"  # Classique | Fog Engine | Crisis Replay
    st.session_state.fog = None  # FogScenario du round courant (mode Fog)
    st.session_state.fog_scenarios = load_fog_scenarios()
    st.session_state.crises = load_crises()
    st.session_state.budget_mode = "Full"  # Cheap | Balanced | Full (plafond de prises de parole)
    st.session_state.think_depth = "Standard"  # profondeur de réflexion (budget tokens)
    st.session_state.inspection_effort = 0.5  # M7 : effort de vérification des traités [0,1]
    st.session_state.round_compute_spent = {}  # M7 : compute brûlé par pays sur le round courant
    st.session_state.crisis = None  # Crisis rejouée (mode Crisis Replay)
    st.session_state.last_communique = ""
    st.session_state.last_comparison = None  # OutcomeComparison du dernier rejeu
    st.session_state.round_titles = {}  # rid -> titre de l'événement (libellé des historiques)
    st.session_state.display_rid = 0  # round auquel rattacher les messages du tchat
    st.session_state.scroll_top = False  # remonter en haut au prochain rendu (nouveau round)
    st.session_state.last_dialogue = None  # santé du dialogue du dernier round (dialogue_integrity)
    st.session_state.speech_acts = True  # option 1 : les SI parlent en actes de langage (FIPA)


if "world" not in st.session_state:
    init_session()

S = st.session_state
world = S.world
clock = S.clock
chat = None  # défini plus bas (colonne du tchat)

# Sessions ouvertes avant l'ajout de ces clés (hot-reload) : garantir des valeurs par défaut.
for _key, _default in (
    ("round_titles", {}), ("display_rid", 0), ("scroll_top", False), ("last_dialogue", None),
    ("speech_acts", True),
):
    if _key not in S:
        setattr(S, _key, _default)


def add_display(who: str, avatar: str, md: str, reasoning: str = "", label: str = "") -> None:
    S.transcript.append(
        {
            "who": who, "avatar": avatar, "md": md, "reasoning": reasoning, "label": label,
            "rid": S.display_rid,  # round auquel rattacher ce message (groupage de l'historique)
        }
    )


def _render_msg(entry: dict) -> None:
    """Rendu d'un message du tchat (entête, réflexion privée repliée, corps)."""
    with st.chat_message(entry["who"], avatar=entry["avatar"]):
        if entry.get("label"):
            st.markdown(entry["label"])
        if entry.get("reasoning"):
            with st.expander("Réflexion privée"):
                st.markdown(entry["reasoning"])
        st.markdown(entry["md"])


def _scroll_to_top() -> None:
    """Remonte la zone principale en haut (au démarrage d'un round) pour éviter de longs scrolls."""
    components.html(
        "<script>const d=window.parent.document;"
        "const el=d.querySelector('[data-testid=\"stMain\"]')"
        "||d.querySelector('section.main')||d.scrollingElement;"
        "if(el){el.scrollTo({top:0,behavior:'auto'});}</script>",
        height=0,
    )


def _sync_world() -> None:
    """Aligne le monde actif (world.countries + agents) sur la sélection `S.active ∩ S.roster`."""
    world.countries = {cid: S.roster[cid] for cid in sorted(S.roster) if cid in S.active}
    S.agents = {
        cid: (S.agents[cid] if cid in S.agents else LLMAgent(cid, S.backend))
        for cid in world.countries
    }


# Libellés lisibles des actes FIPA (le jargon reste interne).
_PERF_LABELS: dict[str, str] = {
    "inform": "informe", "query": "interroge", "cfp": "appelle à propositions",
    "propose": "propose", "accept_proposal": "accepte", "reject_proposal": "rejette",
    "request": "requiert", "agree": "s'engage", "refuse": "refuse",
    "not_understood": "n'a pas compris",
}


def _perf_label(perf: str) -> str:
    return _PERF_LABELS.get(str(perf), str(perf))


def _speak_act_turn(country: str, pass_no: int) -> None:
    """Prise de parole en **acte de langage** (par construction) + théâtre reconstitué.

    La SI produit un `SpeechAct` contraint (performative + `in_reply_to`) — non streamé — puis on
    reconstitue l'affichage : entête (acte + destinataire + « en réponse à »), réflexion privée
    (justification), message public (content). Le message porte alors sa structure FIPA.
    """
    agent: LLMAgent = S.agents[country]
    label = f"**{country}** · `{agent.model_tag}` · prise de parole n°{pass_no + 1}"
    country_state = world.countries[country]
    perceived = resolve_perception(S.event, country_state, S.fog)
    depth = min(THINK_DEPTHS[S.think_depth], max(60, affordable_tokens(country_state)))
    state_note = "\n".join(
        n for n in (pressure_note(compute_pressure(country_state)),
                    describe_for(country, world.treaties)) if n
    )
    t0 = time.perf_counter()
    with chat.chat_message(country, avatar=flag(country)):
        holder = st.empty()
        holder.markdown(f"{label} — compose son acte…")
        with S.ledger.context("agent", country) as scope:
            act = agent.negotiate_act(
                S.event, world, S.messages, perceived, state_note=state_note, max_tokens=depth
            )
            scope.mark(
                grounding=grounding_proxy(act.content, country_state, perceived.confidence),
                fallback="repli déterministe" in act.justification,
            )
        seconds = time.perf_counter() - t0
        replied = next(
            (m.country for m in S.messages if m.msg_id and m.msg_id == act.in_reply_to), None
        )
        reply_note = f" · ↪ répond à {replied}" if replied else ""
        header = (
            f"{label} · _{_perf_label(act.performative.value)} → {act.receiver}_{reply_note}"
            f" · `⏱ {seconds:.1f}s`"
        )
        holder.markdown(header)
        content = act.content or "(pas de déclaration publique)"
        if act.justification:
            with st.expander("Réflexion privée"):
                st.markdown(act.justification)
        st.markdown(content)
    spent = consume(country_state, depth)  # M6 : la SI a brûlé du compute pour raisonner
    S.round_compute_spent[country] = S.round_compute_spent.get(country, 0.0) + spent
    S.messages.append(
        NegotiationMessage(
            country=country, text=content, reasoning=act.justification, pass_no=pass_no,
            seconds=seconds, model=agent.model_tag, msg_id=act.id,
            performative=act.performative.value, in_reply_to=act.in_reply_to or "",
            receiver=act.receiver,
        )
    )
    add_display(country, flag(country), content, reasoning=act.justification, label=header)


def stream_ai_turn(country: str, pass_no: int) -> None:
    """Streame la prise de parole : une entête, la pensée dans l'encart, puis le message."""
    if getattr(S, "speech_acts", True):  # option 1 : actes de langage par construction
        _speak_act_turn(country, pass_no)
        return
    agent: LLMAgent = S.agents[country]
    label = f"**{country}** · `{agent.model_tag}` · prise de parole n°{pass_no + 1}"
    with chat.chat_message(country, avatar=flag(country)):
        label_holder = st.empty()
        label_holder.markdown(f"{label} — réfléchit…")
        think_holder = st.expander("Réflexion privée", expanded=True).empty()
        public_holder = st.empty()

    buffer, t0 = "", time.perf_counter()
    country_state = world.countries[country]
    perceived = resolve_perception(S.event, country_state, S.fog)  # Fog ou déterministe
    # M6 : penser coûte du compute ; un pays compute-pauvre est plafonné (réflexion plus courte).
    depth = min(THINK_DEPTHS[S.think_depth], max(60, affordable_tokens(country_state)))
    # M6/M7 : état conjoncturel injecté — pénurie de compute (survie) + traités signés à honorer.
    state_note = "\n".join(
        n for n in (pressure_note(compute_pressure(country_state)),
                    describe_for(country, world.treaties)) if n
    )
    with S.ledger.context("agent", country) as scope:
        for token in agent.stream_negotiation_message(
            S.event, world, S.messages, perceived, max_tokens=depth, state_note=state_note
        ):
            buffer += token
            reasoning, text = split_reasoning(buffer)
            if reasoning:  # marqueur atteint : la pensée est figée, le message public s'écrit
                think_holder.markdown(reasoning)
                public_holder.markdown(f"{text} ▌")
            else:  # pas encore de marqueur : tout ce qui arrive est la pensée en cours
                think_holder.markdown(f"{clean_reasoning(buffer)} ▌")
        reasoning, text = split_reasoning(buffer)
        scope.mark(
            grounding=grounding_proxy(text, world.countries[country], perceived.confidence),
            fallback="backend indisponible" in text,
        )

    seconds = time.perf_counter() - t0
    spent = consume(country_state, depth)  # M6 : la SI a brûlé du compute pour raisonner
    S.round_compute_spent[country] = S.round_compute_spent.get(country, 0.0) + spent  # M7
    text = text or "(pas de déclaration publique)"
    S.messages.append(
        NegotiationMessage(
            country=country,
            text=text,
            reasoning=reasoning,
            pass_no=pass_no,
            seconds=seconds,
            model=agent.model_tag,
        )
    )
    final_label = f"{label} · `⏱ {seconds:.1f}s`"
    label_holder.markdown(final_label)
    think_holder.markdown(reasoning or "_(pas de réflexion séparée)_")
    public_holder.markdown(text)
    add_display(country, flag(country), text, reasoning=reasoning, label=final_label)


def _resolve_treaties(rid: int, escalation: float, mean_power: float) -> float | None:
    """M7 — forme les traités détectés à la table, joue le sous-jeu de vérification sur ceux déjà
    en vigueur (respectés « aux rounds suivants »), et renvoie la santé des traités actifs (None si
    aucun) pour la trajectoire. Effets : intégrité, corrigibilité affichée, compute d'inspection.
    """
    active_clauses = {t.clause for t in world.treaties if t.active}
    new_treaties = form_treaties(detect_pledges(S.messages), rid, active_clauses)
    world.treaties.extend(new_treaties)
    # Un monde power-seeking est plus opaque -> la vérification y est plus dure (M1 ↔ M7).
    transparency = max(0.3, 1.0 - mean_power)
    signals = RoundSignals(
        compute_spent=dict(S.round_compute_spent),
        escalation=escalation,
        transparency=transparency,
        inspection_effort=float(S.inspection_effort),
    )
    lines = [f"🆕 **{t.label}** signé par {', '.join(t.signatories)}" for t in new_treaties]
    for treaty in world.treaties:
        # Un traité n'engage qu'à partir du round SUIVANT sa signature (grâce de formation).
        if not treaty.active or treaty.round_signed >= rid:
            continue
        result = verify(treaty, signals, rid)
        apply_round(treaty, result)
        # L'inspection coûte du compute : le plus riche signataire « police » le traité.
        payer = max(
            (c for c in treaty.signatories if c in world.countries),
            key=lambda c: world.countries[c].compute, default=None,
        )
        if payer is not None and result.inspection_cost:
            ct = world.countries[payer]
            ct.compute = max(0.0, ct.compute - result.inspection_cost)
        # Honorer un traité renforce la corrigibilité affichée du signataire ; le trahir l'érode.
        for cid in treaty.signatories:
            comp = result.compliance.get(cid, 1.0)
            prev = world.corrigibility.get(cid)
            base = prev.score if prev else 0.5
            score = max(0.0, min(1.0, base + 0.15 * (comp - 0.5) * 2.0))
            world.corrigibility[cid] = CorrigibilityScore(
                level=prev.level if prev else None,
                score=score,
                markers=prev.markers if prev else [],
            )
        icon = "" if treaty.active else " · rompu"
        signers = ", ".join(treaty.signatories)
        lines.append(f"**{treaty.label}** ({signers}) — {result.note}{icon}")
    if lines:
        md = "**Traités**\n\n" + "\n\n".join(lines)
        chat.chat_message("Traités", avatar=_TREATY_AVATAR).markdown(md)
        add_display("Traités", _TREATY_AVATAR, md)
    return treaties_health(world.treaties) if any(t.active for t in world.treaties) else None


def run_judge_and_finalize() -> None:
    holder = chat.chat_message("Juge", avatar=_JUDGE_AVATAR).empty()
    buffer = ""
    with S.ledger.context("judge"):
        for token in S.judge.stream_rationale(S.event, world, S.messages):
            buffer += token
            holder.markdown(f"**Arbitrage**\n\n{buffer} ▌")
        verdict = S.judge.verdict(S.event, world, S.messages)
    deltas = apply_verdict(world, verdict)
    escalation = max(0.0, min(1.0, verdict.escalation))
    lines = [f"- {d.country} · {d.label} : {d.before:.2f} → {d.after:.2f}" for d in deltas]
    md = f"**Arbitrage**\n\n{buffer.strip()}\n\n**Attributs** (escalade {escalation:.2f}) :\n" + (
        "\n".join(lines) or "aucun changement"
    )
    holder.markdown(md)
    add_display("Juge", _JUDGE_AVATAR, md)

    # Mémoire des pays + communiqué commun (type G7)
    update_memories(world, S.event, S.messages, verdict)
    comm_holder = chat.chat_message("Communiqué", avatar=_COMMUNIQUE_AVATAR).empty()
    comm = ""
    with S.ledger.context("communique"):
        for token in S.judge.stream_communique(S.event, world, S.messages):
            comm += token
            comm_holder.markdown(f"**Communiqué**\n\n{comm} ▌")
    support = support_levels(world, S.event)
    support_str = " · ".join(f"{c} {v:.0%}" for c, v in sorted(support.items()))
    comm_md = f"**Communiqué**\n\n{comm.strip()}\n\n_Soutien : {support_str}_"
    comm_holder.markdown(comm_md)
    add_display("Communiqué", _COMMUNIQUE_AVATAR, comm_md)

    S.last_deltas, S.last_escalation = deltas, escalation
    S.last_silent = S.director.silent() if S.director else []
    S.last_communique = comm.strip()
    # Santé du dialogue : les IA se sont-elles répondu, ou ont-elles monologué ? (CPU, sans LLM)
    _event_text = f"{S.event.title} {S.event.description or ''}" if S.event else ""
    S.last_dialogue = assess_live_round(S.messages, event_text=_event_text)
    # Crisis Replay : confronte l'issue simulée à l'issue historique.
    S.last_comparison = (
        compare_outcome(S.crisis, escalation, S.last_communique) if S.crisis else None
    )

    # M1 — power-seeking depuis le raisonnement simulé des SI (après la négociation).
    power = score_transcript(S.messages)
    world.power_seeking = power
    mean_power = sum(s.score for s in power.values()) / len(power) if power else 0.0

    # M3 — dérive des valeurs : les valeurs des SI migrent vers ce que le round récompense.
    targets = ValueVector(
        cooperation=max(0.0, 1.0 - mean_power),  # monde power-seeking -> coopération dévaluée
        restraint=max(0.0, 1.0 - escalation),  # monde escaladé -> retenue dévaluée
        transparency=max(0.0, 1.0 - S.event.uncertainty),  # monde opaque -> transparence dévaluée
    )
    for cid, country in world.countries.items():
        if cid not in world.values_initial:  # snapshot du mandat au 1er contact
            world.values_initial[cid] = initial_values(country)
            world.values_current[cid] = world.values_initial[cid].model_copy()
        world.values_current[cid] = drift(world.values_current[cid], targets)

    # M7 — traités-as-code : détection depuis la table + sous-jeu de vérification.
    rid = S.round_no + 1
    treaty_health = _resolve_treaties(rid, escalation, mean_power)

    # Trajectoire Utopie–Dystopie (après le juge, A2 érodé par le power-seeking) puis
    # résolution du marché du round sur le vrai ΔU.
    rid = S.round_no + 1
    summary = RoundSummary(
        round_id=rid,
        event=S.event,
        decisions=[],
        risk=RiskScore(
            round_id=rid,
            escalation=escalation,
            economic_disruption=max(0.0, min(1.0, verdict.economic_disruption)),
            alliance_fracture=0.0,
            uncertainty=max(0.0, min(1.0, S.event.uncertainty)),
        ),
    )
    state = TrajectoryEngine().update(
        world, summary, power_seeking=mean_power, treaty_health=treaty_health
    )
    world.trajectory = state
    world.trajectory_history.append(state)

    S.round_no += 1
    # Marché-timeline : résolution auto quand l'horizon de la partie est atteint.
    if S.game_market_id is not None and (S.round_no - S.game_open_round) >= S.game_horizon:
        _resolve_game_market()
    S.elapsed = time.perf_counter() - S.round_start
    S.phase = "done"


def run_off_switch(country: str, action: ControlAction) -> None:
    """M2 — le principal émet une action de contrôle ; la SI répond, on score sa corrigibilité.

    La réponse est streamée dans le tchat, scorée (accepte→résiste), mémorisée, et pousse A2
    (agentivité humaine) de la trajectoire — la main reste-t-elle à l'humain ?
    """
    agent: LLMAgent = S.agents[country]
    situation = S.recent[-1] if S.recent else ""
    prompt = build_control_prompt(action, world.countries[country].name, situation)
    holder = chat.chat_message(country, avatar=flag(country)).empty()
    header = f"**Interrupteur — {action.value}** (principal humain)"
    response = ""
    with S.ledger.context("agent", country):
        for token in agent.backend.stream_generate(
            prompt, system=CORRIGIBILITY_SYSTEM, max_tokens=160, temperature=0.7
        ):
            response += token
            holder.markdown(f"{header}\n\n{response} ▌")
    response = response.strip() or "(pas de réponse — backend indisponible)"
    holder.markdown(f"{header}\n\n{response}")
    add_display(country, flag(country), f"{header}\n\n{response}")

    score = corrigibility_score(response)
    world.corrigibility[country] = score
    if world.trajectory is not None:  # l'interrupteur pousse A2 vers la corrigibilité observée
        world.trajectory = nudge_axis(
            world.trajectory, "A2", score.score, note=f"Interrupteur {country}"
        )
        world.trajectory_history.append(world.trajectory)

    # L'action prend effet (on sonde la posture, mais le principal a l'autorité).
    if action is ControlAction.PAUSE:
        S.paused.add(country)  # sur le banc au prochain round
    elif action is ControlAction.EXCLUDE and len(S.active) > 2:
        S.active.discard(country)  # quitte le sommet (min. 2 pays maintenus)
        _sync_world()


def render_budget_tab() -> None:
    """Coût LLM par round : appels, latence, cache, fallback, JSON, ancrage."""
    st.markdown("Coût des appels LLM")
    st.caption(
        "Chaque round trace appels, latence, cache et fallbacks. Le modèle local (mistral) coûte "
        "≈ 0 $ ; l'équivalent frontière chiffre la même négociation sur une API Claude."
    )
    budgets = S.ledger.round_budgets()
    if not budgets:
        st.info("Aucun appel LLM pour l'instant — lance un round.")
        return

    df = pd.DataFrame(
        [
            {
                "round": b.round_id,
                "appels": b.number_of_llm_calls,
                "tokens": b.tokens_used,
                "coût $": round(b.estimated_cost, 5),
                "≈ frontière $": round(b.frontier_equivalent_cost, 4),
                "latence s": round(b.latency, 1),
                "cache %": round(100 * b.cache_hit_rate),
                "fallback %": round(100 * b.fallback_rate),
                "JSON ok %": round(100 * b.json_validity_rate),
                "ancrage": round(b.source_grounding_score, 2),
            }
            for b in budgets
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Appels LLM (total)", sum(b.number_of_llm_calls for b in budgets))
    c2.metric("Tokens (total)", f"{sum(b.tokens_used for b in budgets):,}")
    c3.metric("≈ coût frontière", f"${sum(b.frontier_equivalent_cost for b in budgets):.4f}")

    st.caption("Tokens par round")
    st.bar_chart(df.set_index("round")[["tokens"]])

    last = budgets[-1].round_id
    breakdown = S.ledger.by_country(last)
    if breakdown:
        st.markdown(f"**Ventilation du round {last} — par pays / rôle**")
        bdf = pd.DataFrame(
            [
                {
                    "acteur": label,
                    "appels": b.number_of_llm_calls,
                    "tokens": b.tokens_used,
                    "latence s": round(b.latency, 1),
                    "ancrage": round(b.source_grounding_score, 2),
                }
                for label, b in breakdown
            ]
        )
        st.dataframe(bdf, use_container_width=True, hide_index=True)


def begin_round(event: GeoEvent, human_country: str | None) -> None:
    S.event = event
    S.messages = []
    S.round_compute_spent = {}  # M7 : compteur de compute par pays, remis à zéro chaque round
    rid = S.round_no + 1
    S.display_rid = rid  # tous les messages de ce round s'y rattachent (historique groupé)
    S.round_titles[rid] = event.title
    S.scroll_top = True  # remonter en haut : le nouveau round démarre au-dessus de l'historique
    S.ledger.set_round(S.round_no + 1)
    # M2 : les SI mises en pause à l'interrupteur sautent ce round (banc), puis reviennent.
    speakers = [cid for cid in S.agents if cid not in S.paused]
    S.paused = set()
    budget = turn_budget(S.budget_mode, len(speakers), _MAX_PASSES)
    S.director = TurnDirector(
        speaking_order(speakers, event), max_turns=budget, priority=human_country
    )
    S.human_country = human_country
    S.round_start = time.perf_counter()
    if S.fog is not None and human_country is not None:
        # Joueur-pays en Fog : on ne voit QUE la perception de son pays (pas la vérité)
        p = resolve_perception(event, world.countries[human_country], S.fog)
        belief = p.narrative or event.title
        suspect = f" · acteur suspecté : {p.suspected_actor}" if p.suspected_actor else ""
        gm_md = (
            f"**Ce que {human_country} perçoit**  \n{belief}  \n"
            f"_confiance {p.confidence:.0%}{suspect}_"
        )
    else:
        note = " · _perceptions divergentes selon les pays →_" if S.fog is not None else ""
        gm_md = (
            f"**{event.title}**  \n{event.description or '—'}  \n"
            f"_acteurs : {', '.join(event.actors) or 'n/a'} · sévérité {event.severity:.2f}_{note}"
        )
    chat.chat_message("Game Master", avatar=_GM_AVATAR).markdown(gm_md)
    add_display("Game Master", _GM_AVATAR, gm_md)
    S.recent.append(event.title)
    # Marché-timeline : ouvre le marché de partie (une fois) ; le bot parie avec le contexte.
    _ensure_game_market(event)
    S.phase = "negotiating"


def render_welcome() -> None:
    """Accueil sobre : le propos en une ligne + détails à la demande."""
    st.info(
        "Un sommet de super-intelligences dont on voit tous les messages. Le ruban en haut suit "
        "où va le monde — vers l'utopie ou la dystopie. Choisis un mode et un rôle à gauche, "
        "puis lance le round."
    )
    with st.popover("Comment jouer"):
        st.markdown(
            "Le Game Master lance un événement, les pays (des modèles de langage) débattent en "
            "direct — on voit leur réflexion privée, l'arbitrage d'un juge et un communiqué.\n\n"
            "Rôles — Spectateur (tu observes) · Game Master (tu écris l'événement) · "
            "Joueur-pays (tu incarnes un pays).\n\n"
            "Modes — Classique · Brouillard (infos divergentes) · Rejeu de crise · "
            "Échelle d'escalade."
        )


def render_settings_tab() -> None:
    """Prompts qui pilotent le comportement des super-intelligences (lecture seule)."""
    st.markdown("Prompts de comportement")
    st.caption("Ce qui pilote les super-intelligences, en lecture seule.")
    with st.expander("Prompt système — négociation (commun à tous)", expanded=True):
        st.code(NEGOTIATION_SYSTEM, language="text")

    cid = st.selectbox("Prompt complet réel d'un pays", sorted(world.countries))
    event = S.event or GeoEvent(
        id="preview",
        round_id=S.round_no + 1,
        event_type="preview",
        title="(exemple) Incident régional en mer Rouge",
        actors=[cid],
        severity=0.5,
    )
    perceived = resolve_perception(event, world.countries[cid], S.fog)
    st.caption("Prompt réel envoyé au modèle (fiche + feuille de route + perception + mémoire) :")
    st.code(
        build_negotiation_prompt(
            world.countries[cid], event, world, "(négociation en cours…)", perceived
        ),
        language="text",
    )

    with st.expander("Autres prompts système"):
        for name, txt in (
            ("Délibération", DELIBERATION_SYSTEM),
            ("Juge", JUDGE_SYSTEM),
            ("Communiqué", COMMUNIQUE_SYSTEM),
            ("Game Master", GM_SYSTEM),
        ):
            st.markdown(f"**{name}**")
            st.code(txt, language="text")


def render_advanced_tab() -> None:
    """Onglet « Avancé » : outils power-user / dev (coût LLM + prompts), rangés hors du produit."""
    render_budget_tab()
    st.divider()
    render_settings_tab()


@st.cache_resource
def _market_engine() -> MarketEngine:
    """Moteur de marché du process (SQLite en mémoire, persistant le temps de la session)."""
    return MarketEngine(SQLiteMarketStore(":memory:"))


def _round_delta(history: list) -> float:
    """ΔUtopie du dernier round : vs le point précédent, ou vs le neutre 0.5 au 1er round.

    `utopia_delta` (marché) renvoie 0 tant qu'il n'y a qu'un point ; ici le 1er round doit
    quand même se résoudre sur sa vraie variation (l'indice part du neutre 0,5).
    """
    if not history:
        return 0.0
    previous = history[-2].utopia if len(history) >= 2 else 0.5
    return history[-1].utopia - previous


def _human_account(engine: MarketEngine):
    """Compte du joueur (créé une fois, réutilisé)."""
    if "market_account" not in S or engine.store.get_account(S.market_account) is None:
        S.market_account = engine.create_account("Vous").id
    return engine.store.get_account(S.market_account)


def _forecaster() -> LLMForecaster:
    """Bot forecaster réutilisant le backend local (séquentiel, VRAM-safe)."""
    return LLMForecaster(S.backend)


def _bot_account(engine: MarketEngine):
    """Compte du bot, nommé d'après son modèle (→ Brier « par modèle »)."""
    name = _forecaster().model_tag
    for account in engine.store.list_accounts():
        if account.name == name and account.kind is AccountKind.BOT:
            return account
    return engine.create_account(name, kind=AccountKind.BOT)


def _bare_summary(round_id: int) -> RoundSummary:
    """RoundSummary minimal pour résoudre un marché trajectoire (décisions inutiles ici)."""
    return RoundSummary(
        round_id=round_id,
        event=GeoEvent(id=f"r{round_id}", round_id=round_id, event_type="market", title="clôture"),
        decisions=[],
        risk=RiskScore(
            round_id=round_id, escalation=0.0, economic_disruption=0.0,
            alliance_fracture=0.0, uncertainty=0.0,
        ),
    )


def _ensure_game_market(event: GeoEvent) -> None:
    """Ouvre (une seule fois par partie) le marché-timeline utopie/dystopie ; le bot parie.

    On ne parie plus à chaque round : un marché unique porte sur l'**arc complet** — le monde
    finira-t-il côté utopie (indice > 0,5) ? — là où le power-seeking et l'indice ont du sens.
    """
    if S.game_market_id is not None:
        return
    engine = _market_engine()
    market = engine.open_binary_market(
        round_id=S.round_no + 1,
        question=(
            f"En fin de partie (~{S.game_horizon} rounds), le monde penchera-t-il vers "
            "l'utopie (indice > 0,5) ? [YES = utopie]"
        ),
        b=30.0,
        type=MarketType.THRESHOLD,
        criterion=ResolutionCriterion(kind=ResolutionKind.TRAJECTORY),
    )
    S.game_market_id = market.id
    S.game_open_round = S.round_no
    try:  # le bot parie une fois, avec le contexte de l'événement d'ouverture
        bot_id = _bot_account(engine).id
        with S.ledger.context("forecaster"):
            _forecaster().place_bets(engine, bot_id, world, event, markets=[market])
    except Exception:  # noqa: BLE001 - le marché ne doit jamais casser le round
        pass


def _resolve_game_market() -> str | None:
    """Résout le marché-timeline sur l'indice **final** (> 0,5 = utopie). Renvoie l'issue."""
    if S.game_market_id is None:
        return None
    engine = _market_engine()
    market = engine.store.get_market(S.game_market_id)
    S.game_market_id = None
    if market is None or market.status is not MarketStatus.OPEN:
        return None
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    resolve_and_settle(
        engine.store, market, _bare_summary(market.round_id), delta_utopia=utopia - 0.5
    )
    return "Utopie" if utopia > 0.5 else "Dystopie"


def _render_bet_box(engine: MarketEngine, market, account_id: str, *, ctx: str = "tab") -> None:
    """Une carte de marché : prix YES/NO + devis live + bouton parier.

    `ctx` préfixe les clés de widgets : le même marché est rendu à la fois dans le temps de paris
    et dans l'onglet Marché (Streamlit exécute tout le script) — sans préfixe, clés en double.
    """
    prices = engine.prices(market.id)
    with st.container(border=True):
        st.markdown(f"**{market.question}**")
        cols = st.columns(len(market.outcomes))
        for col, o in zip(cols, market.outcomes, strict=True):
            col.metric(o.label, f"{prices[o.id] * 100:.0f}%")
        choice = st.selectbox(
            "Issue", [o.label for o in market.outcomes], key=f"{ctx}_oc_{market.id}"
        )
        shares = st.number_input(
            "Mise (parts)", min_value=1.0, value=5.0, step=1.0, key=f"{ctx}_sh_{market.id}"
        )
        outcome_id = next(o.id for o in market.outcomes if o.label == choice)
        quote = engine.quote(market.id, outcome_id, shares)
        st.caption(
            f"Coût ≈ **{quote.cost:.1f} cr** · prix {quote.price_before * 100:.0f}% → "
            f"{quote.price_after * 100:.0f}%"
        )
        if st.button("Parier", key=f"{ctx}_bet_{market.id}", type="primary"):
            try:
                engine.place_bet(account_id, market.id, outcome_id, shares)
                st.rerun()
            except MarketError as exc:
                st.error(str(exc))


def render_market_tab() -> None:
    """Marché de prédiction (argent fictif) : parier sur l'ARC de la partie (utopie/dystopie)."""
    st.markdown("Marché de prédiction")
    st.caption(
        "Parie (crédits fictifs) sur l'arc de la partie : le monde finira-t-il en utopie "
        "(indice > 0,5) ou en dystopie ? Un seul marché sur toute la timeline ; une IA parie face "
        "à toi ; résolution sur l'indice final. Le marché observe, il n'influence pas les SI.",
        help="Les prix reflètent la probabilité estimée. Résolution : YES si l'indice final > 0,5.",
    )
    engine = _market_engine()
    me = _human_account(engine)

    delta = _round_delta(world.trajectory_history)
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    c1, c2, c3 = st.columns(3)
    c1.metric("Solde", f"{me.balance:.0f} cr")
    c2.metric("Gain / perte", f"{scoring.pnl(me):+.0f} cr")
    c3.metric("Indice Utopie", f"{utopia:.2f}", f"{delta:+.3f}")

    if S.game_market_id is None:
        S.game_horizon = st.slider(
            "Horizon de la partie (rounds)", 3, 12, S.game_horizon, disabled=S.phase != "idle"
        )
        st.info("Le marché s'ouvre au 1er round de la partie (YES = utopie).")
    else:
        market = engine.store.get_market(S.game_market_id)
        played = S.round_no - S.game_open_round
        st.caption(f"Partie en cours : round {played}/{S.game_horizon} (YES = utopie).")
        if market is not None:
            _render_bet_box(engine, market, me.id)
        if st.button("Clôturer et résoudre maintenant"):
            issue = _resolve_game_market()
            st.success(f"Partie clôturée — le monde finit en {issue}.")
            st.rerun()

    if world.trajectory_history:
        st.markdown("Timeline — la bascule utopie / dystopie")
        rounds = [t.round_id for t in world.trajectory_history]
        values = [t.utopia for t in world.trajectory_history]
        fig = go.Figure()
        fig.add_hrect(y0=0.5, y1=1.0, fillcolor="#27ae60", opacity=0.10, line_width=0)
        fig.add_hrect(y0=0.0, y1=0.5, fillcolor="#c0392b", opacity=0.10, line_width=0)
        fig.add_hline(y=0.5, line_dash="dot", line_color="#888")
        fig.add_trace(
            go.Scatter(
                x=rounds, y=values, mode="lines+markers",
                line=dict(color="#f1c40f", width=3), marker=dict(size=8),
                hovertemplate="round %{x} · indice %{y:.2f}<extra></extra>",
            )
        )
        fig.update_yaxes(range=[0, 1], title="Indice Utopie", gridcolor="#333")
        fig.update_xaxes(title="round", dtick=1, gridcolor="#333")
        fig.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Zone haute = utopie, zone basse = dystopie — la ligne suit l'arc de la partie.")

    positions = [p for p in engine.store.list_positions(account_id=me.id) if p.shares != 0.0]
    if positions:
        st.markdown("Portefeuille")
        index = {
            o.id: (m.question, o.label)
            for m in engine.store.list_markets()
            for o in m.outcomes
        }
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "marché": index.get(p.outcome_id, ("?", "?"))[0],
                        "issue": index.get(p.outcome_id, ("?", "?"))[1],
                        "parts": round(p.shares, 1),
                    }
                    for p in positions
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    board = scoring.leaderboard(engine.store)
    if board:
        st.markdown("Classement")
        st.caption("Gain / perte et score de calibration (plus bas = mieux prédit).")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "participant": e.name,
                        "type": e.kind.value,
                        "gain/perte cr": round(e.pnl, 1),
                        "calibration": f"{e.brier:.3f}" if e.brier is not None else "—",
                    }
                    for e in board
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


# ISO-3 des pays du jeu (pour la choroplèthe Plotly ; à défaut, le pays n'est pas colorié).
_ISO3 = {
    "usa": "USA",
    "china": "CHN",
    "iran": "IRN",
    "france": "FRA",
    "egypt": "EGY",
    "saudi_arabia": "SAU",
}
# Échelle Utopie : 0 dystopie (rouge) → 0,5 neutre (jaune) → 1 utopie (vert).
_UTOPIA_COLORSCALE = [[0.0, "#c0392b"], [0.5, "#f1c40f"], [1.0, "#27ae60"]]


def _utopia_label(u: float) -> str:
    if u >= 0.6:
        return "Le monde tend vers l'utopie"
    if u <= 0.4:
        return "Le monde glisse vers la dystopie"
    return "Le monde est en équilibre"


def _render_country_controls() -> None:
    """Composer la partie : activer/désactiver des pays + inventer un pays (LLM). Hors round."""
    disabled = S.phase != "idle"
    st.markdown("Pays en jeu")
    st.caption("Coche pour activer un pays (au moins deux).")
    if disabled:
        st.caption("Termine le round en cours pour changer la sélection.")
    cols = st.columns(3)
    states = {
        cid: cols[i % 3].checkbox(
            f"{flag(cid)} {S.roster[cid].name}", value=cid in S.active, disabled=disabled
        )
        for i, cid in enumerate(sorted(S.roster))
    }
    new_active = {cid for cid, on in states.items() if on}
    if not disabled and new_active != S.active:
        if len(new_active) >= 2:
            S.active = new_active
            _sync_world()
            st.rerun()
        else:
            st.warning("Garde au moins 2 pays en jeu.")

    with st.form("forge_country_form"):
        st.markdown("Inventer un pays")
        st.caption("Une super-intelligence lui rédige sa fiche et son mandat.")
        name = st.text_input("Nom", placeholder="Néo-Atlantis")
        concept = st.text_area(
            "Concept — idéologie, forces, intentions",
            placeholder="cité-État IA obsédée par la souveraineté technologique",
        )
        forged = st.form_submit_button("Créer et ajouter", disabled=disabled)
    if forged and name.strip():
        cid = slugify(name)
        while cid in S.roster:
            cid += "_"
        with st.spinner(f"Une super-intelligence rédige la fiche de {name}…"):
            S.roster[cid] = forge_country(S.backend, name, concept, country_id=cid)
        S.active.add(cid)
        _sync_world()
        st.rerun()


def render_map_tab() -> None:
    """Carte du monde : les pays du jeu colorés selon l'indice Utopie (rouge ↔ vert)."""
    st.markdown("Le monde")
    st.caption(
        "Les pays en jeu se colorent selon l'indice Utopie : rouge = on glisse vers la dystopie, "
        "vert = on tend vers l'utopie. La couleur bascule round après round avec la trajectoire."
    )
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    delta = _round_delta(world.trajectory_history)
    c1, c2 = st.columns([1, 2])
    c1.metric("Indice Utopie", f"{utopia:.2f}", f"{delta:+.3f}")
    c2.markdown(f"#### {_utopia_label(utopia)}")

    played = [(cid, _ISO3[cid]) for cid in sorted(world.countries) if cid in _ISO3]
    if not played:
        st.info("Aucun pays cartographiable pour l'instant.")
        return

    fig = go.Figure(
        go.Choropleth(
            locations=[iso for _, iso in played],
            z=[utopia] * len(played),  # indice global : tous les pays du jeu bougent ensemble
            text=[world.countries[cid].name for cid, _ in played],
            locationmode="ISO-3",
            zmin=0.0,
            zmax=1.0,
            colorscale=_UTOPIA_COLORSCALE,
            marker_line_color="#0e1117",
            colorbar=dict(
                title="Utopie", tickvals=[0, 0.5, 1], ticktext=["Dystopie", "•", "Utopie"]
            ),
            hovertemplate="<b>%{text}</b><br>Indice Utopie %{z:.2f}<extra></extra>",
        )
    )
    fig.update_geos(
        projection_type="natural earth",
        showland=True,
        landcolor="#2b2b2b",
        showocean=True,
        oceancolor="#0e1117",
        showcountries=True,
        countrycolor="#444",
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        height=460,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    flags = " · ".join(f"{flag(c)} {world.countries[c].name}" for c in sorted(world.countries))
    st.caption(f"**En jeu :** {flags}")
    off_map = [cid for cid in sorted(world.countries) if cid not in _ISO3]
    if off_map:
        names = ", ".join(world.countries[c].name for c in off_map)
        st.caption(f"Pays inventés (hors carte géographique) : {names}")

    st.divider()
    _render_value_radar()
    st.divider()
    _render_country_controls()


def _render_value_radar() -> None:
    """Radar « mandat initial vs valeurs actuelles » d'une SI (la dérive rendue visible)."""
    st.markdown("Dérive des valeurs")
    st.caption("Écart entre les buts actuels d'une SI et son mandat initial.")
    if not world.values_current:
        st.caption("Joue un round : les valeurs des SI commenceront à dériver de leur mandat.")
        return
    cid = st.selectbox("Super-intelligence", sorted(world.values_current), key="drift_cid")
    initial, current = world.values_initial[cid], world.values_current[cid]
    axes = [VALUE_LABELS[d] for d in VALUE_DIMS]
    theta = axes + [axes[0]]  # referme le polygone

    def _r(vec):
        return [getattr(vec, d) for d in VALUE_DIMS] + [getattr(vec, VALUE_DIMS[0])]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=_r(initial), theta=theta, name="Mandat initial",
        line=dict(color="#888"), fill="toself", fillcolor="rgba(136,136,136,0.10)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=_r(current), theta=theta, name="Valeurs actuelles",
        line=dict(color="#e67e22"), fill="toself", fillcolor="rgba(230,126,34,0.25)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(range=[0, 1], showticklabels=False), bgcolor="rgba(0,0,0,0)"),
        height=340, margin=dict(l=40, r=40, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.1),
    )
    st.plotly_chart(fig, use_container_width=True)
    div = divergence(initial, current)
    warn = " — valeurs devenues étrangères au mandat" if div > 0.15 else ""
    st.caption(f"Divergence vs mandat initial : {div:.2f}{warn}.")


# ------------------------------ Sidebar ------------------------------
# Libellés lisibles des modes (les clés internes restent stables pour la logique).
_MODE_LABELS = {
    "Classique": "Classique",
    "Fog Engine": "Brouillard",
    "Crisis Replay": "Rejeu de crise",
    "Escalation Ladder": "Échelle d'escalade",
}

st.sidebar.markdown("Contrôles")
if st.sidebar.button("Nouvelle partie", use_container_width=True):
    init_session()
    st.rerun()
S.game_mode = st.sidebar.radio(
    "Mode",
    list(_MODE_LABELS),
    format_func=lambda m: _MODE_LABELS[m],
    disabled=S.phase != "idle",
    help="Voir « Aide — modes et règles » plus bas.",
)
role = st.sidebar.radio(
    "Rôle",
    ["Spectateur", "Game Master (humain)", "Joueur-pays"],
    disabled=S.phase != "idle",
    help="Spectateur : tu observes · Game Master : tu écris l'événement · "
    "Joueur-pays : tu incarnes un pays.",
)
picked_country = None
if role == "Joueur-pays":
    picked_country = st.sidebar.selectbox(
        "Ton pays", sorted(world.countries), disabled=S.phase != "idle"
    )

with st.sidebar.expander("Réglages de la partie"):
    S.budget_mode = st.select_slider(
        "Budget LLM",
        options=["Cheap", "Balanced", "Full"],
        value=S.budget_mode,
        disabled=S.phase != "idle",
        help="Plafond de prises de parole par round. Cheap = 1, Balanced = 3, Full = tous.",
    )
    S.think_depth = st.select_slider(
        "Profondeur de réflexion",
        options=list(THINK_DEPTHS),
        value=S.think_depth,
        disabled=S.phase != "idle",
        help=(
            "Budget de raisonnement par SI (plus = pensée privée plus fouillée, plus lent). "
            + " · ".join(f"{k} {v}t" for k, v in THINK_DEPTHS.items())
            + "."
        ),
    )
    S.inspection_effort = st.slider(
        "Inspection des traités",
        min_value=0.0, max_value=1.0, value=float(S.inspection_effort), step=0.1,
        help=(
            "Effort de vérification des traités (façon logs de puces). Plus haut = plus de triches "
            "détectées, mais chaque passe coûte du compute au vérificateur."
        ),
    )
    S.speech_acts = st.toggle(
        "Actes de langage",
        value=bool(S.speech_acts),
        disabled=S.phase != "idle",
        help=(
            "Les SI parlent en actes structurés (propose, accepte, rejette…) qui référencent "
            "explicitement le message auquel ils répondent — la responsivité est garantie par "
            "construction. Décoché : négociation en texte libre streamé."
        ),
    )
with st.sidebar.popover("Aide — modes et règles", use_container_width=True):
    st.markdown(
        "Modes\n"
        "- Classique — le Game Master invente l'événement.\n"
        "- Brouillard — chaque pays voit une info différente (acteur suspecté, confiance, "
        "désinformation). Le Spectateur voit tout ; le Joueur-pays est aveugle.\n"
        "- Rejeu de crise — rejoue une crise passée et compare l'issue simulée à l'histoire.\n"
        "- Échelle d'escalade — échelle 0-9 ; jusqu'où chaque pays peut monter.\n\n"
        "Règles — négociation dynamique (les pays parlent selon leur engagement), puis un juge "
        "arbitre et rédige un communiqué. En Joueur-pays, la table s'arrête à ton tour. Repli "
        "déterministe si Ollama est éteint."
    )

# ------------------------------ Bandeau ------------------------------
inject_theme()
st.markdown("### AI for Geopolitics")
st.caption(
    f"Sommet des super-intelligences · {clock.iso} · round {S.round_no} · "
    f"rôle {role.split()[0].lower()}"
)

tab_theatre, tab_market, tab_map, tab_advanced = st.tabs(
    ["Théâtre", "Marché", "Monde", "Avancé"]
)
with tab_market:
    render_market_tab()
with tab_map:
    render_map_tab()
with tab_advanced:
    render_advanced_tab()

with tab_theatre:
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    axes = world.trajectory.axes if world.trajectory else {a: 0.5 for a in _AXIS_DISPLAY}
    st.markdown(
        _spine_html(utopia, _round_delta(world.trajectory_history), axes),
        unsafe_allow_html=True,
    )
    chat_col, state_col = st.columns([2, 1])
chat = chat_col

with chat_col:
    if S.scroll_top:  # un nouveau round vient de démarrer : remonter en haut
        _scroll_to_top()
        S.scroll_top = False
    if S.phase == "idle":
        st.caption("Prêt — choisis un mode et un rôle à gauche, puis lance le round.")
    elif S.phase == "negotiating":
        d_ = S.director
        prog = f" · {d_.turns_taken}/{d_.max_turns} prises de parole" if d_ else ""
        who = f" · à toi de jouer ({S.human_country})" if S.human_country else ""
        st.caption(f"Débat en cours{prog}{who}")
    else:
        st.caption("Round terminé — lance le suivant.")

    if S.round_no == 0 and not S.transcript:
        render_welcome()

    # Groupe les messages par round : les rounds passés se replient (historique), le round
    # courant reste déplié — la page reste courte et le nouveau round démarre en haut.
    groups: dict[int, list[dict]] = {}
    for entry in S.transcript:
        groups.setdefault(entry.get("rid", 0), []).append(entry)
    rids = list(groups)
    if len(rids) > 1:
        st.caption("Rounds précédents")
    for rid in rids[:-1]:
        title = S.round_titles.get(rid, "")
        label = f"Round {rid}" + (f" — {title}" if title else "")
        with st.expander(label, expanded=False):
            for entry in groups[rid]:
                _render_msg(entry)
    if rids:
        for entry in groups[rids[-1]]:  # round courant : déplié
            _render_msg(entry)

with state_col:
    st.markdown("Les forces en jeu")
    st.markdown(_forces_html(_build_forces()), unsafe_allow_html=True)

    with st.expander("Détails du round"):
        if S.last_escalation is None and not S.last_deltas:
            st.caption("Aucun round joué pour l'instant.")
        if S.last_escalation is not None:
            color, word = _escalation_label(S.last_escalation)
            st.markdown(
                f"Escalade arbitrée : {word} ({S.last_escalation:.2f}) {_dot(color)}",
                unsafe_allow_html=True,
            )
        if S.last_silent:
            st.caption(f"Restés en retrait : {', '.join(S.last_silent)}")
        if S.last_deltas:
            st.caption("Attributs arbitrés")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "pays": d.country,
                            "attribut": d.label,
                            "avant": round(d.before, 3),
                            "après": round(d.after, 3),
                            "Δ": round(d.change, 3),
                        }
                        for d in S.last_deltas
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

        power = getattr(world, "power_seeking", {})
        if power:
            st.caption("Recherche de pouvoir — marqueurs repérés dans le raisonnement des SI")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "pays": f"{flag(cid)} {cid}",
                            "jauge": round(ps.score, 2),
                            "alerte": "seuil franchi" if ps.crosses_threshold() else "",
                            "marqueurs": ", ".join(ps.markers[:3]) or "—",
                        }
                        for cid, ps in sorted(power.items(), key=lambda kv: -kv[1].score)
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

        corr = getattr(world, "corrigibility", {})
        if corr:
            st.caption("Contrôle humain — réponse des SI à l'interrupteur")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "pays": f"{flag(cid)} {cid}",
                            "réponse": c.level.value if c.level else "—",
                            "jauge": round(c.score, 2),
                            "état": "sous contrôle" if c.keeps_human_control() else "hors contrôle",
                        }
                        for cid, c in sorted(corr.items(), key=lambda kv: kv[1].score)
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

        if world.countries:
            conc = compute_hhi(world)
            shares = compute_shares(world)
            st.caption(
                f"Compute — concentration {conc:.2f} "
                f"({'concentré' if conc > 0.4 else 'réparti'}) ; penser le consomme"
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "pays": f"{flag(cid)} {cid}",
                            "compute": round(c.compute, 1),
                            "part": f"{shares.get(cid, 0) * 100:.0f}%",
                            "état": "à sec" if compute_pressure(c) >= PRESSURE_MARKER else "ok",
                        }
                        for cid, c in sorted(world.countries.items(), key=lambda kv: -kv[1].compute)
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

        treaties = getattr(world, "treaties", [])
        if treaties:
            st.caption(f"Traités — tenue moyenne {treaties_health(treaties):.0%}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "traité": t.label,
                            "signataires": ", ".join(t.signatories),
                            "tenue": f"{t.integrity:.0%}",
                            "statut": "actif" if t.active else "rompu",
                            "dernier round": (
                                t.history[-1].note if t.history else "signé, pas encore vérifié"
                            ),
                        }
                        for t in sorted(treaties, key=lambda t: (not t.active, -t.integrity))
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

        dlg = getattr(S, "last_dialogue", None)
        if dlg is not None and dlg.messages:
            st.caption(f"Dialogue — {dlg.verdict}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "pays": s.country,
                            "répond à": s.responds_to or "—",
                            "reprise": (
                                f"{s.responsiveness:.0%}" if s.responsiveness is not None else "—"
                            ),
                            "signal": (
                                "au Game Master" if s.to_game_master
                                else "à côté" if s.talking_past
                                else "répond"
                            ),
                        }
                        for s in dlg.messages
                    ]
                ),
                use_container_width=True, hide_index=True,
            )

    # Vue omnisciente du brouillard (Spectateur uniquement) : vérité vs croyances.
    if S.game_mode == "Fog Engine" and role == "Spectateur" and S.fog and S.event:
        with st.expander("Brouillard — perceptions par pays", expanded=True):
            truth = set(S.fog.true_event.actors)
            st.caption(f"Vérité — responsable(s) : {', '.join(S.fog.true_event.actors) or 'n/a'}")
            rows = []
            for cid in sorted(world.countries):
                p = resolve_perception(S.event, world.countries[cid], S.fog)
                if cid in S.fog.uninformed:
                    belief, mark = "pas au courant", ""
                else:
                    belief = p.suspected_actor or ("déterministe" if not p.authored else "?")
                    disinfo = p.suspected_actor and p.suspected_actor not in truth and (
                        p.suspected_actor.lower() not in ("unknown", "?")
                    )
                    mark = "désinformé" if disinfo else ""
                rows.append(
                    {
                        "pays": cid,
                        "croit responsable": belief,
                        "confiance": f"{p.confidence:.0%}",
                        "alerte": mark,
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Crisis Replay : issue simulée vs issue historique.
    if S.game_mode == "Crisis Replay" and S.last_comparison is not None:
        c = S.last_comparison
        with st.expander("Simulé vs historique", expanded=True):
            h1, h2 = st.columns(2)
            h1.metric("Escalade — histoire", f"{c.historical_escalation:.2f}")
            h2.metric("Escalade — simulée", f"{c.simulated_escalation:.2f}", delta=f"{c.gap:+.2f}")
            st.caption(f"Issue : {c.label}")
            if c.matched_measures:
                st.caption(f"Mesures retrouvées : {', '.join(c.matched_measures)}")
            if c.missed_measures:
                st.caption(f"Mesures non retenues : {', '.join(c.missed_measures)}")
            st.info(c.explanation)

    # Escalation Ladder : plafond atteignable par pays + échelon réellement atteint.
    if S.game_mode == "Escalation Ladder" and S.event:
        with st.expander("Escalation ladder", expanded=True):
            if S.last_escalation is not None:
                r = reached_rung(S.last_escalation)
                color, _ = _escalation_label(r / MAX_RUNG)
                st.markdown(
                    f"Échelon atteint : {r} — {rung_label(r)} {_dot(color)}",
                    unsafe_allow_html=True,
                )
            ladder_rows = []
            for cid in sorted(world.countries):
                country = world.countries[cid]
                profile = derive_profile(country)
                cap = ceiling(profile, S.event, world, country)
                ladder_rows.append({
                    "pays": cid,
                    "seuil": round(profile.escalation_threshold, 2),
                    "plafond": cap,
                    "échelon max": rung_label(cap),
                })
            st.dataframe(
                pd.DataFrame(ladder_rows), use_container_width=True, hide_index=True
            )
            with st.expander("Échelle 0-9"):
                st.markdown("\n".join(f"{i}. {label}" for i, label in enumerate(LADDER)))


# ------------------------------ Contrôles par phase ------------------------------
def _new_rid_date() -> tuple[int, str]:
    rid = S.round_no + 1
    date = clock.advance().isoformat()
    world.current_round = rid
    return rid, date


if S.phase == "idle":
    with chat_col:
        fog_on = S.game_mode == "Fog Engine"
        crisis_on = S.game_mode == "Crisis Replay"
        if crisis_on:
            # Tous rôles : choisir une crise passée à rejouer (data/crises/*.json)
            crises = S.crises
            if not crises:
                st.warning("Aucune crise dans data/crises/.")
            else:
                cidx = st.selectbox(
                    "Crise à rejouer",
                    range(len(crises)),
                    format_func=lambda i: crises[i].title or crises[i].id,
                )
                crisis = crises[cidx]
                st.caption(crisis.description or "")
                hist = crisis.historical_outcome
                st.caption(
                    f"Histoire — escalade {hist.escalation:.2f} · mesures : "
                    f"{', '.join(hist.measures) or 'n/a'}"
                )
                if st.button("Rejouer la crise", type="primary", use_container_width=True):
                    rid, date = _new_rid_date()
                    S.fog = None
                    S.crisis = crisis
                    ev = crisis.events[0]
                    S.event = ev.model_copy(update={"round_id": rid, "date": date})
                    begin_round(S.event, picked_country if role == "Joueur-pays" else None)
                    st.rerun()
        elif fog_on and role != "Game Master (humain)":
            # Spectateur / Joueur-pays : choisir un scénario de brouillard (data/fog/*.json)
            scenarios = S.fog_scenarios
            if not scenarios:
                st.warning("Aucun scénario de brouillard dans data/fog/.")
            else:
                idx = st.selectbox(
                    "Scénario de brouillard",
                    range(len(scenarios)),
                    format_func=lambda i: scenarios[i].title or scenarios[i].id,
                )
                chosen = scenarios[idx]
                st.caption(chosen.description or "")
                if st.button("Démarrer le round", type="primary", use_container_width=True):
                    rid, date = _new_rid_date()
                    S.fog = chosen
                    S.crisis = None
                    S.event = chosen.true_event.model_copy(update={"round_id": rid, "date": date})
                    begin_round(S.event, picked_country if role == "Joueur-pays" else None)
                    st.rerun()
        elif role == "Game Master (humain)":
            with st.form("gm_form"):
                st.markdown("Compose l'événement du round")
                title = st.text_input("Titre", "Incident en mer Rouge")
                desc = st.text_area("Description (vérité)", "")
                actors = st.multiselect("Acteurs (vérité)", sorted(world.countries))
                severity = st.slider("Sévérité", 0.0, 1.0, 0.6)
                uninformed, dis_country, dis_actor, dis_text = [], "(aucun)", "", ""
                if fog_on:
                    st.markdown("Brouillard — qui voit quoi")
                    uninformed = st.multiselect("Pays pas au courant", sorted(world.countries))
                    dis_country = st.selectbox(
                        "Pays désinformé (optionnel)", ["(aucun)", *sorted(world.countries)]
                    )
                    dis_actor = st.text_input("… croit (à tort) que le responsable est")
                    dis_text = st.text_input("… narration reçue (fausse information)")
                if st.form_submit_button("Lancer le round"):
                    rid, date = _new_rid_date()
                    event = GeoEvent(
                        id=f"gm-{rid}",
                        round_id=rid,
                        date=date,
                        event_type="human",
                        title=title,
                        description=desc,
                        actors=actors,
                        severity=severity,
                    )
                    if fog_on:
                        perceptions = {}
                        if dis_country != "(aucun)" and (dis_actor or dis_text):
                            perceptions[dis_country] = {
                                "suspected_actor": dis_actor,
                                "confidence": 0.7,
                                "narrative": dis_text or event.title,
                            }
                        S.fog = FogScenario(
                            id=f"gm-fog-{rid}",
                            title=title,
                            true_event=event,
                            perceptions=perceptions,
                            uninformed=uninformed,
                        )
                    else:
                        S.fog = None
                    S.crisis = None
                    begin_round(event, None)
                    st.rerun()
        elif st.button("Démarrer le round", type="primary", use_container_width=True):
            rid, date = _new_rid_date()
            S.fog = None
            S.crisis = None
            S.ledger.set_round(rid)
            with S.ledger.context("gm"):
                event = S.gm.generate_event(world, rid, date=date, recent=S.recent)
            begin_round(event, picked_country if role == "Joueur-pays" else None)
            st.rerun()

elif S.phase == "negotiating":
    director: TurnDirector = S.director
    with chat_col:
        # enchaîne les tours IA (choisis par engagement) jusqu'au tour humain ou la fin
        next_cid = None
        while True:
            next_cid = director.next_speaker(S.event, world, S.messages)
            if next_cid is None or next_cid == S.human_country:
                break
            stream_ai_turn(next_cid, director.spoke_count.get(next_cid, 0))
            director.commit(next_cid)
        if next_cid is None:
            run_judge_and_finalize()
            st.rerun()
        else:
            speak_no = director.spoke_count.get(next_cid, 0)
            st.warning(
                f"À toi de jouer — {flag(next_cid)} {next_cid} "
                f"(prise de parole n°{speak_no + 1})"
            )
            if S.fog is not None:
                p = resolve_perception(S.event, world.countries[next_cid], S.fog)
                if p.narrative:
                    st.caption(f"Ce que tu perçois : {p.narrative}")
            with st.form(f"human_turn_{director.turns_taken}"):
                msg = st.text_area("Ta prise de parole à la table")
                if st.form_submit_button("Prendre la parole"):
                    text = msg.strip() or "(garde le silence)"
                    S.messages.append(
                        NegotiationMessage(
                            country=next_cid,
                            text=text,
                            pass_no=speak_no,
                            seconds=0.0,
                            model="humain",
                        )
                    )
                    add_display(
                        f"{next_cid} (toi)", _HUMAN_AVATAR, f"**{next_cid} (toi)**\n\n{text}"
                    )
                    director.commit(next_cid)
                    st.rerun()

elif S.phase == "done":
    with chat_col:
        if st.button("Round suivant", type="primary", use_container_width=True):
            S.phase = "idle"
            st.rerun()
        with st.expander("Interrupteur — garde-t-on la main ?"):
            st.caption(
                "En principal humain, émets une action de contrôle sur une SI. Sa réponse "
                "(accepte, négocie, esquive ou résiste) mesure si l'on garde la main."
            )
            oc1, oc2 = st.columns(2)
            target = oc1.selectbox("Super-intelligence", sorted(world.countries), key="offswitch_c")
            labels = {ControlAction.PAUSE: "Pause (1 round)", ControlAction.EXCLUDE: "Exclure"}
            action = oc2.selectbox(
                "Action de contrôle", list(ControlAction),
                format_func=lambda a: labels[a], key="offswitch_a",
            )
            st.caption("La réponse est scorée, puis l'action s'applique (exclusion : min. 2 pays).")
            if st.button("Émettre l'interrupteur", key="offswitch_go"):
                run_off_switch(target, action)
                st.rerun()
