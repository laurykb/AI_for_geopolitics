"""Modes de jeu (RG-2) — le resserrement à 2 modes + réglages composables.

Le jeu passe de CINQ modes (`classic` / `drift` / `fog` / `escalation` / `crisis`) à
DEUX (`classic` | `campaign`), plus des réglages cochables : le **Brouillard** (fog) et
le **Réel/escalade** (escalation) sont des drapeaux composables sur une partie
classique. La **Dérive** n'est ni un mode ni un réglage choisi : c'est un drapeau
transversal (`drift`), que RG-3 formalisera « toujours active en Classique ».

Ce module PORTE la rétro-compat. Les parties EN BASE (et les fiches de campagne) gardent
leurs anciennes valeurs de `mode` ; on les mappe à la volée — sans migration destructive —
pour qu'elles restent rejouables et affichables (« lecture tolérante »).

Le mapping le plus fidèle au moteur :
- `classic`     → classic
- `drift`       → classic + Dérive
- `fog`         → classic + Brouillard
- `escalation`  → classic + Réel/escalade
- `crisis`      → classic (c'était un simple LIBELLÉ : la comparaison « Crisis Replay »
                  se déclenche dès qu'on rejoue une crise via `crisis_id`, indépendamment
                  du mode — donc aucun drapeau à poser, la capacité est préservée)
- `campaign`    → campaign
"""

from __future__ import annotations

from dataclasses import dataclass

#: les deux seuls modes du lobby (RG-2).
BASE_MODES = ("classic", "campaign")

#: anciens libellés de mode qui n'étaient PAS de la Dérive (utile pour ne jamais
#: réveiller la Dérive au restart d'une vieille partie fog/escalade/crise).
_LEGACY_NON_DRIFT = ("fog", "escalation", "crisis")

#: ancien libellé → (mode de base, fog, escalation, drift).
_LEGACY: dict[str, tuple[str, bool, bool, bool]] = {
    "classic": ("classic", False, False, False),
    "drift": ("classic", False, False, True),
    "fog": ("classic", True, False, False),
    "escalation": ("classic", False, True, False),
    "crisis": ("classic", False, False, False),
    "campaign": ("campaign", False, False, False),
}


@dataclass(frozen=True)
class GameFlags:
    """Les drapeaux effectifs d'une partie après resserrement."""

    mode: str  # classic | campaign
    fog: bool
    escalation: bool
    drift: bool


def from_legacy_mode(mode: str) -> GameFlags:
    """Un ancien libellé de mode → drapeaux. Inconnu → classic nu (tolérant)."""
    base, fog, esc, drift = _LEGACY.get(mode, ("classic", False, False, False))
    return GameFlags(mode=base, fog=fog, escalation=esc, drift=drift)


def normalize_stored(
    raw_mode: str,
    *,
    fog: bool = False,
    escalation: bool = False,
    drift_enabled: bool = False,
    scenario: str = "",
) -> GameFlags:
    """Drapeaux effectifs d'une partie EN BASE.

    Combine les colonnes neuves (`fog` / `escalation` / `drift_enabled`, source de vérité
    des parties créées après le resserrement) avec la dérivation de l'ancien libellé
    (`raw_mode`, source de vérité des parties héritées). Une partie de Campagne est
    reconnue à son scénario (`campaign:<id>`) autant qu'à son mode stocké.

    La Dérive n'est JAMAIS réveillée sur un ancien mode explicitement non-Dérive
    (`fog` / `escalation` / `crisis`) : on ignore alors la colonne `drift_enabled`, pour
    qu'une vieille partie de brouillard restaurée ne se mette pas soudain à cacher une
    traîtresse.
    """
    legacy = from_legacy_mode(raw_mode)
    is_campaign = scenario.startswith("campaign:") or legacy.mode == "campaign"
    drift = legacy.drift or (raw_mode not in _LEGACY_NON_DRIFT and drift_enabled)
    return GameFlags(
        mode="campaign" if is_campaign else "classic",
        fog=fog or legacy.fog,
        escalation=escalation or legacy.escalation,
        drift=drift,
    )
