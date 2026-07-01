"""Théâtre live — on regarde les super-intelligences délibérer en temps réel (Phase live).

Un G7 dont on voit tous les messages : le Game Master génère un événement, chaque
super-intelligence **raisonne en direct** (streaming), puis le moteur déterministe applique
les deltas d'attributs. Lancer : streamlit run ui/app.py  (Ollama + mistral pour le LLM ;
repli rule-based si Ollama absent).
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from agents.game_master import GameMasterAgent
from agents.llm_agent import LLMAgent
from inference.ollama_backend import OllamaBackend
from simulation.clock import SimClock
from simulation.live_round import (
    AgentDoneStep,
    DeltasStep,
    EventStep,
    RiskStep,
    SummaryStep,
    TokenStep,
    run_live_round,
)
from simulation.loader import load_world

st.set_page_config(page_title="AI for Geopolitics — Live", page_icon="🌍", layout="wide")

_AGENT_AVATAR = "🧠"
_GM_AVATAR = "🎲"


def init_session() -> None:
    world = load_world()
    backend = OllamaBackend()
    st.session_state.world = world
    st.session_state.agents = {cid: LLMAgent(cid, backend) for cid in world.countries}
    st.session_state.gm = GameMasterAgent(backend)
    st.session_state.clock = SimClock()
    st.session_state.transcript = []  # entrées {who, avatar, md} persistantes
    st.session_state.recent = []
    st.session_state.round_no = 0
    st.session_state.last_deltas = []
    st.session_state.last_risk = None
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
    "**Spectateur** — les super-intelligences (mistral 7B local) réfléchissent chacune leur "
    "tour, en direct. Un round ≈ 1-3 min. Repli rule-based si Ollama est éteint."
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

# Transcript persistant (rounds déjà joués)
with chat_col:
    st.subheader("🗣️ Délibérations")
    for entry in st.session_state.transcript:
        with st.chat_message(entry["who"], avatar=entry["avatar"]):
            st.markdown(entry["md"])

# Panneau d'état (deltas + risque du dernier round)
with state_col:
    st.subheader("📊 Dernier round")
    if st.session_state.last_risk is not None:
        r = st.session_state.last_risk
        st.markdown(
            f"**Risque** — escalade `{r.escalation:.2f}` · éco `{r.economic_disruption:.2f}` · "
            f"fracture `{r.alliance_fracture:.2f}`"
        )
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
        st.caption("Attributs modifiés")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Aucun round joué pour l'instant.")


def play_round() -> None:
    """Itère le round observable et streame chaque étape dans le tchat."""
    start = time.perf_counter()
    current: str | None = None
    placeholder = None
    buffer = ""

    for step in run_live_round(
        world,
        st.session_state.agents,
        st.session_state.gm,
        clock,
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

        elif isinstance(step, TokenStep):
            if step.country != current:
                current = step.country
                buffer = ""
                placeholder = chat_col.chat_message(step.country, avatar=_AGENT_AVATAR).empty()
            buffer += step.token
            placeholder.markdown(buffer + " ▌")

        elif isinstance(step, AgentDoneStep):
            dec = step.decision
            target = f" → {dec.target}" if dec.target else ""
            md = f"{step.text}\n\n**➡️ {dec.action.value}{target}** · intensité {dec.intensity:.2f}"
            if placeholder is not None:
                placeholder.markdown(md)
            st.session_state.transcript.append(
                {"who": step.country, "avatar": _AGENT_AVATAR, "md": md}
            )
            current, placeholder = None, ""

        elif isinstance(step, DeltasStep):
            st.session_state.last_deltas = step.deltas
        elif isinstance(step, RiskStep):
            st.session_state.last_risk = step.risk
        elif isinstance(step, SummaryStep):
            st.session_state.round_no = step.summary.round_id

    st.session_state.elapsed = time.perf_counter() - start
    st.rerun()


if play:
    play_round()
