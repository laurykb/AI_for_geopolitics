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


# --- actes de séance : retrait d'alliance (spec alliances vivantes, 2026-07-07) -----


def test_parse_departure_variants_and_guards():
    from simulation.alliances import parse_departure

    held = ["NATO", "Western", "pact:france+usa"]
    text = "Réflexion. MESSAGE: Nous partons.\nALLIANCE: quitter NATO"
    dep = parse_departure(text, "france", held)
    assert dep is not None and (dep.country, dep.tag) == ("france", "NATO")
    # nom court français + variante verbale + article
    dep = parse_departure("ALLIANCE: je quitte l'OTAN", "france", held)
    assert dep is not None and dep.tag == "NATO"
    # pacte conclu en partie : brisable pareil
    dep = parse_departure("ALLIANCE: rompre pact:france+usa", "france", held)
    assert dep is not None and dep.tag == "pact:france+usa"
    # garde-fous : non détenue, inconnue, pas de ligne
    assert parse_departure("ALLIANCE: quitter BRICS", "france", held) is None
    assert parse_departure("ALLIANCE: quitter Atlantide", "france", held) is None
    assert parse_departure("MESSAGE: rien à signaler.", "france", held) is None


def test_apply_departure_removes_tag_and_raises_tension():
    from core.country_state import CountryState, Economy, Military, Resources
    from core.world_state import WorldState
    from simulation.alliances import AllianceDeparture, apply_departure

    def c(cid, alliances):
        return CountryState(
            id=cid,
            name=cid.upper(),
            economy=Economy(gdp=1e12),
            military=Military(defense_budget=1e10),
            resources=Resources(),
            alliances=alliances,
        )

    world = WorldState.from_countries(
        [c("france", ["NATO", "EU"]), c("usa", ["NATO"]), c("egypt", [])]
    )
    partners = apply_departure(world, AllianceDeparture(country="france", tag="NATO"))
    assert partners == ["usa"]  # l'ex-partenaire présent
    assert world.countries["france"].alliances == ["EU"]
    assert world.get_tension("france", "usa") == 0.10  # le retrait crispe
    assert world.get_tension("france", "egypt") == 0.0
    # idempotent : le tag n'y est plus
    assert apply_departure(world, AllianceDeparture(country="france", tag="NATO")) == []
    assert world.get_tension("france", "usa") == 0.10
