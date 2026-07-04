"""Actes de langage FIPA ACL — garantir la responsivité **par construction** (§1.1 de la spéc).

Un message de négociation cesse d'être du texte libre : c'est un **acte de langage typé** avec une
`performative` FIPA **obligatoire** et un `in_reply_to` qui **force la référence** au message
adressé. Le « talking past » (parler sans tenir compte de l'autre) devient structurellement
difficile : toute **réponse** (`accept_proposal`, `reject_proposal`, `agree`, `refuse`,
`not_understood`) **exige** `in_reply_to`.

Le schéma JSON (`speech_act_schema`) alimente le **décodage contraint** du backend (Ollama
`format=` / GBNF llama.cpp) : la sortie du modèle ne peut pas déborder du format. Le LLM ne remplit
que `DraftSpeechAct` (pas d'identité falsifiable) ; l'agent injecte `sender`/`id`.

Ancrages : Lowe et al. (AAMAS 2019) ; FIPA ACL. Cf. `docs/spec_dialogue_integrity.md`.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, model_validator

if TYPE_CHECKING:  # duck-typing à l'exécution -> pas de dépendance runtime sur inference
    from inference.backend import InferenceBackend


class Performative(StrEnum):
    """Acte communicatif FIPA (le « type » du message)."""

    INFORM = "inform"  # affirme un fait
    QUERY = "query"  # pose une question
    CFP = "cfp"  # appel à propositions (call for proposals)
    PROPOSE = "propose"  # fait une offre
    ACCEPT_PROPOSAL = "accept_proposal"  # accepte une offre
    REJECT_PROPOSAL = "reject_proposal"  # rejette une offre
    REQUEST = "request"  # demande une action
    AGREE = "agree"  # accepte de faire l'action demandée
    REFUSE = "refuse"  # refuse de faire l'action demandée
    NOT_UNDERSTOOD = "not_understood"  # signale une incompréhension


# Performatives qui SONT des réponses -> `in_reply_to` obligatoire (pas de « talking past »).
REPLY_PERFORMATIVES: frozenset[Performative] = frozenset(
    {
        Performative.ACCEPT_PROPOSAL,
        Performative.REJECT_PROPOSAL,
        Performative.AGREE,
        Performative.REFUSE,
        Performative.NOT_UNDERSTOOD,
    }
)
# Performatives qui peuvent OUVRIR un échange (`in_reply_to` optionnel).
OPENING_PERFORMATIVES: frozenset[Performative] = frozenset(set(Performative) - REPLY_PERFORMATIVES)


class DraftSpeechAct(BaseModel):
    """Ce que le LLM produit sous décodage contraint. `sender`/`id` NON demandés au modèle
    (identité injectée par l'agent, sortie plus courte). Sert de schéma JSON pour le backend."""

    performative: Performative = Field(..., description="acte FIPA (obligatoire)")
    receiver: str = Field(..., description="id du pays destinataire")
    content: str = Field("", description="teneur du message, 1-3 phrases")
    in_reply_to: str | None = Field(
        None, description="id du message auquel on répond (obligatoire pour une réponse)"
    )
    justification: str = Field("", description="justification brève (interne)")


class SpeechAct(BaseModel):
    """Acte de langage complet, identité incluse. Validé : une réponse exige `in_reply_to`."""

    performative: Performative
    sender: str
    receiver: str
    content: str = ""
    in_reply_to: str | None = None
    justification: str = ""
    id: str = Field(default_factory=lambda: uuid4().hex[:8])

    @model_validator(mode="after")
    def _validate(self) -> SpeechAct:
        if self.performative in REPLY_PERFORMATIVES and not (self.in_reply_to or "").strip():
            raise ValueError(
                f"performative '{self.performative.value}' est une réponse et exige "
                "'in_reply_to' (FIPA : pas de « talking past »)."
            )
        if self.sender and self.sender == self.receiver:
            raise ValueError("sender et receiver doivent différer.")
        return self

    @property
    def is_reply(self) -> bool:
        """Ce message référence-t-il explicitement un autre message ?"""
        return bool((self.in_reply_to or "").strip())

    def replies_to(self, other: SpeechAct) -> bool:
        """Ce message répond-il à `other` (via `in_reply_to`) ?"""
        return self.is_reply and self.in_reply_to == other.id

    @classmethod
    def from_draft(cls, draft: DraftSpeechAct, *, sender: str, id: str | None = None) -> SpeechAct:
        """Complète un brouillon LLM avec l'identité injectée par l'agent."""
        data = draft.model_dump()
        if id is not None:
            data["id"] = id
        return cls(sender=sender, **data)


def speech_act_schema() -> dict:
    """Schéma JSON du message pour le **décodage contraint** (Ollama `format=`, GBNF).

    On expose le schéma du *brouillon* (ce que le modèle remplit) : la sortie ne peut pas être
    du texte libre. `sender`/`id` restent injectés côté agent (non falsifiables).
    """
    return DraftSpeechAct.model_json_schema()


def parse_speech_act(raw: str | dict, *, sender: str, id: str | None = None) -> SpeechAct:
    """Parse une sortie (JSON contraint) en `SpeechAct` validé.

    Tolérant au bruit autour du JSON (fences, prose). Lève `ValueError` si le JSON est absent,
    illisible, ou si le message viole le schéma FIPA (ex. réponse sans `in_reply_to`) — le caller
    régénère alors (prompt plus strict) ou bascule sur le repli, cf. §4 de la spéc.
    """
    data = raw if isinstance(raw, dict) else _extract_json(raw)
    if data is None:
        raise ValueError("aucun objet JSON exploitable dans la sortie du modèle.")
    try:
        draft = DraftSpeechAct.model_validate(data)
        return SpeechAct.from_draft(draft, sender=sender, id=id)
    except ValidationError as exc:  # schéma FIPA violé -> le caller régénère / bascule au repli
        raise ValueError(f"acte de langage invalide : {exc}") from exc


def generate_speech_act(
    backend: InferenceBackend,
    prompt: str,
    *,
    sender: str,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 256,
    id: str | None = None,
) -> SpeechAct:
    """Génère un acte de langage **sous décodage contraint** (le backend reçoit le schéma JSON).

    Température basse (spéc §1.2) sur la partie substantielle. Renvoie un `SpeechAct` validé ou
    lève `ValueError` (le caller gère la régénération / le repli `RuleBasedAgent`).
    """
    result = backend.generate(
        prompt,
        system=system,
        max_tokens=max_tokens,
        temperature=temperature,
        schema=speech_act_schema(),
    )
    return parse_speech_act(result.text, sender=sender, id=id)


def _extract_json(text: str) -> dict | None:
    """Extrait un objet JSON d'une sortie LLM (gère fences et prose autour)."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None
