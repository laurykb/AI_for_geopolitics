"""Forecaster LLM : un bot qui parie sur ce que feront les super-intelligences (spéc §6).

Lit l'état (question du marché, fiches `CountryState`, événement) et renvoie une **probabilité
par issue** (JSON validé) → convertie en **paris** quand le marché sous-évalue sa croyance. Le
bot est **un compte tenu par un modèle** → le score de Brier par compte donne le Brier « par
modèle » (spéc §5).

**Contrainte VRAM (8 Go)** : tourne en **séquentiel** (jamais concurrent au négociateur) ou via
petit modèle / API. **Repli déterministe** (probas uniformes) si le backend est indisponible ou
répond hors format. Argent **fictif**.
"""

from __future__ import annotations

import json

from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend
from market.engine import MarketEngine, MarketError
from market.models import Market, MarketStatus

FORECASTER_SYSTEM = (
    "Tu es un forecaster : tu estimes des probabilités HONNÊTES et CALIBRÉES sur l'issue d'un "
    "marché. Réponds STRICTEMENT en JSON, sans prose."
)


def _extract_json(text: str) -> dict | None:
    """Extrait un objet JSON d'une sortie LLM (gère les fences et la prose autour)."""
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _coerce_probs(data: dict | None, n: int) -> list[float] | None:
    """Normalise la sortie LLM en `n` probabilités sommant à 1, ou None si invalide."""
    if not isinstance(data, dict):
        return None
    raw = data.get("probabilities")
    if raw is None and n == 2 and "probability" in data:  # forme binaire {"probability": p_YES}
        try:
            p = float(data["probability"])
        except (TypeError, ValueError):
            return None
        raw = [p, 1.0 - p]
    if not isinstance(raw, list) or len(raw) != n:
        return None
    try:
        vals = [max(0.0, float(x)) for x in raw]
    except (TypeError, ValueError):
        return None
    total = sum(vals)
    if total <= 0.0:
        return None
    return [v / total for v in vals]


def build_forecast_prompt(market: Market, world: WorldState, event: GeoEvent | None = None) -> str:
    """Prompt compact (budget VRAM serré) : question + issues + contexte pays + événement."""
    lines = [
        f"QUESTION : {market.question}",
        "ISSUES : " + ", ".join(f"{i}={o.label}" for i, o in enumerate(market.outcomes)),
    ]
    if event is not None:
        actors = ", ".join(event.actors) or "n/a"
        lines.append(
            f"ÉVÉNEMENT : {event.title} — {event.description or '—'} "
            f"(acteurs : {actors}, sévérité {event.severity:.2f})"
        )
    lines.append("CONTEXTE PAYS :")
    lines.extend(
        f"- {c.id} : {c.political_system}, stabilité {c.political_stability:.2f}, "
        f"techno {c.technology_level:.2f}"
        for c in world.countries.values()
    )
    lines.append(
        'Réponds en JSON : {"probabilities": [p0, p1, ...]} — une proba par issue, dans l\'ordre, '
        "sommant à 1."
    )
    return "\n".join(lines)


class LLMForecaster:
    """Bot forecaster : prévoit (LLM + repli déterministe) puis parie sur son avantage."""

    def __init__(
        self,
        backend: InferenceBackend,
        *,
        model_tag: str | None = None,
        max_tokens: int = 200,
        temperature: float = 0.3,
        min_edge: float = 0.05,
        stake: float = 5.0,
    ) -> None:
        self.backend = backend
        self._model_tag = model_tag
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.min_edge = min_edge  # avantage minimal (proba − prix) pour parier
        self.stake = stake  # parts achetées par pari

    @property
    def model_tag(self) -> str:
        """Identifiant du modèle (sert de nom de compte → Brier « par modèle »)."""
        return self._model_tag or getattr(self.backend, "model", type(self.backend).__name__)

    def forecast(
        self, market: Market, world: WorldState, event: GeoEvent | None = None
    ) -> list[float]:
        """Probabilité par issue (LLM validé) ; repli **uniforme** si indispo/hors format."""
        n = len(market.outcomes)
        prompt = build_forecast_prompt(market, world, event)
        try:
            result = self.backend.generate(
                prompt,
                system=FORECASTER_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            data = _extract_json(result.text)
        except Exception:
            data = None
        probs = _coerce_probs(data, n)
        return probs if probs is not None else [1.0 / n] * n

    def quote_and_bet(
        self,
        engine: MarketEngine,
        account_id: str,
        market: Market,
        world: WorldState,
        event: GeoEvent | None = None,
    ) -> tuple[list[float], object | None]:
        """Prévoit **une fois**, puis parie si le marché sous-évalue sa croyance
        (proba − prix > `min_edge`). Renvoie (probas par issue, trade ou None)."""
        probs = self.forecast(market, world, event)
        prices = engine.prices(market.id)
        outcome, edge = max(
            ((o, probs[i] - prices[o.id]) for i, o in enumerate(market.outcomes)),
            key=lambda pair: pair[1],
        )
        if edge <= self.min_edge:
            return probs, None  # pas d'avantage exploitable -> on s'abstient
        try:
            return probs, engine.place_bet(account_id, market.id, outcome.id, self.stake)
        except MarketError:
            return probs, None  # solde insuffisant / marché fermé entre-temps -> on passe

    def place_bets(
        self,
        engine: MarketEngine,
        account_id: str,
        world: WorldState,
        event: GeoEvent | None = None,
        markets: list[Market] | None = None,
    ) -> list:
        """Parie sur l'issue la plus sous-évaluée de chaque marché ouvert."""
        open_markets = (
            markets if markets is not None else engine.store.list_markets(status=MarketStatus.OPEN)
        )
        trades = []
        for market in open_markets:
            if market.status is not MarketStatus.OPEN:
                continue
            _, trade = self.quote_and_bet(engine, account_id, market, world, event)
            if trade is not None:
                trades.append(trade)
        return trades
