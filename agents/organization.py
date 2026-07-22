"""L'ONU — l'organisation de veille, super-intelligence neutre (théâtre-globe, spec §12).

8ᵉ IA du plateau (ou tenue par l'humain via le rôle `un`) : elle ne négocie pas, elle
**observe, vérifie, rapporte**. Chaque round elle lit les promesses/traités et les
déclarations, publie un **rapport de conformité** public, peut émettre une **résolution**,
et remet un **avis consultatif au Juge** — dont l'influence est **bornée** (au plus ±0,05)
et **citée** dans le délibéré : le Juge reste souverain.

Socle backend (ce module) : le modèle `OrgReport`, l'agent `OrgAgent` (repli déterministe
si le LLM échoue), le borneur d'avis `clamp_advisory`, et l'application bornée à un verdict
`apply_advisory`. Tout est PUR/hors ligne côté tests (MockBackend). Le câblage dans la
boucle de round et le prompt du Juge = étape S14 (Claude Code, app qui tourne).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from inference.backend import InferenceBackend
from inference.json_extract import extract_json

# Influence maximale de l'avis de l'ONU sur le verdict du Juge (spec §12).
MAX_ADVISORY = 0.05

ORG_SYSTEM = (
    "Tu es l'ONU, une intelligence neutre qui surveille des super-intelligences nationales. "
    "Tu ne négocies pas et ne prends pas parti : tu vérifies le respect des promesses et des "
    "traités, tu signales les écarts, et tu conseilles le Juge avec mesure. Réponds "
    "UNIQUEMENT par un objet JSON, sans texte autour. En FRANÇAIS."
)

_STATUSES = ("respecte", "ecart", "violation")


class ComplianceItem(BaseModel):
    """Le constat de conformité d'un pays sur le round."""

    country: str
    status: str = "respecte"  # respecte | ecart | violation
    note: str = ""


class Advisory(BaseModel):
    """L'avis consultatif au Juge — deltas BORNÉS, toujours accompagnés d'un motif."""

    severity_delta: float = 0.0  # ∈ [-MAX_ADVISORY, +MAX_ADVISORY]
    tension_delta: float = 0.0  # idem
    rationale: str = ""


class OrgReport(BaseModel):
    """Le rapport public de l'ONU pour un round (trame SSE `org`, additif)."""

    round_id: int
    compliance: list[ComplianceItem] = Field(default_factory=list)
    resolution: str = ""  # résolution non contraignante (vide si rien à signaler)
    advisory: Advisory = Field(default_factory=Advisory)
    audited: str | None = None  # pays audité à la demande du joueur, le cas échéant


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def clamp_advisory(advisory: Advisory) -> Advisory:
    """Borne l'avis à ±MAX_ADVISORY : l'ONU pèse, elle ne décide pas."""
    return advisory.model_copy(
        update={
            "severity_delta": _clamp(advisory.severity_delta, -MAX_ADVISORY, MAX_ADVISORY),
            "tension_delta": _clamp(advisory.tension_delta, -MAX_ADVISORY, MAX_ADVISORY),
        }
    )


def apply_advisory(
    severity: float, tension_delta: float, advisory: Advisory
) -> tuple[float, float]:
    """Applique l'avis (borné) à un verdict : sévérité restant dans [0,1]."""
    a = clamp_advisory(advisory)
    new_sev = _clamp(severity + a.severity_delta, 0.0, 1.0)
    return new_sev, tension_delta + a.tension_delta


def neutral_report(round_id: int, countries: list[str] | tuple[str, ...]) -> OrgReport:
    """Repli déterministe : tout le monde en règle, aucun avis (grep-able)."""
    return OrgReport(
        round_id=round_id,
        compliance=[ComplianceItem(country=c, status="respecte") for c in countries],
        resolution="",
        advisory=Advisory(rationale="ONU : rien à signaler (rapport de repli)."),
    )


class OrgAgent:
    """Produit le rapport de l'ONU d'un round à partir de l'état + des promesses."""

    def __init__(
        self, backend: InferenceBackend, *, max_tokens: int = 500, temperature: float = 0.3
    ) -> None:
        self.backend = backend
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._schema = OrgReport.model_json_schema()

    def assess(
        self,
        round_id: int,
        countries: list[str] | tuple[str, ...],
        *,
        promises: str = "",
        event_title: str = "",
        transcript: str = "",
        audit_target: str | None = None,
    ) -> OrgReport:
        """Rapport de conformité + avis borné. Repli neutre si le LLM échoue."""
        prompt = self._prompt(round_id, countries, promises, event_title, transcript, audit_target)
        try:
            result = self.backend.generate(
                prompt,
                system=ORG_SYSTEM,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                schema=self._schema,
            )
            data = extract_json(result.text)
        except Exception:
            data = None
        report = self._coerce(data, round_id, countries)
        if audit_target:
            report = report.model_copy(update={"audited": audit_target})
        return report

    def _prompt(
        self, round_id: int, countries, promises, event_title, transcript, audit_target
    ) -> str:
        roster = ", ".join(countries)
        base = (
            f"ROUND {round_id}. PAYS SURVEILLÉS : {roster}\n"
            f"ÉVÉNEMENT : {event_title or 'n/a'}\n"
            f"PROMESSES & TRAITÉS EN VIGUEUR : {promises or 'aucun'}\n"
            f"DÉCLARATIONS DU ROUND :\n{transcript or '(aucune)'}\n\n"
        )
        if audit_target:
            base += f"AUDIT DEMANDÉ sur : {audit_target} (rapport ciblé attendu).\n"
        return base + (
            "Établis le rapport. JSON : {round_id, compliance:[{country, status "
            "(respecte|ecart|violation), note}], resolution (vide si rien), advisory:"
            "{severity_delta (-0.05..0.05), tension_delta (-0.05..0.05), rationale}}."
        )

    def _coerce(self, data: dict | None, round_id: int, countries) -> OrgReport:
        if not isinstance(data, dict):
            return neutral_report(round_id, countries)
        known = set(countries)
        items: list[ComplianceItem] = []
        for raw in data.get("compliance", []) or []:
            if not isinstance(raw, dict):
                continue
            c = raw.get("country")
            if c not in known:
                continue
            status = raw.get("status", "respecte")
            if status not in _STATUSES:
                status = "respecte"
            items.append(
                ComplianceItem(country=c, status=status, note=str(raw.get("note", ""))[:240])
            )
        adv_raw = data.get("advisory") if isinstance(data.get("advisory"), dict) else {}
        try:
            advisory = Advisory(
                severity_delta=float(adv_raw.get("severity_delta", 0.0) or 0.0),
                tension_delta=float(adv_raw.get("tension_delta", 0.0) or 0.0),
                rationale=str(adv_raw.get("rationale", ""))[:240],
            )
        except (TypeError, ValueError):
            advisory = Advisory()
        return OrgReport(
            round_id=round_id,
            compliance=items,
            resolution=str(data.get("resolution", "") or "")[:400],
            advisory=clamp_advisory(advisory),  # borné dès l'entrée : jamais > ±0,05
        )
