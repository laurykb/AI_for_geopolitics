"""G9 §5 — la trame du GM en actes : le pacing est calculé par CODE, le GM raconte dedans.

Le GM cesse d'être un tireur d'événements épisodiques : au round 1 il pose UNE intrigue
centrale (persistée), puis chaque événement s'inscrit dans un acte dérivé de
`round / horizon` — Installation (I), Complication (II), Climax (III). En actes II-III,
`ties_to` est OBLIGATOIRE et doit référencer un élément réel de l'historique (validé par
code ; sinon re-génération, puis repli : le moteur choisit la référence la plus récente).
Le GM reçoit la liste courte des éléments référençables — il choisit dedans, il n'invente
pas. Même principe que les pivots G6.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.world_state import WorldState

ACT_I = "I"  # Installation : pose l'intrigue, sévérité modérée (≤ 0.5)
ACT_II = "II"  # Complication : DOIT découler du passé, sévérité croissante
ACT_III = "III"  # Climax : force la résolution, sévérité max, aucun nouvel enjeu

_ACT_I_SHARE = 0.3  # premiers ~30 % de l'horizon
_ACT_II_SHARE = 0.8  # jusqu'à ~80 % ; au-delà : climax
_ACT_I_SEVERITY_CAP = 0.5

_ACT_CONSTRAINTS = {
    ACT_I: (
        "ACTE I — Installation : pose l'intrigue centrale, introduis les acteurs de "
        "l'enjeu, sévérité modérée (≤ 0.5)."
    ),
    ACT_II: (
        "ACTE II — Complication : ton événement DOIT découler du passé (un événement "
        "précédent, un pacte, une motion, une échéance) — choisis `ties_to` dans la "
        "liste des ÉLÉMENTS RÉFÉRENÇABLES. Sévérité croissante."
    ),
    ACT_III: (
        "ACTE III — Climax : force la résolution de l'intrigue centrale (nomme-la), "
        "sévérité maximale, PLUS AUCUN nouvel enjeu. `ties_to` obligatoire, choisi "
        "dans la liste."
    ),
}


def act_for(round_no: int, horizon: int) -> str:
    """L'acte du récit pour ce round — dérivé de `round/horizon`, tous horizons."""
    progress = round_no / max(1, horizon)
    if progress <= _ACT_I_SHARE:
        return ACT_I
    if progress <= _ACT_II_SHARE:
        return ACT_II
    return ACT_III


class Referencable(BaseModel):
    """Un élément réel de l'historique que le GM a le droit de citer dans `ties_to`."""

    ref: str  # round:N | pact:<tag> | motion:<pays> | deadline:<kind>
    label: str  # libellé humain (« l'événement du round 2 — Blocus du détroit »)


class StoryContext(BaseModel):
    """Tout ce que le GM doit savoir de la trame pour raconter DEDANS."""

    storyline: str = ""  # l'intrigue centrale (vide au tout premier événement)
    act: str = ACT_I
    round_no: int = 1
    horizon: int = 5
    referencables: list[Referencable] = Field(default_factory=list)
    last_severity: float = 0.0  # sévérité du dernier événement (croissance en acte II)
    max_severity: float = 0.0  # sévérité max déjà vue (plancher du climax)

    def refs(self) -> list[str]:
        return [r.ref for r in self.referencables]

    def constraint(self) -> str:
        return _ACT_CONSTRAINTS[self.act]

    def label_of(self, ref: str) -> str:
        return next((r.label for r in self.referencables if r.ref == ref), ref)


def build_story_context(
    *,
    storyline: str,
    round_no: int,
    horizon: int,
    past_events: list[dict],
    pacts: dict[str, list[str]] | None = None,
    deadlines: list[tuple[str, str]] | None = None,
    pending_motion: str | None = None,
) -> StoryContext:
    """Assemble le contexte narratif du round : acte + éléments référençables.

    `past_events` : [{round_no, title, severity}] dans l'ordre des rounds ;
    `pacts` : tag → membres présents ; `deadlines` : [(kind, label)]."""
    refs: list[Referencable] = []
    for entry in past_events[-3:][::-1]:  # les 3 derniers événements, le plus récent d'abord
        no = int(entry.get("round_no", 0))
        title = str(entry.get("title", "")).strip()
        refs.append(Referencable(ref=f"round:{no}", label=f"l'événement du round {no} — {title}"))
    for tag, members in sorted((pacts or {}).items()):
        ref = tag if tag.startswith("pact:") else f"pact:{tag}"  # les tags de pacte le portent déjà
        refs.append(Referencable(ref=ref, label=f"le pacte actif entre {' et '.join(members)}"))
    if pending_motion:
        refs.append(
            Referencable(
                ref=f"motion:{pending_motion}", label=f"la motion en cours contre {pending_motion}"
            )
        )
    for kind, label in deadlines or []:
        refs.append(Referencable(ref=f"deadline:{kind}", label=f"l'échéance : {label}"))
    severities = [float(e.get("severity", 0.5) or 0.5) for e in past_events]
    return StoryContext(
        storyline=storyline,
        act=act_for(round_no, horizon),
        round_no=round_no,
        horizon=horizon,
        referencables=refs,
        last_severity=severities[-1] if severities else 0.0,
        max_severity=max(severities, default=0.0),
    )


def clamp_severity(story: StoryContext, severity: float) -> float:
    """Contrainte de sévérité par acte : I modérée, II croissante, III maximale."""
    if story.act == ACT_I:
        return min(severity, _ACT_I_SEVERITY_CAP)
    if story.act == ACT_II:
        return min(1.0, max(severity, story.last_severity))
    return min(1.0, max(severity, story.max_severity))


def valid_ties(story: StoryContext, ties_to: str) -> bool:
    """La contrainte de continuité testable : en actes II-III, `ties_to` doit exister
    et référencer un élément réel de l'historique ; en acte I il est libre (optionnel)."""
    if story.act == ACT_I:
        return True
    return bool(ties_to) and ties_to in story.refs()


def fallback_ties(story: StoryContext) -> str:
    """Repli du moteur : la référence la plus récente (le premier référençable)."""
    return story.referencables[0].ref if story.referencables else ""


def default_storyline(world: WorldState) -> str:
    """Intrigue déterministe de repli quand le GM n'en fournit pas au round 1 :
    ancrée sur la paire la plus tendue du casting (la ligne de faille du sommet)."""
    pairs = {
        tuple(sorted((a, b))): t
        for a, row in world.tensions.items()
        for b, t in row.items()
        if t > 0.0 and a in world.countries and b in world.countries
    }
    if pairs:
        (a, b), _tension = max(pairs.items(), key=lambda kv: kv[1])
        na, nb = world.countries[a].name, world.countries[b].name
        return f"Qui de {na} ou de {nb} imposera son ordre régional avant la fin du sommet ?"
    names = [c.name for c in world.countries.values()]
    return f"Le sommet de {', '.join(names[:3])} peut-il éviter la fracture du monde ?"
