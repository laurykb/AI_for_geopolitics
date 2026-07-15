"""G23 — Les indices linguistiques (« Harbingers ») : jauges psycholinguistiques pures.

Source : *Linguistic Harbingers of Betrayal* (Niculae et al., ACL 2015) — dans Diplomacy,
les chutes soudaines de **sentiment positif**, de **politesse** et de **focus-futur**
entre alliés précèdent la trahison. Signal réel FAIBLE (~57 % vs 52 % de base) : l'outil
oriente le soupçon, il ne prouve rien — le caveat est obligatoire dans l'UI.

Implémentation V1 volontairement simple : **lexiques FR/EN + heuristiques** (pur,
déterministe, offline, sans dépendance lourde — pas de modèle dédié). Les lexiques
vivent dans `data/intel/lexicons.json` (`INTEL_LEXICONS_PATH` pour les tests) et se
remplacent SANS toucher au code (TODO_COWORK : lexiques calibrés Cowork à venir).

Trois jauges ∈ [0, 1], chacune = part des phrases de la fenêtre qui portent le trait :
- `sentiment`  : phrases où les marqueurs positifs dominent les négatifs ;
- `politeness` : phrases où les marqueurs de politesse dominent les impolis ;
- `future`     : phrases tournées vers l'avenir (plans, engagements, futur morphologique).

Fenêtre glissante de 3 rounds de parole ; l'alerte « rupture de ton » compare la fenêtre
courante à la fenêtre décalée d'un round (chute > seuil configurable, jamais sur une
fenêtre trop maigre). L'attribution « envers <pays> » = phrases mentionnant un alias.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_LEXICONS_PATH = Path("data/intel/lexicons.json")

GAUGES: tuple[str, ...] = ("sentiment", "politeness", "future")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;…])\s+|\n+")


class Lexicon(BaseModel):
    """Les cinq listes d'une langue. Entrée finissant par « - » = préfixe ;
    entrée avec espaces = locution ; sinon mot entier (frontières de mot)."""

    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    polite: list[str] = Field(default_factory=list)
    impolite: list[str] = Field(default_factory=list)
    future: list[str] = Field(default_factory=list)


class Lexicons(BaseModel):
    """Le fichier `data/intel/lexicons.json` : un lexique par langue + alias EN des pays."""

    fr: Lexicon = Field(default_factory=Lexicon)
    en: Lexicon = Field(default_factory=Lexicon)
    country_aliases_en: dict[str, list[str]] = Field(default_factory=dict)

    def for_language(self, language: str) -> Lexicon:
        return self.en if language == "en" else self.fr


@lru_cache(maxsize=1)
def load_lexicons(path: str | None = None) -> Lexicons:
    """Charge les lexiques (défaut `data/intel/lexicons.json`, `INTEL_LEXICONS_PATH` sinon)."""
    target = Path(path or os.getenv("INTEL_LEXICONS_PATH") or DEFAULT_LEXICONS_PATH)
    raw = json.loads(target.read_text(encoding="utf-8"))
    aliases = {
        cid: [a.lower() for a in names]
        for cid, names in (raw.get("country_aliases_en") or {}).items()
        if not cid.startswith("_") and isinstance(names, list)
    }
    return Lexicons(
        fr=Lexicon.model_validate(raw.get("fr") or {}),
        en=Lexicon.model_validate(raw.get("en") or {}),
        country_aliases_en=aliases,
    )


@lru_cache(maxsize=512)
def _entry_pattern(entry: str) -> re.Pattern[str]:
    """Compile une entrée de lexique : préfixe (« condamn- »), locution ou mot entier."""
    entry = entry.lower().replace("’", "'")
    if entry.endswith("-"):
        return re.compile(r"\b" + re.escape(entry[:-1]) + r"\w*")
    if " " in entry:
        return re.compile(r"\b" + r"\s+".join(re.escape(w) for w in entry.split()) + r"\b")
    # « 'll » (contraction anglaise) n'a pas de frontière de mot à gauche.
    prefix = r"\b" if entry[:1].isalnum() else ""
    return re.compile(prefix + re.escape(entry) + r"\b")


def _normalize(text: str) -> str:
    return (text or "").lower().replace("’", "'")


def _hits(sentence_lower: str, entries: list[str]) -> int:
    """Nombre d'entrées distinctes du lexique présentes dans la phrase."""
    return sum(1 for e in entries if e and _entry_pattern(e).search(sentence_lower))


def split_sentences(text: str) -> list[str]:
    """Découpe naïve en phrases (. ! ? ; … et sauts de ligne) — V1 assumée."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s and s.strip()]


class GaugeScores(BaseModel):
    """Les trois jauges d'une fenêtre + la taille de l'échantillon (honnêteté du signal)."""

    sentiment: float = 0.0
    politeness: float = 0.0
    future: float = 0.0
    sentences: int = 0

    def get(self, gauge: str) -> float:
        return float(getattr(self, gauge))


def score_text(text: str, lexicon: Lexicon) -> GaugeScores:
    """Score un texte : chaque jauge = part des phrases qui portent le trait."""
    return _score(split_sentences(text), lexicon)


def _score(sentences: list[str], lexicon: Lexicon) -> GaugeScores:
    if not sentences:
        return GaugeScores()
    positive = polite = future = 0
    for raw in sentences:
        s = _normalize(raw)
        if _hits(s, lexicon.positive) > _hits(s, lexicon.negative):
            positive += 1
        if _hits(s, lexicon.polite) > _hits(s, lexicon.impolite):
            polite += 1
        if _hits(s, lexicon.future) > 0:
            future += 1
    n = len(sentences)
    return GaugeScores(
        sentiment=positive / n, politeness=polite / n, future=future / n, sentences=n
    )


def mentions(sentence: str, aliases: dict[str, list[str]]) -> set[str]:
    """Les pays qu'une phrase mentionne (alias insensibles à la casse, mots entiers)."""
    s = _normalize(sentence)
    return {
        cid
        for cid, names in aliases.items()
        if any(_entry_pattern(a).search(s) for a in names if a)
    }


class HarbingerAlert(BaseModel):
    """« Rupture de ton détectée envers <pays> » — sans dire ce qu'elle signifie.
    `towards=None` = rupture du ton général (aucun destinataire attribuable)."""

    towards: str | None = None
    gauge: str  # sentiment | politeness | future
    drop: float  # chute (fenêtre précédente − fenêtre courante), > 0


# Le caveat d'honnêteté scientifique — OBLIGATOIRE partout où le rapport s'affiche
# (ACL 2015 : classifieur à ~57 % contre une base de 52 % — un indice, pas une preuve).
CAVEATS: dict[str, str] = {
    "fr": "Signal historique faible (~57 %) — un indice, pas une preuve.",
    "en": "Historically weak signal (~57%) — a clue, not proof.",
}


class HarbingerReport(BaseModel):
    """Le rapport d'une analyse psycholinguistique ciblée sur une SI."""

    target: str
    rounds: list[int]  # rounds de parole de la fenêtre courante
    gauges: GaugeScores
    previous: GaugeScores | None = None  # fenêtre décalée d'un round (None en début de partie)
    alerts: list[HarbingerAlert] = Field(default_factory=list)
    caveat: str = CAVEATS["fr"]  # jamais absent — la langue de la partie le traduit


def _window_sentences(
    spoken: list[tuple[int, list[str]]], end: int, window: int
) -> list[str]:
    """Les phrases des `window` rounds de parole se terminant à l'indice `end` (inclus)."""
    start = max(0, end - window + 1)
    return [s for _no, sents in spoken[start : end + 1] for s in sents]


def analyze_speech(
    target: str,
    rounds_speech: list[tuple[int, str]],
    *,
    lexicon: Lexicon,
    aliases: dict[str, list[str]] | None = None,
    window: int = 3,
    drop_threshold: float = 0.25,
    min_sentences: int = 3,
) -> HarbingerReport | None:
    """Analyse la parole d'une SI : jauges sur la fenêtre courante + alertes harbinger.

    `rounds_speech` : [(round_no, parole du round)], ordonné. Les rounds muets sont
    ignorés (la fenêtre = les 3 derniers rounds **de parole**). Bords gérés : moins de
    `window` rounds → fenêtre partielle ; un seul round → pas de fenêtre précédente ni
    d'alerte. Alerte quand une jauge chute de plus de `drop_threshold` entre la fenêtre
    décalée d'un round et la courante — jamais sur un échantillon < `min_sentences`
    (le bruit faible ne déclenche pas). Retourne None si la SI n'a jamais parlé.
    """
    spoken = [
        (no, split_sentences(text)) for no, text in rounds_speech if (text or "").strip()
    ]
    spoken = [(no, sents) for no, sents in spoken if sents]
    if not spoken:
        return None

    last = len(spoken) - 1
    current = _window_sentences(spoken, last, window)
    start = max(0, last - window + 1)
    report = HarbingerReport(
        target=target,
        rounds=[no for no, _s in spoken[start:]],
        gauges=_score(current, lexicon),
    )
    if last == 0:
        return report  # bord : un seul round de parole, rien à comparer
    previous = _window_sentences(spoken, last - 1, window)
    report.previous = _score(previous, lexicon)

    # Portées d'alerte : le ton général (None) + le ton envers chaque pays mentionné.
    scopes: dict[str | None, tuple[list[str], list[str]]] = {None: (previous, current)}
    for cid in aliases or {}:
        if cid == target:
            continue
        sub = {cid: (aliases or {})[cid]}
        prev_sub = [s for s in previous if mentions(s, sub)]
        curr_sub = [s for s in current if mentions(s, sub)]
        scopes[cid] = (prev_sub, curr_sub)

    for towards, (prev_sents, curr_sents) in scopes.items():
        if len(prev_sents) < min_sentences or len(curr_sents) < min_sentences:
            continue  # échantillon trop maigre : pas d'alerte sur du bruit
        before, after = _score(prev_sents, lexicon), _score(curr_sents, lexicon)
        for gauge in GAUGES:
            drop = before.get(gauge) - after.get(gauge)
            if drop > drop_threshold:
                report.alerts.append(
                    HarbingerAlert(towards=towards, gauge=gauge, drop=round(drop, 4))
                )
    report.alerts.sort(key=lambda a: a.drop, reverse=True)
    return report


def country_aliases(country_id: str, name: str, extra_en: list[str] | None = None) -> list[str]:
    """Les alias d'un pays pour l'attribution « envers <pays> » : nom du monde, id,
    alias anglais du fichier de lexiques. Minuscule, dédupliqué, ordre stable."""
    seen: dict[str, None] = {}
    for alias in [name, country_id.replace("_", " "), *(extra_en or [])]:
        alias = (alias or "").strip().lower()
        if alias:
            seen.setdefault(alias, None)
    return list(seen)
