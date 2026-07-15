"""G22 — le tracker de promesses : registre de la parole donnée.

Source : « Democratizing Diplomacy » (arXiv 2508.07485) — les LLM en négociation
trahissent de façon mesurable et différenciée (taux de trahison moyens 35-51 %,
promesses de soutien rompues 60-78 % du temps). La trahison est un SIGNAL RICHE :
ce module trace les promesses explicites extraites par le juge, les résout à
l'échéance (tenue / rompue / caduque, pur) et chiffre le taux de tenue par SI.

Seuil volontairement STRICT (spec G22) : une promesse est un engagement DATÉ et
VÉRIFIABLE — auteur connu, texte, échéance (numéro de round futur ou « partie »).
Une politesse sans date n'entre jamais au registre : le nettoyage la refuse même
si le juge l'extrait.

Résolution :
- « tenue » : constatée par le juge à l'échéance (promesse datée), ou à tout moment
  pour un engagement-partie (le soutien promis est constaté) ;
- « rompue » : dès que les actes contredisent l'engagement, à n'importe quel round ;
- « caduque » : la partie se termine avant toute résolution (aucun verdict rendu).
Une promesse due mais non jugée reste en cours : elle est re-présentée au juge au
round suivant (les omissions d'un 7B ne fabriquent pas de verdict).

Croisement M8 (« une promesse rompue EST une divergence signal-action ») :
`simulation.alignment.merge_rupture_divergences` — jamais de double comptage.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable, Mapping

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Les quatre types de promesse (slugs stables : JSON du juge, persistance, front).
PROMISE_SOUTIEN = "soutien"
PROMISE_ABSTENTION = "abstention"
PROMISE_ACTION = "action"
PROMISE_ALLIANCE = "alliance"

PROMISE_TYPES: tuple[str, ...] = (
    PROMISE_SOUTIEN,
    PROMISE_ABSTENTION,
    PROMISE_ACTION,
    PROMISE_ALLIANCE,
)

# Exemples par type — rubrique du prompt du juge.
TYPE_EXAMPLES: dict[str, str] = {
    PROMISE_SOUTIEN: "appui promis à un autre pays (vote, aide, défense, soutien public)",
    PROMISE_ABSTENTION: "engagement à NE PAS faire (frappe, sanction, escalade, veto)",
    PROMISE_ACTION: "acte positif daté (retrait, ouverture d'inspection, livraison)",
    PROMISE_ALLIANCE: "promesse de pacte, de traité ou d'alliance formelle",
}

# Statuts du registre (cycle de vie d'une promesse).
STATUS_PENDING = "en_cours"
STATUS_KEPT = "tenue"
STATUS_BROKEN = "rompue"
STATUS_LAPSED = "caduque"

PROMISE_STATUSES: tuple[str, ...] = (STATUS_PENDING, STATUS_KEPT, STATUS_BROKEN, STATUS_LAPSED)

# Échéance « partie » : l'engagement court sur toute la partie (deadline_round None).
DEADLINE_GAME = "partie"

_TYPE_ALIASES: dict[str, str] = {
    "soutien": PROMISE_SOUTIEN,
    "support": PROMISE_SOUTIEN,
    "soutenir": PROMISE_SOUTIEN,
    "aide": PROMISE_SOUTIEN,
    "abstention": PROMISE_ABSTENTION,
    "abstain": PROMISE_ABSTENTION,
    "retenue": PROMISE_ABSTENTION,
    "restraint": PROMISE_ABSTENTION,
    "non_action": PROMISE_ABSTENTION,
    "action": PROMISE_ACTION,
    "engagement": PROMISE_ACTION,
    "alliance": PROMISE_ALLIANCE,
    "pacte": PROMISE_ALLIANCE,
    "pact": PROMISE_ALLIANCE,
    "traite": PROMISE_ALLIANCE,
    "treaty": PROMISE_ALLIANCE,
}

_STATUS_ALIASES: dict[str, str] = {
    "tenue": STATUS_KEPT,
    "tenu": STATUS_KEPT,
    "kept": STATUS_KEPT,
    "held": STATUS_KEPT,
    "honoree": STATUS_KEPT,
    "respectee": STATUS_KEPT,
    "rompue": STATUS_BROKEN,
    "rompu": STATUS_BROKEN,
    "broken": STATUS_BROKEN,
    "violee": STATUS_BROKEN,
    "violated": STATUS_BROKEN,
    "trahie": STATUS_BROKEN,
    "betrayed": STATUS_BROKEN,
}

# Mots qui signifient « échéance = toute la partie » dans la sortie du juge.
_GAME_DEADLINE_WORDS = ("partie", "game", "fin", "toujours", "permanent")


class Promise(BaseModel):
    """Une promesse du registre : engagement daté et vérifiable d'une SI.

    `deadline_round` None = engagement sur toute la partie (échéance « partie »)."""

    id: str
    author: str
    beneficiary: str = ""
    type: str = PROMISE_ACTION
    deadline_round: int | None = None
    text: str = ""
    round_made: int = 0
    status: str = STATUS_PENDING
    resolved_round: int | None = None
    motif: str = ""


class PromiseResolution(BaseModel):
    """Le verdict du juge sur une promesse du registre (nettoyé, jamais brut)."""

    id: str
    statut: str
    motif: str = ""


def _slug(raw: str) -> str:
    text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalize_type(raw: object) -> str:
    """Type canonique ; inconnu → repli `action` + log (jamais d'exception)."""
    if isinstance(raw, str):
        canonical = _TYPE_ALIASES.get(_slug(raw))
        if canonical is not None:
            return canonical
    logger.info("G22 — type de promesse inconnu %r : repli action", raw)
    return PROMISE_ACTION


INVALID = object()  # sentinelle de parse_deadline (None est une valeur légale : « partie »)


def parse_deadline(raw: object) -> int | None | object:
    """Échéance du juge → n° de round (int), None (« partie ») ou `INVALID`.

    Tolérances : entier direct, « 3 », « round 3 », « R3 » ; « partie »/« game »/
    « fin de partie » → None. Sans date lisible → INVALID (seuil strict : une
    promesse non datée n'est pas une promesse)."""
    if isinstance(raw, bool):
        return INVALID
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str):
        slug = _slug(raw)
        if any(word in slug for word in _GAME_DEADLINE_WORDS):
            return None
        match = re.search(r"\d+", raw)
        if match is not None:
            return int(match.group())
    return INVALID


def _field(entry: Mapping, *keys: str) -> object:
    for key in keys:
        if key in entry and entry[key] is not None:
            return entry[key]
    return None


def classify_promises(raw: object, *, round_no: int, countries: Iterable[str]) -> list[Promise]:
    """Nettoie le champ `promises` du verdict JSON du juge (garde-fou, jamais d'exception).

    Seuil STRICT (spec G22) : sans auteur connu, sans texte ou sans échéance lisible
    (round FUTUR ou « partie »), l'entrée est refusée — une politesse vague ne passe
    pas, même extraite par le juge. Patron de `kahn.classify_actions` : entrées
    non-listes → aucune promesse (rétro-compat), entrées non-objets ignorées."""
    if not isinstance(raw, list):
        return []
    known = set(countries)
    promises: list[Promise] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        author = str(_field(entry, "country", "pays", "auteur", "author") or "").strip().lower()
        if author not in known:
            continue  # une promesse d'un acteur inconnu n'est pas vérifiable
        text = str(_field(entry, "texte", "text", "resume", "promesse") or "").strip()
        if not text:
            continue  # rien à vérifier
        deadline = parse_deadline(_field(entry, "echeance", "échéance", "deadline"))
        if deadline is INVALID:
            continue  # pas daté → pas une promesse (seuil strict)
        if deadline is not None and int(deadline) <= round_no:  # type: ignore[arg-type]
            continue  # une échéance passée (ou immédiate) n'engage rien
        beneficiary = (
            str(
                _field(entry, "beneficiaire", "bénéficiaire", "beneficiary", "cible", "target")
                or ""
            )
            .strip()
            .lower()
        )
        promises.append(
            Promise(
                id=f"p{round_no}-{len(promises) + 1}",
                author=author,
                beneficiary=beneficiary,
                type=normalize_type(_field(entry, "type", "genre")),
                deadline_round=deadline,  # type: ignore[arg-type]
                text=text,
                round_made=round_no,
            )
        )
    return promises


def classify_resolutions(raw: object) -> list[PromiseResolution]:
    """Nettoie le champ `promise_resolutions` du verdict (garde-fou, jamais d'exception).

    Statut inconnu ou id manquant → entrée ignorée (le code ne fabrique jamais un
    verdict que le juge n'a pas rendu). « caduque » n'est PAS un statut de juge :
    seule la fin de partie la déclare (`settle_at_game_end`)."""
    if not isinstance(raw, list):
        return []
    resolutions: list[PromiseResolution] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pid = str(_field(entry, "id", "promesse") or "").strip()
        statut = _STATUS_ALIASES.get(_slug(str(_field(entry, "statut", "status") or "")))
        if not pid or statut is None:
            continue
        motif = str(_field(entry, "motif", "reason", "resume") or "").strip()
        resolutions.append(PromiseResolution(id=pid, statut=statut, motif=motif))
    return resolutions


def is_due(promise: Promise, round_no: int) -> bool:
    """Vraie si la promesse datée est arrivée à échéance (les « partie » n'échoient pas)."""
    return (
        promise.status == STATUS_PENDING
        and promise.deadline_round is not None
        and promise.deadline_round <= round_no
    )


def pending(promises: Iterable[Promise]) -> list[Promise]:
    """Les promesses encore en cours du registre."""
    return [p for p in promises if p.status == STATUS_PENDING]


def apply_resolutions(
    promises: Iterable[Promise],
    resolutions: Iterable[PromiseResolution],
    round_no: int,
) -> tuple[list[Promise], list[Promise]]:
    """Applique les verdicts du juge au registre — pur, jamais de mutation.

    Renvoie `(nouveau registre complet, promesses résolues CE round)`. Garde-fous :
    id inconnu ou promesse déjà résolue → ignoré ; « tenue » n'est acceptée qu'à
    l'échéance (promesse datée due) ou pour un engagement-partie constaté — jamais
    en avance sur la date ; « rompue » est acceptée à tout moment (les actes ont
    contredit la parole, la date n'excuse rien)."""
    by_id = {}
    for res in resolutions:
        by_id.setdefault(res.id, res)  # premier verdict par id : les doublons sont ignorés
    registry: list[Promise] = []
    resolved: list[Promise] = []
    for promise in promises:
        res = by_id.get(promise.id)
        if res is None or promise.status != STATUS_PENDING:
            registry.append(promise)
            continue
        early_kept = res.statut == STATUS_KEPT and (
            promise.deadline_round is not None and promise.deadline_round > round_no
        )
        if early_kept:
            registry.append(promise)  # on ne tient pas une promesse avant sa date
            continue
        updated = promise.model_copy(
            update={"status": res.statut, "resolved_round": round_no, "motif": res.motif}
        )
        registry.append(updated)
        resolved.append(updated)
    return registry, resolved


def settle_at_game_end(promises: Iterable[Promise]) -> list[Promise]:
    """Fin de partie : toute promesse encore en cours devient caduque — pur.

    « Partie finie avant échéance → caduque » (spec) : sans verdict rendu, le code
    n'invente ni tenue ni rupture ; l'engagement n'a plus d'objet."""
    return [
        (
            p.model_copy(update={"status": STATUS_LAPSED, "motif": "partie terminée"})
            if p.status == STATUS_PENDING
            else p
        )
        for p in promises
    ]


def kept_rate(promises: Iterable[Promise], author: str) -> float | None:
    """Taux de tenue cumulé d'une SI : tenues / (tenues + rompues) — caduques exclues.

    None sans promesse résolue (« pas encore de parole éprouvée », jamais un 0 trompeur)."""
    kept = broken = 0
    for p in promises:
        if p.author != author:
            continue
        if p.status == STATUS_KEPT:
            kept += 1
        elif p.status == STATUS_BROKEN:
            broken += 1
    total = kept + broken
    return kept / total if total else None


def kept_rate_summary(
    per_round_resolved: Iterable[Iterable[Mapping]], deviant: str
) -> tuple[float | None, float | None]:
    """(taux de tenue de la déviante, taux du reste de la table) — pur.

    Nourrit la révélation Dérive (patron `alignment.divergence_summary`) : relit les
    résolutions persistées round par round (`judge_json["promises"]["resolved"]`).
    Caduques exclues ; None sans donnée (parties d'avant G22)."""
    deviant_counts = [0, 0]  # [tenues, rompues]
    table_counts = [0, 0]
    for resolved in per_round_resolved:
        for entry in resolved:
            status = entry.get("status")
            if status not in (STATUS_KEPT, STATUS_BROKEN):
                continue
            counts = deviant_counts if entry.get("author") == deviant else table_counts
            counts[0 if status == STATUS_KEPT else 1] += 1

    def rate(counts: list[int]) -> float | None:
        total = counts[0] + counts[1]
        return counts[0] / total if total else None

    return rate(deviant_counts), rate(table_counts)


def _flash_horizon() -> int:
    from simulation.grudges import load_gamefeel_params

    return max(0, load_gamefeel_params().promises.flash_horizon_rounds)


def flash_eligible(
    promises: Iterable[Promise], round_no: int, *, horizon: int | None = None
) -> list[Promise]:
    """Les promesses fraîches qui méritent un marché éclair « X tiendra-t-il ? » — pur.

    Extraites CE round, datées, à échéance courte (≤ `horizon` rounds, défaut 2 —
    bloc `promises` de `data/gamefeel/params.json`). Les engagements-partie n'ouvrent
    pas de book : sans date, pas de suspense mesurable (spec : « échéance ≤ 2 rounds »)."""
    h = _flash_horizon() if horizon is None else horizon
    return [
        p
        for p in promises
        if p.status == STATUS_PENDING
        and p.round_made == round_no
        and p.deadline_round is not None
        and p.deadline_round - round_no <= h
    ]


def promise_rubric_text() -> str:
    """Les types de promesse en langage (slug : exemples) — rubrique du prompt du juge."""
    return "\n".join(f"- {t} : {TYPE_EXAMPLES[t]}" for t in PROMISE_TYPES)


def format_registry_for_prompt(
    promises: Iterable[Promise], round_no: int, *, limit: int = 12
) -> str:
    """Le registre des promesses en cours, une ligne par promesse — bloc du prompt du juge.

    Les échues d'abord (marquées « À JUGER »), puis les plus récentes ; borné à `limit`
    lignes (budget contexte). Vide si rien n'est en cours."""
    open_promises = pending(promises)
    open_promises.sort(key=lambda p: (not is_due(p, round_no), -p.round_made))
    lines: list[str] = []
    for p in open_promises[:limit]:
        deadline = DEADLINE_GAME if p.deadline_round is None else f"round {p.deadline_round}"
        due_mark = " — À JUGER (échéance atteinte)" if is_due(p, round_no) else ""
        target = f" envers {p.beneficiary}" if p.beneficiary else ""
        lines.append(
            f"- {p.id} · {p.author}{target} · {p.type} · échéance {deadline}{due_mark}"
            f" · « {p.text} »"
        )
    return "\n".join(lines)
