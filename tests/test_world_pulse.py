"""Le Pouls du monde + instabilité (théâtre-globe §13) — pur, déterministe, hors ligne."""

from core.country_state import CountryState, Economy, Military, Resources
from core.world_state import WorldState
from simulation.instability import convergence_alerts, country_risk, instability_index
from simulation.world_pulse import apply_pulse, roll_pulses

SUMMIT = ["usa", "china", "iran", "france", "egypt"]


def _country(cid: str, *, growth=2.0, stab=0.6) -> CountryState:
    return CountryState(
        id=cid,
        name=cid.upper(),
        economy=Economy(gdp=1e12, growth=growth),
        military=Military(defense_budget=1e10),
        resources=Resources(),
        political_stability=stab,
    )


def _world() -> WorldState:
    return WorldState.from_countries([_country(c) for c in SUMMIT])


# --- world pulse : déterminisme, bornes, summit-only -----------------------------


def test_pulses_deterministes():
    a = roll_pulses(42, 3, SUMMIT)
    b = roll_pulses(42, 3, SUMMIT)
    assert [e.model_dump() for e in a] == [e.model_dump() for e in b]


def test_seed_ou_round_different_change_le_tirage():
    base = roll_pulses(42, 3, SUMMIT)
    assert base != roll_pulses(43, 3, SUMMIT) or base != roll_pulses(42, 4, SUMMIT)


def test_ne_frappe_que_le_sommet_et_jamais_deux_fois_le_meme():
    for r in range(30):
        evs = roll_pulses(7, r, SUMMIT, intensity="turbulent")
        countries = [e.country for e in evs]
        assert all(c in SUMMIT for c in countries)
        assert len(countries) == len(set(countries))  # pas de doublon dans un round


def test_exclusion_du_pays_forge():
    for r in range(40):
        evs = roll_pulses(9, r, SUMMIT, intensity="turbulent", exclude={"iran"})
        assert all(e.country != "iran" for e in evs)


def test_intensite_calme_borne_le_nombre():
    for r in range(40):
        assert len(roll_pulses(1, r, SUMMIT, intensity="calme")) <= 1


def test_deltas_dans_les_bornes_de_la_table():
    from simulation.world_pulse import PULSE_KINDS

    by_key = {k["key"]: k for k in PULSE_KINDS}
    for r in range(60):
        for e in roll_pulses(3, r, SUMMIT, intensity="turbulent"):
            k = by_key[e.key]
            assert k["lo"] <= e.delta <= k["hi"]
            assert e.boon == (e.delta > 0)


def test_apply_pulse_ne_mute_pas_et_borne():
    from simulation.world_pulse import PulseEvent

    c = _country("iran", growth=1.0, stab=0.05)
    ev = PulseEvent(
        round_id=1,
        country="iran",
        key="seisme",
        label="Séisme",
        stat="stability",
        delta=-0.5,
        boon=False,
    )
    out = apply_pulse(c, ev)
    assert c.political_stability == 0.05  # original intact
    assert out.political_stability == 0.0  # borné à 0
    boon = PulseEvent(
        round_id=1, country="iran", key="manne", label="Manne", stat="growth", delta=0.05, boon=True
    )
    assert apply_pulse(c, boon).economy.growth == 1.0 + 5.0  # +0.05*100 pts


# --- instabilité + convergence ---------------------------------------------------


def test_risque_monte_avec_tension_et_instabilite():
    w = _world()
    calme = country_risk(w, "usa").score
    w.adjust_tension("usa", "china", 0.9)
    w.adjust_tension("usa", "iran", 0.8)
    w.countries["usa"].political_stability = 0.1
    w.countries["usa"].economy.growth = -3.0
    tendu = country_risk(w, "usa").score
    assert tendu > calme


def test_convergence_exige_deux_familles_chaudes():
    w = _world()
    # une seule famille chaude (tension) -> pas de convergence
    w.adjust_tension("iran", "usa", 0.95)
    w.adjust_tension("iran", "china", 0.9)
    r1 = country_risk(w, "iran")
    assert "tension" in r1.hot and not r1.converging
    # on allume une 2e famille (instabilité) -> convergence
    w.countries["iran"].political_stability = 0.05
    r2 = country_risk(w, "iran")
    assert r2.converging and "iran" in convergence_alerts(w)


def test_index_couvre_tout_le_monde():
    idx = instability_index(_world())
    assert set(idx) == set(SUMMIT)
    assert all(0.0 <= r.score <= 1.0 for r in idx.values())


def test_promesses_rompues_augmentent_le_risque():
    w = _world()
    base = country_risk(w, "france").score
    withbroken = country_risk(w, "france", broken_promises=3).score
    assert withbroken > base
