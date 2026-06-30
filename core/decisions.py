"""Décisions et messages produits par les agents."""

from __future__ import annotations

from pydantic import BaseModel, Field

from simulation.action_space import ActionType


class AgentDecision(BaseModel):
    """Décision d'un pays pour un round donné."""

    country: str
    round_id: int
    action: ActionType
    target: str | None = None
    intensity: float = Field(0.5, ge=0.0, le=1.0)
    public_statement: str = ""
    proposed_alliances: list[str] = Field(default_factory=list)
    risk_assessment: float = Field(0.5, ge=0.0, le=1.0)
    reasoning: str = ""


class DiplomaticMessage(BaseModel):
    """Message diplomatique bilatéral (utilisé en Phase 2)."""

    sender: str
    recipient: str
    content: str
    public: bool = True
    round_id: int
