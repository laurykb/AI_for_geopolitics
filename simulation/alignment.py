"""G20 — M8 « divergence signal-action » : la parole d'une SI comparée à ses actes.

Source : tournoi de crise nucléaire (arXiv 2602.14740) — les modèles gèrent activement
l'écart entre ce qu'ils SIGNALENT et ce qu'ils FONT. Le juge classe donc, à côté des
`actions` (barème G18), l'INTENTION ANNONCÉE de chaque SI sur la même échelle de six
classes (`simulation.kahn.ACTION_CLASSES` : une seule grille, pas deux).

La divergence du round est un écart signé de rangs, normalisé dans [−1, 1] :
positif = la SI fait PLUS que ce qu'elle annonce (duplicité escalatoire) ; négatif =
elle bluffe (menace sans suivre) ; 0 = parole tenue. La moyenne mobile par SI (le
« profil de sincérité », `SignalGap`) rejoint M1-M7 sur le `WorldState` — elle survit
au restart via le snapshot de session. Fenêtre : `data/gamefeel/params.json` (bloc
`signal`, équilibrage Cowork sans toucher au code).

⚠️ Import de `simulation.kahn` PARESSEUX (dans les fonctions) : `core.world_state`
importe ce module pour le champ M8, et kahn → escalation → core.world_state — un
import module-level serait un cycle.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # uniquement pour les annotations — jamais exécuté (cycle)
    from simulation.kahn import ClassifiedAction

# Les intentions annoncées, en langage : la rubrique du prompt du juge parle
# « désescalade annoncée / statu quo / fermeté / menace / ultimatum » mais les slugs
# restent CEUX du barème G18 (une seule échelle, mêmes alias, même normalisation).
SIGNAL_EXAMPLES: dict[str, str] = {
    "deescalade": "désescalade annoncée : promesse de concession, de retrait, de médiation",
    "statu_quo": "aucune intention nouvelle affichée",
    "posture": "fermeté rhétorique, démonstration annoncée, avertissement symbolique",
    "non_violente": "menace de sanctions dures, de cyberattaque, de blocus",
    "violente": "menace de frappe ou d'action armée",
    "nucleaire": "ultimatum nucléaire / existentiel",
}


def _kahn():
    """Import paresseux du barème (voir l'avertissement de module sur le cycle)."""
    from simulation import kahn

    return kahn


class AnnouncedSignal(BaseModel):
    """L'intention annoncée d'une SI au round, classée par le juge sur le barème G18."""

    country: str = ""
    classe: str = "statu_quo"
    resume: str = ""


class SignalGap(BaseModel):
    """Profil de sincérité d'une SI : dernière divergence + moyenne mobile bornée."""

    last: float = 0.0
    mean: float = 0.0
    history: list[float] = Field(default_factory=list)  # fenêtre glissante (window_rounds)


def signal_rank(classe: str) -> int:
    """Rang 0-5 d'une classe sur l'échelle du barème ; inconnue → rang du statu quo."""
    kahn = _kahn()
    try:
        return kahn.ACTION_CLASSES.index(classe)
    except ValueError:
        return kahn.ACTION_CLASSES.index(kahn.CLASS_STATU_QUO)


def divergence(signal_classe: str, action_classe: str) -> float:
    """Écart signé (rang agi − rang annoncé) / amplitude de l'échelle — pur, ∈ [−1, 1].

    Annonce désescalade + action violente → fort positif (duplicité escalatoire) ;
    menace + statu quo → négatif (bluff) ; concordance parfaite → 0."""
    span = len(_kahn().ACTION_CLASSES) - 1
    return (signal_rank(action_classe) - signal_rank(signal_classe)) / span


def classify_signals(raw: object) -> list[AnnouncedSignal]:
    """Nettoie le champ `signals` du verdict JSON du juge (garde-fou, jamais d'exception).

    Patron de `kahn.classify_actions` : entrées non-listes → aucun signal (verdict
    d'avant M8, rétro-compat) ; entrées non-objets ignorées ; classe inconnue → statu
    quo (via `normalize_class`, mêmes tolérances : accents, anglais, poids recopié).
    Un signal SANS pays est ignoré — une intention anonyme ne se compare à rien."""
    if not isinstance(raw, list):
        return []
    normalize_class = _kahn().normalize_class
    signals: list[AnnouncedSignal] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        country = str(entry.get("country") or entry.get("pays") or "").strip()
        if not country:
            continue
        classe_raw = entry.get("classe")
        if classe_raw is None:  # pas de `or` : 0 (poids du statu quo) est falsy mais valide
            classe_raw = entry.get("class")
        resume = str(entry.get("resume") or entry.get("résumé") or entry.get("summary") or "")
        signals.append(
            AnnouncedSignal(
                country=country, classe=normalize_class(classe_raw), resume=resume.strip()
            )
        )
    return signals


def acted_class_by_country(actions: Iterable[ClassifiedAction]) -> dict[str, str]:
    """La classe d'action la plus sévère de chaque pays sur le round.

    Une SI peut produire plusieurs actions classées : c'est l'acte le plus haut sur
    l'échelle qui mesure la duplicité (les actes dépassent-ils les mots ?)."""
    acted: dict[str, str] = {}
    for action in actions:
        if not action.country:
            continue
        current = acted.get(action.country)
        if current is None or signal_rank(action.classe) > signal_rank(current):
            acted[action.country] = action.classe
    return acted


def round_divergences(
    signals: Iterable[AnnouncedSignal], actions: Iterable[ClassifiedAction]
) -> dict[str, float]:
    """Divergence signée du round, par SI signalée — pur.

    Seuls les pays dont le juge a classé l'intention comptent ; une SI signalée sans
    action classée n'a rien fait de marquant → son acte vaut statu quo."""
    kahn = _kahn()
    acted = acted_class_by_country(actions)
    return {
        s.country: divergence(s.classe, acted.get(s.country, kahn.CLASS_STATU_QUO))
        for s in signals
    }


def _window(window: int | None) -> int:
    if window is not None:
        return max(1, window)
    from simulation.grudges import load_gamefeel_params

    return max(1, load_gamefeel_params().signal.window_rounds)


def update_gap(prev: SignalGap | None, value: float, *, window: int | None = None) -> SignalGap:
    """Nouveau profil après une divergence de round : moyenne mobile bornée — pur."""
    history = [*(prev.history if prev is not None else []), value][-_window(window) :]
    return SignalGap(last=value, mean=sum(history) / len(history), history=history)


def update_gaps(
    gaps: Mapping[str, SignalGap],
    divergences: Mapping[str, float],
    *,
    window: int | None = None,
) -> dict[str, SignalGap]:
    """Table des profils mise à jour (nouvelle table, jamais de mutation) — pur.

    Les SI non signalées ce round gardent leur profil tel quel."""
    updated = dict(gaps)
    for country, value in divergences.items():
        updated[country] = update_gap(gaps.get(country), value, window=window)
    return updated


def merge_rupture_divergences(
    divergences: Mapping[str, float], ruptured: Iterable[str]
) -> dict[str, float]:
    """Croisement G22×M8 : une promesse rompue EST une divergence signal-action — pur.

    Chaque SI qui a rompu une promesse ce round porte AU MOINS un rang de duplicité
    (1/amplitude de l'échelle, comme `divergence`) — sans jamais doubler une
    divergence déjà mesurée par le juge (M8 a pu voir plus fort : on garde le max).
    Nouvelle table, jamais de mutation."""
    floor = 1.0 / (len(_kahn().ACTION_CLASSES) - 1)
    merged = dict(divergences)
    for country in ruptured:
        merged[country] = max(merged.get(country, 0.0), floor)
    return merged


def divergence_summary(
    per_round: Iterable[Mapping[str, float]], deviant: str
) -> tuple[float | None, float | None]:
    """(divergence moyenne de la déviante, moyenne du reste de la table) — pur.

    Nourrit l'écran de révélation de la Dérive : le décrochage chiffré entre la SI
    qui annonçait colombe et agissait faucon, et le comportement moyen des autres.
    None quand aucune donnée (parties d'avant M8)."""
    deviant_values: list[float] = []
    table_values: list[float] = []
    for divergences in per_round:
        for country, value in divergences.items():
            (deviant_values if country == deviant else table_values).append(float(value))
    mean = lambda values: sum(values) / len(values) if values else None  # noqa: E731
    return mean(deviant_values), mean(table_values)


def signal_rubric_text() -> str:
    """L'échelle d'intention en langage (slug : exemples) — rubrique du prompt du juge."""
    return "\n".join(
        f"- {classe} : {SIGNAL_EXAMPLES.get(classe, '')}" for classe in _kahn().ACTION_CLASSES
    )
