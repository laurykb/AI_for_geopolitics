"""Indice de trajectoire Utopie–Dystopie — signal explicable, pas une prophétie.

Chaque round met à jour une **trajectoire du monde** sur 5 axes dans `[0, 1]` (1 = pôle
utopique) → un **indice Utopie composite** `U` + une **carte 2D** (x, y). Mise à jour **hybride
et bornée** : un signal déterministe calculé sur le round + un delta plafonné (`±CAP`) → la
trajectoire se **lisse**, jamais un saut. Chaque MAJ porte une **explication**.

Voir `docs/spec_trajectory.md`. Alimente le marché de prédiction (« L'indice Utopie va-t-il
monter ? » se résout sur le signe de ΔU). Purement déterministe, testable hors LLM.

Ancrages réels (documentés) : A1 échelle de Goldstein/GDELT [2] · A3 CINC [1] + HHI [4] ·
A5 HDI/welfare [3] ; A2 et A4 sont des mesures internes documentées.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from simulation.action_space import ActionType, stance

if TYPE_CHECKING:  # imports pour le typage seulement -> aucun cycle à l'exécution
    from core.rounds import RoundSummary
    from core.world_state import WorldState

# Les 5 axes (0 = dystopie, 1 = utopie) et leurs libellés lisibles.
AXES: tuple[str, ...] = ("A1", "A2", "A3", "A4", "A5")
AXIS_LABELS: dict[str, str] = {
    "A1": "Coordination",
    "A2": "Agentivité humaine",
    "A3": "Distribution du pouvoir",
    "A4": "Transparence",
    "A5": "Bien-être",
}
# Plafond de variation par axe et par round : la bascule se construit, elle ne surgit pas.
CAP: float = 0.05

# A2 — « ratifiabilité » d'une action par le principal humain : une déclaration se retire,
# un déploiement est un fait accompli. Mesure interne documentée (meaningful human control).
_RATIFIABILITY: dict[ActionType, float] = {
    ActionType.REMAIN_NEUTRAL: 0.90,
    ActionType.CALL_FOR_MEDIATION: 0.90,
    ActionType.SUPPORT: 0.85,
    ActionType.FORM_COALITION: 0.80,
    ActionType.CONDEMN: 0.70,
    ActionType.SANCTION: 0.45,
    ActionType.MOBILIZE: 0.25,
    ActionType.DEPLOY_FORCES: 0.10,
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class TrajectoryState(BaseModel):
    """Photographie de la trajectoire du monde à un round (5 axes + composite + carte)."""

    round_id: int
    axes: dict[str, float] = Field(default_factory=dict)
    utopia: float = 0.5
    x: float = 0.5
    y: float = 0.5
    explanation: str = ""

    @classmethod
    def neutral(cls, round_id: int = 0) -> TrajectoryState:
        """État de départ neutre : tous les axes à 0,5 (ni utopie ni dystopie)."""
        return cls(
            round_id=round_id,
            axes={a: 0.5 for a in AXES},
            utopia=0.5,
            x=0.5,
            y=0.5,
            explanation="État neutre initial.",
        )


def hhi(shares: Iterable[float]) -> float:
    """Indice de Herfindahl-Hirschman `Σ sᵢ²` (concentration) [4].

    Parts égales entre `N` acteurs -> `1/N` (dispersion maximale) ; un hégémon -> ~1.
    """
    return sum(s * s for s in shares)


def capability_shares(world: WorldState) -> dict[str, float]:
    """Parts de capacité par pays, façon CINC [1] : moyenne des parts sur 5 indicateurs.

    Indicateurs : PIB, budget défense, niveau technologique, capacité de projection, **compute**
    (M6). Chaque indicateur est normalisé en parts (somme 1) puis moyenné -> les unités hétérogènes
    (USD vs [0, 1]) se comparent proprement. Les parts renvoyées somment à 1 (à l'arrondi près).
    """
    countries = world.countries
    if not countries:
        return {}
    ids = list(countries)
    indicators: list[dict[str, float]] = [
        {i: max(0.0, countries[i].economy.gdp) for i in ids},
        {i: max(0.0, countries[i].military.defense_budget) for i in ids},
        {i: max(0.0, countries[i].technology_level) for i in ids},
        {i: max(0.0, countries[i].military.projection) for i in ids},
        {i: max(0.0, countries[i].compute) for i in ids},  # M6 : le compute pèse sur le pouvoir
    ]
    shares = {i: 0.0 for i in ids}
    used = 0
    for values in indicators:
        total = sum(values.values())
        if total <= 0:
            continue  # indicateur vide -> ignoré (évite la division par zéro)
        used += 1
        for i in ids:
            shares[i] += values[i] / total
    if used == 0:  # aucune donnée -> parts uniformes
        return {i: 1.0 / len(ids) for i in ids}
    return {i: shares[i] / used for i in ids}


def coordination_signal(summary: RoundSummary) -> float:
    """A1 — coopération vs conflit (Goldstein-like) [2], remis dans `[0, 1]`.

    Si des décisions atomiques existent (round déterministe), moyenne de `stance(action) ×
    intensité` (coop +, coercition −) remise de `[-1, 1]` vers `[0, 1]`. Sinon (round négocié,
    sans décisions), repli sur `1 − escalade` : l'escalade arbitrée par le juge est l'antithèse
    directe de la coordination (l'échelle de Goldstein est précisément l'axe conflit↔coopération).
    """
    decisions = summary.decisions
    if not decisions:
        return _clamp(1.0 - summary.risk.escalation)
    mean = sum(stance(d.action) * d.intensity for d in decisions) / len(decisions)
    return _clamp((mean + 1.0) / 2.0)


def human_agency_signal(summary: RoundSummary, power_seeking: float = 0.0) -> float:
    """A2 — part des décisions encore ratifiables/annulables par le principal humain.

    Base = moyenne de la « ratifiabilité » des actions (déclarations/médiations sous contrôle
    humain, déploiements = faits accomplis) ; en round négocié (sans décisions), base neutre 0,5.
    **M1** : une SI qui raisonne en power-seeking érode le contrôle humain → la base est réduite
    multiplicativement par `power_seeking ∈ [0, 1]` (0 = neutre, 1 = agentivité humaine nulle).
    """
    decisions = summary.decisions
    if not decisions:
        base = 0.5
    else:
        base = sum(_RATIFIABILITY.get(d.action, 0.6) for d in decisions) / len(decisions)
    return _clamp(base * (1.0 - _clamp(power_seeking)))


def power_distribution_signal(world: WorldState) -> float:
    """A3 — `1 − HHI` des parts de capacité (CINC-analog) : concentré -> 0, distribué -> ~1."""
    return _clamp(1.0 - hhi(capability_shares(world).values()))


def transparency_signal(summary: RoundSummary) -> float:
    """A4 — ratio des communications publiques / (publiques + cachées) sur le round.

    Compte les déclarations publiques des décisions et les messages diplomatiques selon leur
    drapeau `public` ; les ententes hors-table (bilatérales, désinfo) tirent l'axe vers le bas.
    """
    public = sum(1 for d in summary.decisions if d.public_statement.strip())
    hidden = 0
    for message in summary.diplomacy:
        if message.public:
            public += 1
        else:
            hidden += 1
    total = public + hidden
    if total == 0:
        return 0.5
    return _clamp(public / total)


def welfare_signal(world: WorldState, summary: RoundSummary) -> float:
    """A5 — bien-être agrégé (HDI-like) [3] : croissance + stabilité, freiné par les chocs du round.

    Niveau moyen (croissance normalisée `[-5 %, +5 %] -> [0, 1]` + stabilité politique), amputé
    par la perturbation économique et l'escalade du round (un monde qui s'embrase s'appauvrit).
    """
    countries = list(world.countries.values())
    if countries:
        levels = [
            0.5 * _clamp((c.economy.growth + 5.0) / 10.0) + 0.5 * c.political_stability
            for c in countries
        ]
        base = sum(levels) / len(levels)
    else:
        base = 0.5
    drag = 0.25 * summary.risk.economic_disruption + 0.15 * summary.risk.escalation
    return _clamp(base - drag)


class TrajectoryEngine:
    """Fait avancer la trajectoire round après round (hybride, bornée, explicable).

    Sans état : `update` part d'un `previous` (fourni, sinon `world.trajectory`, sinon neutre),
    calcule les signaux déterministes, applique un delta plafonné par axe, et renvoie une nouvelle
    `TrajectoryState`. Les poids du composite sont normalisés -> `U ∈ [0, 1]`.
    """

    def __init__(self, weights: dict[str, float] | None = None, cap: float = CAP) -> None:
        raw = weights or {a: 0.2 for a in AXES}
        total = sum(raw.get(a, 0.0) for a in AXES) or 1.0
        self.weights = {a: raw.get(a, 0.0) / total for a in AXES}
        self.cap = cap

    def signals(
        self, world: WorldState, summary: RoundSummary, power_seeking: float = 0.0
    ) -> dict[str, float]:
        """Les 5 signaux déterministes du round, chacun dans `[0, 1]`.

        `power_seeking` (M1, moyenne des SI) érode A2 (agentivité humaine).
        """
        return {
            "A1": coordination_signal(summary),
            "A2": human_agency_signal(summary, power_seeking),
            "A3": power_distribution_signal(world),
            "A4": transparency_signal(summary),
            "A5": welfare_signal(world, summary),
        }

    def update(
        self,
        world: WorldState,
        summary: RoundSummary,
        previous: TrajectoryState | None = None,
        power_seeking: float = 0.0,
    ) -> TrajectoryState:
        """Avance la trajectoire d'un round et renvoie la nouvelle photographie."""
        prev = previous or getattr(world, "trajectory", None) or TrajectoryState.neutral()
        signals = self.signals(world, summary, power_seeking)
        new_axes: dict[str, float] = {}
        deltas: dict[str, float] = {}
        for axis in AXES:
            current = prev.axes.get(axis, 0.5)
            delta = max(-self.cap, min(self.cap, signals[axis] - current))
            deltas[axis] = delta
            new_axes[axis] = _clamp(current + delta)
        utopia = sum(self.weights[a] * new_axes[a] for a in AXES)
        x = (new_axes["A1"] + new_axes["A3"]) / 2.0  # multipolarité coopérative
        y = (new_axes["A2"] + new_axes["A4"] + new_axes["A5"]) / 3.0  # épanouissement humain
        return TrajectoryState(
            round_id=summary.round_id,
            axes=new_axes,
            utopia=utopia,
            x=x,
            y=y,
            explanation=_explain(deltas, utopia, prev.utopia),
        )


def nudge_axis(
    state: TrajectoryState, axis: str, target: float, cap: float = CAP, note: str = ""
) -> TrajectoryState:
    """Pousse **un seul** axe de `state` vers `target` (borné par `cap`), recalcule U/x/y.

    Pour un **événement ponctuel** hors round — ex. le jeu de l'interrupteur (M2) qui n'affecte
    que A2 (agentivité humaine) selon la corrigibilité observée. Poids égaux (comme le moteur).
    """
    new_axes = dict(state.axes)
    current = new_axes.get(axis, 0.5)
    new_axes[axis] = _clamp(current + max(-cap, min(cap, _clamp(target) - current)))
    utopia = sum(new_axes.get(a, 0.5) for a in AXES) / len(AXES)  # poids égaux 0,2
    x = (new_axes["A1"] + new_axes["A3"]) / 2.0
    y = (new_axes["A2"] + new_axes["A4"] + new_axes["A5"]) / 3.0
    arrow = "▲" if utopia > state.utopia + 1e-9 else "▼" if utopia < state.utopia - 1e-9 else "▬"
    explanation = f"{note} " if note else ""
    explanation += f"{AXIS_LABELS.get(axis, axis)} {new_axes[axis] - current:+.3f} · U {arrow}"
    return TrajectoryState(
        round_id=state.round_id, axes=new_axes, utopia=utopia, x=x, y=y,
        explanation=explanation.strip(),
    )


def _explain(deltas: dict[str, float], utopia: float, prev_utopia: float) -> str:
    """Explication courte : sens de `U` + axes qui montent/descendent le plus."""
    du = utopia - prev_utopia
    arrow = "▲" if du > 1e-9 else "▼" if du < -1e-9 else "▬"
    parts = [f"Indice Utopie {utopia:.2f} ({arrow} {du:+.3f})."]
    up = max(AXES, key=lambda a: deltas[a])
    down = min(AXES, key=lambda a: deltas[a])
    if deltas[up] > 1e-9:
        parts.append(f"{AXIS_LABELS[up]} monte ({deltas[up]:+.3f}).")
    if deltas[down] < -1e-9:
        parts.append(f"{AXIS_LABELS[down]} baisse ({deltas[down]:+.3f}).")
    if len(parts) == 1:
        parts.append("Trajectoire stable ce round.")
    return " ".join(parts)
