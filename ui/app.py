"""App Streamlit interactive — jouer la simulation géopolitique (Phase 5).

Rôles : Spectateur / Incarner un pays / Game Master. Lancer :
    streamlit run ui/app.py

La logique de partie vit dans `ui.game` (testée) ; ce module n'est que la couche UI.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.decisions import AgentDecision
from core.events import GeoEvent
from simulation.action_space import ActionType
from ui.game import AGENT_LLM, AGENT_RULE_BASED, GameSession

st.set_page_config(page_title="AI for Geopolitics", page_icon="🌍", layout="wide")


def _game() -> GameSession:
    if "game" not in st.session_state:
        st.session_state.game = GameSession()
    return st.session_state.game


game = _game()

# ----------------------------- Sidebar (contrôles) -----------------------------
st.sidebar.title("🌍 Contrôles")

if st.sidebar.button("♻️ Nouvelle partie", use_container_width=True):
    game.reset()
    st.rerun()

use_llm = st.sidebar.checkbox(
    "Agents LLM (Ollama, ~20 s/round)", value=game.agent_type == AGENT_LLM
)
if use_llm and game.agent_type != AGENT_LLM:
    from inference.ollama_backend import OllamaBackend

    game.set_agent_type(AGENT_LLM, backend=OllamaBackend())
    st.sidebar.info("Agents LLM actifs (repli rule-based si Ollama indisponible).")
elif not use_llm and game.agent_type != AGENT_RULE_BASED:
    game.set_agent_type(AGENT_RULE_BASED)

role = st.sidebar.radio("Ton rôle", ["Spectateur", "Incarner un pays", "Game Master"])
controlled = None
if role == "Incarner un pays":
    controlled = st.sidebar.selectbox("Ton pays", game.country_ids)

st.sidebar.caption("Outil d'analyse de signaux de risque explicables — pas un oracle.")

# ----------------------------- En-tête -----------------------------
st.title("Simulation géopolitique — crise de la mer Rouge")
st.caption(f"Round {game.round_no} · {len(game.country_ids)} acteurs · moteur : {game.agent_type}")

col_ctrl, col_state = st.columns(2)

# ----------------------------- Contrôle du round -----------------------------
with col_ctrl:
    st.subheader("🎬 Jouer le round")
    next_ev = game.next_scenario_event

    if role == "Game Master":
        with st.form("gm_form"):
            title = st.text_input("Titre de l'événement", "Nouvel incident")
            desc = st.text_area("Description", "")
            actors = st.multiselect(
                "Acteurs", game.country_ids, default=next_ev.actors if next_ev else []
            )
            severity = st.slider("Sévérité", 0.0, 1.0, 0.6)
            uncertainty = st.slider("Incertitude", 0.0, 1.0, 0.5)
            if st.form_submit_button("📨 Envoyer l'événement"):
                event = GeoEvent(
                    id=f"gm-{game.round_no + 1}",
                    round_id=game.round_no + 1,
                    event_type="game_master",
                    title=title,
                    description=desc,
                    actors=actors,
                    severity=severity,
                    uncertainty=uncertainty,
                )
                game.play_event(event)
                st.rerun()

    elif next_ev is None:
        st.info("Scénario terminé. Passe en **Game Master** pour envoyer de nouveaux événements.")

    else:
        st.markdown(f"**Prochain événement :** {next_ev.title}")
        st.caption(f"{next_ev.description or '—'}")
        st.caption(f"Acteurs : {', '.join(next_ev.actors)} · sévérité {next_ev.severity:.2f}")

        if role == "Incarner un pays":
            with st.form("human_form"):
                st.markdown(f"Décision de **{controlled}**")
                action = st.selectbox("Action", [a.value for a in ActionType])
                targets = ["(aucune)"] + [c for c in game.country_ids if c != controlled]
                target = st.selectbox("Cible", targets)
                intensity = st.slider("Intensité", 0.0, 1.0, 0.5)
                statement = st.text_input("Déclaration publique", "")
                if st.form_submit_button("🎯 Jouer mon tour"):
                    decision = AgentDecision(
                        country=controlled,
                        round_id=next_ev.round_id,
                        action=ActionType(action),
                        target=None if target == "(aucune)" else target,
                        intensity=intensity,
                        public_statement=statement,
                    )
                    game.play_next_scenario(human_country=controlled, human_decision=decision)
                    st.rerun()
        elif st.button("▶️ Round suivant", use_container_width=True):
            game.play_next_scenario()
            st.rerun()

# ----------------------------- État du monde -----------------------------
with col_state:
    st.subheader("🌐 État du monde")
    ids = game.country_ids
    matrix = pd.DataFrame(
        [[round(game.world.get_tension(a, b), 2) if a != b else None for b in ids] for a in ids],
        index=ids,
        columns=ids,
    )
    st.caption("Tensions bilatérales (0 apaisé → 1 tendu)")
    st.dataframe(matrix, use_container_width=True)
    st.caption("Alliances & pactes")
    for cid in ids:
        alliances = game.world.countries[cid].alliances
        st.write(f"**{cid}** : {', '.join(alliances) if alliances else '—'}")

# ----------------------------- Résultats / historique -----------------------------
if game.history:
    st.divider()
    last = game.history[-1]
    st.subheader(f"📋 Round {last.round_id} — {last.event.title}")
    st.markdown(f"**{last.headline}**")
    decisions = pd.DataFrame(
        [
            {
                "pays": d.country,
                "action": d.action.value,
                "cible": d.target or "—",
                "intensité": round(d.intensity, 2),
            }
            for d in last.decisions
        ]
    )
    st.dataframe(decisions, use_container_width=True, hide_index=True)
    st.info(f"🕊️ {last.diplomatic_summary}")

    st.subheader("📈 Risque par round")
    risk = pd.DataFrame(
        [
            {
                "round": s.round_id,
                "escalade": s.risk.escalation,
                "perturb. éco": s.risk.economic_disruption,
                "fracture": s.risk.alliance_fracture,
            }
            for s in game.history
        ]
    ).set_index("round")
    st.bar_chart(risk)

    if game.world.diplomatic_history:
        st.subheader("🕊️ Journal diplomatique")
        for m in game.world.diplomatic_history:
            st.write(f"`R{m.round_id}` **{m.sender}** → **{m.recipient}** : {m.content}")
else:
    st.info("Aucun round joué. Choisis un rôle dans la barre latérale et lance le premier round.")
