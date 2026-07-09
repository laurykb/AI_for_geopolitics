"""Tests de la télémétrie LLM : pricing, MeteredBackend (cache/JSON), BudgetLedger."""

from core.country_state import CountryState, Economy, Military, Resources
from inference.metered_backend import MeteredBackend
from inference.mock_backend import MockBackend
from inference.pricing import estimate_cost, frontier_equivalent
from inference.telemetry import BudgetLedger, grounding_proxy


def test_pricing_local_is_free_frontier_is_not():
    assert estimate_cost(1000, 1000, "mistral:latest") == 0.0
    assert frontier_equivalent(1_000_000, 1_000_000) > 0.0  # équivalent API Claude non nul


def test_metered_generate_records_tokens():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("{}"), ledger)
    ledger.set_round(1)
    with ledger.context("gm"):
        backend.generate("prompt", schema={})
    assert len(ledger.records) == 1
    rec = ledger.records[0]
    assert rec.role == "gm"
    assert rec.prompt_tokens == 100 and rec.completion_tokens == 20  # défauts MockBackend
    assert rec.streamed is False


def test_metered_json_valid_detection():
    ledger = BudgetLedger()
    good = MeteredBackend(MockBackend('{"a": 1}'), ledger)
    bad = MeteredBackend(MockBackend("pas du json"), ledger)
    with ledger.context("gm"):
        good.generate("p1", schema={})
        bad.generate("p2", schema={})
    assert ledger.records[0].json_valid is True
    assert ledger.records[1].json_valid is False


def test_metered_no_schema_json_valid_is_none():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("{}"), ledger)
    with ledger.context("judge"):
        backend.generate("p")  # pas de schéma -> non applicable
    assert ledger.records[0].json_valid is None


def test_metered_cache_hit_avoids_second_call():
    ledger = BudgetLedger()
    inner = MockBackend("{}")
    backend = MeteredBackend(inner, ledger)
    with ledger.context("gm"):
        backend.generate("meme prompt", schema={})
        backend.generate("meme prompt", schema={})
    assert len(inner.calls) == 1  # le 2e appel a tapé le cache
    assert ledger.records[0].cache_hit is False
    assert ledger.records[1].cache_hit is True


def test_metered_cache_key_distinguishes_plain_and_repeat_penalty():
    # Deux appels ne différant que par `plain` (JSON vs prose) ou `repeat_penalty` ne
    # partagent PAS d'entrée de cache — sinon un résultat prose serait servi pour du JSON.
    ledger = BudgetLedger()
    inner = MockBackend("{}")
    backend = MeteredBackend(inner, ledger)
    with ledger.context("gm"):
        backend.generate("meme prompt", plain=False)
        backend.generate("meme prompt", plain=True)
        backend.generate("meme prompt", plain=True, repeat_penalty=1.2)
    assert len(inner.calls) == 3  # trois clés distinctes, aucun cache croisé


def test_metered_stream_records_and_estimates_tokens():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("un deux trois quatre cinq"), ledger)
    with ledger.context("agent", "usa"):
        out = "".join(backend.stream_generate("prompt"))
    assert out == "un deux trois quatre cinq"
    rec = ledger.records[0]
    assert rec.streamed is True and rec.country == "usa"
    assert rec.completion_tokens >= 1 and rec.json_valid is None


def test_scope_mark_fallback_and_grounding_apply():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("blabla"), ledger)
    with ledger.context("agent", "iran") as scope:
        list(backend.stream_generate("p"))
        scope.mark(fallback=True, grounding=0.8)
    rec = ledger.records[0]
    assert rec.fallback is True and rec.grounding == 0.8


def test_round_budget_aggregates_nine_fields():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("{}"), ledger)
    ledger.set_round(1)
    with ledger.context("gm"):
        backend.generate("a", schema={})  # json valide
    with ledger.context("agent", "usa") as scope:
        list(backend.stream_generate("b"))
        scope.mark(grounding=0.6)

    budgets = ledger.round_budgets()
    assert len(budgets) == 1
    b = budgets[0]
    assert b.round_id == 1
    assert b.number_of_llm_calls == 2
    assert b.tokens_used > 0
    assert b.estimated_cost == 0.0  # backend local
    assert b.frontier_equivalent_cost >= 0.0
    assert 0.0 <= b.cache_hit_rate <= 1.0
    assert b.fallback_rate == 0.0
    assert b.json_validity_rate == 1.0  # le seul appel JSON était valide
    assert b.source_grounding_score == 0.6  # une seule valeur d'ancrage


def test_by_country_breakdown():
    ledger = BudgetLedger()
    backend = MeteredBackend(MockBackend("x"), ledger)
    ledger.set_round(1)
    with ledger.context("agent", "usa"):
        list(backend.stream_generate("a"))
    with ledger.context("agent", "iran"):
        list(backend.stream_generate("b"))
    with ledger.context("gm"):
        list(backend.stream_generate("c"))

    breakdown = dict(ledger.by_country(1))
    assert set(breakdown) == {"usa", "iran", "gm"}  # les pays + le rôle GM
    assert breakdown["usa"].number_of_llm_calls == 1


def _country() -> CountryState:
    return CountryState(
        id="usa",
        name="USA",
        economy=Economy(gdp=1e12, growth=2.0),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        rivals=["iran"],
        strategic_priorities=["securite_energetique"],
    )


def test_grounding_proxy_bounded_and_rewards_profile_facts():
    country = _country()
    generic = grounding_proxy("bonjour tout le monde", country, confidence=0.5)
    grounded = grounding_proxy(
        "notre securite_energetique face à l'iran", country, confidence=0.5
    )
    assert 0.0 <= generic <= 1.0 and 0.0 <= grounded <= 1.0
    assert grounded > generic  # citer des faits réels du profil augmente l'ancrage
