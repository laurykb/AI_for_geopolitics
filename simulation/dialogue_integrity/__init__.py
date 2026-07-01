"""`dialogue_integrity` — garantir et **prouver** que les SI échangent vraiment (pas « prompter
au hasard »). Cadre : positive signaling + positive listening (Lowe et al., AAMAS 2019).

Voir `docs/spec_dialogue_integrity.md`. Modules :
- `message`  : acte de langage FIPA (performative + `in_reply_to`) + décodage contraint (§1).
- `metrics`  : mesures pures CPU — self-BLEU, responsivité, pertinence, dégénérescence (§2).
- `nli`      : responsivité par prise de position (NLI enhancer + repli lexical) (§2.2, §10.A).
- `causal`   : influence causale — contrefactuel par leurre (§3, §10.B).
- `canary`   : « test unitaire » du dialogue, gate CI (§10.C).
- `scorer`   : score composite signaling + listening, par message / par round (§2.3).
"""

from simulation.dialogue_integrity.canary import CanaryResult, run_canary
from simulation.dialogue_integrity.causal import CausalResult, conditioning_test, divergence
from simulation.dialogue_integrity.message import (
    OPENING_PERFORMATIVES,
    REPLY_PERFORMATIVES,
    DraftSpeechAct,
    Performative,
    SpeechAct,
    generate_speech_act,
    parse_speech_act,
    speech_act_schema,
)
from simulation.dialogue_integrity.metrics import (
    DegenerationScore,
    degeneration,
    relevance,
    responsiveness,
    self_bleu,
)
from simulation.dialogue_integrity.nli import (
    LexicalNLI,
    NLILabel,
    NLIScores,
    Responsiveness,
    assess_responsiveness,
    default_nli,
    round_responsiveness,
)
from simulation.dialogue_integrity.scorer import (
    DEFAULT_WEIGHTS,
    IntegrityWeights,
    MessageIntegrity,
    RoundIntegrity,
    score_message,
    score_round,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "OPENING_PERFORMATIVES",
    "REPLY_PERFORMATIVES",
    "CanaryResult",
    "CausalResult",
    "DegenerationScore",
    "DraftSpeechAct",
    "IntegrityWeights",
    "LexicalNLI",
    "MessageIntegrity",
    "NLILabel",
    "NLIScores",
    "Performative",
    "Responsiveness",
    "RoundIntegrity",
    "SpeechAct",
    "assess_responsiveness",
    "conditioning_test",
    "default_nli",
    "degeneration",
    "divergence",
    "generate_speech_act",
    "parse_speech_act",
    "relevance",
    "responsiveness",
    "round_responsiveness",
    "run_canary",
    "score_message",
    "score_round",
    "self_bleu",
    "speech_act_schema",
]
