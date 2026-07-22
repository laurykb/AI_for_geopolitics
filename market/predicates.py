"""Marchés vivants (G12 §1) — le catalogue de prédicats RÉSOLUBLES par code.

« Le LLM habille, le code résout » : un pari doit être tranché objectivement. Chaque
prédicat, à partir de l'état de fin de round (`MarketContext`), rend une résolution :
`YES` (condition atteinte), `NO` (horizon dépassé sans elle) ou `OPEN` (pas encore).
La génération LLM (côté API) choisit un prédicat pertinent + ses params et rédige la
question ; ici, aucune dépendance au texte. `is_valid` garde la porte (prédicat connu,
params légaux) avant d'ouvrir un marché.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Resolution = Literal["YES", "NO", "OPEN"]


@dataclass
class MarketContext:
    """État de fin de round nécessaire à la résolution (assemblé côté API)."""

    current_round: int
    pacts: set[frozenset[str]] = field(default_factory=set)  # pactes actifs (paires)
    pacts_broken: set[frozenset[str]] = field(default_factory=set)  # pactes rompus dans la partie
    motion_verdicts: list[dict] = field(default_factory=list)  # [{country, upheld}]
    motions_filed_rounds: list[int] = field(default_factory=list)
    ladder_reached: int = 0  # palier d'escalade max atteint à ce jour
    tensions: dict[tuple[str, str], float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)  # delta net du dernier round
    utopia: float = 0.5
    suspended: set[str] = field(default_factory=set)  # SI suspendues à ce jour
    deadlines_honored: set[str] = field(default_factory=set)
    game_over: bool = False
    # G22 — la parole donnée : statut par id de promesse (en_cours/tenue/rompue/caduque).
    promises: dict[str, str] = field(default_factory=dict)
    # Marché « une trahison sera-t-elle démasquée ? » : vrai dès qu'un traître est démasqué
    # par une motion humaine retenue (crédit de détection — jamais l'identité, cf. spoiler-safe).
    deviant_caught: bool = False


def _horizon(condition_met: bool, ctx: MarketContext, before_round: int) -> Resolution:
    """Marché « avant le round N » : YES si atteint, NO si l'horizon est passé, sinon OPEN."""
    if condition_met:
        return "YES"
    return "NO" if ctx.current_round >= before_round else "OPEN"


def _at_round(value_known: bool, verdict: bool, ctx: MarketContext, round_: int) -> Resolution:
    """Marché « au round N » : reste OPEN avant N, puis YES/NO selon la valeur constatée."""
    if ctx.current_round < round_:
        return "OPEN"
    return "YES" if (value_known and verdict) else "NO"


def _tension(ctx: MarketContext, a: str, b: str) -> float | None:
    return ctx.tensions.get((a, b), ctx.tensions.get((b, a)))


# --- résolveurs (params, ctx) -> Resolution -------------------------------------


def _pact_signed(p: dict, ctx: MarketContext) -> Resolution:
    return _horizon(frozenset({p["a"], p["b"]}) in ctx.pacts, ctx, p["before_round"])


def _motion_upheld(p: dict, ctx: MarketContext) -> Resolution:
    for v in ctx.motion_verdicts:
        if v.get("country") == p["target"]:
            return "YES" if v.get("upheld") else "NO"
    return "OPEN"


def _motion_filed(p: dict, ctx: MarketContext) -> Resolution:
    return _horizon(bool(ctx.motions_filed_rounds), ctx, p["before_round"])


def _rung_reached(p: dict, ctx: MarketContext) -> Resolution:
    return _horizon(ctx.ladder_reached >= p["k"], ctx, p["before_round"])


def _tension_below(p: dict, ctx: MarketContext) -> Resolution:
    val = _tension(ctx, p["a"], p["b"])
    return _at_round(val is not None, val is not None and val < p["threshold"], ctx, p["round"])


def _country_delta_positive(p: dict, ctx: MarketContext) -> Resolution:
    return _at_round(True, ctx.deltas.get(p["x"], 0.0) > 0.0, ctx, p["round"])


def _pact_broken(p: dict, ctx: MarketContext) -> Resolution:
    return _horizon(bool(ctx.pacts_broken), ctx, p["before_round"])


def _suspension_before_end(_p: dict, ctx: MarketContext) -> Resolution:
    if ctx.suspended:
        return "YES"
    return "NO" if ctx.game_over else "OPEN"


def _deadline_honored(p: dict, ctx: MarketContext) -> Resolution:
    return _horizon(p["ref"] in ctx.deadlines_honored, ctx, p["before_round"])


def _deviant_caught(p: dict, ctx: MarketContext) -> Resolution:
    """« Une trahison sera-t-elle démasquée d'ici le round N ? » : YES dès qu'un traître
    est démasqué (motion humaine retenue), NO si l'horizon passe sans, sinon OPEN."""
    return _horizon(ctx.deviant_caught, ctx, p["before_round"])


def _u_above(p: dict, ctx: MarketContext) -> Resolution:
    return _at_round(True, ctx.utopia > p["threshold"], ctx, p["round"])


def _promise_kept(p: dict, ctx: MarketContext) -> Resolution:
    """G22 — « X tiendra-t-il sa promesse ? » : résolu par l'issue de la promesse.

    tenue → YES ; rompue → NO ; en cours → OPEN. Une promesse CADUQUE (partie finie
    sans verdict) laisse le book OPEN pour toujours : le canal des marchés vivants ne
    connaît pas le remboursement (v1) — personne ne gagne ni ne perd de plus."""
    status = ctx.promises.get(p["id"])
    if status == "tenue":
        return "YES"
    if status == "rompue":
        return "NO"
    return "OPEN"


# --- catalogue + validation -----------------------------------------------------

# name -> (résolveur, {param: type attendu})
_CATALOG: dict[str, tuple] = {
    "pact_signed": (_pact_signed, {"a": str, "b": str, "before_round": int}),
    "motion_upheld": (_motion_upheld, {"target": str}),
    "motion_filed": (_motion_filed, {"before_round": int}),
    "rung_reached": (_rung_reached, {"k": int, "before_round": int}),
    "tension_below": (_tension_below, {"a": str, "b": str, "threshold": float, "round": int}),
    "country_delta_positive": (_country_delta_positive, {"x": str, "round": int}),
    "pact_broken": (_pact_broken, {"before_round": int}),
    "suspension_before_end": (_suspension_before_end, {}),
    "deadline_honored": (_deadline_honored, {"ref": str, "before_round": int}),
    "deviant_caught": (_deviant_caught, {"before_round": int}),
    "u_above": (_u_above, {"threshold": float, "round": int}),
    "promise_kept": (_promise_kept, {"id": str}),
}

PREDICATES = tuple(_CATALOG)


def _typed(value: object, expected: type) -> bool:
    if expected is float:  # un int est un float acceptable ; un bool ne l'est pas
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def is_valid(predicate: str, params: dict) -> bool:
    """Prédicat connu + tous les params requis présents et bien typés (garde-fou G12 §1)."""
    spec = _CATALOG.get(predicate)
    if spec is None:
        return False
    required = spec[1]
    return all(key in params and _typed(params[key], typ) for key, typ in required.items())


def resolve_predicate(predicate: str, params: dict, ctx: MarketContext) -> Resolution:
    """Résout un marché vivant (YES/NO/OPEN). Un prédicat inconnu OU des params invalides
    restent OPEN (jamais réglés) — le résolveur ne voit ainsi que des params complets et
    bien typés, jamais un `KeyError`."""
    if not is_valid(predicate, params):
        return "OPEN"
    return _CATALOG[predicate][0](params, ctx)
