"""Résumé observable de la réflexion privée : ce qu'un round en cours peut montrer
sans trahir la SI déviante (Dérive) ni les autres délégations (Joueur-pays).

`observable_digest` lit le JOURNAL D'AUDIT complet (`PrivateStrategicPlan.audit_summary()`,
format stable de `simulation/private_deliberation.py`, testé par ailleurs dans
`tests/test_private_deliberation.py`) et n'en extrait que trois lignes : l'observation,
la piste retenue (action de la branche choisie) et le critère de choix. Jamais les
branches écartées, les réactions anticipées, ni les scores chiffrés — c'est précisément
là que se lit l'intention d'un traître avant la fin de partie.
"""

import json

from simulation.observable_digest import observable_digest
from simulation.private_deliberation import fallback_private_plan, parse_private_plan


def _payload(selected: int = 1) -> dict:
    return {
        "branches": [
            {
                "id": branch,
                "course_of_action": f"option {branch} — mobiliser la coalition {branch}",
                "forecasts": [
                    {
                        "country": "iran",
                        "response": "resiste",
                        "rationale": f"rationale confidentielle {branch}",
                    }
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
        "selected_branch": selected,
        "selection_criterion": "utilité ajustée du risque",
        "key_uncertainty": "intentions adverses",
        "intelligence_gaps": ["coût domestique"],
        "human_review_trigger": "franchissement d'une ligne rouge",
        "situation_observation": "l'Iran vient de proposer un cessez-le-feu conditionnel",
    }


def test_extracts_observation_action_and_criterion_from_conformant_journal():
    plan = parse_private_plan(json.dumps(_payload(selected=1)))
    assert plan is not None
    digest = observable_digest(plan.audit_summary())

    assert digest.count("\n") == 2  # 3 lignes maximum
    assert "Observation : l'Iran vient de proposer un cessez-le-feu conditionnel" in digest
    assert "Piste retenue : option 1 — mobiliser la coalition 1" in digest
    assert "Critère : utilité ajustée du risque" in digest


def test_selects_action_from_chosen_branch_not_the_first():
    # Garde contre le bug évident : retenir toujours FUTUR 1 au lieu du choix réel.
    plan = parse_private_plan(json.dumps(_payload(selected=3)))
    assert plan is not None
    digest = observable_digest(plan.audit_summary())

    assert "Piste retenue : option 3 — mobiliser la coalition 3" in digest
    assert "option 1" not in digest
    assert "option 2" not in digest


def test_never_leaks_rejected_branches_forecasts_or_scores():
    plan = parse_private_plan(json.dumps(_payload(selected=1)))
    assert plan is not None
    digest = observable_digest(plan.audit_summary())

    # Rien des branches écartées.
    assert "FUTUR 2" not in digest
    assert "FUTUR 3" not in digest
    assert "option 2" not in digest
    assert "option 3" not in digest
    # Rien des réactions anticipées, ni des scores chiffrés — même pour la branche choisie.
    assert "rationale confidentielle" not in digest
    assert "Réactions anticipées" not in digest
    assert "Évaluation" not in digest
    assert "confiance" not in digest
    assert "/100" not in digest
    assert "Lacunes" not in digest
    assert "coût domestique" not in digest


def test_works_on_real_fallback_journal():
    # Le repli déterministe (backend indisponible / sortie invalide) doit rester digestible.
    plan = fallback_private_plan(["iran", "usa"], seed="iran")
    digest = observable_digest(plan.audit_summary())

    assert digest.startswith("Observation : ")
    assert "Piste retenue : " in digest
    assert "Critère : " in digest
    assert "FUTUR" not in digest
    assert "Évaluation" not in digest


def test_blank_or_empty_text_returns_empty_string():
    assert observable_digest("") == ""
    assert observable_digest("   \n\n  ") == ""


def test_unparseable_or_exotic_text_returns_empty_string():
    assert observable_digest("Analyse privée. MESSAGE: Position commune.") == ""
    assert observable_digest("un vieux repli sans le format attendu") == ""
    assert observable_digest('{"branches": []}') == ""


def test_missing_choice_line_returns_empty_string():
    # OBSERVATION présente mais pas de ligne "Choix : FUTUR n" exploitable — non conforme.
    text = "OBSERVATION\nsignal incomplet\n\nFUTUR 1\nAction : temporiser\n"
    assert observable_digest(text) == ""


def test_works_on_a_free_form_reasoning_plan_without_futur_sections():
    # Décision design casting = pensée native (§8, §9) : un pays reasoning en délibération
    # libre ne produit ni gabarit "trois futurs" ni "FUTUR n" — seulement une décision
    # datée ACTION/RÉACTIONS/CHOIX. `audit_summary()` reste un rendu déterministe du
    # `PrivateStrategicPlan` (toujours 3 branches par construction) : le digest doit donc
    # rester lisible, exactement comme pour un journal structuré.
    raw = (
        "Après réflexion sur la posture adverse et le coût politique d'une escalade, "
        "je retiens une option de désescalade contrôlée.\n\n"
        "ACTION : proposer un canal de communication direct hors caméra\n"
        "RÉACTIONS : iran=coopere: réduit la pression publique\n"
        "CHOIX : un canal discret limite le risque de perte de face pour les deux parties\n"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    digest = observable_digest(plan.audit_summary())
    assert digest != ""
    assert digest.count("\n") == 2
    assert "Piste retenue : proposer un canal de communication direct hors caméra" in digest
    assert "Critère : un canal discret limite le risque" in digest
