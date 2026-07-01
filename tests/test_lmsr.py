"""Tests du cœur LMSR (pur, offline) : invariants du market maker à perte bornée."""

import math

import pytest

from market.lmsr import cost, cost_to_trade, max_loss, price


def test_prices_sum_to_one():
    for q, b in ([[0, 0], 10], [[3, -1, 2], 5], [[0.5, 0.5, 0.5, 0.5], 1.0]):
        assert sum(price(q, b)) == pytest.approx(1.0)
        assert all(0.0 <= p <= 1.0 for p in price(q, b))


def test_uniform_q_gives_equal_prices():
    p = price([0, 0, 0, 0], 7.0)
    assert p == pytest.approx([0.25, 0.25, 0.25, 0.25])


def test_max_loss_is_b_ln_n():
    assert max_loss(10, 2) == pytest.approx(10 * math.log(2))
    assert max_loss(4, 5) == pytest.approx(4 * math.log(5))


def test_cost_monotone_in_shares():
    q, b = [0, 0], 10.0
    costs = [cost_to_trade(q, b, 0, s) for s in (1, 2, 5, 10)]
    assert costs == sorted(costs)  # plus on achète, plus ça coûte
    assert all(c > 0 for c in costs)


def test_buying_raises_that_outcome_price():
    q, b = [0, 0, 0], 10.0
    before = price(q, b)
    after = price([q[0] + 20, q[1], q[2]], b)
    assert after[0] > before[0]  # l'outcome acheté monte
    assert after[1] < before[1] and after[2] < before[2]  # les autres baissent


def test_buy_positive_sell_negative_and_round_trip_is_neutral():
    q, b, i, delta = [1, -2, 0], 8.0, 1, 4.0
    buy = cost_to_trade(q, b, i, delta)
    assert buy > 0
    after = list(q)
    after[i] += delta
    sell = cost_to_trade(after, b, i, -delta)
    assert sell < 0
    assert buy + sell == pytest.approx(0.0, abs=1e-9)  # aller-retour neutre


def test_numerically_stable_on_large_q():
    p = price([1000, 0], 10.0)  # ne doit pas overflow
    assert p[0] == pytest.approx(1.0) and p[1] == pytest.approx(0.0, abs=1e-9)
    assert cost([1000, 0], 10.0) == pytest.approx(1000.0, abs=1e-6)  # ≈ max(q) quand un domine


def test_marginal_cost_matches_price():
    # Pour un petit Δ, le coût d'achat ≈ prix courant × Δ (dérivée de C = p_i).
    q, b, i, eps = [2, -1, 3], 6.0, 0, 1e-4
    approx_price = cost_to_trade(q, b, i, eps) / eps
    assert approx_price == pytest.approx(price(q, b)[i], abs=1e-3)


def test_cost_increases_when_qi_increases():
    b = 5.0
    assert cost([2, 0], b) > cost([1, 0], b)  # coût monotone en q_i


def test_guards():
    with pytest.raises(ValueError):
        cost([0, 0], 0)  # b <= 0
    with pytest.raises(ValueError):
        price([0, 0], -1)
    with pytest.raises(ValueError):
        max_loss(-2, 3)
    with pytest.raises(ValueError):
        cost([], 5)  # q vide
    with pytest.raises(ValueError):
        cost_to_trade([0, 0], 5, 9, 1)  # outcome hors bornes
