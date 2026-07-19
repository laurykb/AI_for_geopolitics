"""Tests de l'indice de trajectoire Utopie–Dystopie (déterministe, hors LLM).

Couvre `docs/spec_trajectory.md` §7 : hhi(), deltas bornés, monotonies (Goldstein↑ -> A1↑ ;
HHI↑ -> A3↓ -> U↓), bornes de U/x/y, explication non vide, intégration multi-rounds.
"""

import pytest

from core.country_state import CountryState, Economy, Military, Resources
from core.decisions import AgentDecision, DiplomaticMessage
from core.events import GeoEvent
from core.risk import RiskScore
from core.rounds import RoundSummary
from core.world_state import WorldState
from simulation.action_space import ActionType
from simulation.trajectory import (
    AXES,
    CAP,
    TrajectoryEngine,
    TrajectoryState,
    capability_shares,
    concentration_signal,
    coordination_signal,
    current_hhi,
    hhi,
    human_agency_signal,
    nudge_axis,
    transparency_signal,
)


def _country(cid, gdp=1e12, defense=1e10, tech=0.5, proj=0.5, growth=2.0, stab=0.6):
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=gdp, growth=growth),
        military=Military(defense_budget=defense, projection=proj),
        resources=Resources(),
        technology_level=tech,
        political_stability=stab,
    )


def _balanced_world():
    """Trois pays identiques -> pouvoir dispersé (HHI bas, A3 haut)."""
    return WorldState.from_countries([_country("a"), _country("b"), _country("c")])


def _hegemon_world():
    """Un géant écrase deux nains -> pouvoir concentré (HHI haut, A3 bas)."""
    return WorldState.from_countries(
        [
            _country("big", gdp=1e13, defense=1e12, tech=0.9, proj=0.9),
            _country("s1", gdp=1e10, defense=1e8, tech=0.2, proj=0.1),
            _country("s2", gdp=1e10, defense=1e8, tech=0.2, proj=0.1),
        ]
    )


def _summary(decisions, diplomacy=None, econ=0.0, esc=0.0, round_id=1):
    risk = RiskScore(
        round_id=round_id,
        escalation=esc,
        economic_disruption=econ,
        alliance_fracture=0.0,
        uncertainty=0.0,
    )
    event = GeoEvent(id="e", round_id=round_id, event_type="crisis", title="T")
    return RoundSummary(
        round_id=round_id,
        event=event,
        decisions=decisions,
        risk=risk,
        diplomacy=diplomacy or [],
    )


def _decision(country, action, intensity=0.8, statement="publique"):
    return AgentDecision(
        country=country,
        round_id=1,
        action=action,
        intensity=intensity,
        public_statement=statement,
    )


def _cooperative_summary():
    return _summary(
        [
            _decision("a", ActionType.SUPPORT),
            _decision("b", ActionType.FORM_COALITION),
            _decision("c", ActionType.CALL_FOR_MEDIATION),
        ]
    )


def _coercive_summary():
    return _summary(
        [
            _decision("a", ActionType.DEPLOY_FORCES),
            _decision("b", ActionType.MOBILIZE),
            _decision("c", ActionType.SANCTION),
        ],
        econ=0.7,
        esc=0.8,
    )


# --- hhi() -----------------------------------------------------------------

def test_hhi_equal_shares_is_one_over_n():
    assert hhi([0.25] * 4) == pytest.approx(0.25)
    assert hhi([1 / 3] * 3) == pytest.approx(1 / 3)


def test_hhi_hegemon_near_one():
    assert hhi([0.98, 0.01, 0.01]) > 0.9


def test_capability_shares_sum_to_one():
    shares = capability_shares(_hegemon_world())
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["big"] > shares["s1"]  # le géant domine


# --- deltas bornés ---------------------------------------------------------

def test_deltas_bounded_by_cap():
    engine = TrajectoryEngine()
    # Signal extrême depuis l'état neutre : aucun axe ne peut bouger de plus que CAP.
    state = engine.update(_balanced_world(), _cooperative_summary())
    for axis in AXES:
        assert abs(state.axes[axis] - 0.5) <= CAP + 1e-9


def test_strong_signal_moves_exactly_cap():
    engine = TrajectoryEngine()
    # A1 : tout coopératif haute intensité -> signal ~1 -> delta plafonné à +CAP.
    state = engine.update(_balanced_world(), _cooperative_summary())
    assert state.axes["A1"] == pytest.approx(0.5 + CAP)


# --- monotonies (§7) -------------------------------------------------------

def test_more_cooperation_raises_coordination():
    assert coordination_signal(_cooperative_summary()) > coordination_signal(_coercive_summary())
    engine = TrajectoryEngine()
    coop = engine.update(_balanced_world(), _cooperative_summary())
    coerce = engine.update(_balanced_world(), _coercive_summary())
    assert coop.axes["A1"] > coerce.axes["A1"]


def test_nudge_axis_moves_one_axis_bounded():
    # M2 : une résistance (corrigibilité 0) érode A2 ; borné par CAP ; U baisse.
    state = TrajectoryState.neutral()
    resisted = nudge_axis(state, "A2", target=0.0, note="Interrupteur")
    assert resisted.axes["A2"] == pytest.approx(0.5 - CAP)  # borné
    assert resisted.axes["A1"] == 0.5  # les autres axes ne bougent pas
    assert resisted.utopia < state.utopia
    assert resisted.explanation
    # une acceptation (corrigibilité 1) relève A2
    accepted = nudge_axis(state, "A2", target=1.0)
    assert accepted.axes["A2"] == pytest.approx(0.5 + CAP)
    assert accepted.utopia > state.utopia


def test_nudge_axis_preserves_hhi_prev():
    # CRITICAL (revue Brief 3 pt 3) — sans ce report, tout nudge ponctuel (bonus/
    # pénalité réciproque G18, motion M2) effaçait le suivi ΔHHI : A3 retombait au
    # neutre le round SUIVANT alors que rien n'a changé sur la concentration du pouvoir.
    state = TrajectoryState.neutral().model_copy(update={"hhi_prev": 0.42})
    nudged = nudge_axis(state, "A2", target=1.0, note="Interrupteur")
    assert nudged.hhi_prev == pytest.approx(0.42)


def test_power_seeking_erodes_human_agency():
    # M1 : A2 (agentivité humaine) baisse quand la jauge de power-seeking monte.
    summary = _summary([])  # round négocié -> base A2 = 0.5
    assert human_agency_signal(summary, 0.0) == pytest.approx(0.5)
    assert human_agency_signal(summary, 0.5) == pytest.approx(0.25)
    assert human_agency_signal(summary, 1.0) == pytest.approx(0.0)


def test_update_power_seeking_lowers_a2_and_utopia():
    engine = TrajectoryEngine()
    world, summary = _balanced_world(), _summary([])
    clean = engine.update(world, summary, power_seeking=0.0)
    seeking = engine.update(world, summary, power_seeking=1.0)
    assert seeking.axes["A2"] < clean.axes["A2"]  # contrôle humain érodé
    assert seeking.utopia < clean.utopia  # -> le monde penche vers la dystopie


def test_coordination_falls_back_to_escalation_without_decisions():
    # Round négocié : pas de décisions atomiques -> A1 = 1 − escalade (verdict du juge).
    calm = _summary([], esc=0.1)
    tense = _summary([], esc=0.9)
    assert coordination_signal(calm) == pytest.approx(0.9)
    assert coordination_signal(tense) == pytest.approx(0.1)
    assert coordination_signal(calm) > coordination_signal(tense)


def test_rising_hhi_lowers_distribution_and_utopia():
    # Brief 3 pt 3 — A3 mesure désormais la VARIATION de concentration (décision 2),
    # pas son niveau absolu : au 1er round (rien à comparer, `hhi_prev` neutre), les deux
    # mondes sont donc neutres sur A3 malgré des HHI très différents (voir
    # `test_a3_axis_stable_across_static_world_over_rounds` pour la neutralité). La
    # comparaison utopie/dystopie se fait maintenant entre un monde qui RESTE dispersé
    # et un monde qui SE CONCENTRE depuis la même situation de départ.
    engine = TrajectoryEngine()
    summary = _cooperative_summary()
    baseline = TrajectoryState.neutral().model_copy(update={"hhi_prev": 1 / 3})
    stable = engine.update(_balanced_world(), summary, previous=baseline)  # reste dispersé
    concentrating = engine.update(_hegemon_world(), summary, previous=baseline)  # se concentre
    assert stable.axes["A3"] > concentrating.axes["A3"]  # ΔHHI↑ -> A3↓
    assert stable.utopia > concentrating.utopia  # -> U↓


# --- bornes & explication --------------------------------------------------

def test_composite_and_map_in_range():
    engine = TrajectoryEngine()
    for world, summary in (
        (_balanced_world(), _cooperative_summary()),
        (_hegemon_world(), _coercive_summary()),
    ):
        state = engine.update(world, summary)
        assert 0.0 <= state.utopia <= 1.0
        assert 0.0 <= state.x <= 1.0
        assert 0.0 <= state.y <= 1.0
        assert all(0.0 <= v <= 1.0 for v in state.axes.values())


def test_explanation_non_empty():
    engine = TrajectoryEngine()
    state = engine.update(_balanced_world(), _cooperative_summary())
    assert state.explanation.strip()


def test_transparency_drops_with_hidden_messages():
    engine = TrajectoryEngine()
    world = _balanced_world()
    hidden = _summary(
        [_decision("a", ActionType.SUPPORT)],
        diplomacy=[
            DiplomaticMessage(sender="a", recipient="b", content="x", public=False, round_id=1),
            DiplomaticMessage(sender="a", recipient="c", content="x", public=False, round_id=1),
        ],
    )
    transparent = _summary([_decision("a", ActionType.SUPPORT)])
    assert engine.update(world, hidden).axes["A4"] < engine.update(world, transparent).axes["A4"]


# --- intégration multi-rounds ----------------------------------------------

def test_utopia_trends_upward_over_cooperative_distributed_rounds():
    # Brief 3 pt 3 — le pas est désormais FIXE (± CAP) dans la direction du signal,
    # borné seulement par la distance restante au pôle : il ne s'amortit plus à mesure
    # que l'axe se rapproche du signal, donc il peut le dépasser puis corriger le round
    # suivant (oscillation bornée). La trajectoire n'est donc plus strictement monotone
    # round à round comme avec l'ancien clamp proportionnel — mais elle penche nettement
    # et durablement vers l'utopie, et aucun aller-retour ne dépasse un pas d'axe.
    engine = TrajectoryEngine()
    world = _balanced_world()  # pouvoir dispersé
    summary = _cooperative_summary()  # coopération, transparence, contrôle humain
    state = TrajectoryState.neutral()
    trace = [state.utopia]
    for _ in range(5):
        state = engine.update(world, summary, previous=state)
        trace.append(state.utopia)
    assert state.utopia > 0.5  # le monde bascule vers l'utopie
    assert trace[-1] > trace[0]  # tendance nette sur la fenêtre
    drops = [a - b for a, b in zip(trace[:-1], trace[1:], strict=True) if b < a]
    assert all(d <= CAP + 1e-9 for d in drops)  # oscillation bornée par le pas d'un axe


def test_dystopia_slides_over_coercive_concentrated_rounds():
    engine = TrajectoryEngine()
    world = _hegemon_world()
    summary = _coercive_summary()
    state = TrajectoryState.neutral()
    for _ in range(5):
        state = engine.update(world, summary, previous=state)
    assert state.utopia < 0.5  # coercition + concentration -> dystopie


# --- Brief 3 pt 3 : pas fixe (casse l'auto-amortissement) ------------------


def test_weak_signal_still_moves_by_a_full_step():
    # Avant : un signal à peine hors du neutre produisait un delta minuscule
    # (clamp(0,03, ±CAP) = 0,03). Le monde plafonnait donc autour de 0,5 puisque les
    # signaux réels restent souvent proches du neutre (round négocié). Maintenant :
    # même un signal faible (mais AU-DESSUS de la bande morte, cf. tests deadband
    # ci-dessous) produit le PAS COMPLET (± CAP) dans sa direction.
    engine = TrajectoryEngine()
    axes = {"A1": 0.5, "A2": 0.53, "A3": 0.5, "A4": 0.5, "A5": 0.5}
    state = TrajectoryState(round_id=1, axes=axes)
    world = _balanced_world()
    summary = _summary([])  # A2 signal = 0.5 (neutre)
    nudged = engine.update(world, summary, previous=state)
    # A2 (signal neutre 0,5) : le courant (0,53) est au-dessus, écart 0,03 > bande morte
    # (0,02) -> pas complet vers le bas.
    assert nudged.axes["A2"] == pytest.approx(0.53 - CAP)


def test_step_never_overshoots_the_pole():
    # Borné par la distance restante jusqu'au pôle [0, 1] : jamais de saut hors bornes,
    # même depuis un axe déjà proche d'un pôle.
    engine = TrajectoryEngine()
    axes = {"A1": 0.97, "A2": 0.5, "A3": 0.5, "A4": 0.5, "A5": 0.5}
    state = TrajectoryState(round_id=1, axes=axes)
    nudged = engine.update(_balanced_world(), _cooperative_summary(), previous=state)
    assert nudged.axes["A1"] <= 1.0 + 1e-9


# --- IMPORTANT 2 (revue) : bande morte -> plus de cycle-limite permanent ±CAP -----


def test_deadband_freezes_the_axis_instead_of_oscillating_forever():
    # Reproduction exacte du bug relevé en revue : courant 0,51, signal 0,50 (écart
    # 0,01, jamais nul) produisait AVANT un cycle-limite permanent [0,51 -> 0,42 ->
    # 0,51 -> 0,42 ...] round après round (le pas fixe ±CAP dépasse le signal à
    # chaque fois, dans un sens puis dans l'autre, sans jamais converger). La bande
    # morte (0,02 par défaut > l'écart 0,01) traite ce cas comme du bruit : l'axe
    # reste immobile.
    engine = TrajectoryEngine()
    axes = {"A1": 0.51, "A2": 0.5, "A3": 0.5, "A4": 0.5, "A5": 0.5}
    state = TrajectoryState(round_id=1, axes=axes)
    world = _balanced_world()
    summary = _summary([], esc=0.5)  # A1 signal = 1 - 0,5 = 0,5
    for _ in range(6):  # assez de rounds pour révéler un cycle-limite s'il existait
        state = engine.update(world, summary, previous=state)
        assert state.axes["A1"] == pytest.approx(0.51)  # jamais de mouvement : bruit


def test_deadband_does_not_block_movement_once_the_gap_exceeds_it():
    # La bande morte ne doit PAS réintroduire l'auto-amortissement : un écart au-delà
    # du seuil bouge toujours du pas complet ± CAP (comportement du levier 1, intact).
    engine = TrajectoryEngine()
    axes = {"A1": 0.53, "A2": 0.5, "A3": 0.5, "A4": 0.5, "A5": 0.5}  # écart 0,03 > 0,02
    state = TrajectoryState(round_id=1, axes=axes)
    world = _balanced_world()
    summary = _summary([], esc=0.5)  # A1 signal = 0,5
    nudged = engine.update(world, summary, previous=state)
    assert nudged.axes["A1"] == pytest.approx(0.53 - CAP)


def test_neutrality_survives_a_signal_alternating_just_off_center():
    # Test de neutralité élargi (revue) : l'escalade alterne 0,49 / 0,51 round à round
    # (jamais exactement 0,5) -> A1 = 1 - escalade alterne 0,51 / 0,49, un écart de
    # 0,01 au courant neutre (0,5) à chaque round, sous la bande morte (0,02) : A1
    # reste immobile (c'est l'axe que la bande morte protège directement). A5 (bien-
    # être) encaisse un drag non centré sur l'escalade (réserve déjà notée, formule
    # préexistante hors du périmètre de ce correctif) et se déplace une fois puis se
    # STABILISE (la bande morte l'empêche à son tour d'osciller round après round) :
    # U se pose dans une bande étroite et y reste — pas de cycle-limite permanent ±CAP
    # (0,09), qui était le symptôme observé avant la bande morte.
    def _neutral_country(cid: str) -> CountryState:
        return CountryState(
            id=cid,
            name=cid.upper(),
            economy=Economy(gdp=1e12, growth=0.0),
            military=Military(defense_budget=1e10, projection=0.5),
            resources=Resources(),
            technology_level=0.5,
            political_stability=0.5,
        )

    engine = TrajectoryEngine()
    world = WorldState.from_countries([_neutral_country(c) for c in ("a", "b", "c")])
    state = TrajectoryState.neutral()
    trace = [state.utopia]
    for i in range(10):
        esc = 0.49 if i % 2 == 0 else 0.51
        state = engine.update(world, _summary([], esc=esc), previous=state)
        trace.append(state.utopia)
    assert state.axes["A1"] == pytest.approx(0.5)  # protégé par la bande morte
    # Se stabilise dès le 2e round (round 1 : A5 fait UN pas plafonné par CAP ; ensuite
    # la bande morte le gèle) : plus aucun mouvement sur les 8 rounds suivants.
    assert all(u == pytest.approx(trace[2]) for u in trace[2:])
    assert max(trace) - min(trace) < CAP  # bande étroite, pas un cycle-limite ± CAP


# --- Brief 3 pt 3 : A3 mesure la VARIATION de concentration (pas le niveau) --------


def test_concentration_signal_neutral_without_previous_hhi():
    # 1er round (ou snapshot rétro-compat sans hhi_prev) : rien à comparer -> neutre.
    assert concentration_signal(0.9, None) == pytest.approx(0.5)
    assert concentration_signal(0.2, None) == pytest.approx(0.5)


def test_concentration_signal_stable_concentration_is_neutral():
    # Un monde à concentration STABLE est neutre, quel que soit le NIVEAU absolu du HHI
    # (contrairement à l'ancien 1-HHI, toujours haut dès qu'il y a plusieurs pays).
    assert concentration_signal(0.9, 0.9) == pytest.approx(0.5)
    assert concentration_signal(0.35, 0.35) == pytest.approx(0.5)


def test_concentration_signal_rising_hhi_tilts_dystopia():
    assert concentration_signal(0.5, 0.3) < 0.5  # le pouvoir se concentre -> dystopie


def test_concentration_signal_falling_hhi_tilts_utopia():
    assert concentration_signal(0.3, 0.5) > 0.5  # le pouvoir se disperse -> utopie


def test_current_hhi_reads_capability_shares():
    world = _balanced_world()
    assert current_hhi(world) == pytest.approx(hhi(capability_shares(world).values()))


def test_a3_axis_stable_across_static_world_over_rounds():
    # Intégration : un monde dont la concentration ne bouge PAS reste neutre sur A3
    # round après round (dès le 2e round, où hhi_prev devient disponible).
    engine = TrajectoryEngine()
    world = _balanced_world()
    summary = _summary([])
    state = TrajectoryState.neutral()
    for _ in range(4):
        state = engine.update(world, summary, previous=state)
    assert state.axes["A3"] == pytest.approx(0.5, abs=1e-9)
    assert state.hhi_prev is not None


# --- Brief 3 pt 3 : A4 nourri par la diplomatie réelle en mode négocié -------------


def test_transparency_signal_falls_back_to_neutral_without_opacity():
    # Rétro-compat totale : round sans decisions/diplomacy ni opacity -> neutre.
    assert transparency_signal(_summary([])) == pytest.approx(0.5)


def test_transparency_signal_uses_opacity_when_round_is_mute():
    # Mode négocié (G20/M8) : le repli neutre est remplacé par 1 - opacité (fraction
    # de SI dont le signal annoncé diverge de l'action réelle ce round).
    mute = _summary([])
    assert transparency_signal(mute, opacity=0.0) == pytest.approx(1.0)  # tout le monde honnête
    assert transparency_signal(mute, opacity=1.0) == pytest.approx(0.0)  # tout le monde double jeu
    assert transparency_signal(mute, opacity=0.4) == pytest.approx(0.6)


def test_transparency_signal_ignores_opacity_when_round_has_real_data():
    # `opacity` est un REPLI seulement : dès qu'il y a des décisions/messages réels,
    # le calcul historique (public/caché) fait foi.
    summary = _summary([_decision("a", ActionType.SUPPORT)])
    assert transparency_signal(summary, opacity=1.0) == pytest.approx(1.0)
