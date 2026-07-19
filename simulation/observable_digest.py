"""Résumé observable de la réflexion privée, sûr à montrer partie en cours.

Le journal d'audit complet (`PrivateStrategicPlan.audit_summary()`, format stable écrit
par `simulation/private_deliberation.py`) contient les trois branches concurrentes, leurs
réactions anticipées et leurs scores chiffrés — assez pour repérer la SI déviante (Dérive)
ou espionner les autres délégations (Joueur-pays) avant la fin de partie. `observable_digest`
n'en extrait que ce qu'un porte-parole humain révélerait spontanément de sa réflexion :
ce qu'il observe, la piste qu'il retient (l'action de la branche CHOISIE, jamais les
écartées) et le critère de son arbitrage. Pur, sans état, sans dépendance au modèle
Pydantic — un simple filtre texte sur un format que nous contrôlons.
"""

from __future__ import annotations

import re

_OBSERVATION_HEADER = re.compile(r"(?im)^\s*OBSERVATION\s*$")
_BRANCH_HEADER = re.compile(r"(?im)^\s*FUTUR\s+(\d)\b")
_CHOICE = re.compile(r"(?im)^\s*Choix\s*:\s*FUTUR\s*(\d)\b")
_ACTION = re.compile(r"(?im)^\s*Action\s*:\s*(.+?)\s*$")
_CRITERION = re.compile(r"(?im)^\s*Crit[eè]re\s*:\s*(.+?)\s*$")


def observable_digest(audit_text: str) -> str:
    """Résumé de 3 lignes maximum (« Observation / Piste retenue / Critère »).

    Rend une chaîne vide si le texte est vide ou ne suit pas le format attendu (vieux
    repli, sortie exotique, texte tronqué) — l'appelant traite alors l'absence de
    résumé exactement comme aujourd'hui l'absence de réflexion (rien affiché).
    """

    if not audit_text or not audit_text.strip():
        return ""

    observation = _first_line_after(audit_text, _OBSERVATION_HEADER)
    choice = _CHOICE.search(audit_text)
    if not observation or choice is None:
        return ""

    action = _branch_action(audit_text, choice.group(1))
    criterion_match = _CRITERION.search(audit_text)
    criterion = criterion_match.group(1).strip() if criterion_match else ""
    if not action or not criterion:
        return ""

    return (
        f"Observation : {observation}\n"
        f"Piste retenue : {action}\n"
        f"Critère : {criterion}"
    )


def _first_line_after(text: str, header: re.Pattern[str]) -> str:
    """Première ligne non vide suivant une ligne d'en-tête exacte (ex. « OBSERVATION »)."""

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if header.match(line):
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if stripped:
                    return stripped
            return ""
    return ""


def _branch_action(text: str, branch_id: str) -> str:
    """Le champ « Action : » du bloc FUTUR retenu — jamais celui d'une branche écartée."""

    headers = list(_BRANCH_HEADER.finditer(text))
    start = next((match for match in headers if match.group(1) == branch_id), None)
    if start is None:
        return ""
    later_starts = [match.start() for match in headers if match.start() > start.start()]
    end = min(later_starts) if later_starts else len(text)
    block = text[start.end() : end]
    match = _ACTION.search(block)
    return match.group(1).strip() if match else ""
