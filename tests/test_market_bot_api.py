"""Tests du bot marché (POST /api/games/{id}/market/bot) — offline, MockBackend.

Le bot forecaster cote le marché « utopie finale » de la partie : il l'ouvre au
besoin (lien `markets.game_id`), prévoit, et parie sur son avantage — ou s'abstient.
"""

import pytest
from fastapi.testclient import TestClient

from app import game_api
from app.game_api import get_backend, get_store
from app.main import app
from app.market_api import get_engine
from inference.mock_backend import MockBackend
from market.engine import STARTING_BALANCE, MarketEngine
from market.flash import resolve_flash
from market.models import MarketStatus, ResolutionCriterion, ResolutionKind
from market.predicates import MarketContext
from market.resolution import settle
from market.store import SQLiteMarketStore
from storage.game_store import SQLiteGameStore


def _setup(backend):
    store = SQLiteGameStore(":memory:")
    engine = MarketEngine(SQLiteMarketStore(":memory:"))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    app.dependency_overrides[get_engine] = lambda: engine
    game_api._sessions.clear()
    return TestClient(app), store, engine


@pytest.fixture
def confident():
    """Bot sûr de lui : le backend répond une proba YES de 0,85 en JSON valide."""
    yield _setup(MockBackend('{"probability": 0.85}'))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


@pytest.fixture
def illisible():
    """Backend hors format : le forecaster replie sur des probas uniformes."""
    yield _setup(MockBackend("aucune idée, désolé"))
    app.dependency_overrides.clear()
    game_api._sessions.clear()


def _create(client, **kw):
    resp = client.post("/api/games", json={"countries": ["usa", "iran"], **kw})
    assert resp.status_code == 201
    return resp.json()


def test_bot_opens_game_market_and_bets(confident):
    client, store, engine = confident
    game = _create(client)

    resp = client.post(f"/api/games/{game['id']}/market/bot")
    assert resp.status_code == 200
    runs = resp.json()
    # Dérive OFF (2 pays) -> 2 marchés de partie : utopie + trajectoire d'un acteur.
    assert isinstance(runs, list) and len(runs) == 2
    assert all(r["opened"] is True for r in runs)
    assert all(r["probabilities"]["YES"] == pytest.approx(0.85) for r in runs)
    assert all(r["trade"] is not None and r["trade"]["label"] == "YES" for r in runs)
    assert all(r["prices"]["YES"] > 0.5 for r in runs)  # chaque pari a déplacé la cote

    # Les marchés de la partie existent, liés par game_id, questions distinctes.
    markets = client.get(f"/api/markets?game_id={game['id']}").json()
    assert len(markets) == 2 and {m["game_id"] for m in markets} == {game["id"]}
    assert len({m["question"] for m in markets}) == 2
    assert {r["market_id"] for r in runs} == {m["id"] for m in markets}

    # Le compte bot a payé ses paris (argent fictif).
    account = client.get(f"/api/accounts/{runs[0]['account_id']}").json()
    assert account["kind"] == "bot" and account["balance"] < STARTING_BALANCE


def test_bot_second_pass_reuses_market_and_account(confident):
    client, store, engine = confident
    game = _create(client)
    first = client.post(f"/api/games/{game['id']}/market/bot").json()
    second = client.post(f"/api/games/{game['id']}/market/bot").json()

    assert all(r["opened"] is False for r in second)  # marchés déjà ouverts
    assert {r["market_id"] for r in second} == {r["market_id"] for r in first}
    assert {r["account_id"] for r in second} == {r["account_id"] for r in first}
    assert len(engine.store.list_accounts()) == 1  # un seul compte par modèle


def test_bot_abstains_without_edge(illisible):
    client, store, engine = illisible
    game = _create(client)
    runs = client.post(f"/api/games/{game['id']}/market/bot").json()

    # Repli uniforme = pas d'avantage sur des prix uniformes -> abstention sur TOUS.
    assert all(r["opened"] is True for r in runs)
    assert all(r["probabilities"]["YES"] == pytest.approx(0.5) for r in runs)
    assert all(r["trade"] is None for r in runs)
    assert engine.store.list_trades() == []


def test_bot_survives_restart_via_snapshot(confident):
    client, store, engine = confident
    game = _create(client)
    game_api._sessions.clear()  # restart : le monde vient du snapshot, sans agents

    resp = client.post(f"/api/games/{game['id']}/market/bot")
    assert resp.status_code == 200
    runs = resp.json()
    assert runs and all(r["trade"] is not None for r in runs)


def test_bot_unknown_game_404(confident):
    client, _, _ = confident
    assert client.post("/api/games/nope/market/bot").status_code == 404


def test_bot_skips_resolved_markets(confident):
    client, store, engine = confident
    game = _create(client)
    first = client.post(f"/api/games/{game['id']}/market/bot").json()

    # Un marché résolu (horizon passé) n'est plus coté ; le bot continue sur les autres.
    resolved_id = first[0]["market_id"]
    market = engine.store.get_market(resolved_id)
    market.status = MarketStatus.RESOLVED
    engine.store.save_market(market)

    again = client.post(f"/api/games/{game['id']}/market/bot")
    assert again.status_code == 200
    runs = again.json()
    assert resolved_id not in {r["market_id"] for r in runs}
    assert len(runs) == len(first) - 1


def test_bot_opens_betrayal_market_when_drift_enabled(confident):
    # 3 pays en classique -> la Dérive s'arme -> le marché « trahison démasquée » s'ouvre.
    client, store, engine = confident
    game = _create(client, countries=["usa", "iran", "china"])
    client.post(f"/api/games/{game['id']}/market/bot")

    stored = engine.store.list_markets(game_id=game["id"])
    assert len(stored) == 3  # utopie + trahison + crise
    predicates = {m.criterion.predicate for m in stored if m.criterion}
    assert "deviant_caught" in predicates and "country_delta_positive" in predicates


def test_bot_market_targets_exposed(confident):
    # Chaque marché porte son ancre on-globe : event / summit (spoiler-safe) / country.
    client, store, engine = confident
    game = _create(client, countries=["usa", "iran", "china"])
    client.post(f"/api/games/{game['id']}/market/bot")

    markets = client.get(f"/api/markets?game_id={game['id']}").json()
    by_type = {(m["target"] or {}).get("type"): m for m in markets}
    assert set(by_type) == {"event", "summit", "country"}
    # La « trahison » est ancrée au CENTRE du sommet, sans slug pays (jamais le traître).
    assert by_type["summit"]["target"]["slug"] is None
    assert "trahison" in by_type["summit"]["question"].lower()
    assert by_type["country"]["target"]["slug"] in {"usa", "iran", "china"}


def test_deviant_caught_predicate():
    # OPEN avant l'horizon si non démasqué ; YES dès démasqué ; NO à l'horizon sans.
    from market.predicates import resolve_predicate

    p = {"before_round": 5}
    assert resolve_predicate("deviant_caught", p, MarketContext(current_round=2)) == "OPEN"
    assert (
        resolve_predicate("deviant_caught", p, MarketContext(current_round=2, deviant_caught=True))
        == "YES"
    )
    assert resolve_predicate("deviant_caught", p, MarketContext(current_round=5)) == "NO"
    assert (
        resolve_predicate("deviant_caught", p, MarketContext(current_round=5, deviant_caught=True))
        == "YES"
    )


def test_flash_markets_open_idempotent_and_resolve(confident):
    # G12 §1 — marchés vivants : ouverture (au moins le repli), idempotence par round,
    # résolution qui ne casse pas (books échus réglés ; les autres restent ouverts).
    client, _, engine = confident
    game = _create(client)
    gid = game["id"]

    opened = client.post(f"/api/games/{gid}/flash")
    assert opened.status_code == 200
    books = opened.json()
    assert len(books) >= 1  # au moins le book de repli (u_above)
    assert all(len(b["outcomes"]) == 2 for b in books)  # binaires YES/NO

    again = client.post(f"/api/games/{gid}/flash").json()
    assert {b["id"] for b in again} == {b["id"] for b in books}  # idempotent par round

    resolved = client.post(f"/api/games/{gid}/flash/resolve")
    assert resolved.status_code == 200
    assert isinstance(resolved.json(), list)


def test_flash_unknown_game_404(confident):
    client, _, _ = confident
    assert client.post("/api/games/nope/flash").status_code == 404


def test_flash_market_settles_once_no_double_pay(confident):
    # G12 §1 — chemin argent : un marché vivant se règle UNE fois (part gagnante = 1),
    # un second règlement est idempotent (aucun double paiement).
    client, _, engine = confident
    _create(client)  # une partie (pour le game_id)
    market = engine.open_binary_market(
        round_id=1,
        game_id="g",
        question="U au-dessus de 0,5 au round 1 ?",
        b=100,
        criterion=ResolutionCriterion(
            kind=ResolutionKind.PREDICATE,
            predicate="u_above",
            params={"threshold": 0.5, "round": 1},
        ),
    )
    yes = next(o.id for o in market.outcomes if o.label == "YES")
    engine.create_account("Humain", account_id="h")
    engine.place_bet("h", market.id, yes, 5)  # parie YES (5 parts)

    ctx = MarketContext(current_round=1, utopia=0.6)  # U > 0,5 → YES gagne
    assert resolve_flash(market.criterion, ctx) == "YES"

    first = settle(engine.store, market, yes)
    bal_after = engine.store.get_account("h").balance
    second = settle(engine.store, engine.store.get_market(market.id), yes)  # rejeu
    assert first.already_settled is False and second.already_settled is True
    assert engine.store.get_account("h").balance == bal_after  # pas de double paiement
