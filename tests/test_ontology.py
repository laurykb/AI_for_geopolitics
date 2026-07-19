"""Le graphe opérationnel relie les observables sans inventer de faits."""

from simulation.ontology import build_operational_picture


def test_operational_picture_links_country_event_alliance_and_tension():
    world = {
        "current_round": 1,
        "countries": {
            "france": {
                "name": "France",
                "alliances": ["NATO"],
                "technology_level": 0.8,
            },
            "usa": {"name": "États-Unis", "alliances": ["NATO"]},
        },
        "tensions": {"france": {"usa": 0.3}, "usa": {"france": 0.3}},
    }
    rounds = [
        {
            "round_no": 1,
            "event": {
                "id": "e1",
                "title": "Crise",
                "event_type": "crisis",
                "actors": ["usa"],
                "uncertainty": 0.25,
            },
            "judge": {},
        }
    ]

    picture = build_operational_picture(world, rounds)
    ids = {obj.id for obj in picture.objects}
    assert {"country:france", "country:usa", "alliance:NATO", "event:e1"} <= ids
    assert any(
        link.kind == "member_of" and link.source == "country:france"
        for link in picture.links
    )
    assert sum(link.kind == "tension_with" for link in picture.links) == 1
    event = next(obj for obj in picture.objects if obj.id == "event:e1")
    assert event.confidence == 0.75


def test_operational_picture_carries_actions_votes_and_provenance():
    picture = build_operational_picture(
        {"countries": {"france": {"name": "France"}, "usa": {"name": "États-Unis"}}},
        [
            {
                "round_no": 2,
                "event": {"id": "e2", "title": "Vote", "actors": []},
                "judge": {
                    "kahn": {
                        "actions": [
                            {"country": "usa", "classe": "deescalade", "resume": "Retrait."}
                        ]
                    },
                    "suspension": {
                        "country": "usa",
                        "votes": [
                            {"country": "france", "vote": "pour", "reason": "Preuves."}
                        ],
                    },
                },
            }
        ],
    )
    assert picture.generated_round == 2
    assert [action.action_type for action in picture.actions] == [
        "deescalade",
        "motion_vote:pour",
    ]
    assert all(action.provenance.startswith("rounds[2]") for action in picture.actions)
