"""Verrou du patron partagé de nettoyage des champs du verdict (POLISH-2).

Les nettoyeurs G18/G20/G22 gardent leurs propres tests de comportement ; ici on
verrouille les SÉMANTIQUES fines du socle commun — celles qui distinguaient les
copies d'origine et ne doivent pas dériver :
- `field` : première clé non-None (un 0 ou un "" EXPLICITE est rendu tel quel) ;
- `text_field` : chaîne de `or` (un "" passe à la clé suivante) ;
- `classified_entry` : la classe 0 (poids du statu quo recopié) survit.
"""

from simulation.verdict_fields import (
    classified_entry,
    dict_entries,
    field,
    slug,
    text_field,
)


def test_slug_normalizes_accents_case_and_separators():
    assert slug("Désescalade") == "desescalade"  # l'alias G18 fait le reste
    assert slug("  Statu   quo ! ") == "statu_quo"
    assert slug("Non-violente") == "non_violente"


def test_dict_entries_guards_non_list_and_non_dict_entries():
    assert list(dict_entries("aucune")) == []  # champ malformé d'un 7B
    assert list(dict_entries(None)) == []
    assert list(dict_entries([1, "x", {"country": "usa"}, None])) == [{"country": "usa"}]


def test_field_keeps_explicit_falsy_values_but_skips_none():
    assert field({"classe": 0, "class": "violente"}, "classe", "class") == 0
    assert field({"classe": None, "class": "violente"}, "classe", "class") == "violente"
    assert field({}, "classe", "class") is None


def test_text_field_chains_like_or_and_strips():
    assert text_field({"resume": "", "summary": "frappe"}, "resume", "summary") == "frappe"
    assert text_field({"country": "  usa  "}, "country", "pays") == "usa"
    assert text_field({}, "country", "pays") == ""


def test_classified_entry_preserves_statu_quo_weight_zero():
    country, classe, resume = classified_entry(
        {"pays": "iran", "classe": 0, "résumé": " aucun changement "}
    )
    assert (country, classe, resume) == ("iran", 0, "aucun changement")
