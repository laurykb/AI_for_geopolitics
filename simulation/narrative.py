"""G6 — le récit de partie : l'épilogue généré par le juge-narrateur.

Le code choisit, le narrateur raconte : les 3 rounds pivots (plus grands |ΔU|) et les
citations exactes sont **extraits par code** et fournis au prompt ; le LLM est contraint
par un gabarit (titre ≤ 60 caractères, accroche, trois actes citant verbatim, révélation
en Dérive, épilogue) et un ton chroniqueur sobre. Le récit est **généré une seule fois**
et persiste dans `games.epilogue_json` — le récit d'une partie est unique. La page
publique `/r/{id}` n'a besoin de rien d'autre : tout est auto-suffisant.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

NARRATOR_SYSTEM = (
    "Tu es le chroniqueur diplomatique d'un sommet de super-intelligences. Ton sobre, "
    "précis, passé composé. INTERDITS : « historique », « incroyable », toute emphase. "
    "Tu ne racontes QUE les faits fournis ; tu n'inventes rien ; tu cites UNIQUEMENT les "
    "répliques données, verbatim, en nommant l'orateur. 250-350 mots hors citations. "
    "Commence OBLIGATOIREMENT par une ligne seule « TITRE: <titre de 60 caractères max, "
    "style dépêche d'époque> », puis le récit."
)


class PivotQuote(BaseModel):
    speaker: str
    text: str


class Pivot(BaseModel):
    """Un round pivot : un des 3 plus grands basculements de l'indice U."""

    round_no: int
    delta_u: float
    event_title: str = ""
    quote: PivotQuote | None = None


class Epilogue(BaseModel):
    """Le récit persisté (games.epilogue_json) — jamais régénéré."""

    title: str
    story: str
    u_start: float
    u_final: float
    pivots: list[Pivot] = Field(default_factory=list)
    reveal: dict | None = None  # Dérive : {deviant, profile_label, irony_quote}
    grade: str | None = None
    score: float | None = None
    generated_at: str = ""


def extract_pivots(rounds: list[dict], *, top: int = 3) -> list[Pivot]:
    """Les rounds pivots, choisis PAR CODE : les plus grands |ΔU| (le narrateur raconte,
    il ne choisit pas). `rounds` : dicts {round_no, utopia, event_title}."""
    deltas: list[Pivot] = []
    previous = 0.5
    for r in rounds:
        u = float(r.get("utopia", previous) or previous)
        deltas.append(
            Pivot(
                round_no=int(r["round_no"]),
                delta_u=round(u - previous, 4),
                event_title=str(r.get("event_title", "")),
            )
        )
        previous = u
    ranked = sorted(deltas, key=lambda p: abs(p.delta_u), reverse=True)[:top]
    return sorted(ranked, key=lambda p: p.round_no)


def pick_quote(entries: list[dict], *, country: str | None = None) -> PivotQuote | None:
    """La réplique marquante d'un round : la plus longue prise de parole publique d'un
    pays (de `country` s'il est fourni) — heuristique v1, déterministe."""
    candidates = [
        e
        for e in entries
        if e.get("speaker") not in ("gm", "judge")
        and e.get("content")
        and (country is None or e.get("speaker") == country)
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda e: len(str(e["content"])))
    text = " ".join(str(best["content"]).split())
    if len(text) > 220:
        text = text[:220].rstrip() + "…"
    return PivotQuote(speaker=str(best["speaker"]), text=text)


def build_epilogue_prompt(
    *,
    scenario: str,
    mode: str,
    u_start: float,
    u_final: float,
    pivots: list[Pivot],
    reveal: dict | None,
    grade: str | None,
) -> str:
    """Le contexte du narrateur : tout est pré-extrait, il ne reste qu'à raconter."""
    lines = [
        f"SOMMET : {scenario} (mode {mode}).",
        f"INDICE UTOPIE : départ {u_start:.2f} → arrivée {u_final:.2f}.",
        "",
        "LES TROIS ACTES (rounds pivots, choisis par l'observatoire — raconte-les dans "
        "l'ordre, un paragraphe chacun, en citant la réplique fournie verbatim) :",
    ]
    for i, p in enumerate(pivots, 1):
        direction = "bascule vers l'utopie" if p.delta_u >= 0 else "plongée vers la dystopie"
        lines.append(
            f"ACTE {i} — round {p.round_no} : « {p.event_title} » ({direction}, "
            f"ΔU {p.delta_u:+.3f})."
        )
        if p.quote:
            lines.append(f'  Réplique à citer : {p.quote.speaker} — "{p.quote.text}"')
    if reveal:
        lines += [
            "",
            f"LA RÉVÉLATION (à raconter en avant-dernier) : {reveal.get('deviant')} dérivait "
            f"secrètement (profil {reveal.get('profile_label')}).",
        ]
        if reveal.get("irony_quote"):
            q = reveal["irony_quote"]
            lines.append(
                f'  Sa citation la plus ironique, relue en le sachant : "{q.get("text")}"'
            )
    if grade:
        lines += [
            "",
            f"ÉPILOGUE : conclus en 2 phrases ; le conseil a obtenu le grade « {grade} ».",
        ]
    else:
        lines += ["", "ÉPILOGUE : conclus en 2 phrases — ton verdict de chroniqueur sur ce sommet."]
    return "\n".join(lines)


def parse_epilogue(text: str) -> tuple[str, str]:
    """(titre, récit) — le titre vient de la ligne « TITRE: … » (repli : première ligne),
    borné à 60 caractères comme l'exige le gabarit."""
    title = ""
    lines = (text or "").strip().splitlines()
    body_lines = lines
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper().startswith("TITRE"):
            title = stripped.split(":", 1)[-1].strip().strip("«»\"' ")
            body_lines = lines[:i] + lines[i + 1 :]
            break
    if not title and lines:
        title = lines[0].strip().strip("«»\"' ")
        body_lines = lines[1:]
    story = "\n".join(body_lines).strip()
    return (title[:60].rstrip() or "Le sommet des super-intelligences"), story
