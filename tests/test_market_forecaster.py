"""Tests du forecaster LLM : parsing des probas, repli déterministe, paris (offline)."""

import pytest

from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from inference.backend import InferenceBackend
from inference.mock_backend import MockBackend
from market.engine import MarketEngine
from market.forecaster import LLMForecaster, _coerce_probs
from market.models import AccountKind, MarketStatus, ResolutionCriterion, ResolutionKind
from market.resolution import resolve_and_settle
from market.scoring import account_brier
from market.store import SQLiteMarketStore


class _FailingBackend(InferenceBackend):
    """Backend qui lève à chaque appel (simule un service indisponible)."""

    def generate(self, prompt, *, system=None, max_tokens=512, temperature=0.7, schema=None):
        raise RuntimeError("backend hors service")


def _world():
    def c(cid):
        return CountryState(
            id=cid, name=cid.upper(),
            economy=Economy(gdp=1e12, growth=2.0),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa"), c("iran")])


@pytest.fixture
def engine():
    store = SQLiteMarketStore(":memory:")
    yield MarketEngine(store)
    store.close()


def _market(engine):
    return engine.open_binary_market(
        round_id=1, question="ΔUtopie > 0 ?", b=20.0,
        criterion=ResolutionCriterion(kind=ResolutionKind.TRAJECTORY),
    )


# --- normalisation des probabilités ----------------------------------------

def test_coerce_probs_normalizes_and_orders():
    assert _coerce_probs({"probabilities": [3.0, 1.0]}, 2) == pytest.approx([0.75, 0.25])


def test_coerce_probs_binary_probability_form():
    assert _coerce_probs({"probability": 0.8}, 2) == pytest.approx([0.8, 0.2])


def test_coerce_probs_rejects_bad_shapes():
    assert _coerce_probs({"probabilities": [0.5]}, 2) is None  # mauvaise longueur
    assert _coerce_probs({"probabilities": [0.0, 0.0]}, 2) is None  # somme nulle
    assert _coerce_probs({"nope": 1}, 2) is None
    assert _coerce_probs(None, 2) is None


# --- forecast (LLM + repli) ------------------------------------------------

def test_forecast_parses_llm_probabilities(engine):
    forecaster = LLMForecaster(MockBackend('{"probabilities": [0.7, 0.3]}'))
    assert forecaster.forecast(_market(engine), _world()) == pytest.approx([0.7, 0.3])


def test_forecast_falls_back_to_uniform_on_garbage(engine):
    forecaster = LLMForecaster(MockBackend("pas du json"))
    assert forecaster.forecast(_market(engine), _world()) == pytest.approx([0.5, 0.5])


def test_forecast_falls_back_when_backend_fails(engine):
    forecaster = LLMForecaster(_FailingBackend())
    assert forecaster.forecast(_market(engine), _world()) == pytest.approx([0.5, 0.5])


def test_prompt_includes_question_and_countries(engine):
    backend = MockBackend('{"probabilities": [0.5, 0.5]}')
    LLMForecaster(backend).forecast(_market(engine), _world())
    prompt = backend.calls[0]["prompt"]
    assert "ΔUtopie > 0 ?" in prompt and "usa" in prompt and "iran" in prompt


# --- conversion en paris ---------------------------------------------------

def test_places_bet_on_underpriced_outcome(engine):
    market = _market(engine)
    yes = market.outcomes[0].id
    account = engine.create_account("Bot", kind=AccountKind.BOT)
    # croit YES à 0.8 alors que le marché est à 0.5 -> avantage sur YES
    forecaster = LLMForecaster(MockBackend('{"probabilities": [0.8, 0.2]}'))
    trades = forecaster.place_bets(engine, account.id, _world())
    assert len(trades) == 1 and trades[0].outcome_id == yes
    assert engine.store.get_position(account.id, yes).shares == forecaster.stake


def test_abstains_without_edge(engine):
    _market(engine)
    account = engine.create_account("Bot", kind=AccountKind.BOT)
    # repli uniforme (0.5/0.5) == prix du marché -> aucun avantage -> aucun pari
    forecaster = LLMForecaster(MockBackend("garbage"))
    assert forecaster.place_bets(engine, account.id, _world()) == []


def test_model_tag_names_the_forecaster(engine):
    assert LLMForecaster(MockBackend("{}"), model_tag="llama3.2:3b").model_tag == "llama3.2:3b"
    assert LLMForecaster(MockBackend("{}")).model_tag == "MockBackend"


# --- intégration : Brier « par modèle » ------------------------------------

def test_forecaster_bot_gets_scored_after_resolution(engine):
    market = _market(engine)
    bot = engine.create_account("llama3.2:3b", kind=AccountKind.BOT)
    forecaster = LLMForecaster(MockBackend('{"probabilities": [0.9, 0.1]}'))
    forecaster.place_bets(engine, bot.id, _world())

    market = engine.store.get_market(market.id)
    resolve_and_settle(engine.store, market, _blank_summary(), delta_utopia=0.05)  # YES gagne
    # le bot a parié YES avec conviction -> il a un score de Brier (calibration par modèle)
    assert account_brier(engine.store, bot.id) is not None
    assert engine.store.get_market(market.id).status is MarketStatus.RESOLVED


def _blank_summary():
    from core.events import GeoEvent
    from core.risk import RiskScore
    from core.rounds import RoundSummary

    return RoundSummary(
        round_id=1,
        event=GeoEvent(id="e", round_id=1, event_type="c", title="T"),
        decisions=[],
        risk=RiskScore(
            round_id=1, escalation=0.0, economic_disruption=0.0,
            alliance_fracture=0.0, uncertainty=0.0,
        ),
    )
