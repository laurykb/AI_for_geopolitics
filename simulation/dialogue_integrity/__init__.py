"""`dialogue_integrity` — garantir et **prouver** que les SI échangent vraiment (pas « prompter
au hasard »). Cadre : positive signaling + positive listening (Lowe et al., AAMAS 2019).

Voir `docs/spec_dialogue_integrity.md`. Modules :
- `message`  : acte de langage FIPA (performative + `in_reply_to`) + décodage contraint (§1).
- `metrics`  : mesures pures CPU — self-BLEU, responsivité, pertinence, dégénérescence (§2).
"""

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

__all__ = [
    "OPENING_PERFORMATIVES",
    "REPLY_PERFORMATIVES",
    "DegenerationScore",
    "DraftSpeechAct",
    "Performative",
    "SpeechAct",
    "degeneration",
    "generate_speech_act",
    "parse_speech_act",
    "relevance",
    "responsiveness",
    "self_bleu",
    "speech_act_schema",
]
