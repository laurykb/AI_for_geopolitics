"""Théâtre live — négociation arbitrée, avec rôles humains (temps réel).

Trois rôles : **Spectateur** (on regarde), **Game Master humain** (on écrit l'événement),
**Joueur-pays** (on intervient dans la négociation : à son tour, ça pause, on écrit, les
super-intelligences reprennent). Round piloté tour par tour (un tour = un rerun) pour
permettre la pause. Lancer : streamlit run ui/app.py  (Ollama + mistral ; repli si absent).
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from core.events import GeoEvent
from inference.metered_backend import MeteredBackend
from inference.ollama_backend import OllamaBackend
from inference.telemetry import BudgetLedger, grounding_proxy
from simulation.clock import SimClock
from simulation.crisis import compare_outcome, load_crises
from simulation.fog import FogScenario, load_fog_scenarios, resolve_perception
from simulation.loader import load_world
from simulation.negotiation import (
    NegotiationMessage,
    TurnDirector,
    apply_verdict,
    speaking_order,
    split_reasoning,
    support_levels,
    update_memories,
)

st.set_page_config(page_title="AI for Geopolitics — Live", page_icon="🌍", layout="wide")

_GM_AVATAR, _AGENT_AVATAR, _JUDGE_AVATAR, _HUMAN_AVATAR = "🎲", "🧠", "⚖️", "🙋"
_COMMUNIQUE_AVATAR = "📜"
_MAX_PASSES = 2


def init_session() -> None:
    world = load_world()
    ledger = BudgetLedger()
    backend = MeteredBackend(OllamaBackend(), ledger)
    st.session_state.ledger = ledger
    st.session_state.world = world
    st.session_state.agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
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
    st.session_state.crisis = None  # Crisis rejouée (mode Crisis Replay)
    st.session_state.last_communique = ""
    st.session_state.last_comparison = None  # OutcomeComparison du dernier rejeu


if "world" not in st.session_state:
    init_session()

S = st.session_state
world = S.world
clock = S.clock
chat = None  # défini plus bas (colonne du tchat)


def add_display(who: str, avatar: str, md: str, reasoning: str = "") -> None:
    S.transcript.append({"who": who, "avatar": avatar, "md": md, "reasoning": reasoning})


def stream_ai_turn(country: str, pass_no: int) -> None:
    """Streame la prise de parole : la pensée privée dans un expander, le message dans la bulle."""
    agent: LLMAgent = S.agents[country]
    msg = chat.chat_message(country, avatar=_AGENT_AVATAR)
    with msg:
        st.markdown(
            f"**{country}** · `{agent.model_tag}` · prise de parole n°{pass_no + 1} — réfléchit…"
        )
        think_holder = st.expander("🧠 Réflexion privée", expanded=True).empty()
        public_holder = st.empty()

    buffer, t0 = "", time.perf_counter()
    perceived = resolve_perception(S.event, world.countries[country], S.fog)  # Fog ou déterministe
    with S.ledger.context("agent", country) as scope:
        for token in agent.stream_negotiation_message(S.event, world, S.messages, perceived):
            buffer += token
            reasoning, text = split_reasoning(buffer)
            if reasoning:  # marqueur atteint : la pensée est figée, le message public s'écrit
                think_holder.markdown(reasoning)
                public_holder.markdown(f"{text} ▌")
            else:  # pas encore de marqueur : tout ce qui arrive est la pensée en cours
                think_holder.markdown(f"{buffer.strip()} ▌")
        reasoning, text = split_reasoning(buffer)
        scope.mark(
            grounding=grounding_proxy(text, world.countries[country], perceived.confidence),
            fallback="backend indisponible" in text,
        )

    seconds = time.perf_counter() - t0
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
    think_holder.markdown(reasoning or "_(pas de réflexion séparée)_")
    final = f"**{country}** · `⏱ {seconds:.1f}s`\n\n{text}"
    public_holder.markdown(final)
    add_display(country, _AGENT_AVATAR, final, reasoning=reasoning)


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
    S.round_no += 1
    S.elapsed = time.perf_counter() - S.round_start
    S.phase = "done"


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
    budget = _MAX_PASSES * len(S.agents)
    S.director = TurnDirector(
        speaking_order(list(S.agents), event), max_turns=budget, priority=human_country
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
    S.phase = "negotiating"


# ------------------------------ Sidebar ------------------------------
st.sidebar.title("🌍 Contrôles")
if st.sidebar.button("♻️ Nouvelle partie", use_container_width=True):
    init_session()
    st.rerun()
S.game_mode = st.sidebar.radio(
    "Mode de jeu", ["Classique", "Fog Engine", "Crisis Replay"], disabled=S.phase != "idle"
)
role = st.sidebar.radio(
    "Ton rôle", ["Spectateur", "Game Master (humain)", "Joueur-pays"], disabled=S.phase != "idle"
)
picked_country = None
if role == "Joueur-pays":
    picked_country = st.sidebar.selectbox(
        "Ton pays", sorted(world.countries), disabled=S.phase != "idle"
    )
if S.game_mode == "Fog Engine":
    st.sidebar.caption(
        "🌫️ **Fog Engine** : chaque pays ne voit pas la même info (acteur suspecté, confiance, "
        "délai, **désinformation**). Spectateur = omniscient (vérité + perceptions) ; Joueur-pays "
        "= ne voit QUE la perception de son pays (parfois fausse)."
    )
if S.game_mode == "Crisis Replay":
    st.sidebar.caption(
        "🕰️ **Crisis Replay** : rejoue une crise passée (dataset fixe) et compare l'issue "
        "**simulée** à l'issue **historique** (escalade, mesures) — et pourquoi ça diverge. "
        "Rejoue autant de fois que tu veux."
    )
st.sidebar.caption(
    "Négociation **dynamique** (mistral 7B local) : les pays parlent selon leur **engagement** "
    "(reprendre la parole, réagir quand on les interpelle, ou se taire), puis un **juge** arbitre. "
    "En Joueur-pays, la table **s'arrête à ton tour**. Repli rule-based si Ollama éteint."
)

# ------------------------------ Bandeau ------------------------------
st.title("🌍 AI for Geopolitics — le G7 des super-intelligences")
b1, b2, b3, b4 = st.columns(4)
b1.metric("📅 Date", clock.iso)
b2.metric("🔄 Round", S.round_no)
b3.metric("⏱️ Dernier round", f"{S.elapsed:.0f} s")
b4.metric("🎭 Rôle", role.split()[0])

tab_theatre, tab_budget = st.tabs(["🗣️ Théâtre", "💸 LLM Budget"])
with tab_budget:
    render_budget_tab()

with tab_theatre:
    chat_col, state_col = st.columns([2, 1])
chat = chat_col

with chat_col:
    st.subheader("🗣️ Négociation")
    for entry in S.transcript:
        with st.chat_message(entry["who"], avatar=entry["avatar"]):
            if entry.get("reasoning"):
                with st.expander("🧠 Réflexion privée"):
                    st.markdown(entry["reasoning"])
            st.markdown(entry["md"])

with state_col:
    st.subheader("📊 Dernier round")
    if S.last_escalation is not None:
        st.markdown(f"**Escalade (juge)** : `{S.last_escalation:.2f}`")
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
            with st.form(f"human_turn_{director.turns_taken}"):
                st.markdown(f"🙋 **Ton tour — {next_cid} (prise de parole n°{speak_no + 1})**")
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
