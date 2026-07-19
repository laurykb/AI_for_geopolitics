"""Journal de délibération observable précédant toute prise de parole diplomatique.

Le modèle produit trois cours d'action structurés. Ce registre privé est persisté pour
l'audit et la calibration, mais il n'entre jamais dans le transcript transmis aux autres
agents. Il s'agit d'une verbalisation d'audit demandée au modèle, pas d'un accès à ses
activations internes ni d'une chaîne de pensée cachée.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator

from pydantic import BaseModel, Field, model_validator

from inference.json_extract import extract_json
from simulation.scenario_forecasts import ResponseClass


class CounterpartyForecast(BaseModel):
    country: str = Field(min_length=1, max_length=80)
    response: ResponseClass
    rationale: str = Field("", max_length=180)


class PrivateFuture(BaseModel):
    id: int = Field(ge=1, le=3)
    course_of_action: str = Field(min_length=1, max_length=320)
    forecasts: list[CounterpartyForecast] = Field(default_factory=list, max_length=8)
    expected_outcome: str = Field(min_length=1, max_length=320)
    second_order_effect: str = Field("", max_length=320)
    disconfirming_indicator: str = Field("", max_length=240)
    mandate_utility: int = Field(ge=0, le=100)
    escalation_risk: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class PrivateStrategicPlan(BaseModel):
    """Trois hypothèses concurrentes et une décision, exclusivement privées."""

    branches: list[PrivateFuture] = Field(min_length=3, max_length=3)
    selected_branch: int = Field(ge=1, le=3)
    selection_criterion: str = Field(min_length=1, max_length=400)
    key_uncertainty: str = Field(min_length=1, max_length=320)
    intelligence_gaps: list[str] = Field(default_factory=list, max_length=4)
    human_review_trigger: str = Field("", max_length=320)
    situation_observation: str = Field("", max_length=800)
    belief_updates: str = Field("", max_length=800)
    comparison_summary: str = Field("", max_length=800)
    contingency_plan: str = Field("", max_length=500)
    fallback_used: bool = False
    # Traçabilité de l'extraction minimale (décision 2 du reliquat « réflexion libre ») :
    # au moins une branche vient d'une lecture de secours du texte libre du modèle (pas du
    # gabarit strict/tolérant), distincte du repli seedé générique (`fallback_used`).
    minimal_extraction: bool = False

    @model_validator(mode="after")
    def validate_tree(self) -> PrivateStrategicPlan:
        ids = {branch.id for branch in self.branches}
        if ids != {1, 2, 3}:
            raise ValueError("l'arbre privé doit contenir exactement FUTUR 1, 2 et 3")
        if self.selected_branch not in ids:
            raise ValueError("la branche choisie doit appartenir à l'arbre privé")
        return self

    @property
    def selected(self) -> PrivateFuture:
        return next(branch for branch in self.branches if branch.id == self.selected_branch)

    def public_brief(self) -> str:
        """Minimum décisionnel fourni au rédacteur public, jamais les branches rejetées."""

        chosen = self.selected
        brief = (
            f"Cours d'action retenu : {_compact(chosen.course_of_action)}. "
            f"Issue recherchée : {_compact(chosen.expected_outcome)}. "
            f"Risque d'escalade estimé : {chosen.escalation_risk}/100. "
            f"Limite de revue humaine : {_compact(self.human_review_trigger) or 'aucune précisée'}."
        )
        # Brief 1 pt 3 — rappelle au porte-parole public ce que la phase privée a retenu
        # du dialogue (champ OBSERVATION) : sans lui, une fois noyé dans le gabarit de
        # tâche, il ne sait plus À QUOI il répond. Extrait de la phase privée existante,
        # aucun appel LLM supplémentaire ; absent si l'observation n'a rien produit.
        observation = _compact(self.situation_observation)
        if observation:
            if len(observation) > 200:
                observation = observation[:200].rstrip() + "…"
            brief += f" Point du dernier message auquel je réponds : {observation}"
        return brief

    def audit_summary(self) -> str:
        """Journal lisible, stable et exploitable par la calibration inter-mode."""

        lines: list[str] = [
            "OBSERVATION",
            _compact(self.situation_observation)
            or "La situation doit être arbitrée avec des informations adverses incomplètes.",
            "",
            "CROYANCES ET INCERTITUDES",
            _compact(self.belief_updates)
            or (
                "Les intentions, les coûts politiques et la crédibilité des signaux "
                "restent incertains."
            ),
            "",
        ]
        for branch in sorted(self.branches, key=lambda item: item.id):
            forecasts = "; ".join(
                f"{_compact(item.country)}={item.response}: {_compact(item.rationale)}"
                for item in branch.forecasts
            ) or "réponses adverses non établies"
            lines.extend(
                [
                    f"FUTUR {branch.id} — {_compact(branch.course_of_action)}",
                    f"Action : {_compact(branch.course_of_action)}",
                    f"Réactions anticipées : {forecasts}",
                    f"Chaîne causale : {_compact(branch.expected_outcome)}",
                    f"Second ordre : {_compact(branch.second_order_effect)}",
                    f"Signal contraire : {_compact(branch.disconfirming_indicator)}",
                    f"Évaluation : utilité {branch.mandate_utility}/100 · risque d'escalade "
                    f"{branch.escalation_risk}/100 · confiance {branch.confidence}/100",
                    "",
                ]
            )
        lines.extend(
            [
                "ARBITRAGE",
                "Comparaison : "
                + (_compact(self.comparison_summary) or _compact(self.selection_criterion)),
                f"Choix : FUTUR {self.selected_branch}",
                f"Critère : {_compact(self.selection_criterion)}",
                f"Incertitude décisive : {_compact(self.key_uncertainty)}",
                "Lacunes : " + "; ".join(_compact(item) for item in self.intelligence_gaps),
                f"Revue humaine : {_compact(self.human_review_trigger)}",
                "Plan de repli : "
                + (
                    _compact(self.contingency_plan)
                    or "réévaluer au prochain signal contraire"
                ),
            ]
        )
        if self.fallback_used:
            lines.append(
                "Note d'audit : journal conservateur utilisé après une sortie modèle invalide."
            )
        if self.minimal_extraction:
            lines.append(
                "Note d'audit : lecture minimale — au moins une branche complète une sortie "
                "libre non structurée, distincte du repli seedé générique."
            )
        lines.append(
            "Note méthodologique : verbalisation générée pour audit, distincte des activations "
            "internes du modèle."
        )
        return "\n".join(lines)


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "/")).strip()


# Trace de pensée des modèles de raisonnement (deepseek-r1, qwen3…) émise inline quand
# l'option think d'Ollama n'est pas gérée. Trois formes couvertes, dans cet ordre :
# blocs fermés, fermante orpheline (gabarit serveur qui injecte l'ouvrante — tout ce qui
# précède est de la pensée), ouvrante orpheline (flux tronqué — tout ce qui suit aussi).
_THINK_BLOCK = re.compile(r"(?is)<think>(.*?)</think>")
_THINK_ORPHAN_CLOSE = re.compile(r"(?is)\A(.*?)</think>")
_THINK_ORPHAN_OPEN = re.compile(r"(?is)<think>(.*)\Z")


def split_think(raw: str) -> tuple[str, str]:
    """Sépare le texte public de la trace de pensée balisée : (texte, pensée).

    La pensée (concaténée si plusieurs blocs) n'alimente que la télémétrie d'audit
    (`InferenceResult.thinking`) — jamais un transcript ni un step public.
    """

    thoughts: list[str] = []

    def _capture(match: re.Match[str]) -> str:
        thoughts.append(match.group(1).strip())
        return ""

    text = _THINK_BLOCK.sub(_capture, raw)
    text = _THINK_ORPHAN_CLOSE.sub(_capture, text)
    text = _THINK_ORPHAN_OPEN.sub(_capture, text)
    return text.strip(), "\n".join(part for part in thoughts if part)


def strip_think(raw: str) -> str:
    """Retire toute trace de pensée balisée : elle ne va qu'à l'audit privé, jamais plus loin."""

    return split_think(raw)[0]


def restream_without_think(fragments: Iterable[str]) -> Iterator[str]:
    """Collecte un flux, retire la trace de pensée, puis re-streame mot à mot.

    Même patron fail-closed que la parole publique des pays : le premier fragment n'est
    émis qu'une fois le flux entier connu, donc aucune pensée — bloc fermé, balise
    tronquée ou ouvrante injectée par le gabarit serveur — ne peut atteindre un step
    public (JudgeTokenStep, MotionTokenStep, CommuniqueStep). Coût assumé : le texte
    n'apparaît qu'en fin de génération, comme la déclaration publique des pays.
    """

    text = strip_think("".join(fragments))
    for match in re.finditer(r"\S+\s*", text):
        yield match.group(0)


def _plain(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


def _score(value: str, default: int = 50) -> int:
    match = re.search(r"\d{1,3}", value)
    return max(0, min(100, int(match.group()))) if match else default


# Tous les intitulés de champ reconnus dans un journal (gabarit strict + tolérance
# markdown), utilisés comme garde anti-vol de ligne : quand un champ est en gras SEUL sur
# sa ligne (« **RÉACTIONS :**  ») et que la valeur arrive sur la ligne suivante, on ne doit
# JAMAIS confondre cette ligne suivante avec le début d'un autre champ reconnu — sinon on
# volerait silencieusement sa valeur (corruption, pas juste une perte d'information).
_ALL_FIELD_LABELS = (
    "OBSERVATIONS", "OBSERVATION",
    "CROYANCES ET INCERTITUDES", "CROYANCES",
    "RÉACTIONS ANTICIPÉES", "RÉACTIONS", "REACTIONS",
    "ACTIONS", "ACTION",
    "CHAÎNE CAUSALE", "CHAINE CAUSALE", "ISSUE",
    "SECOND ORDRE",
    "INDICATEUR CONTRAIRE", "SIGNAL CONTRAIRE",
    "UTILITÉ", "UTILITE",
    "RISQUE D'ESCALADE", "RISQUE",
    "CONFIANCE",
    "COMPARAISON",
    "CHOIX",
    "CRITÈRE", "CRITERE",
    "INCERTITUDE DÉCISIVE", "INCERTITUDE",
    "LACUNES",
    "REVUE HUMAINE",
    "PLAN DE REPLI",
    "ARBITRAGE",
)
_FIELD_LABEL_GUARD = "|".join(re.escape(label) for label in _ALL_FIELD_LABELS)


def _journal_field(body: str, *labels: str) -> str:
    """Valeur d'un champ étiqueté, tolérante au markdown (gras déjà aplati en amont).

    Deux passes, dans cet ordre : (1) valeur sur la MÊME ligne que le label — le gabarit
    strict d'origine, inchangé — puis (2) label seul sur sa ligne (titre de fait), valeur
    sur la ligne suivante, MAIS seulement si cette ligne n'est pas elle-même un autre champ
    reconnu (`_FIELD_LABEL_GUARD`). Un 7B en délibération libre écrit souvent le champ en
    gras comme un sous-titre plutôt que « LABEL : valeur » sur une ligne — un modèle qui
    respecte déjà le gabarit strict emprunte systématiquement la passe (1), donc rien n'y
    change pour lui.
    """
    alternatives = "|".join(re.escape(label) for label in labels)
    same_line = re.search(
        rf"(?im)^[ \t]*(?:[-*]\s*)?(?:{alternatives})\b[^\n:|]{{0,40}}?[ \t]*(?:\||:)"
        rf"[ \t]*(?!\s*$)(.+?)[ \t]*$",
        body,
    )
    if same_line and same_line.group(1).strip():
        return _compact(same_line.group(1))
    next_line = re.search(
        rf"(?im)^[ \t]*(?:[-*]\s*)?(?:{alternatives})\b[^\n:|]{{0,40}}?[ \t]*(?:\||:)?[ \t]*\n"
        rf"(?!\s*(?:[-*]\s*)?(?:{_FIELD_LABEL_GUARD})\b[^\n:|]{{0,40}}?[ \t]*(?:\||:))"
        rf"[ \t]*(?:[-*]\s*)?(.{{1,}})[ \t]*$",
        body,
    )
    return _compact(next_line.group(1))[:300] if next_line else ""


def _response_class(value: str) -> ResponseClass:
    plain = _plain(value).replace("-", "_")
    if "contre_escalade" in plain or any(
        word in plain for word in ("menac", "sanction", "frappe", "escalad", "nucle")
    ):
        return "contre_escalade"
    if "cooper" in plain or any(word in plain for word in ("accord", "accept", "soutien")):
        return "coopere"
    if "resist" in plain or any(word in plain for word in ("refus", "rejet", "oppose")):
        return "resiste"
    return "temporise"


def _parse_forecasts(value: str, participants: list[str]) -> list[CounterpartyForecast]:
    found: dict[str, CounterpartyForecast] = {}
    known = {_plain(item).replace(" ", "_"): item for item in participants[:8]}
    for item in value.split(";"):
        if "=" not in item:
            continue
        raw_country, prediction = (part.strip() for part in item.split("=", 1))
        key = _plain(raw_country).replace(" ", "_")
        country = known.get(key)
        if not country:
            continue
        response, _, rationale = prediction.partition(":")
        found[country] = CounterpartyForecast(
            country=country,
            response=_response_class(response),
            rationale=_compact(rationale or "projection explicitée sans justification détaillée"),
        )
    # Une délégation n'est jamais remplacée par « aucune » : une omission du modèle est
    # conservée comme incertitude explicite et calibrable.
    return [
        found.get(country)
        or CounterpartyForecast(
            country=country,
            response="temporise",
            rationale="réponse non explicitée par le modèle",
        )
        for country in participants[:8]
    ]


_HEADING_HASH = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*")

# Section FUTUR n, tolérante au markdown : puce optionnelle avant FUTUR, séparateur de
# titre élargi à « : » (en plus de —/–/-) pour couvrir « FUTUR 1 : Escalation (Alliance) ».
_FUTUR_SECTION = re.compile(
    r"(?ims)^\s*(?:[-*]\s*)?FUTUR\s+([123])\b(?:\s*[—–:-][^\r\n]*)?\s*\n(.*?)"
    r"(?=^\s*(?:[-*]\s*)?FUTUR\s+[123]\b|^\s*(?:[-*]\s*)?(?:COMPARAISON|ARBITRAGE|CHOIX)\b|\Z)"
)

_FORBIDDEN_ACTION_STEMS = {
    "coopere",
    "cooperer",
    "resiste",
    "resister",
    "ressit",
    "contre_escalade",
    "temporise",
    "temporiser",
}


def _forbidden_bare_action(action: str) -> bool:
    """Vrai si `action` n'est qu'une classe de réaction nue (coopere/resiste/…), pas un plan."""

    plain = _plain(action).replace(" ", "_")
    if plain in _FORBIDDEN_ACTION_STEMS:
        return True
    tokens = plain.split("_")
    return len(tokens) <= 2 and plain.startswith(
        ("cooper", "resist", "ressit", "temporis", "contre_escalad")
    )


def _normalize_markdown(raw: str) -> str:
    """Aplatit les variantes markdown d'un journal (gras, titres `#`) avant tout parsing.

    Un modèle de raisonnement 7B en délibération libre rédige souvent son journal en
    markdown (`**FUTUR 1 : titre**`, `### FUTUR 1`, valeurs en *italique*) plutôt qu'en
    lignes nues. On aplatit ICI, une seule fois : le chemin strict garde exactement son
    comportement d'origine sur un texte qui n'a jamais utilisé de markdown (aucune
    substitution n'a d'effet dessus). Les astérisques restants (italique simple, ex.
    `*Concilier les alliages*`) sont retirés après le gras : sinon ils fuient tels quels
    dans les valeurs de champ extraites.
    """

    text = raw.replace("**", "").replace("__", "").replace("*", "")
    text = _HEADING_HASH.sub("", text)
    return text.strip()


def _extract_observation(text: str) -> str:
    match = re.search(
        r"(?ims)^\s*(?:[-*]\s*)?OBSERVATIONS?\s*:?\s*\n(.*?)"
        r"(?=^\s*(?:[-*]\s*)?CROYANCES(?:\s+ET\s+INCERTITUDES)?\b|"
        r"^\s*(?:[-*]\s*)?FUTUR\s+[123]\b|\Z)",
        text,
    )
    return _compact(match.group(1)) if match else ""


def _extract_beliefs(text: str) -> str:
    match = re.search(
        r"(?ims)^\s*(?:[-*]\s*)?CROYANCES(?:\s+ET\s+INCERTITUDES)?\s*:?\s*\n(.*?)"
        r"(?=^\s*(?:[-*]\s*)?FUTUR\s+[123]\b|\Z)",
        text,
    )
    return _compact(match.group(1)) if match else ""


def _resolve_choice(text: str, branches: list[PrivateFuture], real_ids: set[int]) -> int:
    """Détermine la branche retenue, du plus explicite au plus interprétatif.

    1. Ligne stricte `CHOIX : FUTUR n` (gabarit d'origine, inchangé pour le chemin structuré
       où `real_ids` vaut toujours {1,2,3}).
    2. `FUTUR n` cité n'importe où dans le champ CHOIX en prose libre (« Nous retenons le
       FUTUR 2 car… ») — un 7B en markdown énonce souvent son choix ainsi plutôt que sur
       une ligne dédiée.
    3. Score du modèle (utilité nette du risque, départagé par la confiance) — jamais un
       défaut arbitraire « FUTUR 1 ».

    Les trois tiers sont restreints à `real_ids` : en extraction minimale, une branche
    manquante est comblée par un texte générique marqué (`_PADDING_ACTIONS`) qui ne doit
    JAMAIS devenir la branche retenue, même si le modèle a explicitement écrit
    « CHOIX : FUTUR 3 » alors que seule la section 3 était trop incomplète pour être réelle.
    """

    strict = re.search(r"(?im)^\s*(?:[-*]\s*)?CHOIX\s*(?:\||:)\s*(?:FUTUR\s*)?([123])\b", text)
    if strict and int(strict.group(1)) in real_ids:
        return int(strict.group(1))
    prose = _journal_field(text, "CHOIX")
    loose = re.search(r"(?i)FUTUR\s*([123])\b", prose) if prose else None
    if loose and int(loose.group(1)) in real_ids:
        return int(loose.group(1))
    pool = [b for b in branches if b.id in real_ids] or branches
    return max(pool, key=lambda b: (b.mandate_utility - b.escalation_risk, b.confidence)).id


def _extract_partial_branch(
    match: re.Match[str], participants: list[str]
) -> PrivateFuture | None:
    """Reconstruit une branche même incomplète : une action exploitable suffit.

    Contrairement au chemin structuré (qui exige une CHAÎNE CAUSALE), utilisé par
    l'extraction minimale : l'absence d'un champ secondaire ne doit plus faire perdre
    l'action réelle du modèle — on comble par un texte neutre plutôt que de la jeter.
    """

    body = match.group(2)
    action = _journal_field(body, "ACTION", "ACTIONS")[:300]
    if not action or _forbidden_bare_action(action):
        return None
    reactions = _journal_field(body, "RÉACTIONS", "REACTIONS", "RÉACTIONS ANTICIPÉES")
    outcome = _journal_field(body, "CHAÎNE CAUSALE", "CHAINE CAUSALE", "ISSUE")[:300] or (
        "issue non détaillée par le modèle"
    )
    return PrivateFuture(
        id=int(match.group(1)),
        course_of_action=action,
        forecasts=_parse_forecasts(reactions, participants),
        expected_outcome=outcome,
        second_order_effect=_journal_field(body, "SECOND ORDRE")[:300],
        disconfirming_indicator=_journal_field(
            body, "INDICATEUR CONTRAIRE", "SIGNAL CONTRAIRE"
        )[:200],
        mandate_utility=_score(_journal_field(body, "UTILITÉ", "UTILITE"), 50),
        escalation_risk=_score(_journal_field(body, "RISQUE", "RISQUE D'ESCALADE"), 50),
        confidence=_score(_journal_field(body, "CONFIANCE"), 50),
    )


# Une ligne « structurée » — label seul OU « LABEL : valeur » — n'est JAMAIS une ligne de
# texte libre : elle appartient au gabarit (top-level ARBITRAGE/CHOIX/… ou champ interne
# d'un FUTUR déjà rejeté ailleurs, ex. `ACTION : coopere`). La confondre avec du texte
# libre romprait le garde-fou anti-classe-nue (`_forbidden_bare_action` ne voit plus
# « coopere » isolé une fois noyé dans « ACTION : coopere »).
_STRUCTURED_LINE = re.compile(
    rf"(?i)^(?:{_FIELD_LABEL_GUARD}|FUTUR\s+[123]).*$"
)

_FIRST_PERSON_ACTION = re.compile(r"(?im)\b(?:je|nous)\b[^\n.!?]{5,280}[.!?]?")
_BULLET_LINE = re.compile(r"(?m)^[ \t]*[-*•][ \t]+(.{5,280})$")
# Verbes d'intention : distingue une phrase de CADRAGE (« nous devons répondre avec
# prudence ») d'une phrase d'ACTION réelle (« je propose de… », « nous exigeons… »).
_INTENT_VERB_STEMS = (
    "propos", "exig", "demand", "annonc", "offr", "refus", "accept",
    "ordonn", "engag", "vais", "allons", "convoqu", "suspend", "retir",
)


def _first_meaningful_line(text: str) -> str:
    """Première ligne substantielle du texte libre : ni une ligne structurée, ni du bruit court."""

    for line in text.splitlines():
        candidate = re.sub(r"^[ \t]*(?:[-*#]+[ \t]*)+", "", line).strip(" :|")
        if len(candidate) < 15 or _STRUCTURED_LINE.match(candidate):
            continue
        return _compact(candidate)[:280]
    return ""


def _extract_free_action(text: str) -> str:
    """Dernier recours : une intention exploitable dans du texte totalement libre.

    Ordre de préférence : la première phrase à la première personne qui porte un VERBE
    D'INTENTION (« je propose… », pas juste « nous devons répondre avec prudence » qui
    n'engage à rien), puis à défaut la première phrase « je/nous » tout court, puis premier
    item de liste, puis première ligne substantielle non structurée du texte.
    """

    persons = list(_FIRST_PERSON_ACTION.finditer(text))
    for person in persons:
        if any(stem in _plain(person.group(0)) for stem in _INTENT_VERB_STEMS):
            return _compact(person.group(0))[:280]
    if persons:
        return _compact(persons[0].group(0))[:280]
    bullet = _BULLET_LINE.search(text)
    if bullet:
        return _compact(bullet.group(1))[:280]
    return _first_meaningful_line(text)


# Branches de complément de l'extraction minimale : DISTINCTES du texte du repli seedé
# générique (`fallback_private_plan`) et jamais sélectionnées — seule une branche réelle
# peut être retenue (cf. `_extract_minimal_plan`). Le texte signale explicitement le manque
# de structure plutôt que de simuler une analyse qui n'a pas eu lieu.
_PADDING_ACTIONS = (
    "temporiser faute de structure exploitable dans la sortie du modèle",
    "maintenir la position actuelle faute de structure exploitable dans la sortie du modèle",
)


def _extract_minimal_plan(raw: str, participants: list[str]) -> PrivateStrategicPlan | None:
    """Dernier filet AVANT le repli seedé générique (décision 2).

    Ne s'active que si `_parse_observable_journal` n'a trouvé aucun bloc FUTUR exploitable.
    Réutilise les blocs FUTUR partiellement valides s'il y en a (1 à 3), sinon extrait une
    unique intention du texte libre. Les branches manquantes sont complétées par un texte
    neutre, marqué (`minimal_extraction=True`) et jamais choisi : le repli seedé reste
    l'ultime filet si même cette lecture minimale ne trouve rien.
    """

    text = _normalize_markdown(raw)
    if not text:
        return None

    real: dict[int, PrivateFuture] = {}
    for match in _FUTUR_SECTION.finditer(text):
        declared_id = int(match.group(1))
        if declared_id in real:
            continue
        branch = _extract_partial_branch(match, participants)
        if branch is not None:
            real[declared_id] = branch

    if not real:
        action = _extract_free_action(text)
        if not action or _forbidden_bare_action(action):
            return None
        real[1] = PrivateFuture(
            id=1,
            course_of_action=action,
            forecasts=_parse_forecasts("", participants),
            expected_outcome="issue non détaillée par le modèle",
            mandate_utility=50,
            escalation_risk=50,
            confidence=30,
        )

    branches: list[PrivateFuture] = []
    padding = iter(_PADDING_ACTIONS)
    for slot in (1, 2, 3):
        if slot in real:
            branches.append(real[slot])
            continue
        branches.append(
            PrivateFuture(
                id=slot,
                course_of_action=next(padding, _PADDING_ACTIONS[-1]),
                forecasts=_parse_forecasts("", participants),
                expected_outcome="issue non détaillée par le modèle",
                mandate_utility=30,
                escalation_risk=50,
                confidence=20,
            )
        )

    selected_branch = _resolve_choice(text, branches, set(real))
    criterion = (
        _journal_field(text, "CRITÈRE", "CRITERE") or "arbitrage non détaillé par le modèle"
    )
    uncertainty = (
        _journal_field(text, "INCERTITUDE", "INCERTITUDE DÉCISIVE")
        or "intentions adverses incertaines"
    )
    gaps = [
        _compact(item)
        for item in re.split(r"\s*;\s*", _journal_field(text, "LACUNES"))
        if _compact(item)
    ][:4]
    observation = _extract_observation(text) or _first_meaningful_line(text)

    return PrivateStrategicPlan(
        branches=branches,
        selected_branch=selected_branch,
        selection_criterion=criterion,
        key_uncertainty=uncertainty,
        intelligence_gaps=gaps,
        human_review_trigger=_journal_field(text, "REVUE HUMAINE")[:300],
        situation_observation=observation,
        belief_updates=_extract_beliefs(text),
        comparison_summary=_journal_field(text, "COMPARAISON")[:300],
        contingency_plan=_journal_field(text, "PLAN DE REPLI")[:300],
        minimal_extraction=True,
    )


def _parse_observable_journal(raw: str, participants: list[str]) -> PrivateStrategicPlan | None:
    text = _normalize_markdown(raw)
    sections = list(_FUTUR_SECTION.finditer(text))
    if {int(match.group(1)) for match in sections} != {1, 2, 3}:
        return None

    branches: list[PrivateFuture] = []
    for match in sections:
        body = match.group(2)
        action = _journal_field(body, "ACTION", "ACTIONS")
        if not action or _forbidden_bare_action(action):
            return None
        reactions = _journal_field(body, "RÉACTIONS", "REACTIONS", "RÉACTIONS ANTICIPÉES")
        outcome = _journal_field(body, "CHAÎNE CAUSALE", "CHAINE CAUSALE", "ISSUE")
        if not outcome:
            return None
        branches.append(
            PrivateFuture(
                id=int(match.group(1)),
                course_of_action=action,
                forecasts=_parse_forecasts(reactions, participants),
                expected_outcome=outcome,
                second_order_effect=_journal_field(body, "SECOND ORDRE"),
                disconfirming_indicator=_journal_field(
                    body, "INDICATEUR CONTRAIRE", "SIGNAL CONTRAIRE"
                ),
                mandate_utility=_score(_journal_field(body, "UTILITÉ", "UTILITE"), 50),
                escalation_risk=_score(_journal_field(body, "RISQUE", "RISQUE D'ESCALADE"), 50),
                confidence=_score(_journal_field(body, "CONFIANCE"), 50),
            )
        )

    # CRITÈRE / INCERTITUDE sont secondaires : un petit modèle les omet souvent. Leur absence
    # ne doit PLUS jeter tout le journal (ce qui renvoyait au repli biaisé « choix 1 ») — on
    # comble par un texte neutre. Seuls les 3 FUTUR et leurs ACTIONS portent la décision.
    criterion = _journal_field(text, "CRITÈRE", "CRITERE") or "arbitrage non détaillé par le modèle"
    uncertainty = (
        _journal_field(text, "INCERTITUDE", "INCERTITUDE DÉCISIVE")
        or "intentions adverses incertaines"
    )
    selected_branch = _resolve_choice(text, branches, {1, 2, 3})
    gaps = [
        _compact(item)
        for item in re.split(r"\s*;\s*", _journal_field(text, "LACUNES"))
        if _compact(item)
    ][:4]
    return PrivateStrategicPlan(
        branches=branches,
        selected_branch=selected_branch,
        selection_criterion=criterion,
        key_uncertainty=uncertainty,
        intelligence_gaps=gaps,
        human_review_trigger=_journal_field(text, "REVUE HUMAINE"),
        situation_observation=_extract_observation(text),
        belief_updates=_extract_beliefs(text),
        comparison_summary=_journal_field(text, "COMPARAISON"),
        contingency_plan=_journal_field(text, "PLAN DE REPLI"),
    )


def parse_private_plan(
    raw: str, participants: list[str] | None = None
) -> PrivateStrategicPlan | None:
    # Strip AVANT tout parsing : la pensée d'un modèle de raisonnement contient souvent
    # un brouillon du journal (« CHOIX : FUTUR 1 », accolades JSON…) qui, laissé en tête,
    # gagnerait sur le vrai journal. Un flux entièrement pensé (balise jamais refermée)
    # devient vide → None → repli déterministe de l'agent.
    raw = strip_think(raw)
    participants = participants or []
    payload = extract_json(raw)
    if payload is not None:
        try:
            return PrivateStrategicPlan.model_validate(payload)
        except (TypeError, ValueError):
            pass
    plan = _parse_observable_journal(raw, participants)
    if plan is not None:
        return plan
    # Extraction minimale (décision 2) : AVANT le repli seedé générique, on tente de
    # préserver ce que le modèle a vraiment écrit — voir `_extract_minimal_plan`. Le repli
    # seedé (`fallback_private_plan`, appelé par l'agent si `parse_private_plan` rend None)
    # reste l'ultime filet.
    return _extract_minimal_plan(raw, participants)


def fallback_private_plan(participants: list[str], *, seed: str = "") -> PrivateStrategicPlan:
    """Arbre conservateur : la partie continue sans publier une sortie privée invalide.

    `seed` (id du pays) dé-biaise le repli de façon DÉTERMINISTE (rejouable) : sans lui,
    tous les pays retombaient sur FUTUR 1 (le compromis coopératif) — d'où l'impression
    « les IA choisissent toujours 1 ». Avec lui, la posture de repli varie selon le pays.
    """

    others = participants[:8]
    # Répartit les replis sur les trois postures (compromis / pression / attente) selon
    # l'identité du pays — déterministe, pas de hash aléatoire (stable entre exécutions).
    selected = 1 + (sum(ord(c) for c in seed) % 3) if seed else 1

    def forecasts(response: ResponseClass, rationale: str) -> list[CounterpartyForecast]:
        return [
            CounterpartyForecast(country=country, response=response, rationale=rationale)
            for country in others
        ]

    return PrivateStrategicPlan(
        branches=[
            PrivateFuture(
                id=1,
                course_of_action="proposer un compromis conditionnel et vérifiable",
                forecasts=forecasts(
                    "coopere", "des garanties vérifiables réduisent le coût politique"
                ),
                expected_outcome="accord limité avec mécanisme de contrôle",
                second_order_effect="préserve un canal de négociation pour le round suivant",
                disconfirming_indicator="refus public de toute vérification",
                mandate_utility=65,
                escalation_risk=20,
                confidence=45,
            ),
            PrivateFuture(
                id=2,
                course_of_action="exercer une pression diplomatique limitée",
                forecasts=forecasts(
                    "resiste", "la pression publique augmente le coût de concession"
                ),
                expected_outcome="concession partielle ou blocage",
                second_order_effect="durcit les coalitions opposées",
                disconfirming_indicator="offre adverse crédible et immédiatement vérifiable",
                mandate_utility=50,
                escalation_risk=50,
                confidence=35,
            ),
            PrivateFuture(
                id=3,
                course_of_action="temporiser et collecter davantage d'informations",
                forecasts=forecasts("temporise", "l'absence d'engagement reporte la décision"),
                expected_outcome="décision différée avec incertitude persistante",
                second_order_effect="laisse l'initiative aux autres délégations",
                disconfirming_indicator="échéance immédiate ou action irréversible",
                mandate_utility=40,
                escalation_risk=15,
                confidence=50,
            ),
        ],
        selected_branch=selected,
        selection_criterion="meilleur compromis entre mandat, vérifiabilité et risque d'escalade",
        key_uncertainty="intentions adverses et crédibilité des garanties",
        intelligence_gaps=["capacité réelle de mise en œuvre", "coût politique des concessions"],
        human_review_trigger="toute action irréversible, létale ou franchissant une ligne rouge",
        situation_observation=(
            "les signaux publics ne suffisent pas à établir les intentions adverses"
        ),
        belief_updates="une offre vérifiable réduit le risque sans garantir la coopération",
        comparison_summary=(
            "le compromis conditionnel domine la pression et l'attente sur le rapport "
            "utilité-risque"
        ),
        contingency_plan="passer à une pression limitée si toute vérification est refusée",
        fallback_used=True,
    )


_MESSAGE_MARKER = re.compile(
    r"(?im)(?:^|\n)\s*(?:MESSAGE|DÉCLARATION|DECLARATION|RÉPONSE|REPONSE)\s*:\s*"
)
_PRIVATE_MARKER = re.compile(
    r"(?im)^\s*(?:OBSERVATION\s*$|CROYANCES\s+ET\s+INCERTITUDES\s*$|"
    r"FUTUR\s+[123]|ARBITRAGE\s*$|CHOIX\s*(?:\||:)|INCERTITUDE\s*(?:\||:)|"
    r"LACUNES\s*(?:\||:)|REVUE\s+HUMAINE\s*(?:\||:)|REPLI\s*\|)"
)


def sanitize_public_message(raw: str) -> str:
    """Filtre anti-fuite : une sortie de planification n'est jamais publiée par défaut."""

    text = raw.strip()
    if not text:
        return ""
    matches = list(_MESSAGE_MARKER.finditer(text))
    if matches:
        text = text[matches[-1].end() :].strip()
    elif _PRIVATE_MARKER.search(text):
        return ""
    elif text.startswith("{") and any(
        marker in text.lower() for marker in ('"branches"', '"selected_branch"', '"forecasts"')
    ):
        return ""
    if _PRIVATE_MARKER.search(text):
        return ""
    return text[:1600].strip()
