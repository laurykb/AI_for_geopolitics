"""Modèles de domaine du marché de prédiction (Pydantic).

Reflètent les tables SQLite de `docs/spec_market.md` §8 : Account, Market, Outcome, Position,
Trade. Argent **fictif** (crédits) uniquement. Le marché **observe** les super-intelligences,
il ne les **influence pas**.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class MarketType(StrEnum):
    """Type de question. Le seuil (ex. « ΔUtopie > 0 ») est ramené au binaire."""

    BINARY = "binary"
    CATEGORICAL = "categorical"
    THRESHOLD = "threshold"


class MarketStatus(StrEnum):
    """Cycle de vie d'un marché (spéc §3) : ouvert -> verrouillé -> résolu."""

    OPEN = "open"
    LOCKED = "locked"
    RESOLVED = "resolved"


class AccountKind(StrEnum):
    """Nature d'un participant : humain ou bot forecaster."""

    HUMAN = "human"
    BOT = "bot"


class ResolutionKind(StrEnum):
    """Comment le Juge (oracle) résout un marché — cf. `market.resolution` (spéc §4)."""

    ACTION = "action"  # une décision (pays, action[, cible]) a-t-elle eu lieu ce round ?
    TRAJECTORY = "trajectory"  # l'indice Utopie a-t-il monté (ΔU > 0) ?
    COUNCIL = "council"  # quelle SI a gagné le Conseil (catégoriel) ?


class ResolutionCriterion(BaseModel):
    """Critère porté par un marché pour le résoudre automatiquement à la fin du round."""

    kind: ResolutionKind
    # Spécifiques à l'action (les autres kinds les laissent à None) :
    country: str | None = None
    action: str | None = None
    target: str | None = None


class Account(BaseModel):
    """Solde de crédits d'un participant ; `initial_balance` = base du P&L (spéc §5)."""

    id: str
    name: str
    kind: AccountKind = AccountKind.HUMAN
    balance: float = 0.0
    initial_balance: float | None = None  # défaut = balance à la création

    @model_validator(mode="after")
    def _default_initial(self) -> Account:
        if self.initial_balance is None:
            self.initial_balance = self.balance
        return self


class Outcome(BaseModel):
    """Une issue d'un marché ; `q` = parts nettes émises (état LMSR)."""

    id: str
    market_id: str
    label: str
    q: float = 0.0


class Market(BaseModel):
    """Une question résolue à la fin d'un round par le Juge (oracle)."""

    id: str
    round_id: int
    game_id: str | None = None  # vrai lien partie↔marché (R2) ; round_id reste pour compat
    question: str
    type: MarketType = MarketType.BINARY
    status: MarketStatus = MarketStatus.OPEN
    b: float = Field(gt=0.0, description="Liquidité LMSR (perte bornée = b·ln(N))")
    outcomes: list[Outcome] = Field(default_factory=list)
    criterion: ResolutionCriterion | None = None  # comment le Juge le résout
    resolved_outcome: str | None = None  # id de l'outcome gagnant, une fois résolu
    created_at: str = ""

    def q_vector(self) -> list[float]:
        """Vecteur `q` (parts nettes) dans l'ordre des outcomes — entrée du market maker."""
        return [o.q for o in self.outcomes]

    def find_outcome(self, outcome_id: str) -> Outcome | None:
        return next((o for o in self.outcomes if o.id == outcome_id), None)

    def outcome_index(self, outcome_id: str) -> int:
        """Index de l'outcome dans le vecteur `q` (lève `KeyError` si inconnu)."""
        for i, o in enumerate(self.outcomes):
            if o.id == outcome_id:
                return i
        raise KeyError(f"outcome inconnu : {outcome_id}")


class Position(BaseModel):
    """Parts détenues par un compte sur un outcome."""

    account_id: str
    outcome_id: str
    shares: float = 0.0


class Trade(BaseModel):
    """Achat (shares > 0) ou vente (shares < 0) de parts au prix LMSR, en crédits."""

    id: str
    account_id: str
    market_id: str
    outcome_id: str
    shares: float
    cost: float
    price: float  # prix implicite de l'outcome APRÈS le trade
    ts: str


class Quote(BaseModel):
    """Devis d'un pari (sans exécution) : coût et impact sur le prix."""

    market_id: str
    outcome_id: str
    shares: float
    cost: float
    price_before: float
    price_after: float
