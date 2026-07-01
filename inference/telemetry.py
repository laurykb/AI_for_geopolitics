"""Journal de bord des appels LLM (télémétrie) : coût, latence, cache, fallback, JSON, ancrage.

Le `BudgetLedger` enregistre chaque appel (via `MeteredBackend`) avec un contexte (round, rôle,
pays), puis agrège par round les 9 indicateurs du *LLM Budget Dashboard*. On transforme la
contrainte VRAM en feature de gouvernance : on mesure ce qu'on dépense, appel par appel.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from core.country_state import CountryState
from inference.pricing import estimate_cost, frontier_equivalent


@dataclass
class CallRecord:
    """Un appel LLM mesuré."""

    round_id: int
    role: str  # "agent" | "gm" | "judge" | "communique" | ...
    country: str | None
    model: str
    streamed: bool
    prompt_tokens: int
    completion_tokens: int
    duration_s: float
    cache_hit: bool = False
    fallback: bool = False
    json_valid: bool | None = None  # None = non applicable (prose streamée)
    grounding: float | None = None

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost(self) -> float:
        return estimate_cost(self.prompt_tokens, self.completion_tokens, self.model)

    @property
    def frontier_cost(self) -> float:
        return frontier_equivalent(self.prompt_tokens, self.completion_tokens)


@dataclass
class RoundBudget:
    """Les 9 indicateurs du dashboard, agrégés sur un round (ou un groupe)."""

    round_id: int
    number_of_llm_calls: int
    tokens_used: int
    estimated_cost: float
    latency: float  # somme des durées (s)
    cache_hit_rate: float
    fallback_rate: float
    json_validity_rate: float  # sur les appels JSON (schéma) ; 1.0 si aucun
    source_grounding_score: float  # moyenne des groundings disponibles ; 0.0 si aucun
    frontier_equivalent_cost: float


@dataclass
class _Scope:
    """Contexte courant d'un appel ; `mark` renseigne ce que seul l'appelant connaît."""

    role: str
    country: str | None
    fallback: bool = False
    grounding: float | None = None

    def mark(self, *, fallback: bool | None = None, grounding: float | None = None) -> None:
        if fallback is not None:
            self.fallback = fallback
        if grounding is not None:
            self.grounding = grounding


def _aggregate(round_id: int, recs: list[CallRecord]) -> RoundBudget:
    n = len(recs)
    json_recs = [r for r in recs if r.json_valid is not None]
    grounded = [r.grounding for r in recs if r.grounding is not None]
    return RoundBudget(
        round_id=round_id,
        number_of_llm_calls=n,
        tokens_used=sum(r.tokens for r in recs),
        estimated_cost=round(sum(r.cost for r in recs), 6),
        latency=round(sum(r.duration_s for r in recs), 3),
        cache_hit_rate=(sum(r.cache_hit for r in recs) / n) if n else 0.0,
        fallback_rate=(sum(r.fallback for r in recs) / n) if n else 0.0,
        json_validity_rate=(sum(bool(r.json_valid) for r in json_recs) / len(json_recs))
        if json_recs
        else 1.0,
        source_grounding_score=round(sum(grounded) / len(grounded), 3) if grounded else 0.0,
        frontier_equivalent_cost=round(sum(r.frontier_cost for r in recs), 6),
    )


def grounding_proxy(message: str, country: CountryState, confidence: float) -> float:
    """Proxy d'ancrage (0-1), clairement approché : perception + recoupement avec le profil réel.

    N/A tant que le RAG n'est pas branché dans la négociation : on mêle la confiance de
    perception au nombre de faits réels du pays (priorités, rivaux, alliances, idéologie)
    effectivement cités dans le message.
    """
    facts = [
        *country.strategic_priorities,
        *country.rivals,
        *country.alliances,
        *country.ideology,
    ]
    low = message.lower()
    hits = sum(1 for f in facts if f and f.lower() in low)
    overlap = min(1.0, hits / 3)  # 3 faits cités = ancrage « plein »
    return round(0.5 * confidence + 0.5 * overlap, 2)


class BudgetLedger:
    """Recueille les `CallRecord` et les agrège par round / par groupe (pays ou rôle)."""

    def __init__(self) -> None:
        self.records: list[CallRecord] = []
        self._round_id = 0
        self._scope: _Scope | None = None

    def set_round(self, round_id: int) -> None:
        self._round_id = round_id

    @contextmanager
    def context(self, role: str, country: str | None = None) -> Iterator[_Scope]:
        """Ouvre un contexte : les appels mesurés à l'intérieur héritent de (role, country).

        À la sortie, les annotations `mark(fallback=…, grounding=…)` sont appliquées aux
        enregistrements créés pendant le contexte.
        """
        previous = self._scope
        scope = _Scope(role=role, country=country)
        self._scope = scope
        start = len(self.records)
        try:
            yield scope
        finally:
            for rec in self.records[start:]:
                if scope.fallback:
                    rec.fallback = True
                if scope.grounding is not None and rec.grounding is None:
                    rec.grounding = scope.grounding
            self._scope = previous

    def record(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_s: float,
        streamed: bool,
        cache_hit: bool = False,
        json_valid: bool | None = None,
    ) -> None:
        scope = self._scope
        self.records.append(
            CallRecord(
                round_id=self._round_id,
                role=scope.role if scope else "unknown",
                country=scope.country if scope else None,
                model=model,
                streamed=streamed,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_s=duration_s,
                cache_hit=cache_hit,
                json_valid=json_valid,
            )
        )

    def round_ids(self) -> list[int]:
        return sorted({r.round_id for r in self.records})

    def round_budgets(self) -> list[RoundBudget]:
        """Agrégat par round (une ligne du tableau du dashboard par round)."""
        return [
            _aggregate(rid, [r for r in self.records if r.round_id == rid])
            for rid in self.round_ids()
        ]

    def by_country(self, round_id: int) -> list[tuple[str, RoundBudget]]:
        """Ventilation d'un round par pays (les appels GM/juge sont regroupés sous leur rôle)."""
        recs = [r for r in self.records if r.round_id == round_id]
        groups: dict[str, list[CallRecord]] = {}
        for r in recs:
            label = r.country or r.role
            groups.setdefault(label, []).append(r)
        return [(label, _aggregate(round_id, rs)) for label, rs in sorted(groups.items())]
