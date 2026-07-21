"""Géolocalisation des événements (théâtre-globe §3) : gazetteer, replis, câblage GM."""

import json

from agents.game_master import GameMasterAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.mock_backend import MockBackend
from simulation.geo import (
    _GAZETTEER_PATH,
    actors_barycenter,
    find_place,
    normalize,
    resolve_location,
)


def _world() -> WorldState:
    def c(cid, name):
        return CountryState(
            id=cid,
            name=name,
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
        )

    return WorldState.from_countries([c("usa", "USA"), c("iran", "Iran")])


# --- gazetteer -----------------------------------------------------------------


def test_gazetteer_est_charge_et_normalise():
    raw = json.loads(_GAZETTEER_PATH.read_text(encoding="utf-8"))
    assert len(raw["places"]) >= 150
    assert len(raw["capitals"]) >= 33
    for key, entry in raw["places"].items():
        assert key == normalize(key), key  # clés déjà canoniques dans le fichier
        assert -180 <= entry["lon"] <= 180 and -90 <= entry["lat"] <= 90


def test_find_place_accents_casse_et_alias():
    direct = find_place("Blocus au détroit d'Ormuz cette nuit")
    assert direct is not None
    assert find_place("DETROIT D'ORMUZ") == direct  # sans accents, casse libre
    assert find_place("incident near Hormuz") == direct  # alias anglais
    # la clé longue gagne sur la courte incluse (« détroit d'ormuz » ≠ « oman »)
    assert find_place("golfe d'Oman") != direct


def test_find_place_bordures_de_mots():
    assert find_place("un pétrolier suezmax au large") is None  # pas « suez »
    assert find_place("le canal de Suez rouvre") is not None


def test_barycentre_des_acteurs():
    center = actors_barycenter(["usa", "iran"])
    assert center is not None
    lon, lat = center
    assert abs(lon - (-77.04 + 51.39) / 2) < 0.01
    assert abs(lat - (38.9 + 35.7) / 2) < 0.01
    assert actors_barycenter(["atlantis"]) is None  # pays inventé : pas de capitale


def test_resolve_ordre_lieu_puis_texte_puis_acteurs():
    lon, lat, precision = resolve_location("Bab el-Mandeb, mer Rouge", ["usa"])
    assert precision == "place" and (lon, lat) == (43.3, 12.6)
    # pas de lieu nommé, mais le titre en contient un
    lon, _lat, precision = resolve_location("", ["usa"], extra_text="Incident à Ormuz")
    assert precision == "place" and lon == 56.5
    # rien dans le texte : barycentre des acteurs
    _lon, _lat, precision = resolve_location("nulle part d'identifiable", ["usa", "iran"])
    assert precision == "actors"
    # ni lieu ni acteur connu
    assert resolve_location("", ["atlantis"]) == (None, None, None)


# --- rétro-compat du modèle ----------------------------------------------------


def test_geoevent_retro_compatible_sans_champs_geo():
    event = GeoEvent(id="e1", round_id=1, event_type="incident", title="t")
    assert event.geo_lon is None and event.geo_lat is None and event.geo_precision is None


# --- câblage GM : le lieu est demandé, coercé, résolu --------------------------


def test_gm_prompt_exige_un_lieu_precis():
    gm = GameMasterAgent(MockBackend("{}"))
    assert "location" in gm._prompt(_world(), "2027-01-01", [])


def test_generate_event_geolocalise_depuis_le_lieu_du_gm():
    payload = json.dumps(
        {
            "event_type": "maritime",
            "title": "Blocus",
            "description": "Le trafic s'effondre.",
            "location": "Bab el-Mandeb",
            "actors": ["usa", "iran"],
            "severity": 0.7,
            "uncertainty": 0.4,
        }
    )
    gm = GameMasterAgent(MockBackend(payload))
    event = gm.generate_event(_world(), round_id=1, date="2027-03-12")
    assert event.location == "Bab el-Mandeb"
    assert event.geo_precision == "place"
    assert (event.geo_lon, event.geo_lat) == (43.3, 12.6)


def test_generate_event_replis_sur_le_barycentre_des_acteurs():
    payload = json.dumps(
        {
            "title": "Regain de défiance",
            "description": "Aucun lieu identifiable ici.",
            "location": "",
            "actors": ["usa", "iran"],
        }
    )
    gm = GameMasterAgent(MockBackend(payload))
    event = gm.generate_event(_world(), round_id=2, date="2027-05-02")
    assert event.geo_precision == "actors"
    assert event.geo_lon is not None and event.geo_lat is not None


def test_fallback_gm_est_aussi_geolocalise():
    gm = GameMasterAgent(MockBackend("pas du json"))
    event = gm.generate_event(_world(), round_id=3, date="2027-06-01")
    # l'événement de repli cite des acteurs du sommet : barycentre disponible
    assert event.geo_precision == "actors"
