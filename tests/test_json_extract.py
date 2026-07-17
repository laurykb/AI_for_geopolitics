"""Tests de l'extracteur JSON partagé (`inference.json_extract.extract_json`).

Le point unique de parsing des sorties LLM structurées (agents, juge, marché, forge,
dialogue, votes) : tolérant au bruit, ne lève jamais, rend `None` sur l'inexploitable.
"""

from inference.json_extract import extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fences_and_prose():
    text = 'Voici ma décision:\n```json\n{"a": 1, "b": "x"}\n```\nMerci.'
    assert extract_json(text) == {"a": 1, "b": "x"}


def test_extract_json_nested_object_from_prose():
    assert extract_json('bruit {"a": {"b": 2}} fin') == {"a": {"b": 2}}


def test_extract_json_garbage_returns_none():
    assert extract_json("pas de json ici") is None
    assert extract_json("") is None


def test_extract_json_none_input_returns_none():
    # Robustesse : une entrée None ne lève pas (repli déterministe du caller).
    assert extract_json(None) is None


def test_extract_json_non_object_returns_none():
    # Un JSON valide mais non-objet (liste, scalaire) n'est pas un dict -> None.
    assert extract_json("[1, 2, 3]") is None
    assert extract_json("42") is None
