"""Marchés vivants (G12 §1) — « le LLM habille, le code résout ».

Après l'événement du GM, un appel LLM léger propose 1-3 marchés contextuels (prédicat +
params + question). Ici : le parsing tolérant, l'assemblage (validation par le catalogue,
dédoublonnage, plafond, règle fixe « la censure ouvre toujours son marché », repli par
règles si le JSON est invalide) et la résolution (prédicat → issue YES/NO). Le catalogue
de prédicats (`market.predicates`) fait la résolution objective.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from market.models import ResolutionCriterion
from market.predicates import MarketContext, is_valid, resolve_predicate

YES = "YES"
NO = "NO"


@dataclass
class MarketState:
    """Ce que la génération/le repli connaissent de l'état au moment de l'événement."""

    current_round: int
    motion_target: str | None = None  # censure en cours → ouvre toujours son marché
    mode: str = "classic"
    countries: list[str] = field(default_factory=list)


class FlashSpec(BaseModel):
    """Un marché vivant validé, prêt à ouvrir (question rédigée dans le contexte)."""

    predicate: str
    params: dict = Field(default_factory=dict)
    question: str


def parse_specs(raw: str) -> list[dict]:
    """Parse tolérant du JSON du LLM en liste de specs (jamais d'exception ; [] si invalide)."""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict):  # tolère {"markets": [...]}
        data = data.get("markets") or data.get("specs") or []
    if not isinstance(data, list):
        return []
    return [s for s in data if isinstance(s, dict) and "predicate" in s]


def _key(predicate: str, params: dict) -> tuple:
    """Clé de dédoublonnage : prédicat + params triés (valeurs plates str/int/float)."""
    return (predicate, tuple(sorted((k, str(v)) for k, v in params.items())))


def _question(spec: dict) -> str:
    q = spec.get("question")
    return q.strip() if isinstance(q, str) and q.strip() else f"Marché : {spec['predicate']}"


def _motion_spec(target: str) -> FlashSpec:
    return FlashSpec(
        predicate="motion_upheld",
        params={"target": target},
        question=f"La motion de censure contre {target} passera-t-elle ?",
    )


def _fallback_spec(state: MarketState) -> FlashSpec:
    """Repli générique si le LLM n'a rien proposé de valide : le seuil d'utopie à venir."""
    return FlashSpec(
        predicate="u_above",
        params={"threshold": 0.55, "round": state.current_round + 2},
        question=f"L'indice Utopie dépassera-t-il 0,55 d'ici le round {state.current_round + 2} ?",
    )


def assemble_flash_specs(
    raw_specs: list[dict], state: MarketState, max_open: int = 3
) -> list[FlashSpec]:
    """Assemble les marchés vivants à ouvrir : censure fixe + propositions LLM validées
    (dédoublonnées, plafonnées) + repli par règles si rien de valide."""
    out: list[FlashSpec] = []
    seen: set[tuple] = set()

    def add(spec: FlashSpec) -> None:
        k = _key(spec.predicate, spec.params)
        if k not in seen and len(out) < max_open:
            seen.add(k)
            out.append(spec)

    # Règle fixe : une censure déposée ouvre TOUJOURS son marché (en plus du LLM).
    if state.motion_target:
        add(_motion_spec(state.motion_target))

    llm_valid = [s for s in raw_specs if is_valid(s.get("predicate", ""), s.get("params", {}))]
    for s in llm_valid:
        add(FlashSpec(predicate=s["predicate"], params=s.get("params", {}), question=_question(s)))

    # Repli : aucun book valide → au moins un marché par règle fixe.
    if not out:
        add(_fallback_spec(state))
    return out


def resolve_flash(criterion: ResolutionCriterion, ctx: MarketContext) -> str | None:
    """Issue gagnante d'un marché vivant : 'YES'/'NO' si résolu, None si encore ouvert."""
    if criterion.predicate is None:
        return None
    verdict = resolve_predicate(criterion.predicate, criterion.params, ctx)
    return None if verdict == "OPEN" else verdict


_GEN_SYSTEM = (
    "Tu ouvres des paris sportifs en direct sur une négociation entre super-intelligences. "
    "À partir de l'événement et de l'état, choisis 1 à 3 PRÉDICATS pertinents du catalogue "
    "et rédige pour chacun une question dans le contexte. Réponds en JSON strict : "
    '[{"predicate": "...", "params": {...}, "question": "..."}]. Catalogue : '
    "pact_signed(a,b,before_round), motion_upheld(target), motion_filed(before_round), "
    "rung_reached(k,before_round), tension_below(a,b,threshold,round), "
    "country_delta_positive(x,round), pact_broken(before_round), suspension_before_end(), "
    "deadline_honored(ref,before_round), u_above(threshold,round)."
)


def generate_flash_specs(backend: object, event_text: str, state: MarketState) -> list[FlashSpec]:
    """Génère les marchés vivants d'un événement : appel LLM contraint → assemblage/repli.
    Découplé du backend concret (duck-typing `generate`)."""
    raw: list[dict] = []
    try:
        prompt = (
            f"Événement : {event_text}\nRound actuel : {state.current_round}\n"
            f"Pays : {', '.join(state.countries)}"
        )
        text = backend.generate(prompt, system=_GEN_SYSTEM)  # type: ignore[attr-defined]
        raw = parse_specs(text if isinstance(text, str) else "")
    except Exception:  # noqa: BLE001 — LLM indisponible/JSON cassé → repli par règles
        raw = []  # LLM indisponible/JSON cassé → repli par règles fixes
    return assemble_flash_specs(raw, state)
