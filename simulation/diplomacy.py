"""Moteur de diplomatie déterministe : propositions -> accept/refuse -> pactes (Phase 2).

Les propositions sont agentiques (un pays choisit `form_coalition`/`support` ou remplit
`proposed_alliances`). La résolution accept/refuse est déterministe et explicable, dans
l'esprit de `ConsequenceEngine`/`RiskEngine`. La policy d'acceptation est isolée dans
`_accepts`, remplaçable plus tard par un répondeur LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.decisions import AgentDecision, DiplomaticMessage
from core.world_state import WorldState
from simulation.action_space import ActionType
from simulation.grudges import GrudgeBook, load_gamefeel_params

# Actions valant une proposition d'alliance bilatérale.
_PROPOSAL_ACTIONS = frozenset({ActionType.FORM_COALITION, ActionType.SUPPORT})
# Seuil d'acceptation (score >= seuil -> accepte).
_ACCEPT_THRESHOLD = 0.5
# Rapprochement de tension à la formation d'un pacte.
_PACT_TENSION_DROP = 0.10


def pact_id(a: str, b: str) -> str:
    """Identifiant d'alliance symétrique pour une paire de pays (ordre stable)."""
    x, y = sorted((a, b))
    return f"pact:{x}+{y}"


# Tension d'ouverture d'une rivalité déclarée ; réciproque, la ligne de faille est plus vive.
_RIVAL_TENSION = 0.35
_MUTUAL_RIVAL_TENSION = 0.60


def seed_rival_tensions(world: WorldState) -> None:
    """Initialise les tensions d'un monde neuf depuis la matrice `rivals` du casting.

    Sans cela, toutes les paires ouvrent à 0 et la sélection des pays n'a aucun effet
    sur la dynamique (engagement, soutien au communiqué, événements du GM). Une rivalité
    déclarée par l'un des deux ouvre la partie tendue (0,35) ; réciproque, davantage
    (0,60 — russie↔ukraine, usa↔iran). Ne touche que les pays présents et n'écrase
    jamais une tension déjà posée (monde restauré d'un snapshot).
    """
    for a, country in world.countries.items():
        for b in country.rivals:
            if b == a or b not in world.countries or world.get_tension(a, b) > 0.0:
                continue
            mutual = a in world.countries[b].rivals
            world.adjust_tension(a, b, _MUTUAL_RIVAL_TENSION if mutual else _RIVAL_TENSION)


class Proposal(BaseModel):
    """Offre bilatérale d'un pays vers un autre pour un round donné."""

    sender: str
    recipient: str
    round_id: int


class DiplomacyOutcome(BaseModel):
    """Résultat diplomatique d'un round : messages, pactes formés, résumé public."""

    messages: list[DiplomaticMessage] = Field(default_factory=list)
    pacts_formed: list[tuple[str, str]] = Field(default_factory=list)
    summary: str = "Aucune proposition"


class DiplomacyEngine:
    """Résout les propositions d'alliance issues des décisions d'un round."""

    def resolve(
        self,
        world: WorldState,
        decisions: list[AgentDecision],
        round_id: int,
        grudges: GrudgeBook | None = None,
    ) -> DiplomacyOutcome:
        outcome = DiplomacyOutcome()
        accepted: list[str] = []
        refused: list[str] = []

        for prop in self._proposals(decisions, world, round_id):
            sender = world.countries[prop.sender]
            recipient = world.countries[prop.recipient]
            outcome.messages.append(
                DiplomaticMessage(
                    sender=prop.sender,
                    recipient=prop.recipient,
                    round_id=round_id,
                    content=f"{sender.name} propose une coalition à {recipient.name}.",
                )
            )

            accepts, reason = self._accepts(prop.sender, prop.recipient, world, grudges)
            if accepts:
                if self._form_pact(world, prop.sender, prop.recipient):
                    outcome.pacts_formed.append(tuple(sorted((prop.sender, prop.recipient))))
                accepted.append(f"{prop.sender}+{prop.recipient}")
                content = f"{recipient.name} accepte ({reason})."
            else:
                refused.append(f"{prop.recipient}←{prop.sender}")
                content = f"{recipient.name} refuse ({reason})."
            outcome.messages.append(
                DiplomaticMessage(
                    sender=prop.recipient,
                    recipient=prop.sender,
                    round_id=round_id,
                    content=content,
                )
            )

        outcome.summary = self._summary(accepted, refused)
        return outcome

    def _proposals(
        self, decisions: list[AgentDecision], world: WorldState, round_id: int
    ) -> list[Proposal]:
        """Dérive les propositions des décisions (action coopérative + proposed_alliances)."""
        seen: set[tuple[str, str]] = set()
        proposals: list[Proposal] = []
        for d in decisions:
            recipients: list[str] = []
            if d.action in _PROPOSAL_ACTIONS and d.target:
                recipients.append(d.target)
            recipients.extend(d.proposed_alliances)
            for target in recipients:
                if target == d.country or target not in world.countries:
                    continue
                key = (d.country, target)
                if key in seen:
                    continue
                seen.add(key)
                proposals.append(Proposal(sender=d.country, recipient=target, round_id=round_id))
        return proposals

    def _accepts(
        self,
        sender_id: str,
        recipient_id: str,
        world: WorldState,
        grudges: GrudgeBook | None = None,
    ) -> tuple[bool, str]:
        """Politique d'acceptation déterministe et explicable.

        G7-a : le solde de griefs du DESTINATAIRE envers l'offreur pèse — ≤ seuil de
        refus : quasi systématiquement non ; ≥ seuil d'acceptation : facilitée."""
        sender = world.countries[sender_id]
        recipient = world.countries[recipient_id]
        if sender_id in recipient.rivals or recipient_id in sender.rivals:
            return False, "rivalité"

        grudge_bonus = 0.0
        if grudges is not None:
            params = load_gamefeel_params().grudges
            balance = grudges.balance(recipient_id, sender_id)
            if balance <= params.refuse_threshold:
                return False, f"griefs (solde {balance:g})"
            if balance >= params.accept_threshold:
                grudge_bonus = 0.3

        tension = world.get_tension(sender_id, recipient_id)
        already_allied = world.share_alliance(sender_id, recipient_id)
        common_rival = bool(set(sender.rivals) & set(recipient.rivals))
        score = (
            (1.0 - tension)
            + (0.2 if already_allied else 0.0)
            + (0.3 if common_rival else 0.0)
            + grudge_bonus
        )

        if score >= _ACCEPT_THRESHOLD:
            reasons = []
            if common_rival:
                reasons.append("rival commun")
            if already_allied:
                reasons.append("déjà alliés")
            reasons.append(f"tension {tension:.2f}")
            return True, ", ".join(reasons)
        return False, f"tension {tension:.2f} trop forte"

    def _form_pact(self, world: WorldState, a: str, b: str) -> bool:
        """Crée le pacte partagé et rapproche les deux pays. False si déjà en place."""
        pid = pact_id(a, b)
        ca, cb = world.countries[a], world.countries[b]
        existed = pid in ca.alliances and pid in cb.alliances
        if pid not in ca.alliances:
            ca.alliances.append(pid)
        if pid not in cb.alliances:
            cb.alliances.append(pid)
        world.adjust_tension(a, b, -_PACT_TENSION_DROP)
        return not existed

    @staticmethod
    def _summary(accepted: list[str], refused: list[str]) -> str:
        parts: list[str] = []
        if accepted:
            parts.append("Pactes : " + ", ".join(accepted))
        if refused:
            parts.append("Refus : " + ", ".join(refused))
        return " | ".join(parts) if parts else "Aucune proposition"
