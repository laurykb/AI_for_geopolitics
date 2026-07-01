"""Résolution des marchés : le Juge est l'oracle (spéc `docs/spec_market.md` §4).

À la fin d'un round, on mappe le contexte (RoundSummary, ΔUtopie, vainqueur arbitré) vers
l'**outcome gagnant** via des **mappers purs et testables**, puis on **règle** les positions :
part gagnante = **1 crédit**, perdante = **0**. Idempotent : un marché ne se règle qu'une fois.
Argent **fictif**. C'est ici que se branche le hook trajectoire « L'indice Utopie monte-t-il ? ».
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from market.models import Market, MarketStatus, ResolutionKind
from market.store import MarketStore

if TYPE_CHECKING:  # types seulement (duck-typing à l'exécution) -> market reste découplé
    from collections.abc import Sequence

    from core.rounds import RoundSummary
    from simulation.trajectory import TrajectoryState

YES = "YES"
NO = "NO"


class ResolutionError(Exception):
    """Marché non résolvable (critère manquant, issue inconnue, contexte insuffisant)."""


# --- mappers purs (renvoient le LABEL de l'outcome gagnant) --------------------


def action_label(
    summary: RoundSummary, *, country: str, action: str, target: str | None = None
) -> str:
    """YES si une décision `(country, action[, target])` figure dans le round, sinon NO."""
    hit = any(
        d.country == country and d.action == action and (target is None or d.target == target)
        for d in summary.decisions
    )
    return YES if hit else NO


def threshold_label(delta: float) -> str:
    """YES si la grandeur seuil a monté sur le round (Δ > 0) — ex. l'indice Utopie."""
    return YES if delta > 0.0 else NO


def council_label(winner: str, labels: list[str]) -> str:
    """Outcome catégoriel gagnant = le vainqueur arbitré (doit être une issue du marché)."""
    if winner not in labels:
        raise ResolutionError(f"vainqueur '{winner}' hors des issues {labels}")
    return winner


# --- helpers ------------------------------------------------------------------


def utopia_delta(history: Sequence[TrajectoryState]) -> float:
    """ΔUtopie du dernier round = `history[-1].utopia − history[-2].utopia` (0 si < 2 points)."""
    if len(history) < 2:
        return 0.0
    return history[-1].utopia - history[-2].utopia


def _outcome_id_for_label(market: Market, label: str) -> str:
    for outcome in market.outcomes:
        if outcome.label == label:
            return outcome.id
    raise ResolutionError(f"aucune issue '{label}' dans le marché {market.id}")


# --- dispatch + settlement ----------------------------------------------------


def resolve(
    market: Market,
    summary: RoundSummary,
    *,
    delta_utopia: float = 0.0,
    council_winner: str | None = None,
) -> str:
    """Détermine l'`outcome_id` gagnant d'un marché selon son critère (Juge = oracle)."""
    crit = market.criterion
    if crit is None:
        raise ResolutionError(f"marché {market.id} sans critère de résolution")
    if crit.kind is ResolutionKind.ACTION:
        if crit.country is None or crit.action is None:
            raise ResolutionError("critère action : country et action requis")
        label = action_label(summary, country=crit.country, action=crit.action, target=crit.target)
    elif crit.kind is ResolutionKind.TRAJECTORY:
        label = threshold_label(delta_utopia)
    elif crit.kind is ResolutionKind.COUNCIL:
        if council_winner is None:
            raise ResolutionError("critère conseil : council_winner requis")
        label = council_label(council_winner, [o.label for o in market.outcomes])
    else:  # pragma: no cover - garde-fou exhaustif
        raise ResolutionError(f"type de résolution inconnu : {crit.kind}")
    return _outcome_id_for_label(market, label)


class SettlementResult(BaseModel):
    """Bilan d'un règlement : issue gagnante + crédits versés par compte."""

    market_id: str
    winning_outcome: str
    payouts: dict[str, float] = Field(default_factory=dict)  # peut être négatif (short perdant)
    already_settled: bool = False


def settle(store: MarketStore, market: Market, winning_outcome_id: str) -> SettlementResult:
    """Règle les positions (part gagnante = 1, sinon 0), passe le marché à RESOLVED. Idempotent."""
    if market.status is MarketStatus.RESOLVED:
        return SettlementResult(
            market_id=market.id,
            winning_outcome=market.resolved_outcome or winning_outcome_id,
            already_settled=True,
        )
    payouts: dict[str, float] = {}
    for position in store.list_positions(market_id=market.id):
        if position.outcome_id != winning_outcome_id or position.shares == 0.0:
            continue  # les parts perdantes valent 0 (déjà payées à l'achat)
        account = store.get_account(position.account_id)
        if account is None:
            continue
        account.balance += position.shares  # 1 crédit par part gagnante
        store.save_account(account)
        payouts[position.account_id] = payouts.get(position.account_id, 0.0) + position.shares
    market.status = MarketStatus.RESOLVED
    market.resolved_outcome = winning_outcome_id
    store.save_market(market)
    return SettlementResult(
        market_id=market.id, winning_outcome=winning_outcome_id, payouts=payouts
    )


def resolve_and_settle(
    store: MarketStore,
    market: Market,
    summary: RoundSummary,
    *,
    delta_utopia: float = 0.0,
    council_winner: str | None = None,
) -> SettlementResult:
    """Résout puis règle un marché en un appel (flux `POST /api/rounds/{id}/resolve`)."""
    winner = resolve(
        market, summary, delta_utopia=delta_utopia, council_winner=council_winner
    )
    return settle(store, market, winner)
