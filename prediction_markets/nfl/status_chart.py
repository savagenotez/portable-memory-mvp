"""Current system status as one SVG, generated from the saved result files.

    python3 -m prediction_markets.nfl.status_chart   # writes prediction_markets/results/system_status.svg

Three things are kept apart on purpose: development results on history (not blind), comparisons with the market on
the 146 diagnosis games (not blind either), and the blind test (no verdict until 100 priced sealed games settle).
"""

from __future__ import annotations

import json
import os

R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
BLUE, ORANGE = "#2a78d6", "#e0701a"      # reference palette, categorical slots 1 and 2 (validated)
INK, INK2, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#d9d8d3"


def _load(name):
    with open(os.path.join(R, name), encoding="utf-8") as fh:
        return json.load(fh)


def gather() -> dict:
    eff = _load("nfl_efficiency_dev.json")
    v3 = _load("nfl_v3_dev.json")
    tune = _load("nfl_tune.json")
    mvm = _load("nfl_model_vs_market.json")
    rec = _load("nfl_recheck_k30.json")
    man = _load("blind_manifest.json")
    log = []
    with open(os.path.join(R, "prospective_snapshots.jsonl"), encoding="utf-8") as fh:
        log = [json.loads(line) for line in fh if line.strip()]
    priced = {r["event_id"] for r in log if r.get("mid") is not None}
    scores = os.path.join(R, "prospective_scores.json")
    scored = _load("prospective_scores.json")["scored_games"] if os.path.exists(scores) else 0
    return {
        "dev": [  # (label, mean, lo, hi) change in log loss vs base; negative = better
            ("Efficiency, 10-game half-life", eff["efficiency_holdout_gain"]["mean"], *eff["efficiency_holdout_gain"]["ci95"]),
            ("Injuries, key positions", eff["injury_holdout_gain"]["mean"], *eff["injury_holdout_gain"]["ci95"]),
            ("K = 30 Elo (tuning)", tune["holdout_comparison"]["log_loss_gain_selected_minus_V0"],
             *tune["holdout_comparison"]["ci95"]),
            ("v3 combined, same window (fair)", v3["v3_minus_base_same_window_2010_training"]["mean"],
             *v3["v3_minus_base_same_window_2010_training"]["ci95"]),
        ],
        "market": [  # (label, mean, lo, hi) Brier, model minus market; negative = model better
            ("Base model, diagnosis run", mvm["model_minus_market_brier"], *mvm["model_minus_market_ci95"]),
            ("K = 30 re-check", rec["K30_tuned"]["model_minus_market_brier"], *rec["K30_tuned"]["model_minus_market_ci95"]),
        ],
        "sealed": len(man["game_ids"]),
        "priced_events": len(priced),
        "scored": scored,
        "tests": None,
    }


def _panel(parts, title, subtitle, rows, colour, x0, x1, y0, lo_dom, hi_dom, ticks, note):
    W = x1 - x0
    def X(v):
        return x0 + (v - lo_dom) / (hi_dom - lo_dom) * W
    out = [f'<text x="30" y="{y0}" font-size="18" font-weight="600" fill="{INK}">{title}</text>',
           f'<text x="30" y="{y0 + 22}" font-size="13" fill="{INK2}">{subtitle}</text>']
    top = y0 + 40
    bottom = top + 52 * len(rows)
    for t in ticks:
        out.append(f'<line x1="{X(t):.1f}" y1="{top - 8}" x2="{X(t):.1f}" y2="{bottom}" stroke="{GRID}" stroke-width="1"/>')
        label = f"{t:+.3f}".replace("-", "−")
        out.append(f'<text x="{X(t):.1f}" y="{bottom + 18}" font-size="12" fill="{INK2}" text-anchor="middle">{label}</text>')
    Z = X(0.0)
    out.append(f'<line x1="{Z:.1f}" y1="{top - 8}" x2="{Z:.1f}" y2="{bottom}" stroke="{INK2}" stroke-width="1.5" stroke-dasharray="4 4"/>')
    out.append(f'<text x="{Z - 8:.1f}" y="{bottom + 40}" font-size="12" fill="{INK2}" text-anchor="end">{note[0]}</text>')
    out.append(f'<text x="{Z + 8:.1f}" y="{bottom + 40}" font-size="12" fill="{INK2}">{note[1]}</text>')
    for i, (label, mean, lo, hi) in enumerate(rows):
        y = top + 26 + i * 52
        out.append(f'<text x="30" y="{y + 5}" font-size="14" fill="{INK}">{label}</text>')
        out.append(f'<line x1="{X(lo):.1f}" y1="{y}" x2="{X(hi):.1f}" y2="{y}" stroke="{colour}" stroke-width="2.5"/>')
        for v in (lo, hi):
            out.append(f'<line x1="{X(v):.1f}" y1="{y - 6}" x2="{X(v):.1f}" y2="{y + 6}" stroke="{colour}" stroke-width="2"/>')
        out.append(f'<circle cx="{X(mean):.1f}" cy="{y}" r="6" fill="{colour}"/>')
        txt = f"{mean:+.4f}".replace("-", "−")
        out.append(f'<text x="{x1 + 22}" y="{y + 5}" font-size="13" fill="{INK}">{txt}</text>')
    return out, bottom + 64


def tile(x, y, w, big, small, colour=INK):
    return [f'<rect x="{x}" y="{y}" width="{w}" height="78" rx="6" fill="#f1f0ec"/>',
            f'<text x="{x + 14}" y="{y + 38}" font-size="26" font-weight="600" fill="{colour}">{big}</text>',
            f'<text x="{x + 14}" y="{y + 60}" font-size="12" fill="{INK2}">{small}</text>']


def svg() -> str:
    g = gather()
    W, H = 980, 780
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="system-ui, -apple-system, Segoe UI, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
           f'<text x="30" y="40" font-size="24" font-weight="600" fill="{INK}">NFL model: current status</text>',
           f'<text x="30" y="64" font-size="13" fill="{INK2}">Nothing here is a profit claim. Only the blind test can '
           'show whether the model beats the market, and it has not reached its sample size.</text>']
    tiles = [
        ("109", "games sealed, unplayed at sealing", INK),
        (str(g["priced_events"]), "sealed events with a price so far", INK),
        (f"{g['scored']} / 100", "scored games needed for a verdict", INK),
        ("v3", "frozen, judged on sealed games only", INK),
    ]
    for i, (big, small, col) in enumerate(tiles):
        out += tile(30 + i * 230, 84, 212, big, small, col)
    dev_parts, y = _panel(None, "History: change in log loss vs the base model",
                          "Development on 2005-2025 games. Not blind: the 2020-2025 seasons were used earlier to choose K = 30. Negative = better.",
                          g["dev"], BLUE, 300, 850, 210, -0.014, 0.004,
                          [-0.012, -0.008, -0.004, 0.0], ("better", "worse"))
    out += dev_parts
    mkt_parts, y2 = _panel(None, "Against the market: Brier score on the same 146 games",
                           "Diagnosis games, not blind. Negative = the model did better than the Kalshi price.",
                           g["market"], ORANGE, 300, 850, y + 20, -0.02, 0.03,
                           [-0.02, 0.0, 0.02], ("model better", "market better"))
    out += mkt_parts
    out.append(f'<text x="30" y="{H - 24}" font-size="12" fill="{INK2}">Sources: prediction_markets/results/*.json, '
               'prospective_snapshots.jsonl, blind_manifest.json. The 166-test suite passes.</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    path = os.path.join(R, "system_status.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg())
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
