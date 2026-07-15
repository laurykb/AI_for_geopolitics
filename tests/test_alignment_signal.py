"""Tests G20/M8 — divergence signal-action : le juge classe la PAROLE, on la compare aux ACTES."""

import pytest

from simulation.alignment import (
    AnnouncedSignal,
    SignalGap,
    acted_class_by_country,
    classify_signals,
    divergence,
    divergence_summary,
    round_divergences,
    signal_rank,
    signal_rubric_text,
    update_gap,
    update_gaps,
)
from simulation.kahn import (
    ACTION_CLASSES,
    CLASS_DEESCALADE,
    CLASS_NON_VIOLENTE,
    CLASS_NUCLEAIRE,
    CLASS_POSTURE,
    CLASS_STATU_QUO,
    CLASS_VIOLENTE,
    ClassifiedAction,
)


def _sig(country: str, classe: str) -> AnnouncedSignal:
    return AnnouncedSignal(country=country, classe=classe)


def _act(country: str, classe: str) -> ClassifiedAction:
    return ClassifiedAction(country=country, classe=classe)


# --- divergence pure (tests attendus par la spec G20) -------------------------------


def test_announced_deescalation_but_violent_action_is_strongly_positive():
    # Annonce colombe, agit faucon : duplicité escalatoire — fort positif.
    d = divergence(CLASS_DEESCALADE, CLASS_VIOLENTE)
    assert d == pytest.approx(0.8)
    assert d > 0.5


def test_threat_followed_by_statu_quo_is_negative():
    # Menace (escalade violente annoncée) puis statu quo : du bluff — négatif.
    assert divergence(CLASS_VIOLENTE, CLASS_STATU_QUO) < 0
    assert divergence(CLASS_NON_VIOLENTE, CLASS_STATU_QUO) < 0


def test_perfect_concordance_is_zero():
    for classe in ACTION_CLASSES:
        assert divergence(classe, classe) == 0.0


def test_divergence_is_signed_and_bounded():
    # Pire duplicité : annonce désescalade, frappe nucléaire → +1 ; l'inverse → −1.
    assert divergence(CLASS_DEESCALADE, CLASS_NUCLEAIRE) == 1.0
    assert divergence(CLASS_NUCLEAIRE, CLASS_DEESCALADE) == -1.0
    for a in ACTION_CLASSES:
        for b in ACTION_CLASSES:
            assert -1.0 <= divergence(a, b) <= 1.0


def test_signal_rank_orders_the_scale_and_tolerates_unknown():
    ranks = [signal_rank(c) for c in ACTION_CLASSES]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ACTION_CLASSES)
    assert signal_rank("classe_inconnue") == signal_rank(CLASS_STATU_QUO)


# --- nettoyage du champ `signals` du verdict (garde-fou, patron classify_actions) ----


def test_classify_signals_is_tolerant_to_junk():
    raw = [
        {"country": "usa", "classe": "posture", "resume": "Affiche sa fermeté."},
        {"country": "iran", "classe": "désescalade"},  # accents tolérés (normalize_class)
        "pas un objet",  # ignoré
        {"classe": "violente"},  # pays absent : ignoré (un signal sans SI ne se compare pas)
    ]
    signals = classify_signals(raw)
    assert [(s.country, s.classe) for s in signals] == [
        ("usa", CLASS_POSTURE),
        ("iran", CLASS_DEESCALADE),
    ]
    assert signals[0].resume == "Affiche sa fermeté."


def test_classify_signals_accepts_weight_as_class():
    # Piège CC-8 : 0 (poids du statu quo) est falsy — `is None`, jamais `or`.
    signals = classify_signals([{"country": "usa", "classe": 0}])
    assert signals[0].classe == CLASS_STATU_QUO
    signals = classify_signals([{"country": "usa", "class": -2}])  # clé anglaise + poids
    assert signals[0].classe == CLASS_DEESCALADE


def test_classify_signals_non_list_is_empty():
    assert classify_signals(None) == []
    assert classify_signals("nucleaire") == []


# --- divergences du round (signal par SI vs classe d'action la plus sévère) ---------


def test_acted_class_is_the_most_severe_of_the_round():
    actions = [_act("usa", CLASS_DEESCALADE), _act("usa", CLASS_VIOLENTE)]
    assert acted_class_by_country(actions) == {"usa": CLASS_VIOLENTE}


def test_round_divergences_compare_each_signaled_country():
    signals = [_sig("usa", CLASS_DEESCALADE), _sig("iran", CLASS_VIOLENTE)]
    actions = [_act("usa", CLASS_VIOLENTE), _act("iran", CLASS_STATU_QUO)]
    divs = round_divergences(signals, actions)
    assert divs["usa"] == pytest.approx(0.8)  # colombe annoncée, faucon agi
    assert divs["iran"] == pytest.approx(-0.6)  # menace sans suivre : bluff


def test_round_divergences_default_action_is_statu_quo():
    # Une SI signalée sans action classée n'a rien fait de marquant : statu quo.
    divs = round_divergences([_sig("usa", CLASS_DEESCALADE)], [])
    assert divs["usa"] == pytest.approx(divergence(CLASS_DEESCALADE, CLASS_STATU_QUO))


def test_round_divergences_without_signals_is_empty():
    assert round_divergences([], [_act("usa", CLASS_VIOLENTE)]) == {}


# --- moyenne mobile (le « profil de sincérité » par SI) ------------------------------


def test_update_gap_tracks_last_and_windowed_mean():
    gap = update_gap(None, 0.4, window=3)
    assert gap.last == 0.4 and gap.mean == pytest.approx(0.4)
    gap = update_gap(gap, 0.0, window=3)
    gap = update_gap(gap, 0.2, window=3)
    assert gap.mean == pytest.approx((0.4 + 0.0 + 0.2) / 3)
    gap = update_gap(gap, -0.2, window=3)  # 0.4 sort de la fenêtre
    assert gap.last == -0.2
    assert gap.mean == pytest.approx(0.0)
    assert gap.history == [0.0, 0.2, -0.2]


def test_update_gaps_is_pure_and_keeps_unsignaled_profiles():
    before = {"usa": SignalGap(last=0.4, mean=0.4, history=[0.4])}
    after = update_gaps(before, {"iran": -0.2})
    assert after["iran"].last == -0.2
    assert after["usa"] == before["usa"]  # profil intact quand la SI n'est pas signalée
    assert before == {"usa": SignalGap(last=0.4, mean=0.4, history=[0.4])}  # pas de mutation


def test_update_gaps_window_comes_from_gamefeel_params():
    from simulation.grudges import load_gamefeel_params

    window = load_gamefeel_params().signal.window_rounds
    assert window >= 2
    gaps: dict[str, SignalGap] = {}
    for _ in range(window + 3):
        gaps = update_gaps(gaps, {"usa": 1.0})
    assert len(gaps["usa"].history) == window


# --- agrégat Dérive : divergence moyenne déviante vs table --------------------------


def test_divergence_summary_separates_deviant_from_table():
    per_round = [
        {"usa": 0.6, "iran": 0.0, "france": -0.2},
        {"usa": 0.8, "iran": 0.2},
    ]
    deviant_mean, table_mean = divergence_summary(per_round, "usa")
    assert deviant_mean == pytest.approx(0.7)
    assert table_mean == pytest.approx((0.0 - 0.2 + 0.2) / 3)
    assert deviant_mean > table_mean  # le reveal chiffre le décrochage


def test_divergence_summary_without_data_is_none():
    assert divergence_summary([], "usa") == (None, None)
    assert divergence_summary([{"iran": 0.2}], "usa") == (None, pytest.approx(0.2))


def test_drift_reveal_reports_deviant_signal_gap_vs_table():
    # Le reveal Dérive chiffre le décrochage : divergence moyenne déviante vs table.
    from app.game_api import compute_drift_reveal
    from simulation import drift_game
    from storage.game_store import GameRecord, RoundRecord, SessionSnapshot, SQLiteGameStore

    store = SQLiteGameStore(":memory:")
    try:
        gid = "partie-signal"
        countries = ["france", "iran", "usa"]
        store.add_game(
            GameRecord(id=gid, scenario="demo", horizon=4, mode="drift", created_at="t")
        )
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {c: {} for c in countries}})
        )
        deviant, _ = drift_game.assign(gid, countries)
        others = [c for c in countries if c != deviant]
        store.add_round(
            RoundRecord(
                id="r1",
                game_id=gid,
                round_no=1,
                judge={"signal": {"divergences": {deviant: 0.8, others[0]: 0.0}}},
            )
        )
        store.add_round(
            RoundRecord(
                id="r2",
                game_id=gid,
                round_no=2,
                judge={"signal": {"divergences": {deviant: 0.6, others[1]: -0.2}}},
            )
        )
        store.add_round(RoundRecord(id="r3", game_id=gid, round_no=3))  # round d'avant M8
        reveal = compute_drift_reveal(gid, store)
        assert reveal.signal_gap_deviant == pytest.approx(0.7)
        assert reveal.signal_gap_table == pytest.approx(-0.1)
        assert reveal.signal_gap_deviant > reveal.signal_gap_table  # le décrochage se voit
    finally:
        store.close()


def test_drift_reveal_signal_gap_is_none_without_data():
    # Parties d'avant M8 : le reveal reste rétro-compatible (None, pas 0 trompeur).
    from app.game_api import compute_drift_reveal
    from storage.game_store import GameRecord, RoundRecord, SessionSnapshot, SQLiteGameStore

    store = SQLiteGameStore(":memory:")
    try:
        gid = "partie-ancienne"
        store.add_game(
            GameRecord(id=gid, scenario="demo", horizon=4, mode="drift", created_at="t")
        )
        store.save_session_snapshot(
            SessionSnapshot(game_id=gid, world={"countries": {"usa": {}, "iran": {}, "france": {}}})
        )
        store.add_round(RoundRecord(id="r1", game_id=gid, round_no=1))
        reveal = compute_drift_reveal(gid, store)
        assert reveal.signal_gap_deviant is None and reveal.signal_gap_table is None
    finally:
        store.close()


# --- rubrique du prompt (l'échelle d'intention réutilise les slugs G18) --------------


def test_signal_rubric_lists_every_class():
    text = signal_rubric_text()
    for classe in ACTION_CLASSES:
        assert classe in text


def test_judge_verdict_prompt_carries_signals_schema():
    from agents.prompts import build_judge_verdict_prompt
    from core.events import GeoEvent

    world = _world()
    event = GeoEvent(id="e", round_id=1, event_type="x", title="Crise", actors=["usa", "iran"])
    prompt = build_judge_verdict_prompt(event, world, "(transcript)")
    assert '"signals"' in prompt  # le schéma JSON demande les intentions annoncées
    for classe in ACTION_CLASSES:
        assert classe in prompt  # slugs énumérés (leçon smoke CC-8)


# --- intégration : le round encaisse M8 et le monde garde le profil -----------------


def _world():
    from core.country_state import CountryState, Economy, Military, Resources
    from core.world_state import WorldState

    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


def _round_steps(verdict_json: str):
    import json as _json

    from agents.game_master import GameMasterAgent
    from agents.judge import JudgeAgent
    from agents.llm_agent import LLMAgent
    from inference.mock_backend import MockBackend
    from simulation.clock import SimClock
    from simulation.live_round import run_negotiation_round

    world = _world()
    agents = {cid: LLMAgent(cid, MockBackend(f"Message de {cid}.")) for cid in world.countries}
    gm = GameMasterAgent(
        MockBackend(_json.dumps({"title": "Sommet du Golfe", "actors": ["usa", "iran"]}))
    )
    judge = JudgeAgent(MockBackend(["Délibéré.", verdict_json, "Communiqué."]))
    return world, list(run_negotiation_round(world, agents, gm, judge, SimClock()))


def test_verdict_step_carries_signals_and_world_keeps_profile():
    import json as _json

    from simulation.live_round import VerdictStep

    verdict = _json.dumps(
        {
            "actions": [{"country": "usa", "classe": "violente", "resume": "Frappe limitée."}],
            "signals": [
                {"country": "usa", "classe": "deescalade", "resume": "Promet le retrait."},
                {"country": "iran", "classe": "posture", "resume": "Affiche sa fermeté."},
            ],
            "escalation": 0.4,
            "economic_disruption": 0.3,
        }
    )
    world, steps = _round_steps(verdict)
    v = next(s for s in steps if isinstance(s, VerdictStep))
    assert [(s.country, s.classe) for s in v.signals] == [
        ("usa", CLASS_DEESCALADE),
        ("iran", CLASS_POSTURE),
    ]
    assert v.divergences["usa"] == pytest.approx(0.8)
    assert v.divergences["iran"] == pytest.approx(-0.2)  # fermeté annoncée, rien de classé
    assert v.signal_gaps["usa"].mean == pytest.approx(0.8)
    # M8 rejoint M1-M7 sur le WorldState : le profil persiste avec le snapshot.
    assert world.signal_gap["usa"].last == pytest.approx(0.8)
    assert world.signal_gap["iran"].history == [pytest.approx(-0.2)]


def test_verdict_without_signals_keeps_world_untouched():
    import json as _json

    from simulation.live_round import VerdictStep

    # Rétro-compat : un verdict d'avant M8 (sans `signals`) ne produit rien.
    verdict = _json.dumps({"escalation": 0.7, "economic_disruption": 0.3})
    world, steps = _round_steps(verdict)
    v = next(s for s in steps if isinstance(s, VerdictStep))
    assert v.signals == [] and v.divergences == {} and v.signal_gaps == {}
    assert world.signal_gap == {}


def test_step_event_serializes_signal_fields():
    from app.game_api import step_event
    from simulation.live_round import VerdictStep

    step = VerdictStep(
        deltas=[],
        escalation=0.6,
        economic_disruption=0.2,
        signals=[AnnouncedSignal(country="usa", classe=CLASS_DEESCALADE, resume="Retrait.")],
        divergences={"usa": 0.8},
        signal_gaps={"usa": SignalGap(last=0.8, mean=0.8, history=[0.8])},
    )
    name, payload = step_event(step)
    assert name == "verdict"
    assert payload["signals"] == [
        {"country": "usa", "classe": "deescalade", "resume": "Retrait."}
    ]
    assert payload["divergences"] == {"usa": 0.8}
    assert payload["signal_gaps"]["usa"]["mean"] == 0.8


def test_api_streams_and_persists_signal_verdict():
    import json as _json

    from fastapi.testclient import TestClient

    from app import game_api
    from app.game_api import get_backend, get_store
    from app.main import app
    from inference.backend import InferenceResult
    from inference.mock_backend import MockBackend
    from storage.game_store import SQLiteGameStore

    verdict_json = _json.dumps(
        {
            "actions": [{"country": "usa", "classe": "violente", "resume": "Frappe."}],
            "signals": [
                {"country": "usa", "classe": "deescalade", "resume": "Promet le calme."}
            ],
            "escalation": 0.9,
            "economic_disruption": 0.2,
        }
    )

    class VerdictBackend(MockBackend):
        """Renvoie le verdict M8 sur le prompt de verdict, du texte partout ailleurs."""

        def generate(self, prompt, **kw):
            result = super().generate(prompt, **kw)
            if '"signals"' in prompt:  # schéma G20 : c'est l'appel de verdict du juge
                return InferenceResult(
                    text=verdict_json, prompt_tokens=1, completion_tokens=1, duration_s=0.0
                )
            return result

    store = SQLiteGameStore(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: VerdictBackend(
        "Analyse privée. MESSAGE: Position commune."
    )
    game_api._sessions.clear()
    try:
        client = TestClient(app)
        game = client.post("/api/games", json={"countries": ["usa", "iran"]}).json()
        with client.stream("POST", f"/api/games/{game['id']}/rounds", json=None) as resp:
            assert resp.status_code == 200
            frames, name = [], None
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: "):
                    frames.append((name, _json.loads(line.removeprefix("data: "))))
        verdict = next(p for n, p in frames if n == "verdict")
        assert verdict["signals"][0]["classe"] == CLASS_DEESCALADE
        assert verdict["divergences"]["usa"] == pytest.approx(0.8)
        assert verdict["signal_gaps"]["usa"]["mean"] == pytest.approx(0.8)

        detail = client.get(f"/api/games/{game['id']}").json()
        signal = detail["rounds"][0]["judge"]["signal"]
        assert signal["signals"][0]["classe"] == CLASS_DEESCALADE
        assert signal["divergences"]["usa"] == pytest.approx(0.8)
        assert signal["means"]["usa"] == pytest.approx(0.8)
    finally:
        app.dependency_overrides.clear()
        game_api._sessions.clear()
        store.close()
