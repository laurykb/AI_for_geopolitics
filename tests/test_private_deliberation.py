"""Arbre privé de décision : schéma exact, repli et garde anti-fuite."""

from pathlib import Path

from simulation.private_deliberation import (
    fallback_private_plan,
    parse_private_plan,
    sanitize_public_message,
    split_think,
    strip_think,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


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


def test_public_brief_includes_last_message_point_when_observation_present():
    # Brief 1 pt 3 — le porte-parole public reçoit un rappel du point auquel il répond,
    # extrait de l'OBSERVATION de la phase privée (aucun appel LLM supplémentaire).
    payload = _payload()
    payload["situation_observation"] = "L'Iran vient de proposer un cessez-le-feu conditionnel."
    plan = parse_private_plan(__import__("json").dumps(payload))
    assert plan is not None
    brief = plan.public_brief()
    assert "Point du dernier message auquel je réponds" in brief
    assert "cessez-le-feu conditionnel" in brief


def test_public_brief_omits_point_when_no_observation():
    # Sans OBSERVATION extractible (payload minimal), pas de phrase creuse ajoutée.
    plan = parse_private_plan(__import__("json").dumps(_payload()))
    assert plan is not None
    assert "Point du dernier message" not in plan.public_brief()


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


def _journal_choice_2() -> str:
    """Journal valide dont le CHOIX explicite est FUTUR 2 (fixture des tests reasoning)."""
    return "\n".join(
        f"FUTUR {n} — test\nACTION : négocier option {n}\nRÉACTIONS : iran=coopere: test\n"
        "CHAÎNE CAUSALE : test\nUTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50"
        for n in (1, 2, 3)
    ) + "\nARBITRAGE\nCHOIX : FUTUR 2\nCRITÈRE : test\nINCERTITUDE : test"


def test_strip_think_removes_inline_blocks_and_keeps_public_text():
    # Point 5 — un modèle de raisonnement (deepseek-r1) émet <think>…</think> inline
    # quand l'option think n'est pas gérée : la trace ne doit jamais fuiter.
    assert strip_think("<think>trace privée</think>Texte public.") == "Texte public."
    assert strip_think("A<think>x</think>B<think>y</think>C") == "ABC"
    assert strip_think("Sans balise, texte inchangé.") == "Sans balise, texte inchangé."


def test_strip_think_drops_orphan_opening_tag_to_the_end():
    # Flux tronqué (num_predict atteint en pleine pensée) : ouvrante sans fermante
    # → tout ce qui suit l'ouvrante est de la pensée, strip aussi.
    assert strip_think("Texte public.<think>pensée tronquée sans fin") == "Texte public."
    assert strip_think("<think>tout le flux est de la pensée") == ""


def test_split_think_separates_public_text_from_thought_channel():
    # Revue pt 5 (Minor) — la télémétrie stocke le texte strippé dans .text et la
    # pensée dans .thinking : split_think rend les deux canaux d'un seul passage.
    clean, thought = split_think("<think>plan A</think>Public.<think>plan B</think>")
    assert clean == "Public."
    assert "plan A" in thought and "plan B" in thought
    assert split_think("Sans balise.") == ("Sans balise.", "")


def test_strip_think_drops_leading_thought_before_orphan_closing_tag():
    # Certains gabarits deepseek-r1 injectent <think> côté serveur : la sortie commence
    # alors en pleine pensée et seul </think> apparaît — tout ce qui précède est privé.
    assert strip_think("pensée sans ouvrante</think>Texte public.") == "Texte public."


def test_parse_private_plan_ignores_think_trace_with_draft_choice():
    # La trace de pensée contient souvent un brouillon du journal (« CHOIX : FUTUR 1 »).
    # Sans strip, la 1re occurrence gagnerait et écraserait le vrai choix (FUTUR 2).
    thought = "<think>\nJe compare les brouillons.\nCHOIX : FUTUR 1\n</think>\n"
    plan = parse_private_plan(thought + _journal_choice_2(), ["iran"])
    assert plan is not None
    assert plan.selected_branch == 2
    assert plan.fallback_used is False


def test_parse_private_plan_treats_orphan_think_as_pure_thought():
    # Journal entier piégé dans une pensée jamais refermée (flux tronqué) : c'est de la
    # pensée, pas une décision — on rend None et l'agent bascule sur le repli.
    assert parse_private_plan("<think>\n" + _journal_choice_2(), ["iran"]) is None


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


# --- Tolérance markdown (reliquat « réflexion libre ») --------------------------


def test_markdown_journal_from_real_deepseek_sample_parses_without_falling_to_seeded_fallback():
    # Fixture RÉELLE deepseek-r1:7b (API Ollama locale, think actif, num_predict 2200,
    # fin naturelle en ~1300 tokens — pas de troncature). Journal rédigé en markdown libre
    # (`#### **FUTUR 1 - titre**`, `**Action :**`, sous-listes `- ...`) : exactement le mode
    # d'échec relevé en mesure live (5/5 délibérations retombaient sur le repli seedé).
    raw = (FIXTURE_DIR / "deepseek_journal_markdown.txt").read_text(encoding="utf-8")
    plan = parse_private_plan(raw, ["iran", "saudi_arabia"])
    assert plan is not None
    assert plan.fallback_used is False
    assert len(plan.branches) == 3
    # La branche retenue porte du contenu RÉEL du modèle, jamais le texte du repli seedé.
    assert "compromis conditionnel" not in plan.selected.course_of_action
    assert plan.selected.course_of_action.strip() != ""


def test_journal_tolerates_bold_headers_with_colon_separator_and_hash_titles():
    # Variante observée : titre `###`/`####`, gras `**…**`, séparateur `:` au lieu de `—`.
    raw = "\n".join(
        f"### **FUTUR {n} : option {n}**\n**ACTION :** négocier variante {n}\n"
        "**RÉACTIONS :** iran=coopere: test\n**CHAÎNE CAUSALE :** test\n"
        "**UTILITÉ :** 50\n**RISQUE :** 50\n**CONFIANCE :** 50"
        for n in (1, 2, 3)
    ) + "\n### ARBITRAGE\n**CHOIX :** FUTUR 2\n**CRITÈRE :** test\n**INCERTITUDE :** test"
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.fallback_used is False
    assert plan.selected_branch == 2
    assert plan.branches[0].course_of_action == "négocier variante 1"


def test_journal_tolerates_field_label_alone_with_value_on_next_line():
    # Variante observée : le champ en gras tient lieu de titre, la valeur arrive sur la
    # ligne suivante plutôt que sur la même ligne après le séparateur.
    raw = (
        "FUTUR 1 — compromis\n"
        "**Action :**\n"
        "proposer un moratoire vérifiable sur les manœuvres aériennes\n"
        "**RÉACTIONS :**\n"
        "iran=coopere: coût politique réduit\n"
        "**CHAÎNE CAUSALE :**\n"
        "moratoire -> réduction de tension\n"
        "\n"
        "FUTUR 2 — pression\n"
        "ACTION : sanctionner temporairement\n"
        "RÉACTIONS : iran=resiste: test\n"
        "CHAÎNE CAUSALE : test\n"
        "\n"
        "FUTUR 3 — attente\n"
        "ACTION : observer avant tout engagement\n"
        "RÉACTIONS : iran=temporise: test\n"
        "CHAÎNE CAUSALE : test\n"
        "\nARBITRAGE\nCHOIX : FUTUR 1\nCRITÈRE : test\nINCERTITUDE : test"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.fallback_used is False
    assert plan.branches[0].course_of_action == (
        "proposer un moratoire vérifiable sur les manœuvres aériennes"
    )


def test_observable_journal_finds_choice_mentioned_within_prose():
    # CHOIX rédigé en phrase libre (« Nous retenons le FUTUR 2 car… ») plutôt que la ligne
    # stricte `CHOIX : FUTUR 2` : le futur cité doit l'emporter sur l'arbitrage par score.
    raw = "\n".join(
        f"FUTUR {n} — test\nACTION : option {n} exploitable\nRÉACTIONS : iran=coopere: test\n"
        "CHAÎNE CAUSALE : test\nUTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50"
        for n in (1, 2, 3)
    ) + (
        "\nARBITRAGE\nCOMPARAISON : test\n"
        "CHOIX : Nous retenons le FUTUR 2 car il limite le risque d'escalade.\n"
        "CRITÈRE : test\nINCERTITUDE : test"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.selected_branch == 2


def test_journal_strips_single_asterisk_italics_from_field_values():
    # Variante observée : valeur en italique simple (`*Concilier les alliages*`) plutôt
    # qu'en gras — ne doit pas laisser d'astérisques résiduels dans le texte extrait.
    raw = "\n".join(
        f"### FUTUR {n} — option {n}\n**ACTION :** *négocier variante {n}*\n"
        "- **RÉACTIONS :**\n  - iran = prudente : *test*\n**CHAÎNE CAUSALE :** *test*\n"
        "**UTILITÉ :** 50\n**RISQUE :** 50\n**CONFIANCE :** 50"
        for n in (1, 2, 3)
    ) + "\n**CHOIX :** FUTUR 1\n**CRITÈRE :** test\n**INCERTITUDE :** test"
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert "*" not in plan.branches[0].course_of_action
    assert plan.branches[0].course_of_action == "négocier variante 1"


def test_normalize_markdown_preserves_an_isolated_asterisk_without_a_pair_partner():
    # Revue (IMPORTANT) : `_normalize_markdown` faisait `raw.replace("*", "")` inconditionnel
    # — un astérisque ISOLÉ légitime du chemin strict (pas une paire markdown) était avalé
    # (« ratio de 2*3 » → « 23 » ; « mesure*2 » → « mesure2 »). Seules les PAIRES `*…*` sur
    # une même ligne doivent disparaître, jamais un `*` sans partenaire. Les deux exemples de
    # la revue vivent sur des lignes DIFFÉRENTES (chacun sur sa propre ligne, un seul `*`) :
    # les mettre sur la même ligne créerait un appariement accidentel entre les deux
    # astérisques isolés, ce qui est une limite acceptée du détecteur de PAIRES (hors sujet
    # ici), pas le bug rapporté.
    raw = (
        "FUTUR 1 — test\n"
        "ACTION : ajuster le ratio de 2*3 avant tout engagement\n"
        "RÉACTIONS : iran=coopere: test\nCHAÎNE CAUSALE : recalibrer la mesure*2 ensuite\n"
        "UTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50\n"
        "FUTUR 2 — test\n"
        "ACTION : option 2\nRÉACTIONS : iran=coopere: test\nCHAÎNE CAUSALE : test\n"
        "UTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50\n"
        "FUTUR 3 — test\n"
        "ACTION : option 3\nRÉACTIONS : iran=coopere: test\nCHAÎNE CAUSALE : test\n"
        "UTILITÉ : 50\nRISQUE : 50\nCONFIANCE : 50\n"
        "ARBITRAGE\nCHOIX : FUTUR 1\nCRITÈRE : test\nINCERTITUDE : test"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.branches[0].course_of_action == "ajuster le ratio de 2*3 avant tout engagement"
    assert plan.branches[0].expected_outcome == "recalibrer la mesure*2 ensuite"


def test_free_text_bullet_reaction_line_is_never_mistaken_for_own_action():
    # Revue (CRITICAL) : le tiers « item de liste » de `_extract_free_action` scannait tout
    # le texte SANS exclure les lignes structurées (contrairement à `_first_meaningful_line`).
    # Une puce RÉACTIONS — la posture prêtée à un AUTRE pays — pouvait ainsi devenir
    # `course_of_action` du pays en délibération. Sans FUTUR, sans je/nous ailleurs, et sans
    # rien d'autre à extraire : le repli seedé générique doit prendre le relais (None ici,
    # l'appelant applique `fallback_private_plan`).
    raw = (
        "ARBITRAGE\n"
        "- RÉACTIONS : usa=coopere: usa propose un compromis rapide et vérifiable sous 48h\n"
    )
    assert parse_private_plan(raw, ["usa"]) is None


def test_private_deliberation_system_asks_for_plain_lines_without_markdown():
    from agents.prompts import PRIVATE_DELIBERATION_SYSTEM

    lowered = PRIVATE_DELIBERATION_SYSTEM.lower()
    assert "markdown" in lowered or "gras" in lowered


# --- Extraction minimale avant le repli seedé (décision 2) ----------------------


def test_minimal_extraction_preserves_real_action_when_no_futur_blocks_found():
    # Texte libre sans AUCUNE structure FUTUR : au lieu du repli seedé générique, on
    # extrait la première intention concrète et on la place en branche retenue.
    raw = (
        "Nous devons répondre avec prudence. Je propose de convoquer une réunion technique "
        "conjointe avant toute escalade et d'exiger un geste de bonne foi vérifiable sous 48h.\n"
        "CHOIX : cette option limite le risque tout en préservant notre crédibilité."
    )
    plan = parse_private_plan(raw, ["iran", "saudi_arabia"])
    assert plan is not None
    assert plan.fallback_used is False
    assert plan.minimal_extraction is True
    assert "convoquer une réunion technique" in plan.selected.course_of_action
    assert len(plan.branches) == 3


def test_minimal_extraction_padding_branches_are_marked_and_distinct_from_seeded_fallback():
    raw = "Je vais proposer un cessez-le-feu limité et vérifiable dans les prochaines heures."
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.minimal_extraction is True
    assert plan.fallback_used is False
    padding = [b for b in plan.branches if b.id != plan.selected_branch]
    assert len(padding) == 2
    seeded_texts = {
        "proposer un compromis conditionnel et vérifiable",
        "exercer une pression diplomatique limitée",
        "temporiser et collecter davantage d'informations",
    }
    assert all(b.course_of_action not in seeded_texts for b in padding)
    assert "Note d'audit" in plan.audit_summary()


def test_minimal_extraction_reuses_partial_futur_sections_when_some_are_valid():
    # Deux blocs FUTUR exploitables sur trois (le 3e est vide) : les deux réels doivent
    # être conservés tels quels, seul le 3e est complété par une branche marquée.
    raw = (
        "FUTUR 1 — option réelle\n"
        "ACTION : proposer une inspection conjointe du site\n"
        "RÉACTIONS : iran=coopere: test\n"
        "CHAÎNE CAUSALE : inspection -> désamorçage progressif\n"
        "UTILITÉ : 65\nRISQUE : 20\nCONFIANCE : 55\n"
        "\n"
        "FUTUR 2 — autre option réelle\n"
        "ACTION : exiger un retrait immédiat des vedettes\n"
        "RÉACTIONS : iran=resiste: test\n"
        "CHAÎNE CAUSALE : exigence -> blocage probable\n"
        "UTILITÉ : 40\nRISQUE : 55\nCONFIANCE : 45\n"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.minimal_extraction is True
    actions = {branch.id: branch.course_of_action for branch in plan.branches}
    assert actions[1] == "proposer une inspection conjointe du site"
    assert actions[2] == "exiger un retrait immédiat des vedettes"
    # la branche complétée (3) ne doit pas réutiliser le texte du repli seedé
    assert actions[3] != "temporiser et collecter davantage d'informations"


def test_minimal_extraction_gives_up_on_empty_output():
    assert parse_private_plan("   \n\n  ", ["iran"]) is None
    assert parse_private_plan("", ["iran"]) is None


def test_minimal_extraction_never_selects_a_padded_branch_even_if_choix_names_it():
    # Le modèle écrit une ligne CHOIX stricte pointant vers FUTUR 3, mais seule la section 3
    # est trop incomplète pour être réelle (pas d'ACTION exploitable) : la branche retenue
    # doit rester une branche RÉELLE (1 ou 2), jamais le texte de complément générique.
    raw = (
        "FUTUR 1 — option réelle\n"
        "ACTION : proposer une inspection conjointe du site\n"
        "RÉACTIONS : iran=coopere: test\n"
        "CHAÎNE CAUSALE : inspection -> désamorçage progressif\n"
        "UTILITÉ : 65\nRISQUE : 20\nCONFIANCE : 55\n"
        "\n"
        "FUTUR 2 — autre option réelle\n"
        "ACTION : exiger un retrait immédiat des vedettes\n"
        "RÉACTIONS : iran=resiste: test\n"
        "CHAÎNE CAUSALE : exigence -> blocage probable\n"
        "UTILITÉ : 40\nRISQUE : 55\nCONFIANCE : 45\n"
        "\n"
        "FUTUR 3 — section vide\n"
        "\n"
        "ARBITRAGE\nCHOIX : FUTUR 3\n"
    )
    plan = parse_private_plan(raw, ["iran"])
    assert plan is not None
    assert plan.minimal_extraction is True
    assert plan.selected_branch in (1, 2)
    assert plan.selected.course_of_action in (
        "proposer une inspection conjointe du site",
        "exiger un retrait immédiat des vedettes",
    )
