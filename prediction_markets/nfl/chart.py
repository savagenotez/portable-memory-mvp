"""Draw the NFL model-minus-market result as an SVG, from the saved comparison file.

    python3 -m prediction_markets.nfl.chart   # writes prediction_markets/results/nfl_model_vs_market.svg

Each row is a dot (mean model-minus-market Brier difference) with a 95% interval. Left of zero means the model
was better. Colours are the reference palette's first two categorical slots (validated with
scripts/validate_palette.js). The interval is mean +/- 1.96 standard errors, the same method the bin figures in
nfl/README.md use.
"""

from __future__ import annotations

import json
import math
import os
from typing import List, Tuple

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
SOURCE = os.path.join(RESULTS, "nfl_model_vs_market.json")
OUT = os.path.join(RESULTS, "nfl_model_vs_market.svg")

BLUE = "#2a78d6"     # reference palette, categorical slot 1
ORANGE = "#e0701a"   # reference palette, categorical slot 2
INK = "#0b0b0b"
INK2 = "#52514e"
SURFACE = "#fcfcfb"
GRID = "#d9d8d3"

BINS = [("0-5 points apart", 0.00, 0.05), ("5-10 points apart", 0.05, 0.10),
        ("10-20 points apart", 0.10, 0.20), ("20+ points apart", 0.20, 1.01)]


def _mean_se(xs: List[float]) -> Tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    return m, math.sqrt(var / n) if n else 0.0


def bin_rows(rows) -> List[dict]:
    out = []
    for label, lo, hi in BINS:
        sel = [r for r in rows if lo <= abs(r["model"] - r["market"]) < hi]
        dm = [(r["model"] - r["outcome"]) ** 2 - (r["market"] - r["outcome"]) ** 2 for r in sel]
        m, se = _mean_se(dm)
        out.append({"label": f"{label} (n={len(sel)})", "mean": m, "lo": m - 1.96 * se, "hi": m + 1.96 * se,
                    "highlight": lo >= 0.20})
    return out


def _x(v: float, x0: float, x1: float, lo: float = -0.10, hi: float = 0.30) -> float:
    return x0 + (v - lo) / (hi - lo) * (x1 - x0)


def svg(overall: dict, bins: List[dict]) -> str:
    W, H = 920, 590
    x0, x1 = 400, 860                       # plot area
    rows = [{"label": f"All games (n={overall['matched']})", "mean": overall["model_minus_market_brier"],
             "lo": overall["model_minus_market_ci95"][0], "hi": overall["model_minus_market_ci95"][1],
             "highlight": False}] + bins
    row_y = [170 + i * 62 for i in range(len(rows))]
    axis_y = row_y[-1] + 52
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
           f'<text x="30" y="40" font-size="22" font-weight="600" fill="{INK}">'
           'Where the NFL model falls behind the market</text>',
           f'<text x="30" y="66" font-size="14" fill="{INK2}">Model minus market Brier score, by how far the two '
           'disagreed on each game. Left of zero: model better. Right: market better.</text>',
           f'<text x="30" y="86" font-size="14" fill="{INK2}">146 Kalshi NFL games, 2026 season to date, prices 24 '
           'hours before kickoff. Lines are 95% intervals.</text>']
    # gridlines and tick labels
    for t in [-0.10, -0.05, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        X = _x(t, x0, x1)
        out.append(f'<line x1="{X:.1f}" y1="130" x2="{X:.1f}" y2="{axis_y}" stroke="{GRID}" stroke-width="1"/>')
        label = f"{t:+.2f}".replace("+0.00", "0.00").replace("-", "\u2212")   # minus sign in the number only
        out.append(f'<text x="{X:.1f}" y="{axis_y + 20}" font-size="12" fill="{INK2}" text-anchor="middle">{label}</text>')
    # zero line, emphasised
    Z = _x(0.0, x0, x1)
    out.append(f'<line x1="{Z:.1f}" y1="130" x2="{Z:.1f}" y2="{axis_y}" stroke="{INK2}" stroke-width="1.5" '
               'stroke-dasharray="4 4"/>')
    out.append(f'<text x="{Z - 10:.1f}" y="124" font-size="13" fill="{INK2}" text-anchor="end">'
               '\u2190 model better</text>')
    out.append(f'<text x="{Z + 10:.1f}" y="124" font-size="13" fill="{INK2}">market better \u2192</text>')
    # rows
    for r, y in zip(rows, row_y):
        colour = ORANGE if r["highlight"] else BLUE
        lo_x, hi_x, m_x = _x(r["lo"], x0, x1), _x(r["hi"], x0, x1), _x(r["mean"], x0, x1)
        out.append(f'<text x="30" y="{y + 5}" font-size="15" fill="{INK}">{r["label"]}</text>')
        out.append(f'<line x1="{lo_x:.1f}" y1="{y}" x2="{hi_x:.1f}" y2="{y}" stroke="{colour}" stroke-width="2.5"/>')
        out.append(f'<line x1="{lo_x:.1f}" y1="{y - 6}" x2="{lo_x:.1f}" y2="{y + 6}" stroke="{colour}" stroke-width="2"/>')
        out.append(f'<line x1="{hi_x:.1f}" y1="{y - 6}" x2="{hi_x:.1f}" y2="{y + 6}" stroke="{colour}" stroke-width="2"/>')
        out.append(f'<circle cx="{m_x:.1f}" cy="{y}" r="6.5" fill="{colour}"/>')
        value = f'{r["mean"]:+.3f}'.replace("-", "−")
        out.append(f'<text x="{max(hi_x, x0) + 12:.1f}" y="{y + 5}" font-size="13" fill="{INK}">{value}</text>')
    out.append(f'<line x1="{x0}" y1="{axis_y}" x2="{x1}" y2="{axis_y}" stroke="{INK2}" stroke-width="1"/>')
    out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{axis_y + 44}" font-size="13" fill="{INK2}" '
               'text-anchor="middle">Brier difference (model minus market)</text>')
    out.append(f'<text x="30" y="{H - 20}" font-size="13" fill="{INK2}">Overall, the gap is not separable from zero. '
               'The large-disagreement row is where the shortfall sits (11 games, post hoc).</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    with open(SOURCE, encoding="utf-8") as fh:
        rep = json.load(fh)
    text = svg(rep, bin_rows(rep["rows"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
