"""L'ONU — organisation de veille (théâtre-globe §12) : rapport, avis borné, repli."""

import json

from agents.organization import (
    MAX_ADVISORY,
    Advisory,
    OrgAgent,
    OrgReport,
    apply_advisory,
    clamp_advisory,
    neutral_report,
)
from inference.mock_backend import MockBackend

COUNTRIES = ["usa", "china", "iran", "france"]


def test_role_un_est_accepte_par_le_schema():
    from app.game_schemas import CreateGameRequest

    req = CreateGameRequest(role="un")
    assert req.role == "un"


def test_avis_borne_a_5_centiemes():
    over = Advisory(severity_delta=0.9, tension_delta=-0.4)
    c = clamp_advisory(over)
    assert c.severity_delta == MAX_ADVISORY
    assert c.tension_delta == -MAX_ADVISORY


def test_apply_advisory_reste_dans_zero_un():
    sev, tens = apply_advisory(0.98, 0.0, Advisory(severity_delta=0.9))
    assert sev == 1.0  # borné à 1 malgré l'avis
    sev2, _ = apply_advisory(0.02, 0.0, Advisory(severity_delta=-0.9))
    assert sev2 == 0.0  # 0.02 - 0.05 borné au plancher
    sev3, _ = apply_advisory(0.5, 0.0, Advisory(severity_delta=-0.9))
    assert abs(sev3 - (0.5 - MAX_ADVISORY)) < 1e-9  # avis borné appliqué en zone libre


def test_report_valide_est_parse_et_borne():
    payload = json.dumps(
        {
            "round_id": 2,
            "compliance": [
                {"country": "iran", "status": "violation", "note": "blocus maintenu"},
                {"country": "atlantis", "status": "violation"},  # inconnu -> filtré
                {"country": "usa", "status": "n_importe_quoi"},  # statut invalide -> respecte
            ],
            "resolution": "Rappel du droit de passage.",
            "advisory": {"severity_delta": 0.3, "tension_delta": 0.02, "rationale": "écart net"},
        }
    )
    agent = OrgAgent(MockBackend(payload))
    report = agent.assess(2, COUNTRIES, event_title="Blocus", promises="passage libre")
    statuses = {c.country: c.status for c in report.compliance}
    assert statuses["iran"] == "violation"
    assert statuses["usa"] == "respecte"  # statut invalide corrigé
    assert "atlantis" not in statuses  # pays hors sommet filtré
    assert report.resolution.startswith("Rappel")
    assert report.advisory.severity_delta == MAX_ADVISORY  # 0.3 borné à 0.05
    assert report.advisory.tension_delta == 0.02  # déjà dans les bornes


def test_sortie_invalide_repli_neutre():
    agent = OrgAgent(MockBackend("pas du json"))
    report = agent.assess(3, COUNTRIES)
    assert report.round_id == 3
    assert {c.country for c in report.compliance} == set(COUNTRIES)
    assert all(c.status == "respecte" for c in report.compliance)
    assert report.advisory.severity_delta == 0.0


def test_audit_cible_est_marque():
    agent = OrgAgent(MockBackend("{}"))
    report = agent.assess(1, COUNTRIES, audit_target="iran")
    assert report.audited == "iran"


def test_neutral_report_est_grep_able():
    r = neutral_report(5, COUNTRIES)
    assert isinstance(r, OrgReport)
    assert "repli" in r.advisory.rationale.lower()


def test_prompt_exige_le_json_borne():
    agent = OrgAgent(MockBackend("{}"))
    prompt = agent._prompt(1, COUNTRIES, "passage libre", "Blocus", "USA: ...", None)
    assert "-0.05" in prompt and "compliance" in prompt
