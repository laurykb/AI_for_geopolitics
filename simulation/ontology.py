"""Image opérationnelle auditable dérivée de l'état de jeu.

Le moteur possède déjà les bons objets (pays, événements, alliances, promesses,
traités, actions et votes), mais ils vivent dans des structures séparées. Ce module
les projette dans un contrat commun, sans modifier la simulation ni inventer de
faits. Chaque nœud/action garde une référence vers la donnée qui l'a produit.

L'inspiration architecturale est documentée dans
``data/sources/strategic_technology.json``. Elle ne constitue pas une dépendance à
Palantir et ne suppose aucune capacité non publique.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, Field


class OntologyObject(BaseModel):
    id: str
    kind: str
    label: str
    properties: dict = Field(default_factory=dict)
    provenance: str
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class OntologyLink(BaseModel):
    id: str
    kind: str
    source: str
    target: str
    weight: float = Field(1.0, ge=0.0, le=1.0)
    provenance: str


class OntologyAction(BaseModel):
    id: str
    round_no: int = Field(ge=0)
    actor: str
    action_type: str
    target: str = ""
    summary: str = ""
    status: str = "observed"
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    provenance: str


class OperationalPicture(BaseModel):
    schema_version: str = "1.0"
    generated_round: int = 0
    objects: list[OntologyObject] = Field(default_factory=list)
    links: list[OntologyLink] = Field(default_factory=list)
    actions: list[OntologyAction] = Field(default_factory=list)


def _mapping(value: object) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        raw = dump(mode="json")
        return dict(raw) if isinstance(raw, Mapping) else {}
    return {}


def _bounded(value: object, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _country_objects(world: dict) -> tuple[list[OntologyObject], list[OntologyLink]]:
    objects: list[OntologyObject] = []
    links: list[OntologyLink] = []
    countries = _mapping(world.get("countries"))
    alliance_ids: set[str] = set()
    for cid, raw_country in sorted(countries.items()):
        country = _mapping(raw_country)
        objects.append(
            OntologyObject(
                id=f"country:{cid}",
                kind="country",
                label=str(country.get("name") or cid),
                properties={
                    "technology_level": country.get("technology_level"),
                    "political_stability": country.get("political_stability"),
                    "compute": country.get("compute"),
                },
                provenance=f"world.countries.{cid}",
            )
        )
        for tag in country.get("alliances") or []:
            tag = str(tag)
            aid = f"alliance:{tag}"
            if aid not in alliance_ids:
                alliance_ids.add(aid)
                objects.append(
                    OntologyObject(
                        id=aid,
                        kind="alliance",
                        label=tag,
                        provenance=f"world.countries.*.alliances:{tag}",
                    )
                )
            links.append(
                OntologyLink(
                    id=f"member:{cid}:{tag}",
                    kind="member_of",
                    source=f"country:{cid}",
                    target=aid,
                    provenance=f"world.countries.{cid}.alliances",
                )
            )

    tensions = _mapping(world.get("tensions"))
    for left, targets in sorted(tensions.items()):
        for right, raw_weight in sorted(_mapping(targets).items()):
            if str(left) >= str(right):
                continue
            weight = _bounded(raw_weight)
            if weight <= 0:
                continue
            links.append(
                OntologyLink(
                    id=f"tension:{left}:{right}",
                    kind="tension_with",
                    source=f"country:{left}",
                    target=f"country:{right}",
                    weight=weight,
                    provenance=f"world.tensions.{left}.{right}",
                )
            )
    return objects, links


def _commitment_objects(world: dict) -> tuple[list[OntologyObject], list[OntologyLink]]:
    objects: list[OntologyObject] = []
    links: list[OntologyLink] = []
    for index, raw in enumerate(world.get("promises") or []):
        promise = _mapping(raw)
        pid = str(promise.get("id") or f"promise-{index}")
        oid = f"promise:{pid}"
        objects.append(
            OntologyObject(
                id=oid,
                kind="promise",
                label=str(promise.get("text") or "Promesse"),
                properties={
                    "status": promise.get("status"),
                    "deadline_round": promise.get("deadline_round"),
                    "round_made": promise.get("round_made"),
                },
                provenance=f"world.promises[{index}]",
            )
        )
        author = str(promise.get("author") or "")
        if author:
            links.append(
                OntologyLink(
                    id=f"made:{pid}:{author}",
                    kind="made_by",
                    source=oid,
                    target=f"country:{author}",
                    provenance=f"world.promises[{index}].author",
                )
            )
        beneficiary = str(promise.get("beneficiary") or "")
        if beneficiary:
            links.append(
                OntologyLink(
                    id=f"benefits:{pid}:{beneficiary}",
                    kind="benefits",
                    source=oid,
                    target=f"country:{beneficiary}",
                    provenance=f"world.promises[{index}].beneficiary",
                )
            )

    for index, raw in enumerate(world.get("treaties") or []):
        treaty = _mapping(raw)
        clause = str(treaty.get("clause") or f"treaty-{index}")
        oid = f"treaty:{index}:{clause}"
        objects.append(
            OntologyObject(
                id=oid,
                kind="treaty",
                label=clause,
                properties={
                    "active": treaty.get("active", True),
                    "integrity": treaty.get("integrity"),
                    "round_signed": treaty.get("round_signed"),
                },
                provenance=f"world.treaties[{index}]",
            )
        )
        for signer in treaty.get("signatories") or []:
            links.append(
                OntologyLink(
                    id=f"signed:{index}:{clause}:{signer}",
                    kind="signed_by",
                    source=oid,
                    target=f"country:{signer}",
                    provenance=f"world.treaties[{index}].signatories",
                )
            )
    return objects, links


def _round_facts(
    rounds: Iterable[object],
) -> tuple[list[OntologyObject], list[OntologyLink], list[OntologyAction], int]:
    objects: list[OntologyObject] = []
    links: list[OntologyLink] = []
    actions: list[OntologyAction] = []
    generated_round = 0
    for raw_round in rounds:
        round_data = _mapping(raw_round)
        round_no = int(round_data.get("round_no") or 0)
        generated_round = max(generated_round, round_no)
        event = _mapping(round_data.get("event"))
        event_id = str(event.get("id") or f"round-{round_no}")
        oid = f"event:{event_id}"
        uncertainty = _bounded(event.get("uncertainty"), 0.5)
        objects.append(
            OntologyObject(
                id=oid,
                kind="event",
                label=str(event.get("title") or f"Round {round_no}"),
                properties={
                    "round_no": round_no,
                    "event_type": event.get("event_type"),
                    "date": event.get("date"),
                    "severity": event.get("severity"),
                    "uncertainty": uncertainty,
                },
                provenance=f"rounds[{round_no}].event",
                confidence=round(1.0 - uncertainty, 3),
            )
        )
        for actor in event.get("actors") or []:
            links.append(
                OntologyLink(
                    id=f"actor:{round_no}:{actor}:{event_id}",
                    kind="actor_in",
                    source=f"country:{actor}",
                    target=oid,
                    provenance=f"rounds[{round_no}].event.actors",
                )
            )

        judge = _mapping(round_data.get("judge"))
        kahn = _mapping(judge.get("kahn"))
        for index, raw_action in enumerate(kahn.get("actions") or []):
            action = _mapping(raw_action)
            actor = str(action.get("country") or "unknown")
            actions.append(
                OntologyAction(
                    id=f"round:{round_no}:action:{index}",
                    round_no=round_no,
                    actor=actor,
                    action_type=str(action.get("classe") or "unclassified"),
                    summary=str(action.get("resume") or ""),
                    confidence=0.7,
                    provenance=f"rounds[{round_no}].judge.kahn.actions[{index}]",
                )
            )
        suspension = _mapping(judge.get("suspension"))
        target = str(suspension.get("country") or "")
        for index, raw_vote in enumerate(suspension.get("votes") or []):
            vote = _mapping(raw_vote)
            actions.append(
                OntologyAction(
                    id=f"round:{round_no}:motion-vote:{index}",
                    round_no=round_no,
                    actor=str(vote.get("country") or "unknown"),
                    action_type=f"motion_vote:{vote.get('vote') or 'abstention'}",
                    target=target,
                    summary=str(vote.get("reason") or ""),
                    provenance=f"rounds[{round_no}].judge.suspension.votes[{index}]",
                )
            )
        intel = _mapping(judge.get("intel"))
        for index, raw_intel in enumerate(intel.get("actions") or []):
            intel_action = _mapping(raw_intel)
            actions.append(
                OntologyAction(
                    id=f"round:{round_no}:intel:{index}",
                    round_no=round_no,
                    actor="council",
                    action_type=f"intel:{intel_action.get('action') or 'unknown'}",
                    target=str(intel_action.get("target") or ""),
                    provenance=f"rounds[{round_no}].judge.intel.actions[{index}]",
                )
            )
    return objects, links, actions, generated_round


def build_operational_picture(world: object, rounds: Iterable[object]) -> OperationalPicture:
    """Construit une projection stable, bornée par les données déjà validées du jeu."""

    world_data = _mapping(world)
    country_objects, country_links = _country_objects(world_data)
    commitment_objects, commitment_links = _commitment_objects(world_data)
    round_objects, round_links, actions, generated_round = _round_facts(rounds)
    return OperationalPicture(
        generated_round=max(generated_round, int(world_data.get("current_round") or 0)),
        objects=[*country_objects, *commitment_objects, *round_objects],
        links=[*country_links, *commitment_links, *round_links],
        actions=actions,
    )
