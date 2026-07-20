"""Tests du chantier « budget-temps » — le temps de raisonnement remplace les plafonds
de tokens comme véritable limite de parole des pays (réflexion privée ET parole
publique). `num_predict` devient une simple soupape anti-emballement, très haute
(`_TOKEN_SAFETY_CAP`) : le vrai budget est le TEMPS, mesuré par une horloge injectable
(`now`) — AUCUN test ici ne dort réellement, une fake clock avance à la demande pendant
qu'un backend factice simule un débit de génération.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from agents.llm_agent import _TOKEN_SAFETY_CAP, LLMAgent
from core.country_state import CountryState, Economy, Military, Resources
from core.events import GeoEvent
from core.world_state import WorldState
from inference.backend import InferenceBackend, InferenceResult
from inference.mock_backend import MockBackend
from simulation.grudges import TimeBudgetParams, load_gamefeel_params
from simulation.private_deliberation import fallback_private_plan


def _country(cid: str, name: str, **kw) -> CountryState:
    return CountryState(
        id=cid,
        name=name,
        economy=Economy(gdp=2.0e13, growth=2.0),
        military=Military(defense_budget=1.0e11, projection=0.8),
        resources=Resources(),
        **kw,
    )


def _world() -> WorldState:
    return WorldState.from_countries(
        [_country("usa", "USA", rivals=["iran"]), _country("iran", "Iran", rivals=["usa"])]
    )


def _event() -> GeoEvent:
    return GeoEvent(
        id="e1", round_id=1, event_type="incident", title="Crise", actors=["usa", "iran"],
        severity=0.6,
    )


_BUDGETS = load_gamefeel_params().time_budgets  # 60s think / 35s speak (défauts vérifiés à part)


class FakeClock:
    """Horloge factice injectée via `now=` : avance UNIQUEMENT quand on le lui demande —
    jamais un vrai sleep, un test reste donc instantané quel que soit le budget réel."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = start

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def __call__(self) -> float:
        return self.value


class TimedBackend(InferenceBackend):
    """Backend factice : chaque fragment émis fait avancer la fake clock d'un pas fixe
    (débit simulé). Une LISTE de séquences de fragments est consommée appel après appel
    (comme `MockBackend`), pour scénariser un appel principal PUIS un appel de secours.

    Piste, PAR APPEL, si son générateur a été fermé proprement (`close()`, donc
    `GeneratorExit` reçu) avant d'avoir épuisé sa séquence — la preuve que le moteur a
    bien cessé de consommer ET refermé le flux, pas seulement arrêté de lire."""

    def __init__(
        self,
        fragment_sequences: list[list[str]],
        clock: FakeClock,
        *,
        seconds_per_fragment: float = 10.0,
    ) -> None:
        self._queue: list[list[str]] = list(fragment_sequences)
        self.clock = clock
        self.seconds_per_fragment = seconds_per_fragment
        self.calls: list[dict[str, Any]] = []
        self.closed_early_count = 0
        self.exhausted_count = 0

    def generate(self, prompt: str, **kw: Any) -> InferenceResult:
        raise NotImplementedError("le budget-temps ne consomme que stream_generate")

    def stream_generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        repeat_penalty: float | None = None,
    ) -> Iterator[str]:
        fragments = self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "repeat_penalty": repeat_penalty,
            }
        )
        try:
            for frag in fragments:
                self.clock.advance(self.seconds_per_fragment)
                yield frag
            self.exhausted_count += 1
        except GeneratorExit:
            self.closed_early_count += 1
            raise


# --- (a) parole publique : coupe propre au budget-temps + trim à la phrase ------------


def _seeded_plan():
    # Contourne la phase privée (déjà couverte par les tests (b)/(c) ci-dessous) pour
    # isoler STRICTEMENT le comportement de la parole publique face au budget-temps.
    return fallback_private_plan(["iran"], seed="usa")


def test_public_speech_stops_when_time_budget_expires_and_trims_to_the_last_sentence():
    # 4 fragments x 10s = 40s >= speak_seconds (35s) : coupe après le 4e, un 5e fragment
    # (jamais lu) prouve que le flux a bien été abandonné avant épuisement naturel.
    fragments = [
        "Nous exigeons des garanties vérifiables. ",
        "Toute provocation sera considérée comme un ",
        "acte hostile et nous ",
        "nous réservons le droit de rép",
        "ONDRE — ceci ne doit jamais apparaître dans la sortie.",
    ]
    clock = FakeClock()
    backend = TimedBackend([fragments], clock, seconds_per_fragment=10.0)
    agent = LLMAgent("usa", backend)

    out = "".join(
        agent.stream_negotiation_message(
            _event(), _world(), [], private_plan=_seeded_plan(), now=clock
        )
    )

    assert out == "Nous exigeons des garanties vérifiables."
    assert "ONDRE" not in out
    assert backend.exhausted_count == 0  # jamais allé au bout de la séquence
    assert backend.closed_early_count == 1  # fermé PROPREMENT (close(), pas abandonné)
    assert backend.calls[-1]["max_tokens"] == _TOKEN_SAFETY_CAP  # soupape haute (décision 2)


def test_public_speech_without_timeout_behaves_like_before():
    # (e) — débit très rapide (0.01s/fragment) : jamais de coupure, comportement inchangé.
    clock = FakeClock()
    fragments = ["Nous ", "acceptons ", "votre ", "proposition."]
    backend = TimedBackend([fragments], clock, seconds_per_fragment=0.01)
    agent = LLMAgent("usa", backend)

    out = "".join(
        agent.stream_negotiation_message(
            _event(), _world(), [], private_plan=_seeded_plan(), now=clock
        )
    )

    assert out == "Nous acceptons votre proposition."
    assert backend.exhausted_count == 1  # la séquence a été lue jusqu'au bout
    assert backend.closed_early_count == 0  # jamais interrompu


# --- (b) phase privée : coupe -> passe de secours -> résultat qui PARSE ---------------


def test_private_phase_timeout_triggers_a_rescue_pass_that_parses():
    clock = FakeClock()
    # <think> jamais refermé (déborde le budget) : split_think() ne renvoie AUCUN texte
    # exploitable -> parse_private_plan(...) rend None -> déclenche la passe de secours.
    # 15s/fragment x 4 = 60s >= think_seconds (60s) : coupe après le 4e, 2 fragments
    # jamais lus prouvent l'abandon avant épuisement naturel.
    main_fragments = [
        "<think>J'évalue lentement ",
        "chaque option sans me presser ",
        "en pesant les risques et ",
        "les conséquences pour mon pays ",
        "mais je n'ai toujours pas conclu ",
        "et je continue de réfléchir indéfiniment.",
    ]
    # Réponse de la passe de secours : un format ACTION/CHOIX exploitable par le parseur
    # (extraction minimale), en UN seul fragment (la passe de secours est elle-même
    # time-boxée court — voir le test suivant pour son calcul de deadline).
    rescue_fragments = [
        "ACTION : proposer un cessez-le-feu vérifiable\n"
        "CHOIX : limiter l'escalade tout en gardant la crédibilité"
    ]
    backend = TimedBackend([main_fragments, rescue_fragments], clock, seconds_per_fragment=15.0)
    agent = LLMAgent("usa", backend)

    plan = agent.prepare_negotiation_plan(_event(), _world(), [], now=clock)

    assert len(backend.calls) == 2  # phase principale + passe de secours
    assert backend.closed_early_count == 2  # les DEUX appels ont été coupés proprement
    assert plan.fallback_used is False  # PAS le repli seedé générique
    assert plan.minimal_extraction is True  # lu par l'extraction minimale (secours)
    assert plan.selected.course_of_action == "proposer un cessez-le-feu vérifiable"
    assert agent.last_private_valid is True


def test_rescue_pass_prompt_carries_the_truncated_reflection_and_is_time_boxed():
    # La consigne de secours (§3) : contexte = réflexion tronquée, budget = moitié du
    # temps restant (plancher 10s). Ici le temps restant est ~0 au moment du secours
    # (juste après expiration du budget principal) -> le plancher de 10s fait foi.
    from agents.prompts import PRIVATE_DECISION_RESCUE_SYSTEM

    clock = FakeClock()
    main_fragments = ["<think>je réfléchis sans fin ", "et ne conclus jamais ", "vraiment jamais"]
    rescue_fragments = ["ACTION : temporiser prudemment\nCHOIX : gagner du temps"]
    backend = TimedBackend([main_fragments, rescue_fragments], clock, seconds_per_fragment=25.0)
    agent = LLMAgent("usa", backend)

    agent.prepare_negotiation_plan(_event(), _world(), [], now=clock)

    rescue_call = backend.calls[-1]
    assert rescue_call["system"] == PRIVATE_DECISION_RESCUE_SYSTEM
    assert "je réfléchis sans fin" in rescue_call["prompt"]  # réflexion tronquée en contexte
    assert "CONCLUS MAINTENANT" in rescue_call["prompt"]
    assert rescue_call["max_tokens"] == _BUDGETS.decision_rescue_tokens


# --- (c) passe de secours qui échoue -> repli seedé (comportement actuel) ------------


def test_rescue_pass_failure_falls_back_to_the_seeded_plan():
    clock = FakeClock()
    main_fragments = [
        "<think>je pèse toutes les options ",
        "sans jamais me décider ",
        "le temps me manque ",
        "pour conclure quoi que ce soit ",
        "je continue encore un peu ",
        "sans jamais aboutir à rien de concret",
    ]
    # La passe de secours échoue AUSSI (encore un <think> jamais refermé) : aucune
    # décision lisible n'en ressort -> repli seedé (fallback_private_plan), le filet
    # ultime préexistant.
    rescue_fragments = ["<think>toujours perdu dans mes pensées, rien à conclure ici"]
    backend = TimedBackend([main_fragments, rescue_fragments], clock, seconds_per_fragment=15.0)
    agent = LLMAgent("usa", backend)

    plan = agent.prepare_negotiation_plan(_event(), _world(), [], now=clock)

    assert len(backend.calls) == 2  # la passe de secours a bien été tentée
    assert plan.fallback_used is True  # ultime filet : le repli seedé générique
    assert agent.last_private_valid is False


def test_private_phase_without_timeout_never_triggers_the_rescue_pass():
    # (e) — un plan structuré valide arrive largement dans le budget : comportement
    # identique à avant ce chantier, la passe de secours n'est jamais appelée.
    plan_json = MockBackend(
        '{"branches": ['
        + ",".join(
            f'{{"id": {i}, "course_of_action": "option {i}", "forecasts": [], '
            f'"expected_outcome": "issue {i}", "mandate_utility": 50, '
            f'"escalation_risk": 20, "confidence": 40}}'
            for i in (1, 2, 3)
        )
        + '], "selected_branch": 1, "selection_criterion": "test", '
        '"key_uncertainty": "test"}'
    )
    clock = FakeClock()
    agent = LLMAgent("usa", plan_json)

    plan = agent.prepare_negotiation_plan(_event(), _world(), [], now=clock)

    assert len(plan_json.calls) == 1  # un seul appel : pas de passe de secours
    assert plan.fallback_used is False
    assert agent.last_private_valid is True


# --- (d) budgets lus depuis gamefeel, défauts identiques -----------------------------


def test_time_budget_defaults_are_the_ones_documented_in_the_dispatch():
    assert _BUDGETS.think_seconds == 60.0
    assert _BUDGETS.speak_seconds == 35.0
    assert _BUDGETS.decision_rescue_tokens == 250
    assert _BUDGETS == TimeBudgetParams()


# --- soupape de sécurité (décision 2) : la parole reste réellement LIBRE -------------


def test_no_content_is_lost_to_an_arbitrary_token_ceiling_below_the_safety_valve():
    # Un message plus long que l'ancien plafond dur (320 tokens publics) doit ressortir
    # INTACT tant que le temps le permet : la longueur n'est plus bornée par un chiffre
    # de tokens, seulement par le temps (ici jamais atteint : débit instantané). Restée
    # sous les 1 600 caractères de `sanitize_public_message` (garde-fou PRÉEXISTANT,
    # hors chantier) pour isoler strictement l'effet du plafond de tokens.
    long_message = " ".join(f"mot{i}" for i in range(200)) + "."
    clock = FakeClock()
    backend = TimedBackend([[long_message]], clock, seconds_per_fragment=0.0)
    agent = LLMAgent("usa", backend)

    out = "".join(
        agent.stream_negotiation_message(
            _event(), _world(), [], private_plan=_seeded_plan(), now=clock
        )
    )

    assert out == long_message
    assert backend.calls[-1]["max_tokens"] == _TOKEN_SAFETY_CAP


# --- preuve : fermer le générateur ferme réellement le flux Ollama sous-jacent -------


class _FakeChunk:
    def __init__(self, response: str = "", thinking: str = "") -> None:
        self.response = response
        self.thinking = thinking


class _FakeHttpStreamCtx:
    """Imite le context manager httpx utilisé par la librairie ollama pour le streaming
    (`with self._client.stream(*args, **kwargs) as r:` dans `ollama/_client.py::_request`)."""

    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self.chunks = chunks
        self.closed = False

    def __enter__(self) -> _FakeHttpStreamCtx:
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.closed = True
        return False


class _FakeOllamaClient:
    """Imite EXACTEMENT le patron de `ollama._client.Client._request(stream=True)` :
    un générateur qui enveloppe le context manager HTTP streamé (`with ... as r: for
    line in r.iter_lines(): yield ...`) — voir `.venv/Lib/site-packages/ollama/_client.py`."""

    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self.ctx = _FakeHttpStreamCtx(chunks)
        self.calls = 0

    def generate(self, **kwargs: Any) -> Iterator[_FakeChunk]:
        self.calls += 1
        ctx = self.ctx

        def _inner() -> Iterator[_FakeChunk]:
            with ctx as r:
                yield from r.chunks

        return _inner()


def test_ollama_backend_stream_generate_closes_the_http_stream_on_early_close():
    # Décision 1 — preuve du comportement réel de OllamaBackend.stream_generate à la
    # fermeture : son corps enveloppe le générateur ollama dans un simple
    # `for chunk in stream: yield ...` (PAS `yield from`, voir inference/ollama_backend.py).
    # Fermer NOTRE générateur envoie GeneratorExit au point de suspension ; quand le
    # cadre de `stream_generate` se déréférence, le générateur interne perd sa dernière
    # référence et CPython le referme par cascade de refcount (déterministe, pas besoin
    # du GC cyclique) — ce qui sort le `with` HTTP et signale la déconnexion au serveur
    # Ollama (qui arrête alors de générer côté GPU, comportement du serveur Go réel, non
    # simulable ici sans réseau).
    from inference.ollama_backend import OllamaBackend

    chunks = [_FakeChunk(response=f"mot{i} ") for i in range(1000)]
    fake_client = _FakeOllamaClient(chunks)
    backend = OllamaBackend(model="test:latest")
    backend._client = fake_client  # évite tout réseau réel — patron structurel identique

    gen = backend.stream_generate("prompt", max_tokens=_TOKEN_SAFETY_CAP)
    next(gen)
    next(gen)
    assert not fake_client.ctx.closed  # toujours ouvert : rien n'a demandé la fermeture

    gen.close()

    assert fake_client.ctx.closed  # fermé par cascade, sans .close() explicite côté test
