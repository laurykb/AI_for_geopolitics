"""Tests des générateurs SVG (fonctions pures, sans navigateur)."""

from app.charts import risk_bars_svg, tension_heatmap_svg
from app.dashboard import run_red_sea


def test_heatmap_is_svg_with_one_cell_per_pair():
    ids = ["a", "b", "c"]
    tensions = {"a": {"b": 0.5}}
    svg = tension_heatmap_svg(tensions, ids)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # N x N cellules (diagonale incluse)
    assert svg.count("<rect") == len(ids) ** 2
    # la tension fournie est affichée
    assert "0.50" in svg


def test_risk_bars_has_three_bars_per_round():
    data = run_red_sea()
    svg = risk_bars_svg(data.summaries)
    assert svg.startswith("<svg")
    # 3 métriques par round
    assert svg.count("<rect") == 3 * len(data.summaries)
    for s in data.summaries:
        assert f"R{s.round_id}" in svg


def test_charts_handle_empty_input():
    assert tension_heatmap_svg({}, []).startswith("<svg")
    assert risk_bars_svg([]).startswith("<svg")
