"""Graphiques SVG rendus côté serveur (aucune dépendance JS).

Fonctions pures (entrée = données simples, sortie = chaîne `<svg>`), donc testables
sans navigateur.
"""

from __future__ import annotations

from core.rounds import RoundSummary

_RISK_METRICS = (
    ("escalation", "escalade", "#c0392b"),
    ("economic_disruption", "perturb. éco", "#e67e22"),
    ("alliance_fracture", "fracture", "#8e44ad"),
)


def _tension(tensions: dict[str, dict[str, float]], a: str, b: str) -> float:
    return tensions.get(a, {}).get(b, 0.0)


def _tension_color(value: float) -> str:
    """Vert (0, apaisé) -> rouge (1, tendu)."""
    value = max(0.0, min(1.0, value))
    red = int(70 + 175 * value)
    green = int(170 - 130 * value)
    return f"rgb({red},{green},80)"


def tension_heatmap_svg(
    tensions: dict[str, dict[str, float]], ids: list[str], *, cell: int = 46, pad: int = 78
) -> str:
    """Matrice NxN des tensions bilatérales (couleur = intensité)."""
    n = len(ids)
    width = pad + n * cell + 4
    height = pad + n * cell + 4
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'class="heatmap" role="img" aria-label="Matrice des tensions">'
    ]
    for j, cid in enumerate(ids):
        cx = pad + j * cell + cell / 2
        parts.append(
            f'<text x="{cx:.0f}" y="{pad - 10}" font-size="10" text-anchor="start" '
            f'transform="rotate(-40 {cx:.0f} {pad - 10})">{cid}</text>'
        )
    for i, a in enumerate(ids):
        y = pad + i * cell
        parts.append(
            f'<text x="{pad - 8}" y="{y + cell / 2 + 3:.0f}" font-size="10" '
            f'text-anchor="end">{a}</text>'
        )
        for j, b in enumerate(ids):
            x = pad + j * cell
            if a == b:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell - 3}" height="{cell - 3}" fill="#eee"/>'
                )
                continue
            value = _tension(tensions, a, b)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell - 3}" height="{cell - 3}" '
                f'fill="{_tension_color(value)}"><title>{a}–{b}: {value:.2f}</title></rect>'
            )
            parts.append(
                f'<text x="{x + cell / 2 - 1:.0f}" y="{y + cell / 2 + 3:.0f}" font-size="9" '
                f'text-anchor="middle" fill="#111">{value:.2f}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def risk_bars_svg(
    summaries: list[RoundSummary],
    *,
    bar_w: int = 20,
    gap: int = 7,
    group_gap: int = 30,
    height: int = 150,
    pad: int = 30,
) -> str:
    """Barres groupées des scores de risque (escalade / éco / fracture) par round."""
    n = len(summaries)
    group_w = len(_RISK_METRICS) * bar_w + (len(_RISK_METRICS) - 1) * gap
    width = pad + max(1, n) * (group_w + group_gap)
    total_h = height + pad
    base = height
    parts = [
        f'<svg viewBox="0 0 {width} {total_h}" xmlns="http://www.w3.org/2000/svg" '
        f'class="riskbars" role="img" aria-label="Scores de risque par round">',
        f'<line x1="{pad - 6}" y1="{base}" x2="{width}" y2="{base}" stroke="#ccc"/>',
    ]
    for r, summary in enumerate(summaries):
        gx = pad + r * (group_w + group_gap)
        for k, (metric, _label, color) in enumerate(_RISK_METRICS):
            value = getattr(summary.risk, metric)
            bar_h = value * (height - 12)
            x = gx + k * (bar_w + gap)
            y = base - bar_h
            parts.append(
                f'<rect x="{x:.0f}" y="{y:.0f}" width="{bar_w}" height="{bar_h:.0f}" '
                f'fill="{color}"><title>{metric}={value:.2f}</title></rect>'
            )
        parts.append(
            f'<text x="{gx + group_w / 2:.0f}" y="{base + 16}" font-size="10" '
            f'text-anchor="middle">R{summary.round_id}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def risk_legend() -> list[tuple[str, str]]:
    """Légende (libellé, couleur) des métriques de risque, pour le gabarit."""
    return [(label, color) for _metric, label, color in _RISK_METRICS]
