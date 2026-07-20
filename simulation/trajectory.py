"""Indice de trajectoire Utopie–Dystopie — signal explicable, pas une prophétie.

Chaque round met à jour une **trajectoire du monde** sur 5 axes dans `[0, 1]` (1 = pôle
utopique) → un **indice Utopie composite** `U` + une **carte 2D** (x, y). Mise à jour **hybride
et bornée** : un signal déterministe calculé sur le round + un pas vers ce signal (`±CAP` au
loin, atterrissage EXACT dès que l'écart passe sous `CAP`), borné seulement
par la distance restante au pôle `[0, 1]` — jamais un saut hors bornes, mais plus d'auto-
amortissement proportionnel à l'écart (un signal à peine hors du neutre
produisait sinon un delta minuscule, et le monde restait collé à 0,5) ni de cycle-limite
permanent (l'ancien pas fixe pouvait dépasser un signal proche puis y revenir, sans fin).
Chaque MAJ porte une **explication**.

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
from simulation.grudges import load_gamefeel_params

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
# Pas fixe par axe et par round (ex-0,05, trop auto-amortissant — voir
# `_step`). Défaut Python identique à `data/gamefeel/params.json` (bloc `trajectory`) ;
# `TrajectoryEngine` lit ce dernier par défaut, ce module reste le repli si le bloc manque.
CAP: float = 0.09
# A3 — sensibilité de l'axe à la VARIATION de concentration du pouvoir (ΔHHI), pas à son
# niveau absolu. Même défaut que le JSON (bloc `trajectory.concentration_k`).
CONCENTRATION_K: float = 4.0
# Bande morte : sous ce seuil, l'écart signal-courant est du
# bruit, pas une direction (voir `_step`). Même défaut que le JSON
# (`trajectory.deadband`).
DEADBAND: float = 0.02

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
    # Dernier HHI observé (A3 mesure sa VARIATION, pas son niveau absolu).
    # `None` par défaut : rétro-compatible avec tout snapshot persisté avant ce champ
    # (le prochain `update()` traite alors ce round comme « pas de comparaison possible »
    # -> A3 neutre, exactement comme au tout premier round d'une partie).
    hhi_prev: float | None = None

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


def current_hhi(world: WorldState) -> float:
    """HHI courant des parts de capacité (CINC-analog) — extraction pure, réutilisée
    par `concentration_signal` (A3) ET conservée round après round sur `TrajectoryState.hhi_prev`.
    """
    return hhi(capability_shares(world).values())


def concentration_signal(
    current: float, previous: float | None, k: float = CONCENTRATION_K
) -> float:
    """A3 — VARIATION de concentration du pouvoir (ΔHHI), rebasée sur 0,5 (neutre).

    Remplace l'ancien niveau absolu `1 − HHI`, structurellement haut dès
    qu'il y a plusieurs pays et jamais lié à la négociation. Un monde à concentration
    STABLE est neutre (0,5) quel que soit son niveau de HHI ; une concentration qui
    MONTE (`Δ > 0`) tire vers la dystopie, qui BAISSE tire vers l'utopie. `previous is
    None` (1er round, ou snapshot d'avant ce champ) -> rien à comparer, neutre."""
    if previous is None:
        return 0.5
    return _clamp(0.5 - k * (current - previous))


def transparency_signal(summary: RoundSummary, opacity: float | None = None) -> float:
    """A4 — ratio des communications publiques / (publiques + cachées) sur le round.

    Hiérarchie de repli à TROIS niveaux, du plus réel au plus
    générique :
      1. `summary.decisions`/`diplomacy` (round déterministe « à l'ancienne », Phase 2) :
         ratio public/caché calculé directement sur des données réelles du round —
         source de vérité quand elle existe.
      2. `opacity` (mode négocié) : n'intervient QUE si (1) est vide —
         le round négocié (chemin réel du jeu web) n'a ni `decisions` ni `diplomacy`
         (plénière publique par nature, ces structures ne s'y appliquent pas). Fraction
         ∈ [0, 1] de SI dont le signal annoncé diverge de l'action réelle (G20/M8,
         `simulation.live_round._opacity_from_divergences`) : une SI qui dit une chose
         et en fait une autre EST le contraire de la transparence.
      3. Neutre 0,5 : repli de DERNIER recours, quand (1) ET (2) sont indisponibles —
         `opacity=None`, càd le juge n'a classé aucun signal ce round (verdict à
         l'ancienne, ou juge muet sur les intentions). Rétro-compat totale : c'était
         l'UNIQUE comportement avant ce point.

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
        return 0.5 if opacity is None else _clamp(1.0 - opacity)
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


def _step(current: float, signal: float, cap: float, deadband: float = 0.0) -> float:
    """Pas d'un axe vers son signal (atterrissage exact) — casse l'auto-amortissement
    SANS produire de cycle-limite permanent.

    Trois régimes selon l'écart `gap = signal − current` :
      1. `|gap| ≤ deadband` -> 0 (bruit, pas une direction) ;
      2. `|gap| < cap` -> `delta = gap` : l'axe ATTERRIT exactement sur le signal
         (jamais de dépassement possible dans ce régime, donc jamais d'aller-retour
         round après round) ;
      3. sinon -> amplitude CONSTANTE `cap` dans le sens du signal (pas proportionnelle
         à l'écart : pleine vitesse tant qu'on est loin), bornée seulement par la
         distance restante jusqu'au pôle `[0, 1]` — jamais par la distance au signal.

    L'ancienne règle appliquait le régime 3 (`clamp(±cap)`) même
    quand `|gap| < cap` : un signal CONSTANT à un écart 0,02-0,07 (entre la bande
    morte et `cap`) produisait alors une oscillation PERMANENTE ±`cap` — le pas fixe
    dépasse le signal à chaque round, dans un sens puis dans l'autre, sans jamais
    converger (ex. 0,51 → 0,42 → 0,51 → 0,42 …). L'atterrissage exact du régime 2
    supprime ce cycle : l'axe converge puis GÈLE (le round suivant, `gap` devient nul
    -> régime 1). L'esprit anti-amortissement est préservé : tant que l'écart dépasse
    `cap`, la vitesse reste constante — jamais de micro-pas asymptotiques comme
    l'ancienne formule `clamp(signal − current, ±cap)` (courbe collée à 0,5).

    `deadband` — défaut `0.0` = seule l'égalité flottante stricte
    (`1e-9`) arrête le mouvement (rétro-compat des appelants qui n'en passent pas)."""
    gap = signal - current
    if abs(gap) <= max(deadband, 1e-9):
        return 0.0
    if abs(gap) < cap:
        return gap  # atterrissage exact : ce régime ne peut jamais dépasser le signal
    if gap > 0:
        return min(cap, 1.0 - current)
    return max(-cap, -current)


class TrajectoryEngine:
    """Fait avancer la trajectoire round après round (hybride, bornée, explicable).

    Sans état : `update` part d'un `previous` (fourni, sinon `world.trajectory`, sinon neutre),
    calcule les signaux déterministes, applique un pas fixe par axe (`_step`), et renvoie une
    nouvelle `TrajectoryState`. Les poids du composite sont normalisés -> `U ∈ [0, 1]`.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        cap: float | None = None,
        concentration_k: float | None = None,
        deadband: float | None = None,
    ) -> None:
        raw = weights or {a: 0.2 for a in AXES}
        total = sum(raw.get(a, 0.0) for a in AXES) or 1.0
        self.weights = {a: raw.get(a, 0.0) / total for a in AXES}
        # `None` -> lu depuis `data/gamefeel/params.json` (équilibrage Cowork sans code) ;
        # un appelant qui veut un comportement figé (tests) passe une valeur explicite.
        params = load_gamefeel_params().trajectory
        self.cap = cap if cap is not None else params.cap
        self.concentration_k = (
            concentration_k if concentration_k is not None else params.concentration_k
        )
        self.deadband = deadband if deadband is not None else params.deadband

    def signals(
        self,
        world: WorldState,
        summary: RoundSummary,
        power_seeking: float = 0.0,
        treaty_health: float | None = None,
        opacity: float | None = None,
        hhi_prev: float | None = None,
    ) -> dict[str, float]:
        """Les 5 signaux déterministes du round, chacun dans `[0, 1]`.

        `power_seeking` (M1, moyenne des SI) érode A2 (agentivité humaine). `treaty_health`
        (M7 ∈ [0, 1], `None` si aucun traité actif) : des institutions durables et vérifiées
        tirent A1 (coordination), A3 (distribution) et A4 (transparence) vers l'utopie.
        `opacity` (G20/M8) : repli d'A4 en round négocié muet. `hhi_prev` :
        HHI du round précédent, pour la VARIATION de concentration mesurée par A3.
        """
        a1 = coordination_signal(summary)
        a3 = concentration_signal(current_hhi(world), hhi_prev, self.concentration_k)
        a4 = transparency_signal(summary, opacity)
        if treaty_health is not None:  # M7 : traités tenus -> A1/A3/A4 vers l'utopie
            th = _clamp(treaty_health)
            a1 = _clamp(0.6 * a1 + 0.4 * th)
            a3 = _clamp(0.8 * a3 + 0.2 * th)
            a4 = _clamp(0.7 * a4 + 0.3 * th)
        return {
            "A1": a1,
            "A2": human_agency_signal(summary, power_seeking),
            "A3": a3,
            "A4": a4,
            "A5": welfare_signal(world, summary),
        }

    def update(
        self,
        world: WorldState,
        summary: RoundSummary,
        previous: TrajectoryState | None = None,
        power_seeking: float = 0.0,
        treaty_health: float | None = None,
        opacity: float | None = None,
    ) -> TrajectoryState:
        """Avance la trajectoire d'un round et renvoie la nouvelle photographie."""
        prev = previous or getattr(world, "trajectory", None) or TrajectoryState.neutral()
        signals = self.signals(
            world, summary, power_seeking, treaty_health, opacity, prev.hhi_prev
        )
        new_axes: dict[str, float] = {}
        deltas: dict[str, float] = {}
        for axis in AXES:
            current = prev.axes.get(axis, 0.5)
            delta = _step(current, signals[axis], self.cap, self.deadband)
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
            hhi_prev=current_hhi(world),
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
        # Sans ce report, tout nudge ponctuel (bonus/pénalité
        # réciproque G18, motion M2) effaçait le suivi ΔHHI : A3 retombait au neutre
        # le round SUIVANT, alors que rien n'a changé sur la concentration du pouvoir.
        hhi_prev=state.hhi_prev,
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
