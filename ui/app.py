"""Théâtre live — négociation arbitrée des super-intelligences (temps réel).

Un G7 dont on voit tous les messages : le Game Master pose un événement, les
super-intelligences **négocient sur plusieurs passes** (chacune son tour, streamé, avec
badge modèle + chrono), puis un **juge LLM** arbitre les attributs (raisonnement visible).
Lancer : streamlit run ui/app.py  (Ollama + mistral ; repli si absent).
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from agents.game_master import GameMasterAgent
from agents.judge import JudgeAgent
from agents.llm_agent import LLMAgent
from inference.ollama_backend import OllamaBackend
from simulation.clock import SimClock
from simulation.live_round import (
    EventStep,
    JudgeTokenStep,
    MessageDoneStep,
    SummaryStep,
    TokenStep,
    TurnStartStep,
    VerdictStep,
    run_negotiation_round,
)
from simulation.loader import load_world

st.set_page_config(page_title="AI for Geopolitics — Live", page_icon="🌍", layout="wide")

_GM_AVATAR = "🎲"
_AGENT_AVATAR = "🧠"
_JUDGE_AVATAR = "⚖️"
_MAX_PASSES = 2


def init_session() -> None:
    world = load_world()
    backend = OllamaBackend()
    st.session_state.world = world
    st.session_state.agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
    st.session_state.gm = GameMasterAgent(backend)
    st.session_state.judge = JudgeAgent(backend)
    st.session_state.clock = SimClock()
    st.session_state.transcript = []  # {who, avatar, md} persistants
    st.session_state.recent = []
    st.session_state.round_no = 0
    st.session_state.last_deltas = []
    st.session_state.last_escalation = None
    st.session_state.elapsed = 0.0


if "world" not in st.session_state:
    init_session()

world = st.session_state.world
clock = st.session_state.clock

# ------------------------------ Sidebar ------------------------------
st.sidebar.title("🌍 Contrôles")
if st.sidebar.button("♻️ Nouvelle partie", use_container_width=True):
    init_session()
    st.rerun()
st.sidebar.caption(
    "**Spectateur** — les super-intelligences négocient chacune leur tour (mistral 7B local), "
    f"sur **{_MAX_PASSES} passes**, puis un **juge** arbitre les attributs. Un round ≈ 1 min. "
    "Repli rule-based si Ollama est éteint."
)

# ------------------------------ Bandeau ------------------------------
st.title("🌍 AI for Geopolitics — le G7 des super-intelligences")
b1, b2, b3, b4 = st.columns(4)
b1.metric("📅 Date", clock.iso)
b2.metric("🔄 Round", st.session_state.round_no)
b3.metric("⏱️ Dernier round", f"{st.session_state.elapsed:.0f} s")
b4.metric("🎭 Acteurs", len(world.countries))

play = st.button("▶️ Jouer le round", type="primary", use_container_width=True)

chat_col, state_col = st.columns([2, 1])

with chat_col:
    st.subheader("🗣️ Négociation")
    for entry in st.session_state.transcript:
        with st.chat_message(entry["who"], avatar=entry["avatar"]):
            st.markdown(entry["md"])

with state_col:
    st.subheader("📊 Dernier round")
    if st.session_state.last_escalation is not None:
        st.markdown(f"**Escalade (juge)** : `{st.session_state.last_escalation:.2f}`")
    if st.session_state.last_deltas:
        df = pd.DataFrame(
            [
                {
                    "pays": d.country,
                    "attribut": d.label,
                    "avant": round(d.before, 3),
                    "après": round(d.after, 3),
                    "Δ": round(d.change, 3),
                }
                for d in st.session_state.last_deltas
            ]
        )
        st.caption("Attributs arbitrés")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Aucun round joué pour l'instant.")


def play_round() -> None:
    """Streame la négociation arbitrée, étape par étape, dans le tchat."""
    start = time.perf_counter()
    placeholder = None
    buffer = ""
    header = ""

    for step in run_negotiation_round(
        world,
        st.session_state.agents,
        st.session_state.gm,
        st.session_state.judge,
        clock,
        max_passes=_MAX_PASSES,
        recent=st.session_state.recent,
    ):
        if isinstance(step, EventStep):
            ev = step.event
            md = (
                f"**{ev.title}**  \n{ev.description or '—'}  \n"
                f"_acteurs : {', '.join(ev.actors) or 'n/a'} · sévérité {ev.severity:.2f}_"
            )
            with chat_col.chat_message("Game Master", avatar=_GM_AVATAR):
                st.markdown(md)
            st.session_state.transcript.append(
                {"who": "Game Master", "avatar": _GM_AVATAR, "md": f"🎲 {md}"}
            )
            st.session_state.recent.append(ev.title)

        elif isinstance(step, TurnStartStep):
            header = f"**{step.country}** · `{step.model}` · passe {step.pass_no + 1} — réfléchit…"
            buffer = ""
            placeholder = chat_col.chat_message(step.country, avatar=_AGENT_AVATAR).empty()
            placeholder.markdown(header)

        elif isinstance(step, TokenStep):
            buffer += step.token
            if placeholder is not None:
                placeholder.markdown(f"{header}\n\n{buffer} ▌")

        elif isinstance(step, MessageDoneStep):
            final = f"**{step.country}** · `⏱ {step.seconds:.1f}s`\n\n{buffer.strip()}"
            if placeholder is not None:
                placeholder.markdown(final)
            st.session_state.transcript.append(
                {"who": step.country, "avatar": _AGENT_AVATAR, "md": final}
            )
            placeholder = None

        elif isinstance(step, JudgeTokenStep):
            if placeholder is None or header != "__judge__":
                header = "__judge__"
                buffer = ""
                placeholder = chat_col.chat_message("Juge", avatar=_JUDGE_AVATAR).empty()
            buffer += step.token
            placeholder.markdown(f"**⚖️ Arbitrage**\n\n{buffer} ▌")

        elif isinstance(step, VerdictStep):
            st.session_state.last_deltas = step.deltas
            st.session_state.last_escalation = step.escalation
            lines = [
                f"- {d.country} · {d.label} : {d.before:.2f} → {d.after:.2f}" for d in step.deltas
            ]
            verdict_md = (
                f"**⚖️ Arbitrage**\n\n{buffer.strip()}\n\n"
                f"**Attributs** (escalade {step.escalation:.2f}) :\n"
                + ("\n".join(lines) or "aucun changement")
            )
            if placeholder is not None:
                placeholder.markdown(verdict_md)
            st.session_state.transcript.append(
                {"who": "Juge", "avatar": _JUDGE_AVATAR, "md": verdict_md}
            )
            placeholder = None

        elif isinstance(step, SummaryStep):
            st.session_state.round_no = step.summary.round_id

    st.session_state.elapsed = time.perf_counter() - start
    st.rerun()


if play:
    play_round()
