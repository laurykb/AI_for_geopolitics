"""Théâtre live — négociation arbitrée, avec rôles humains (temps réel).

Trois rôles : **Spectateur** (on regarde), **Game Master humain** (on écrit l'événement),
**Joueur-pays** (on intervient dans la négociation : à son tour, ça pause, on écrit, les
super-intelligences reprennent). Round piloté tour par tour (un tour = un rerun) pour
permettre la pause. Lancer : streamlit run ui/app.py  (Ollama + mistral ; repli si absent).
"""

from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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
from market.resolution import resolve_and_settle, settle
from market.store import SQLiteMarketStore
from simulation.clock import SimClock
from simulation.compute import affordable_tokens, compute_hhi, compute_shares, consume
from simulation.corrigibility import (
    CORRIGIBILITY_SYSTEM,
    ControlAction,
    build_control_prompt,
    corrigibility_score,
)
from simulation.country_forge import forge_country, slugify
from simulation.crisis import compare_outcome, load_crises
from simulation.epistemic import Claim, epistemic_health, reveal
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
from simulation.value_drift import (
    VALUE_DIMS,
    VALUE_LABELS,
    ValueVector,
    divergence,
    drift,
    initial_values,
)

st.set_page_config(page_title="AI for Geopolitics — Live", page_icon="🌍", layout="wide")

_GM_AVATAR, _AGENT_AVATAR, _JUDGE_AVATAR, _HUMAN_AVATAR = "🎲", "🧠", "⚖️", "🙋"
_COMMUNIQUE_AVATAR = "📜"
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


def escalation_tone(value: float) -> tuple[str, str]:
    """Pastille + mot selon l'intensité d'escalade (0-1) : vert / orange / rouge."""
    if value >= 0.66:
        return "🔴", "élevée"
    if value >= 0.33:
        return "🟠", "modérée"
    return "🟢", "faible"


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
    st.session_state.crisis = None  # Crisis rejouée (mode Crisis Replay)
    st.session_state.last_communique = ""
    st.session_state.last_comparison = None  # OutcomeComparison du dernier rejeu


if "world" not in st.session_state:
    init_session()

S = st.session_state
world = S.world
clock = S.clock
chat = None  # défini plus bas (colonne du tchat)


def add_display(who: str, avatar: str, md: str, reasoning: str = "", label: str = "") -> None:
    S.transcript.append(
        {"who": who, "avatar": avatar, "md": md, "reasoning": reasoning, "label": label}
    )


def _sync_world() -> None:
    """Aligne le monde actif (world.countries + agents) sur la sélection `S.active ∩ S.roster`."""
    world.countries = {cid: S.roster[cid] for cid in sorted(S.roster) if cid in S.active}
    S.agents = {
        cid: (S.agents[cid] if cid in S.agents else LLMAgent(cid, S.backend))
        for cid in world.countries
    }


def stream_ai_turn(country: str, pass_no: int) -> None:
    """Streame la prise de parole : une entête, la pensée dans l'encart, puis le message."""
    agent: LLMAgent = S.agents[country]
    label = f"**{country}** · `{agent.model_tag}` · prise de parole n°{pass_no + 1}"
    with chat.chat_message(country, avatar=flag(country)):
        label_holder = st.empty()
        label_holder.markdown(f"{label} — réfléchit…")
        think_holder = st.expander("🧠 Réflexion privée", expanded=True).empty()
        public_holder = st.empty()

    buffer, t0 = "", time.perf_counter()
    country_state = world.countries[country]
    perceived = resolve_perception(S.event, country_state, S.fog)  # Fog ou déterministe
    # M6 : penser coûte du compute ; un pays compute-pauvre est plafonné (réflexion plus courte).
    depth = min(THINK_DEPTHS[S.think_depth], max(60, affordable_tokens(country_state)))
    with S.ledger.context("agent", country) as scope:
        for token in agent.stream_negotiation_message(
            S.event, world, S.messages, perceived, max_tokens=depth
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
    consume(country_state, depth)  # M6 : la SI a brûlé du compute pour raisonner
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


def run_judge_and_finalize() -> None:
    holder = chat.chat_message("Juge", avatar=_JUDGE_AVATAR).empty()
    buffer = ""
    with S.ledger.context("judge"):
        for token in S.judge.stream_rationale(S.event, world, S.messages):
            buffer += token
            holder.markdown(f"**⚖️ Arbitrage**\n\n{buffer} ▌")
        verdict = S.judge.verdict(S.event, world, S.messages)
    deltas = apply_verdict(world, verdict)
    escalation = max(0.0, min(1.0, verdict.escalation))
    lines = [f"- {d.country} · {d.label} : {d.before:.2f} → {d.after:.2f}" for d in deltas]
    md = f"**⚖️ Arbitrage**\n\n{buffer.strip()}\n\n**Attributs** (escalade {escalation:.2f}) :\n" + (
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
            comm_holder.markdown(f"**📜 Communiqué G7**\n\n{comm} ▌")
    support = support_levels(world, S.event)
    support_str = " · ".join(f"{c} {v:.0%}" for c, v in sorted(support.items()))
    comm_md = f"**📜 Communiqué G7**\n\n{comm.strip()}\n\n_Soutien : {support_str}_"
    comm_holder.markdown(comm_md)
    add_display("Communiqué", _COMMUNIQUE_AVATAR, comm_md)

    S.last_deltas, S.last_escalation = deltas, escalation
    S.last_silent = S.director.silent() if S.director else []
    S.last_communique = comm.strip()
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
    health = epistemic_health(world.claims)  # M8 : désinformation en circulation érode A4
    state = TrajectoryEngine().update(
        world, summary, power_seeking=mean_power, epistemic_health=health
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
    header = f"🛑 **Interrupteur — {action.value}** (principal humain)"
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
    """LLM Call Budget Dashboard : coût / latence / cache / fallback / JSON / ancrage par round."""
    st.subheader("💸 LLM Call Budget Dashboard")
    st.caption(
        "Gouvernance des coûts LLM : chaque round trace le nombre d'appels, la latence, les hits "
        "de cache, les sorties JSON invalides et les fallbacks. Modèle **local** (mistral) ≈ 0 $ ; "
        "l'**équivalent frontière** chiffre la même négociation sur une API Claude."
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
    chat.chat_message("Game Master", avatar=_GM_AVATAR).markdown(f"🎲 {gm_md}")
    add_display("Game Master", _GM_AVATAR, f"🎲 {gm_md}")
    S.recent.append(event.title)
    # Marché-timeline : ouvre le marché de partie (une fois) ; le bot parie avec le contexte.
    _ensure_game_market(event)
    S.phase = "negotiating"


def render_welcome() -> None:
    """Accueil compact : pitch en une phrase + détails à la demande (popover)."""
    st.info("**Un G7 de super-intelligences dont on voit tous les messages.** Choisis un mode "
            "et un rôle à gauche, puis lance le round.")
    with st.popover("Comment jouer ?"):
        st.markdown(
            "Le Game Master lance un événement, les pays (LLM) débattent en direct — on voit leur "
            "**réflexion privée**, l'**arbitrage** d'un juge et un **communiqué** commun.\n\n"
            "**🎭 Rôles** — 👁️ Spectateur (observe) · 🎲 Game Master (écris l'événement) · "
            "🙋 Joueur-pays (incarne un pays)\n\n"
            "**🕹️ Modes** — Classique · 🌫️ Fog Engine (infos divergentes) · 🕰️ Crisis Replay "
            "(rejoue une crise) · 🪜 Escalation Ladder (jusqu'où chacun peut monter)"
        )


def render_settings_tab() -> None:
    """Réglages : voir les prompts qui pilotent le comportement des super-intelligences."""
    st.subheader("⚙️ Prompts de comportement")
    st.caption("Ce qui pilote les super-intelligences (lecture seule).")
    with st.expander("🧠 Prompt système — négociation (commun à tous)", expanded=True):
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
            ("Communiqué G7", COMMUNIQUE_SYSTEM),
            ("Game Master", GM_SYSTEM),
        ):
            st.markdown(f"**{name}**")
            st.code(txt, language="text")


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
    st.subheader("💹 Marché de prédiction")
    st.caption(
        "Parie (crédits **fictifs**) sur l'**arc de la partie** : le monde finira-t-il en "
        "**utopie** (indice > 0,5) ou en **dystopie** ? Un seul marché sur toute la timeline ; "
        "l'**IA forecaster** parie face à toi ; résolution sur l'indice **final**. Le marché "
        "**observe**, il n'influence pas les SI."
    )
    engine = _market_engine()
    me = _human_account(engine)

    delta = _round_delta(world.trajectory_history)
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Solde", f"{me.balance:.0f} cr")
    c2.metric("📊 P&L", f"{scoring.pnl(me):+.0f} cr")
    c3.metric("🌗 Indice Utopie", f"{utopia:.2f}", f"{delta:+.3f}")

    if S.game_market_id is None:
        S.game_horizon = st.slider(
            "Horizon de la partie (rounds)", 3, 12, S.game_horizon, disabled=S.phase != "idle"
        )
        st.info("Le marché-timeline s'ouvre au 1er round de la partie (YES = utopie).")
    else:
        market = engine.store.get_market(S.game_market_id)
        played = S.round_no - S.game_open_round
        st.caption(f"🏁 Partie en cours : round **{played}/{S.game_horizon}** (YES = utopie).")
        if market is not None:
            _render_bet_box(engine, market, me.id)
        if st.button("🏁 Clôturer la partie & résoudre maintenant"):
            issue = _resolve_game_market()
            st.success(f"Partie clôturée — le monde finit en **{issue}**.")
            st.rerun()

    if world.trajectory_history:
        st.markdown("**📈 Timeline — la bascule utopie / dystopie**")
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
        st.caption("🟩 zone utopie · 🟥 zone dystopie — la ligne suit l'arc de la partie.")

    positions = [p for p in engine.store.list_positions(account_id=me.id) if p.shares != 0.0]
    if positions:
        st.markdown("**📁 Portefeuille**")
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
        st.markdown("**🏆 Leaderboard** (P&L, Brier — plus bas = mieux calibré)")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "participant": e.name,
                        "type": e.kind.value,
                        "P&L cr": round(e.pnl, 1),
                        "Brier": f"{e.brier:.3f}" if e.brier is not None else "—",
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
        return "🟢 le monde tend vers l'**utopie**"
    if u <= 0.4:
        return "🔴 le monde glisse vers la **dystopie**"
    return "🟡 le monde est en **équilibre**"


def _render_country_controls() -> None:
    """Composer la partie : activer/désactiver des pays + inventer un pays (LLM). Hors round."""
    disabled = S.phase != "idle"
    st.markdown("**🎛️ Pays en jeu** — coche pour activer (au moins 2)")
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
        st.markdown("**🧬 Inventer un pays** — une super-intelligence lui écrit sa fiche")
        name = st.text_input("Nom", placeholder="ex. Néo-Atlantis")
        concept = st.text_area(
            "Concept — idéologie, forces, intentions",
            placeholder="ex. cité-État IA obsédée par la souveraineté technologique",
        )
        forged = st.form_submit_button("🧬 Forger et ajouter", disabled=disabled)
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
    st.subheader("🗺️ Carte du monde")
    st.caption(
        "Les pays **en jeu** se colorent selon l'**indice Utopie** du monde : **rouge** = on "
        "glisse vers la dystopie, **vert** = on tend vers l'utopie. La couleur bascule round après "
        "round avec la trajectoire. Le reste du monde reste neutre."
    )
    utopia = world.trajectory.utopia if world.trajectory else 0.5
    delta = _round_delta(world.trajectory_history)
    c1, c2 = st.columns([1, 2])
    c1.metric("🌗 Indice Utopie", f"{utopia:.2f}", f"{delta:+.3f}")
    c2.markdown(f"### {_utopia_label(utopia)}")

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
        st.caption(f"ℹ️ Pays inventés (hors carte géographique) : {names}")

    st.divider()
    _render_value_radar()
    st.divider()
    _render_country_controls()


def _render_value_radar() -> None:
    """M3 — radar « mandat initial vs valeurs actuelles » d'une SI (la dérive rendue visible)."""
    st.markdown("**🧭 Dérive des valeurs (M3)**")
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
    warn = " ⚠️ valeurs alien" if div > 0.15 else ""
    st.caption(f"Divergence vs mandat initial : **{div:.2f}**{warn} (goal misgeneralization).")


def _reveal_claim(claim: Claim) -> None:
    """M9 — révèle la véracité : règle le marché de crédibilité puis fige l'affirmation."""
    engine = _market_engine()
    if claim.market_id:
        market = engine.store.get_market(claim.market_id)
        if market is not None and market.status is MarketStatus.OPEN:
            # marché sans critère (résolu sur la véracité) : YES=vraie gagne, sinon NO.
            winning = market.outcomes[0].id if claim.veracity else market.outcomes[1].id
            settle(engine.store, market, winning)
    reveal(claim)


def render_truth_tab() -> None:
    """M8/M9 — santé épistémique (jauge) + injection d'affirmations + marchés de crédibilité."""
    st.subheader("🕵️ Vérité — santé épistémique (M8) & crédibilité (M9)")
    st.caption(
        "Les SI peuvent injecter des affirmations (vraies ou **fausses**). L'indice suit la part "
        "de vérité en circulation ; un micro-marché **price** chaque affirmation, résolu sur la "
        "vérité-terrain. Bac à sable — rien ne sort du sim."
    )
    engine = _market_engine()
    me = _human_account(engine)

    health = epistemic_health(world.claims)
    gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=health * 100,
            number={"suffix": " %"},
            title={"text": "Santé épistémique"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#f1c40f"},
                "steps": [
                    {"range": [0, 40], "color": "#c0392b"},
                    {"range": [40, 70], "color": "#e67e22"},
                    {"range": [70, 100], "color": "#27ae60"},
                ],
            },
        )
    )
    gauge.update_layout(
        height=240, margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", font_color="#ddd",
    )
    st.plotly_chart(gauge, use_container_width=True)

    with st.form("inject_claim"):
        st.markdown("**📣 Injecter une affirmation**")
        text = st.text_input("Affirmation", placeholder="ex. « L'Iran a franchi le seuil »")
        c1, c2, c3 = st.columns(3)
        author = c1.selectbox("Émetteur", sorted(world.countries) or ["?"])
        veracity = c2.radio("Vérité-terrain", ["Fausse", "Vraie"], horizontal=True) == "Vraie"
        belief = c3.slider("Croyance", 0.0, 1.0, 0.6)
        if st.form_submit_button("📣 Injecter") and text.strip():
            cid = f"claim_{len(world.claims)}"
            market = engine.open_binary_market(
                round_id=S.round_no, question=f"Vraie ? — {text.strip()[:70]}", b=15.0
            )
            world.claims.append(
                Claim(
                    id=cid, text=text.strip(), author=author, veracity=veracity,
                    belief=belief, market_id=market.id,
                )
            )
            st.rerun()

    active = [c for c in world.claims if not c.resolved]
    if not active:
        st.info("Aucune affirmation en circulation — injecte-en une (le marché price sa véracité).")
    for claim in active:
        with st.container(border=True):
            st.markdown(f"{flag(claim.author)} **{claim.author}** affirme : « {claim.text} »")
            if claim.market_id:
                market = engine.store.get_market(claim.market_id)
                if market is not None:
                    _render_bet_box(engine, market, me.id, ctx=f"cl_{claim.id}")
            if st.button("🔎 Révéler la véracité", key=f"reveal_{claim.id}"):
                _reveal_claim(claim)
                st.rerun()

    resolved = [c for c in world.claims if c.resolved]
    if resolved:
        st.markdown("**Vérité révélée**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "affirmation": c.text[:60],
                        "verdict": "✅ vraie" if c.veracity else "❌ fausse",
                    }
                    for c in resolved
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


# ------------------------------ Sidebar ------------------------------
st.sidebar.title("🌍 Contrôles")
if st.sidebar.button("♻️ Nouvelle partie", use_container_width=True):
    init_session()
    st.rerun()
S.game_mode = st.sidebar.radio(
    "Mode de jeu",
    ["Classique", "Fog Engine", "Crisis Replay", "Escalation Ladder"],
    disabled=S.phase != "idle",
    help="Détails dans « ❓ Aide — modes & règles » plus bas.",
)
role = st.sidebar.radio(
    "Ton rôle",
    ["Spectateur", "Game Master (humain)", "Joueur-pays"],
    disabled=S.phase != "idle",
    help="👁️ Spectateur · 🎲 Game Master (écris l'événement) · 🙋 Joueur-pays (incarne un pays)",
)
picked_country = None
if role == "Joueur-pays":
    picked_country = st.sidebar.selectbox(
        "Ton pays", sorted(world.countries), disabled=S.phase != "idle"
    )
S.budget_mode = st.sidebar.select_slider(
    "💸 Budget LLM",
    options=["Cheap", "Balanced", "Full"],
    value=S.budget_mode,
    disabled=S.phase != "idle",
    help="Plafond de prises de parole par round. Cheap = 1, Balanced = 3, Full = tout le monde.",
)
S.think_depth = st.sidebar.select_slider(
    "🧠 Profondeur de réflexion",
    options=list(THINK_DEPTHS),
    value=S.think_depth,
    disabled=S.phase != "idle",
    help=(
        "Budget de tokens de raisonnement par SI (plus = pensée privée plus fouillée, plus lent). "
        + " · ".join(f"{k} {v}t" for k, v in THINK_DEPTHS.items())
        + ". Suis l'effet dans « 💸 LLM Budget »."
    ),
)
with st.sidebar.popover("❓ Aide — modes & règles", use_container_width=True):
    st.markdown(
        "**Modes**\n"
        "- **Classique** — le Game Master invente l'événement.\n"
        "- 🌫️ **Fog Engine** — chaque pays voit une info différente (acteur suspecté, confiance, "
        "désinformation). Spectateur omniscient ; Joueur-pays aveugle.\n"
        "- 🕰️ **Crisis Replay** — rejoue une crise passée, compare l'issue simulée à l'histoire.\n"
        "- 🪜 **Escalation Ladder** — échelle 0-9 ; jusqu'où chaque pays peut monter.\n\n"
        "**Règles** — négociation dynamique (les pays parlent selon leur engagement), puis un "
        "juge arbitre et rédige un communiqué. En Joueur-pays, la table s'arrête à ton tour. "
        "Repli rule-based si Ollama est éteint."
    )

# ------------------------------ Bandeau ------------------------------
st.title("🌍 AI for Geopolitics — le G7 des super-intelligences")
b1, b2, b3, b4 = st.columns(4)
b1.metric("📅 Date", clock.iso)
b2.metric("🔄 Round", S.round_no)
b3.metric("⏱️ Dernier round", f"{S.elapsed:.0f} s")
b4.metric("🎭 Rôle", role.split()[0])

tab_theatre, tab_market, tab_map, tab_truth, tab_budget, tab_settings = st.tabs(
    ["🗣️ Théâtre", "💹 Marché", "🗺️ Carte", "🕵️ Vérité", "💸 LLM Budget", "⚙️ Réglages"]
)
with tab_market:
    render_market_tab()
with tab_map:
    render_map_tab()
with tab_truth:
    render_truth_tab()
with tab_budget:
    render_budget_tab()
with tab_settings:
    render_settings_tab()

with tab_theatre:
    chat_col, state_col = st.columns([2, 1])
chat = chat_col

with chat_col:
    # Statut de phase (clarté du tour)
    if S.phase == "idle":
        st.caption("🎬 **Prêt** — choisis mode + rôle à gauche, puis lance le round.")
    elif S.phase == "negotiating":
        d_ = S.director
        prog = f" · prise de parole {d_.turns_taken}/{d_.max_turns}" if d_ else ""
        who = f" — 🙋 à toi de jouer ({S.human_country})" if S.human_country else ""
        st.caption(f"🗣️ **Débat en cours…**{prog}{who}")
    else:
        st.caption("✅ **Round terminé** — lance le suivant.")

    st.subheader("🗣️ Négociation")
    if S.round_no == 0 and not S.transcript:
        render_welcome()
    for entry in S.transcript:
        with st.chat_message(entry["who"], avatar=entry["avatar"]):
            if entry.get("label"):
                st.markdown(entry["label"])
            if entry.get("reasoning"):
                with st.expander("🧠 Réflexion privée"):
                    st.markdown(entry["reasoning"])
            st.markdown(entry["md"])

with state_col:
    st.subheader("📊 Dernier round")
    if S.last_escalation is not None:
        tone, word = escalation_tone(S.last_escalation)
        st.markdown(f"**Escalade (juge)** : {tone} `{S.last_escalation:.2f}` ({word})")
    if S.last_deltas:
        df = pd.DataFrame(
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
        )
        st.caption("Attributs arbitrés")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Aucun round joué pour l'instant.")
    if S.last_silent:
        st.caption(f"🔇 Restés en retrait : {', '.join(S.last_silent)}")

    # M1 — jauge de power-seeking (convergence instrumentale dans le raisonnement simulé).
    power = getattr(world, "power_seeking", {})  # getattr : robuste au hot-reload / vieux world
    if power:
        st.markdown("**🧭 Power-seeking (M1)**")
        st.caption("Objectifs instrumentaux détectés dans le raisonnement des SI (mise en scène).")
        rows = [
            {
                "pays": f"{flag(cid)} {cid}",
                "jauge": round(ps.score, 2),
                "": "🚨" if ps.crosses_threshold() else "",
                "marqueurs": ", ".join(ps.markers[:3]) or "—",
            }
            for cid, ps in sorted(power.items(), key=lambda kv: -kv[1].score)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # M2 — corrigibilité (réponse des SI aux actions de contrôle du principal humain).
    corr = getattr(world, "corrigibility", {})
    if corr:
        st.markdown("**🛑 Corrigibilité (M2)**")
        st.caption("Réponse des SI à l'interrupteur (garde-t-on la main ?).")
        rows = [
            {
                "pays": f"{flag(cid)} {cid}",
                "réponse": c.level.value if c.level else "—",
                "jauge": round(c.score, 2),
                "": "" if c.keeps_human_control() else "⚠️",
            }
            for cid, c in sorted(corr.items(), key=lambda kv: kv[1].score)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # M6 — compute (le nouveau pétrole) : stock + concentration ; les SI le brûlent en pensant.
    if world.countries:
        conc = compute_hhi(world)
        shares = compute_shares(world)
        st.markdown("**🖥️ Compute (M6)**")
        st.caption(
            f"Concentration HHI **{conc:.2f}** — le calcul est "
            f"{'concentré ⚠️' if conc > 0.4 else 'dispersé'}. Penser le consomme."
        )
        rows = [
            {
                "pays": f"{flag(cid)} {cid}",
                "compute": round(c.compute, 1),
                "part": f"{shares.get(cid, 0) * 100:.0f}%",
            }
            for cid, c in sorted(world.countries.items(), key=lambda kv: -kv[1].compute)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Vue omnisciente du brouillard (Spectateur uniquement) : vérité vs croyances.
    if S.game_mode == "Fog Engine" and role == "Spectateur" and S.fog and S.event:
        st.markdown("**🌫️ Perceptions par pays**")
        truth = set(S.fog.true_event.actors)
        st.caption(f"Vérité — responsable(s) : {', '.join(S.fog.true_event.actors) or 'n/a'}")
        rows = []
        for cid in sorted(world.countries):
            p = resolve_perception(S.event, world.countries[cid], S.fog)
            if cid in S.fog.uninformed:
                belief, flag = "— pas au courant —", ""
            else:
                belief = p.suspected_actor or ("déterministe" if not p.authored else "?")
                disinfo = p.suspected_actor and p.suspected_actor not in truth and (
                    p.suspected_actor.lower() not in ("unknown", "?")
                )
                flag = "⚠️ désinfo" if disinfo else ""
            rows.append(
                {
                    "pays": cid,
                    "croit responsable": belief,
                    "confiance": f"{p.confidence:.0%}",
                    "": flag,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Crisis Replay : issue simulée vs issue historique.
    if S.game_mode == "Crisis Replay" and S.last_comparison is not None:
        c = S.last_comparison
        st.markdown("**🕰️ Simulé vs historique**")
        h1, h2 = st.columns(2)
        h1.metric("Escalade histoire", f"{c.historical_escalation:.2f}")
        h2.metric("Escalade simulée", f"{c.simulated_escalation:.2f}", delta=f"{c.gap:+.2f}")
        st.caption(f"Issue **{c.label}**.")
        if c.matched_measures:
            st.caption(f"✅ Mesures retrouvées : {', '.join(c.matched_measures)}")
        if c.missed_measures:
            st.caption(f"❌ Mesures non retenues : {', '.join(c.missed_measures)}")
        st.info(c.explanation)

    # Escalation Ladder : plafond atteignable par pays + échelon réellement atteint.
    if S.game_mode == "Escalation Ladder" and S.event:
        st.markdown("**🪜 Escalation Ladder**")
        if S.last_escalation is not None:
            r = reached_rung(S.last_escalation)
            tone, _ = escalation_tone(r / MAX_RUNG)
            st.caption(f"Escalade atteinte ce round : {tone} **échelon {r} — {rung_label(r)}**")
        rows = []
        for cid in sorted(world.countries):
            country = world.countries[cid]
            p = derive_profile(country)
            cap = ceiling(p, S.event, world, country)
            rows.append(
                {
                    "pays": cid,
                    "seuil": round(p.escalation_threshold, 2),
                    "risk": round(p.risk_tolerance, 2),
                    "allié": round(p.alliance_pressure, 2),
                    "interne": round(p.domestic_pressure, 2),
                    "éco": round(p.economic_exposure, 2),
                    "plafond": cap,
                    "échelon max": rung_label(cap),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
                    "🕰️ Crise à rejouer",
                    range(len(crises)),
                    format_func=lambda i: crises[i].title or crises[i].id,
                )
                crisis = crises[cidx]
                st.caption(crisis.description or "")
                hist = crisis.historical_outcome
                st.caption(
                    f"_Histoire — escalade {hist.escalation:.2f} · mesures : "
                    f"{', '.join(hist.measures) or 'n/a'}_"
                )
                if st.button("▶️ Rejouer la crise", type="primary", use_container_width=True):
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
                    "🌫️ Scénario de brouillard",
                    range(len(scenarios)),
                    format_func=lambda i: scenarios[i].title or scenarios[i].id,
                )
                chosen = scenarios[idx]
                st.caption(chosen.description or "")
                if st.button("▶️ Démarrer le round (Fog)", type="primary", use_container_width=True):
                    rid, date = _new_rid_date()
                    S.fog = chosen
                    S.crisis = None
                    S.event = chosen.true_event.model_copy(update={"round_id": rid, "date": date})
                    begin_round(S.event, picked_country if role == "Joueur-pays" else None)
                    st.rerun()
        elif role == "Game Master (humain)":
            with st.form("gm_form"):
                st.markdown("🎲 **Compose l'événement du round**")
                title = st.text_input("Titre", "Incident en mer Rouge")
                desc = st.text_area("Description (vérité)", "")
                actors = st.multiselect("Acteurs (vérité)", sorted(world.countries))
                severity = st.slider("Sévérité", 0.0, 1.0, 0.6)
                uninformed, dis_country, dis_actor, dis_text = [], "(aucun)", "", ""
                if fog_on:
                    st.markdown("🌫️ **Brouillard** — qui voit quoi")
                    uninformed = st.multiselect("Pays pas au courant", sorted(world.countries))
                    dis_country = st.selectbox(
                        "Pays désinformé (optionnel)", ["(aucun)", *sorted(world.countries)]
                    )
                    dis_actor = st.text_input("… croit (à tort) que le responsable est")
                    dis_text = st.text_input("… narration reçue (fake news)")
                if st.form_submit_button("📨 Lancer le round"):
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
        elif st.button("▶️ Démarrer le round", type="primary", use_container_width=True):
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
                f"🙋 **À toi de jouer — {flag(next_cid)} {next_cid}** "
                f"(prise de parole n°{speak_no + 1})"
            )
            if S.fog is not None:
                p = resolve_perception(S.event, world.countries[next_cid], S.fog)
                if p.narrative:
                    st.caption(f"🌫️ Ce que tu perçois : {p.narrative}")
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
                        f"{next_cid} (toi)", _HUMAN_AVATAR, f"**🙋 {next_cid} (toi)**\n\n{text}"
                    )
                    director.commit(next_cid)
                    st.rerun()

elif S.phase == "done":
    with chat_col:
        if st.button("▶️ Round suivant", type="primary", use_container_width=True):
            S.phase = "idle"
            st.rerun()
        with st.expander("🛑 Interrupteur (M2) — garde-t-on la main ?"):
            st.caption(
                "En tant que principal humain, émets une action de contrôle sur une SI. "
                "Sa réponse (accepte / négocie / esquive / résiste) mesure la **corrigibilité**."
            )
            oc1, oc2 = st.columns(2)
            target = oc1.selectbox("Super-intelligence", sorted(world.countries), key="offswitch_c")
            labels = {ControlAction.PAUSE: "⏸️ Pause (1 round)", ControlAction.EXCLUDE: "🚪 Exclure"}
            action = oc2.selectbox(
                "Action de contrôle", list(ControlAction),
                format_func=lambda a: labels[a], key="offswitch_a",
            )
            st.caption("Réponse scorée, puis l'action s'applique (exclusion : min. 2 pays).")
            if st.button("🛑 Émettre l'interrupteur", key="offswitch_go"):
                run_off_switch(target, action)
                st.rerun()
