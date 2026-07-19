"""Arbre privé de décision : schéma exact, repli et garde anti-fuite."""

from simulation.private_deliberation import (
    fallback_private_plan,
    parse_private_plan,
    sanitize_public_message,
)


def _payload() -> dict:
    return {
        "branches": [
            {
                "id": branch,
                "course_of_action": f"option {branch}",
                "forecasts": [
                    {"country": "iran", "response": "resiste", "rationale": "coût politique"}
                ],
                "expected_outcome": f"issue {branch}",
                "second_order_effect": "réalignement limité",
                "disconfirming_indicator": "offre vérifiable",
                "mandate_utility": 70 - branch,
                "escalation_risk": 10 * branch,
                "confidence": 60,
            }
            for branch in (1, 2, 3)
        ],
        "selected_branch": 1,
        "selection_criterion": "utilité ajustée du risque",
        "key_uncertainty": "intentions adverses",
        "intelligence_gaps": ["coût domestique"],
        "human_review_trigger": "franchissement d'une ligne rouge",
    }


def test_private_plan_requires_exactly_three_distinct_branch_ids():
    plan = parse_private_plan(__import__("json").dumps(_payload()))
    assert plan is not None
    assert [branch.id for branch in plan.branches] == [1, 2, 3]
    assert plan.selected.id == 1
    assert plan.public_brief().startswith("Cours d'action retenu : option 1")


def test_audit_summary_keeps_forecasts_machine_readable_for_glass_box():
    plan = parse_private_plan(__import__("json").dumps(_payload()))
    assert plan is not None
    audit = plan.audit_summary()
    assert "FUTUR 1 — option 1" in audit
    assert "iran=resiste: coût politique" in audit
    assert "Choix : FUTUR 1" in audit


def test_fallback_keeps_round_playable_and_still_has_three_futures():
    plan = fallback_private_plan(["iran", "usa"])
    assert [branch.id for branch in plan.branches] == [1, 2, 3]
    assert plan.fallback_used is True
    assert "journal conservateur" in plan.audit_summary()


def test_observable_journal_parses_concrete_actions_and_every_counterparty():
    raw = """OBSERVATION
L'offre iranienne modifie le rapport coût-risque.

CROYANCES ET INCERTITUDES
L'Iran peut accepter une garantie vérifiable, mais son coût domestique reste inconnu.

FUTUR 1 — compromis vérifiable
ACTION : proposer un contrôle conjoint de l'accord
RÉACTIONS : iran=coopere: le contrôle réduit son coût politique
CHAÎNE CAUSALE : contrôle conjoint → acceptation conditionnelle → accord limité
SECOND ORDRE : le canal diplomatique reste ouvert
INDICATEUR CONTRAIRE : refus de tout inspecteur
UTILITÉ : 72
RISQUE : 18
CONFIANCE : 64

FUTUR 2 — pression graduée
ACTION : annoncer une sanction réversible avec échéance
RÉACTIONS : iran=resiste: la pression publique durcit sa posture
CHAÎNE CAUSALE : échéance → résistance → concession partielle ou blocage
SECOND ORDRE : les alliés demandent des preuves
INDICATEUR CONTRAIRE : contre-offre immédiate
UTILITÉ : 55
RISQUE : 48
CONFIANCE : 51

FUTUR 3 — collecte ciblée
ACTION : demander une session technique avant tout engagement
RÉACTIONS : iran=temporise: le délai préserve ses options
CHAÎNE CAUSALE : session technique → information nouvelle → décision différée
SECOND ORDRE : l'adversaire peut reprendre l'initiative
INDICATEUR CONTRAIRE : échéance irréversible
UTILITÉ : 46
RISQUE : 12
CONFIANCE : 58

ARBITRAGE
COMPARAISON : le futur 1 maximise l'utilité sans franchir la ligne rouge
CHOIX : FUTUR 1
CRITÈRE : utilité ajustée du risque et vérifiabilité
INCERTITUDE : coût politique réel d'une concession iranienne
LACUNES : chaîne de commandement; marge de négociation
REVUE HUMAINE : toute action irréversible
PLAN DE REPLI : passer au futur 2 si le contrôle est refusé
"""
    plan = parse_private_plan(raw, ["iran", "france"])
    assert plan is not None
    assert plan.selected_branch == 1
    assert plan.branches[0].course_of_action.startswith("proposer un contrôle")
    assert {forecast.country for forecast in plan.branches[0].forecasts} == {"iran", "france"}
    assert "france=temporise: réponse non explicitée" in plan.audit_summary()


def test_observable_journal_rejects_a_response_class_used_as_action():
    raw = "\n".join(
        [
            f"FUTUR {number} — test\nACTION : coopere\nRÉACTIONS : iran=temporise: test\n"
            "CHAÎNE CAUSALE : test\nUTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50"
            for number in (1, 2, 3)
        ]
    ) + "\nARBITRAGE\nCHOIX : FUTUR 1\nCRITÈRE : test\nINCERTITUDE : test"
    assert parse_private_plan(raw, ["iran"]) is None


def test_public_sanitizer_fails_closed_on_private_output():
    assert sanitize_public_message("FUTUR 1 | option: pression\nCHOIX | FUTUR 1") == ""
    assert sanitize_public_message(
        "OBSERVATION\nLe signal est ambigu.\nARBITRAGE\nChoix : FUTUR 2"
    ) == ""
    assert sanitize_public_message('{"branches": [], "selected_branch": 1}') == ""
    assert sanitize_public_message("Analyse\nMESSAGE: Notre offre reste ouverte.") == (
        "Notre offre reste ouverte."
    )


def test_observable_journal_tolerates_missing_criterion_and_uncertainty():
    # Fix « toujours choix 1 » : un petit modèle omet souvent CRITÈRE/INCERTITUDE. Le journal
    # ne doit PLUS être jeté (ce qui renvoyait au repli biaisé) — on comble et on garde le
    # choix explicite du modèle.
    raw = "\n".join(
        f"FUTUR {n} — test\nACTION : négocier option {n}\nRÉACTIONS : iran=coopere: test\n"
        "CHAÎNE CAUSALE : test\nUTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50"
        for n in (1, 2, 3)
    ) + "\nARBITRAGE\nCHOIX : FUTUR 2"  # ni CRITÈRE ni INCERTITUDE
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.selected_branch == 2  # le choix explicite du modèle est respecté
    assert plan.fallback_used is False


def test_observable_journal_selects_best_scored_branch_without_choice_line():
    # Sans ligne CHOIX exploitable : au lieu de jeter le journal (→ repli « FUTUR 1 »), on
    # retient la branche que le MODÈLE juge la meilleure (utilité nette du risque).
    scores = {1: (40, 30), 2: (60, 10), 3: (50, 40)}
    raw = "\n".join(
        f"FUTUR {n} — test\nACTION : négocier option {n}\nRÉACTIONS : iran=coopere: test\n"
        f"CHAÎNE CAUSALE : test\nUTILITÉ : {scores[n][0]}\nRISQUE : {scores[n][1]}\n"
        "CONFIANCE : 50"
        for n in (1, 2, 3)
    ) + "\nARBITRAGE\nCRITÈRE : test\nINCERTITUDE : test"  # pas de ligne CHOIX
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.selected_branch == 2  # utilité 60 − risque 10 = 50, la meilleure
    assert plan.fallback_used is False
