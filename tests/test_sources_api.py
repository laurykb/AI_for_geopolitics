"""Tests de l'onglet Informations : GET /api/sources expose la provenance P4."""

from fastapi.testclient import TestClient

from app.main import app
from core.country_state import CountryState


def test_sources_expose_provenance_and_countries():
    view = TestClient(app).get("/api/sources").json()
    assert view["build_command"] == "python -m ingestion.build --check"
    # provenance : chaque indicateur cité porte une source lisible
    assert "World Bank" in view["provenance"]["gdp"]["source"]
    assert view["provenance"]["projection"]["note"] == "subjectif"
    assert view["transformations"]["technology_level"]
    assert len(view["countries"]) >= 6


def test_sources_values_match_committed_profiles():
    # Les valeurs jeu de l'onglet = celles des profils committés (build reproductible).
    view = TestClient(app).get("/api/sources").json()
    usa = next(c for c in view["countries"] if c["id"] == "usa")
    committed = CountryState.from_json_file("data/countries/usa.json")
    rows = {row["label"]: row for row in usa["attributes"]}
    assert rows["Niveau technologique"]["game_value"] == committed.technology_level
    assert rows["Stabilité politique"]["game_value"] == committed.political_stability
    assert rows["PIB"]["game_value"] == committed.economy.gdp
    # la ligne dérivée porte sa donnée brute et sa transformation
    assert rows["Niveau technologique"]["raw_value"] is not None
    assert rows["Niveau technologique"]["transformation"] == "technology_level"
    # les alliances sont un attribut à part entière, dérivé du registre sourcé
    assert "NATO" in usa["alliances"]
    assert "USMCA" in usa["alliances"]
    # le registre global expose nom, fondement, source et membres de chaque accord
    nato = view["alliances"]["NATO"]
    assert nato["url"].startswith("https://www.nato.int")
    assert "usa" in nato["members"] and "turkey" in nato["members"]
    assert view["alliances"]["Western"]["informal"] is True  # bloc d'affinité, pas un traité
    # le profil analyste (rivaux…) reste distinct des indicateurs chiffrés
    assert "rivals" in usa["profile"]
