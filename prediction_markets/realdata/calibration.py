"""How well calibrated were real market prices some hours before close?

This is the benchmark any model has to beat. It uses no model at all: just the market's own price and the outcome.
A calibrated price of 0.70 should be followed by a YES about 70% of the time.

Caveats that go with every number it prints:
  * prices are taken at ONE time before close, so this says nothing about earlier or later prices;
  * the base-rate comparison is in-sample, which flatters the baseline slightly;
  * two-outcome Polymarket markets track the FIRST listed outcome, which is arbitrary for team-vs-team markets.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from ..markets import wilson_interval
from .observation import Observation

EDGES = [i / 10.0 for i in range(11)]


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def fit_calibration(obs: Sequence[Observation]) -> Dict[str, float]:
    """Logistic regression of the outcome on logit(price). Slope 1 and intercept 0 mean perfectly calibrated."""
    xs = [_logit(o.price) for o in obs]
    ys = [o.outcome for o in obs]
    a, b = 0.0, 1.0
    h00 = h01 = h11 = 0.0
    for _ in range(30):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, ys):
            q = 1.0 / (1.0 + math.exp(-(a + b * x)))
            w = q * (1.0 - q)
            g0 += y - q
            g1 += (y - q) * x
            h00 += w
            h01 += w * x
            h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        da = (h11 * g0 - h01 * g1) / det
        db = (-h01 * g0 + h00 * g1) / det
        a, b = a + da, b + db
        if abs(da) + abs(db) < 1e-9:
            break
    det = h00 * h11 - h01 * h01
    se_b = math.sqrt(h00 / det) if det > 1e-12 else float("nan")
    se_a = math.sqrt(h11 / det) if det > 1e-12 else float("nan")
    return {"intercept": a, "slope": b, "slope_se": se_b, "intercept_se": se_a}


def reliability_table(obs: Sequence[Observation], edges: Sequence[float] = EDGES) -> List[dict]:
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = [o for o in obs if lo <= o.price < hi or (hi >= 1.0 and o.price >= 1.0)]
        n = len(sel)
        if n == 0:
            continue
        wins = sum(o.outcome for o in sel)
        mp = sum(o.price for o in sel) / n
        lo_ci, hi_ci = wilson_interval(wins, n)
        rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": n, "mean_price": mp, "realized": wins / n,
                     "gap": wins / n - mp, "ci_low": lo_ci, "ci_high": hi_ci,
                     "price_inside_ci": lo_ci <= mp <= hi_ci})
    return rows


def summarize(obs: Sequence[Observation]) -> dict:
    n = len(obs)
    if n < 5:
        return {"n": n}
    base = sum(o.outcome for o in obs) / n
    brier = sum((o.price - o.outcome) ** 2 for o in obs) / n
    brier_base = sum((base - o.outcome) ** 2 for o in obs) / n
    ll = sum(-math.log(o.price if o.outcome else 1.0 - o.price) for o in obs) / n
    fit = fit_calibration(obs)
    return {"n": n, "events": len({(o.source, o.event_id) for o in obs}),
            "mean_price": sum(o.price for o in obs) / n, "realized_rate": base,
            "brier_market": brier, "brier_base_rate": brier_base,
            "skill_vs_base_rate": 1.0 - brier / brier_base if brier_base > 0 else None,
            "log_loss_market": ll, "calibration": fit}


def report(obs: Sequence[Observation]) -> dict:
    out = {"overall": summarize(obs), "reliability": reliability_table(obs), "by_source": {}}
    for src in sorted({o.source for o in obs}):
        sel = [o for o in obs if o.source == src]
        out["by_source"][src] = {"summary": summarize(sel), "reliability": reliability_table(sel)}
    horizons = sorted({o.horizon_hours for o in obs})
    out["horizon_hours"] = horizons
    return out


def format_report(rep: dict) -> str:
    lines = []
    def block(title, summary, table):
        lines.append(title)
        if summary.get("n", 0) < 5:
            lines.append("  not enough observations")
            return
        c = summary["calibration"]
        lines.append(f"  n={summary['n']} ({summary['events']} events)   mean price {100*summary['mean_price']:.1f}%   "
                     f"realized {100*summary['realized_rate']:.1f}%")
        lines.append(f"  Brier {summary['brier_market']:.4f} vs base rate {summary['brier_base_rate']:.4f}   "
                     f"skill {100*summary['skill_vs_base_rate']:+.1f}%")
        lines.append(f"  calibration slope {c['slope']:.2f} +/- {1.96*c['slope_se']:.2f}   intercept {c['intercept']:+.2f} +/- {1.96*c['intercept_se']:.2f}"
                     "   (1.00 and 0.00 = perfectly calibrated)")
        lines.append(f"  {'bin':<9}{'n':>6}{'price':>8}{'realized':>10}{'gap':>8}{'95% interval':>18}  price inside?")
        for r in table:
            lines.append(f"  {r['bin']:<9}{r['n']:>6}{100*r['mean_price']:>7.1f}%{100*r['realized']:>9.1f}%"
                         f"{100*r['gap']:>+7.1f}{'':>3}{100*r['ci_low']:>5.1f}% to {100*r['ci_high']:>5.1f}%  "
                         f"{'yes' if r['price_inside_ci'] else 'NO'}")
    block("ALL SOURCES", rep["overall"], rep["reliability"])
    for src, d in rep["by_source"].items():
        lines.append("")
        block(src.upper(), d["summary"], d["reliability"])
    return "\n".join(lines)
