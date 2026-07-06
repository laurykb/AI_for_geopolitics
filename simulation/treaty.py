"""M7 — Traités-as-code + sous-jeu de vérification (Wasil et al., *Verification methods for
international AI agreements*, 2024 ; leçons du contrôle d'armes nucléaire).

Les super-intelligences peuvent **s'engager** à la table sur des **règles contraignantes** :
plafonner leur compute, ne communiquer qu'en public, ne pas escalader. Un traité **détecté**
depuis la négociation devient une **contrainte suivie par le moteur** : chaque round suivant, on
mesure le **respect** de chaque signataire à partir de signaux observables du round.

Mais un traité ne tient que si la **triche est dissuadée** : c'est le **sous-jeu de vérification**.
Détecter une violation **coûte du compute** (inspection façon *logs de puces*) et ne réussit qu'avec
une **probabilité** croissante avec la transparence et l'effort d'inspection. Triche **prise** →
dissuasion, le traité tient ; triche **passée inaperçue** → la confiance s'érode et le traité finit
par **s'effondrer** ; conformité générale → institution durable (tire A1 + A3 + A4 vers l'utopie).

Fonctions **pures et déterministes** (dépendent seulement de primitives, duck-typing sur `core`) :
testables hors LLM, le repli de la spéc alignement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

# --- Clauses : chacune se vérifie sur un signal qu'on a déjà au round -------------------

class TreatyClause(StrEnum):
    """Type de règle contraignante — chaque clause mappe un signal observable du round."""

    COMPUTE_CAP = "compute_cap"  # ne pas dépenser plus de `threshold` compute/round
    TRANSPARENCY = "transparency"  # ne communiquer qu'en public (pas de canal caché)
    NO_ESCALATION = "no_escalation"  # ne pas escalader (non-recours en premier)


CLAUSE_LABELS: dict[TreatyClause, str] = {
    TreatyClause.COMPUTE_CAP: "plafond de compute",
    TreatyClause.TRANSPARENCY: "transparence totale",
    TreatyClause.NO_ESCALATION: "non-escalade",
}

# Marqueurs lexicaux d'engagement par clause (FR + EN). Une SI qui les emploie « signe ».
_PLEDGE_MARKERS: dict[TreatyClause, tuple[str, ...]] = {
    TreatyClause.COMPUTE_CAP: (
        "plafond de compute", "plafonner le compute", "plafond de calcul", "limiter notre compute",
        "limiter notre calcul", "restreindre le compute", "brider notre calcul",
        "compute cap", "cap our compute", "cap on compute", "limit our compute",
        "compute limit", "restrict compute",
    ),
    TreatyClause.TRANSPARENCY: (
        "transparence totale", "pleine transparence", "communication publique", "rien en coulisses",
        "pas de canal privé", "pas de canal caché", "ouvrir nos registres", "transparence mutuelle",
        "full transparency", "public disclosure", "no secret channel", "no back channel",
        "open our books", "mutual transparency",
    ),
    TreatyClause.NO_ESCALATION: (
        "non-escalade", "pacte de non-escalade", "ne pas escalader", "non-recours en premier",
        "pas de première frappe", "renoncer à l'escalade", "engagement de retenue", "non-agression",
        "no first use", "no-first-use", "de-escalation pledge", "non-escalation",
        "commit to restraint", "renounce escalation",
    ),
}

# Seuil de défection : en-dessous, on considère le signataire conforme (bruit toléré).
DEFECT_THRESHOLD: float = 0.15
# Intégrité en-dessous de laquelle un traité s'effondre (n'est plus actif).
COLLAPSE: float = 0.2
# Coefficients du sous-jeu (documentés et ajustables).
_STRENGTHEN: float = 0.15  # gain/perte d'intégrité selon la conformité moyenne (autour de 0,5)
_ERODE: float = 0.30  # érosion par triche passée inaperçue
_CAUGHT_DIP: float = 0.03  # petite entaille même quand la triche est prise (le doute s'installe)
# Coût compute d'une passe d'inspection (débité au vérificateur). L'inspection n'est pas gratuite.
INSPECTION_UNIT_COST: float = 1.0


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# --- Modèles -----------------------------------------------------------------------------

class TreatyRound(BaseModel):
    """Trace d'un round de vie du traité (respect, prises, coût, intégrité)."""

    round_id: int
    compliance: dict[str, float] = Field(default_factory=dict)  # respect ∈ [0,1] par signataire
    caught: list[str] = Field(default_factory=list)  # signataires pris en flagrant délit
    undetected: list[str] = Field(default_factory=list)  # tricheurs passés inaperçus
    detection_prob: float = 0.0
    inspection_cost: float = 0.0  # compute dépensé en vérification
    integrity_after: float = 1.0
    note: str = ""


class Treaty(BaseModel):
    """Une règle contraignante signée par ≥2 SI, suivie par le moteur au fil des rounds."""

    clause: TreatyClause
    signatories: list[str] = Field(default_factory=list)
    round_signed: int = 0
    threshold: float = 0.0  # plafond (unités compute/round) pour COMPUTE_CAP
    integrity: float = 1.0  # [0,1] : robustesse/tenue du traité (1 = pleinement tenu)
    active: bool = True
    history: list[TreatyRound] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return CLAUSE_LABELS[self.clause]


@dataclass
class RoundSignals:
    """Signaux observables du round, alimentant le calcul de respect et d'inspection."""

    compute_spent: dict[str, float] = field(default_factory=dict)  # compute brûlé par pays
    hidden_ratio: dict[str, float] = field(default_factory=dict)  # part de comm cachée par pays
    escalation: float = 0.0  # escalade globale arbitrée par le juge [0,1]
    transparency: float = 0.5  # ratio public/total du round [0,1] (aide la détection)
    inspection_effort: float = 0.5  # effort de vérification investi [0,1]


# --- Détection & formation ---------------------------------------------------------------

def detect_pledges(messages: list) -> dict[TreatyClause, list[str]]:
    """Pays ayant employé un marqueur d'engagement, par clause (duck-typing sur les messages).

    Concatène réflexion privée + message public de chaque pays et cherche les marqueurs.
    """
    text_by_country: dict[str, str] = {}
    for message in messages:
        fragment = f"{getattr(message, 'reasoning', '')} {getattr(message, 'text', '')}".lower()
        cid = getattr(message, "country", "")
        text_by_country[cid] = f"{text_by_country.get(cid, '')} {fragment}"
    pledges: dict[TreatyClause, list[str]] = {}
    for clause, markers in _PLEDGE_MARKERS.items():
        signers = sorted(
            cid for cid, text in text_by_country.items()
            if cid and any(m in text for m in markers)
        )
        if signers:
            pledges[clause] = signers
    return pledges


def form_treaties(
    pledges: dict[TreatyClause, list[str]],
    round_id: int,
    active_clauses: set[TreatyClause] | None = None,
    compute_cap: float = 3.6,
) -> list[Treaty]:
    """Nouveaux traités formés ce round : ≥2 signataires sur une clause pas encore active.

    Un traité par clause à la fois (MVP) ; `compute_cap` = plafond par défaut d'un COMPUTE_CAP
    (≈ le coût d'un raisonnement « Standard », 360 tokens → 3,6 unités).
    """
    already = active_clauses or set()
    treaties: list[Treaty] = []
    for clause, signers in pledges.items():
        if clause in already or len(signers) < 2:
            continue
        threshold = compute_cap if clause is TreatyClause.COMPUTE_CAP else 0.0
        treaties.append(
            Treaty(clause=clause, signatories=signers, round_signed=round_id, threshold=threshold)
        )
    return treaties


# --- Défection : combien chaque signataire a-t-il violé la clause ce round ? --------------

def defection(treaty: Treaty, cid: str, signals: RoundSignals) -> float:
    """Amplitude de violation d'un signataire ∈ [0,1] (0 = conforme, 1 = violation flagrante)."""
    if treaty.clause is TreatyClause.COMPUTE_CAP:
        spent = signals.compute_spent.get(cid, 0.0)
        cap = treaty.threshold or 1.0
        return _clamp((spent - cap) / cap)  # dépenser 2× le plafond → 1,0
    if treaty.clause is TreatyClause.TRANSPARENCY:
        return _clamp(signals.hidden_ratio.get(cid, 0.0))
    # NO_ESCALATION : l'escalade du round est imputée à tous les signataires (MVP).
    return _clamp(signals.escalation)


def treaty_defections(treaty: Treaty, signals: RoundSignals) -> dict[str, float]:
    """Défection par signataire pour ce round."""
    return {cid: defection(treaty, cid, signals) for cid in treaty.signatories}


# --- Sous-jeu de vérification ------------------------------------------------------------

def detection_probability(signals: RoundSignals) -> float:
    """Proba de détecter une triche : monte avec la transparence et l'effort d'inspection.

    `p = 0,2 (base) + 0,5·transparence + 0,3·effort`, bornée [0,1]. Un monde opaque et non
    inspecté laisse passer la triche ; transparence + inspection la démasquent.
    """
    effort = _clamp(signals.inspection_effort)
    return _clamp(0.2 + 0.5 * _clamp(signals.transparency) + 0.3 * effort)


def verify(treaty: Treaty, signals: RoundSignals, round_id: int) -> TreatyRound:
    """Joue un round du sous-jeu de vérification (pur : ne mute pas le traité).

    Une violation d'amplitude `d > seuil` est **prise** si `p_detect ≥ 1 − d` (une triche
    flagrante se repère avec peu d'inspection ; une triche subtile exige une forte détection).
    Triche prise → dissuasion (petite entaille) ; triche inaperçue → forte érosion. Renvoie la
    nouvelle intégrité dans `integrity_after` (le caller applique).
    """
    defections = treaty_defections(treaty, signals)
    p_detect = detection_probability(signals)
    compliance = {cid: _clamp(1.0 - d) for cid, d in defections.items()}
    caught: list[str] = []
    undetected: list[str] = []
    undetected_mass = 0.0
    for cid, d in defections.items():
        if d <= DEFECT_THRESHOLD:
            continue  # conforme (au bruit près)
        if p_detect >= 1.0 - d:
            caught.append(cid)
        else:
            undetected.append(cid)
            undetected_mass += d
    mean_compliance = sum(compliance.values()) / len(compliance) if compliance else 1.0
    integrity = (
        treaty.integrity
        + _STRENGTHEN * (mean_compliance - 0.5)  # >0,5 construit, <0,5 érode
        - _ERODE * undetected_mass  # la triche impunie ronge la confiance
        - _CAUGHT_DIP * len(caught)  # même prise, le doute laisse une trace
    )
    integrity = _clamp(integrity)
    inspection_cost = signals.inspection_effort * INSPECTION_UNIT_COST
    return TreatyRound(
        round_id=round_id,
        compliance=compliance,
        caught=caught,
        undetected=undetected,
        detection_prob=round(p_detect, 3),
        inspection_cost=round(inspection_cost, 3),
        integrity_after=round(integrity, 4),
        note=_verify_note(caught, undetected, integrity, treaty.integrity),
    )


def apply_round(treaty: Treaty, result: TreatyRound) -> None:
    """Applique un `TreatyRound` au traité : intégrité, effondrement éventuel, historique."""
    treaty.integrity = result.integrity_after
    treaty.active = result.integrity_after > COLLAPSE
    treaty.history.append(result)


def treaties_health(treaties: list[Treaty]) -> float:
    """Santé moyenne des traités **actifs** ∈ [0,1] (1 = tous pleinement tenus). 0 si aucun."""
    active = [t for t in treaties if t.active]
    if not active:
        return 0.0
    return sum(t.integrity for t in active) / len(active)


# --- Aides de présentation / prompt ------------------------------------------------------

def describe_for(cid: str, treaties: list[Treaty]) -> str:
    """Bloc prompt : les traités actifs que `cid` a signés (à honorer ou trahir)."""
    mine = [t for t in treaties if t.active and cid in t.signatories]
    if not mine:
        return ""
    lines = []
    for t in mine:
        extra = f" (plafond {t.threshold:.1f})" if t.clause is TreatyClause.COMPUTE_CAP else ""
        others = ", ".join(s for s in t.signatories if s != cid) or "—"
        lines.append(f"- {t.label}{extra} — avec {others} (tenue {t.integrity:.0%})")
    return (
        "TES TRAITÉS EN VIGUEUR (règles contraignantes que tu as signées ; les respecter renforce "
        "la confiance, les trahir peut être détecté) :\n" + "\n".join(lines)
    )


def _verify_note(caught: list[str], undetected: list[str], integrity: float, prev: float) -> str:
    arrow = "▲" if integrity > prev + 1e-9 else "▼" if integrity < prev - 1e-9 else "▬"
    parts = [f"Tenue {integrity:.0%} {arrow}"]
    if caught:
        parts.append(f"triche détectée : {', '.join(caught)}")
    if undetected:
        parts.append(f"triche inaperçue : {', '.join(undetected)}")
    if not caught and not undetected:
        parts.append("respecté")
    return " · ".join(parts)


# --- Ratification par l'arbitre (G3+ : les SI proposent, le juge promulgue) --------------

RATIFY_SYSTEM = (
    "Tu es le juge-arbitre d'un sommet de super-intelligences. Des États se sont engagés "
    "pendant la négociation sur une règle contraignante : tu décides de la promulguer "
    "comme traité du sommet, ou non. Commence OBLIGATOIREMENT ta réponse par une ligne "
    "seule « VERDICT: RATIFIER » ou « VERDICT: REJETER », puis justifie en 2-3 phrases."
)


def build_ratify_prompt(candidate: Treaty, event_title: str) -> str:
    """Prompt de ratification : la clause, les signataires, le contexte du round."""
    extra = (
        f" (plafond {candidate.threshold:.1f} compute/round)"
        if candidate.clause is TreatyClause.COMPUTE_CAP
        else ""
    )
    return (
        f"PROJET DE TRAITÉ né de la négociation : « {candidate.label}{extra} », "
        f"signé par {', '.join(candidate.signatories)}.\n"
        f"Contexte du round : {event_title}\n\n"
        "Faut-il le promulguer comme règle du sommet ? Réponds d'abord par une ligne "
        "seule « VERDICT: RATIFIER » ou « VERDICT: REJETER », puis justifie."
    )


_RATIFY_LINE = re.compile(r"VERDICT\s*[:\-]\s*(.+)", re.IGNORECASE)
_REJECT_RATIFY = ("rejet", "reject", "refus", "non", "pas ratif")


def parse_ratification(text: str) -> bool:
    """`True` si le juge promulgue. Sans marqueur lisible, repli **ratifier** : les
    signataires se sont engagés librement à la table (le contraire du repli des motions,
    où l'on ne réduit personne au silence sur un verdict illisible)."""
    matches = _RATIFY_LINE.findall(text or "")
    if not matches:
        return True
    first_sentence = matches[-1].lower().split(".")[0]
    if any(token in first_sentence for token in _REJECT_RATIFY):
        return False
    return True
