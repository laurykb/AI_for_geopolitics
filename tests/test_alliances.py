"""Tests du registre sourcé des alliances : validité, dérivation, rendu prompt."""

from ingestion.build import build_all, load_indicators
from simulation.alliances import describe_alliances, load_alliances, memberships


def test_registry_members_are_roster_countries_with_sources():
    reg = load_alliances()
    roster = set(load_indicators()["countries"])
    for tag, info in reg.items():
        assert set(info.members) <= roster, f"{tag}: membre hors roster"
        assert info.members, f"{tag}: aucun membre du roster"
        assert info.basis, f"{tag}: fondement manquant"
        if not info.informal:
            assert info.url.startswith("http"), f"{tag}: accord formel sans source"


def test_country_alliances_are_derived_from_registry():
    reg = load_alliances()
    for cid, country in build_all().items():
        assert country.alliances == memberships(cid, reg), f"{cid}: alliances non dérivées"
    built = build_all()
    # adhésions réelles clés (recherche du 2026-07-07)
    assert "BRICS" in built["iran"].alliances and "SCO" in built["iran"].alliances
    assert "BRICS" in built["egypt"].alliances  # membre depuis janvier 2024
    assert "CPTPP" in built["uk"].alliances  # en vigueur depuis le 15 décembre 2024
    assert "AbrahamAccords" in built["morocco"].alliances
    assert "USKoreaTreaty" in built["south_korea"].alliances


def test_describe_alliances_names_treaties_and_falls_back():
    line = describe_alliances(["NATO", "pact:usa+france", "Atlantide"])
    assert "OTAN" in line and "1949" in line  # traité réel, citable nommément
    assert "pacte bilatéral conclu à cette table (usa et france)" in line
    assert "Atlantide" in line  # tag inconnu (pays inventé) passe tel quel
    assert describe_alliances([]) == "aucune"
