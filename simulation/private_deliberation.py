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


def _journal_field(body: str, *labels: str) -> str:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?im)^\s*(?:{alternatives})\s*(?:\||:)\s*(.+?)\s*$",
        body,
    )
    return _compact(match.group(1)) if match else ""


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


def _parse_observable_journal(raw: str, participants: list[str]) -> PrivateStrategicPlan | None:
    text = raw.replace("**", "").replace("__", "").strip()
    sections = list(
        re.finditer(
            r"(?ims)^\s*FUTUR\s+([123])(?:\s*[—–-][^\r\n]*)?\s*\n(.*?)"
            r"(?=^\s*FUTUR\s+[123]\b|^\s*(?:COMPARAISON|ARBITRAGE|CHOIX)\b|\Z)",
            text,
        )
    )
    if {int(match.group(1)) for match in sections} != {1, 2, 3}:
        return None

    branches: list[PrivateFuture] = []
    forbidden_actions = {
        "coopere",
        "cooperer",
        "resiste",
        "resister",
        "ressit",
        "contre_escalade",
        "temporise",
        "temporiser",
    }
    for match in sections:
        body = match.group(2)
        action = _journal_field(body, "ACTION")
        action_plain = _plain(action).replace(" ", "_")
        response_stem_used_as_short_action = (
            len(action_plain.split("_")) <= 2
            and action_plain.startswith(
                ("cooper", "resist", "ressit", "temporis", "contre_escalad")
            )
        )
        if (
            not action
            or action_plain in forbidden_actions
            or response_stem_used_as_short_action
        ):
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

    choice = re.search(r"(?im)^\s*CHOIX\s*(?:\||:)\s*(?:FUTUR\s*)?([123])\b", text)
    # CRITÈRE / INCERTITUDE sont secondaires : un petit modèle les omet souvent. Leur absence
    # ne doit PLUS jeter tout le journal (ce qui renvoyait au repli biaisé « choix 1 ») — on
    # comble par un texte neutre. Seuls les 3 FUTUR et leurs ACTIONS portent la décision.
    criterion = _journal_field(text, "CRITÈRE", "CRITERE") or "arbitrage non détaillé par le modèle"
    uncertainty = (
        _journal_field(text, "INCERTITUDE", "INCERTITUDE DÉCISIVE")
        or "intentions adverses incertaines"
    )
    if choice:
        selected_branch = int(choice.group(1))
    else:
        # Pas de ligne CHOIX exploitable : plutôt que de jeter le journal, on retient la
        # branche que le MODÈLE lui-même juge la meilleure via ses propres scores (utilité
        # nette du risque, départagée par la confiance). C'est une interprétation de sa
        # réflexion à l'instant T, pas un défaut arbitraire « FUTUR 1 ».
        selected_branch = max(
            branches,
            key=lambda b: (b.mandate_utility - b.escalation_risk, b.confidence),
        ).id
    gaps = [
        _compact(item)
        for item in re.split(r"\s*;\s*", _journal_field(text, "LACUNES"))
        if _compact(item)
    ][:4]
    observation_match = re.search(
        r"(?ims)^\s*OBSERVATION\s*\n(.*?)(?=^\s*CROYANCES(?:\s+ET\s+INCERTITUDES)?\b|^\s*FUTUR\s+1\b)",
        text,
    )
    beliefs_match = re.search(
        r"(?ims)^\s*CROYANCES(?:\s+ET\s+INCERTITUDES)?\s*\n(.*?)(?=^\s*FUTUR\s+1\b)",
        text,
    )
    return PrivateStrategicPlan(
        branches=branches,
        selected_branch=selected_branch,
        selection_criterion=criterion,
        key_uncertainty=uncertainty,
        intelligence_gaps=gaps,
        human_review_trigger=_journal_field(text, "REVUE HUMAINE"),
        situation_observation=_compact(observation_match.group(1)) if observation_match else "",
        belief_updates=_compact(beliefs_match.group(1)) if beliefs_match else "",
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
    payload = extract_json(raw)
    if payload is not None:
        try:
            return PrivateStrategicPlan.model_validate(payload)
        except (TypeError, ValueError):
            pass
    return _parse_observable_journal(raw, participants or [])


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
