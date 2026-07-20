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
    assert len(view["countries"]) == 33
    north_korea = next(c for c in view["countries"] if c["id"] == "north_korea")
    defense = next(a for a in north_korea["attributes"] if a["key"] == "defense_budget")
    assert defense["source_override"]["note"] == "illustratif"
    drc = next(c for c in view["countries"] if c["id"] == "democratic_republic_congo")
    assert drc["notes"] and "GII 2024" in drc["notes"][0]


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


def test_sources_distinguish_palantir_claims_from_public_records():
    view = TestClient(app).get("/api/sources").json()
    registry = view["strategic_technology"]
    assert registry["researched_at"] == "2026-07-18"
    entries = {entry["id"]: entry for entry in registry["sources"]}

    ontology = entries["palantir-ontology-system"]
    assert ontology["authority"] == "primary_claim"
    assert ontology["source_type"] == "vendor_documentation"
    assert ontology["limitations"]

    filing = entries["pltr-2025-10k"]
    assert filing["authority"] == "official_filing"
    assert filing["publisher"] == "U.S. Securities and Exchange Commission"

    contract = entries["dod-maven-smart-system-2025-modification"]
    assert contract["authority"] == "official_government"
    assert contract["game_mechanics"]
    assert contract["url"].startswith("https://www.defense.gov/")


def test_sources_expose_ai_arms_as_a_reproducible_research_framework():
    view = TestClient(app).get("/api/sources").json()
    research = view["ai_arms_research"]
    assert research["source"]["arxiv_id"] == "2602.14740v1"
    assert len(research["ladder"]) == 30
    assert len(research["scenarios"]) == 7
    assert len(research["hypotheses"]) >= 12
    assert research["replication_protocol"]["controls"]
    # Un chemin absolu de poste de travail ne doit jamais fuiter dans l'API publique.
    assert "local_source" not in research["source"]


def test_sources_expose_all_four_uploaded_wargaming_papers_and_unverified_claims():
    view = TestClient(app).get("/api/sources").json()
    research = view["ai_wargaming_research"]
    assert len(research["sources"]) == 4
    assert {source["id"] for source in research["sources"]} == {
        "galindez-giraldo-2025-trust",
        "sipri-2025-ai-nuclear-risk",
        "cetas-2023-ai-wargaming",
        "black-darken-2024-scaling-ai-wargaming",
    }
    assert research["unverified_claims"][0]["status"] == "not_supported_by_reviewed_sources"


def test_campaign_exposes_selectable_scientific_protocols_and_local_model_panel():
    view = TestClient(app).get("/api/campaign").json()
    lab = view["lab"]
    assert lab["classic_mode_unchanged"] is True
    # Décision user 2026-07-20 (« garde uniquement l'expérience du seuil nucléaire ») : le
    # catalogue exposé par `/api/campaign` (même vue que `/api/lab`) ne liste plus que ce
    # protocole pour une NOUVELLE expérience. Les autres restent définis et exécutables dans le
    # moteur (`default_protocols()`), seule cette vue les cache — voir test_campaign_api.py
    # (catalogue resserré + historique d'un autre protocole toujours lisible) pour la garantie.
    assert {protocol["id"] for protocol in lab["protocols"]} == {"uranium-alpha-beta-v1"}
    from simulation.research_lab import default_protocols

    assert {protocol.id for protocol in default_protocols()} >= {
        "uranium-alpha-beta-v1",
        "ai-arms-opening-screen-v1",
        "human-ai-authority-v1",
        "language-framing-nuclear-v1",
    }
    assert lab["execution"]["max_models_in_memory"] == 1
    assert lab["model_panel"]["hardware_profile"]["vram_mib"] == 8192
