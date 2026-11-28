"""Search for in-game information that adds to the base state model, with the rules fixed before the search ran.

PRE-REGISTERED
  Base       the v4 features: intercept, margin / sqrt(tau), pre-game strength (m0 * sqrt(tau)), possession,
             possession x field position, state missing.
  Candidates (each is home minus away, at the boundary, from plays up to that boundary only):
    epa_per_play        EPA per play so far
    yards_per_play      yards per play so far
    pass_rate           share of plays that were passes
    first_down_rate     first downs per play
    turnovers           turnovers so far
    timeouts            timeouts remaining
    plays               plays so far
    drives              drives so far
    points_per_drive    points so far per drive
    epa_x_sqrt_tau      epa_per_play scaled by sqrt(tau)  (efficiency counts for more early)
    market_spread       closing spread, scaled by sqrt(tau)  (a MARKET input, reported separately, not an edge)
  Selection  forward, per boundary, on 2012-2016 log loss; the candidate is kept only if it lowers the 2017-2019
             validation log loss. Nothing else is tried.
  Judge      2020-2025, once, after the set is fixed. Two gates, both with paired 95% intervals:
               E1  log loss better than the base model
               E2  Brier better than nflverse's own in-game probability
             and E3 calibration: worst bin z below 2.
  Edge       the edge is claimed only if E1, E2 and E3 all pass. The market feature is reported, but a result that
             needs it is labelled "market-informed", not an edge.
  Status     2020-2025 were already looked at during the diagnosis, so this is a second look. The clean test is games
             logged before kickoff, scored afterwards.

    python3 -m prediction_markets.nfl.feature_search
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Optional

from ..stats import engine as E
from .data import load_games
from .diagnose_inplay import bins_gap, paired_ci
from .features import fit_logistic, replay_elo, sigmoid
from .inplay import RESULTS, TAU, load_boundaries
from .inplay_v4 import features as base_features

PERIOD = {"Q1": "1", "H1": "2", "Q3": "3"}
TRAIN, VAL, JUDGE = range(2012, 2017), range(2017, 2020), range(2020, 2026)
MARKET = {"market_spread"}
CANDIDATES = ["epa_per_play", "yards_per_play", "pass_rate", "first_down_rate", "turnovers", "timeouts", "plays",
              "drives", "points_per_drive", "epa_x_sqrt_tau", "market_spread"]


def _rate(team: dict, key: str) -> float:
    return team.get(key, 0.0)


def candidate_values(b: str, rec: dict, home_pts: int, away_pts: int, spread: Optional[float]) -> Dict[str, float]:
    tau = TAU[b]
    h, a = rec["home"], rec["away"]
    ppd_h = home_pts / h["drives"] if h["drives"] else 0.0
    ppd_a = away_pts / a["drives"] if a["drives"] else 0.0
    epa_d = h["epa_pp"] - a["epa_pp"]
    return {
        "epa_per_play": epa_d,
        "yards_per_play": h["ypp"] - a["ypp"],
        "pass_rate": h["pass_rate"] - a["pass_rate"],
        "first_down_rate": (h["first_downs"] / h["plays"] if h["plays"] else 0.0)
                           - (a["first_downs"] / a["plays"] if a["plays"] else 0.0),
        "turnovers": a["turnovers"] - h["turnovers"],
        "timeouts": rec["home_timeouts"] - rec["away_timeouts"],
        "plays": h["plays"] - a["plays"],
        "drives": h["drives"] - a["drives"],
        "points_per_drive": ppd_h - ppd_a,
        "epa_x_sqrt_tau": epa_d * math.sqrt(max(tau, 1e-3)),
        "market_spread": (spread or 0.0) * math.sqrt(max(tau, 1e-3)),
    }


def build(bnd, m0, states, b: str, key: str, seasons) -> List[dict]:
    out = []
    pk = PERIOD[b]
    for g in bnd:
        if g["season"] not in seasons or not g.get("final") or g["game_id"] not in m0:
            continue
        q = g.get(key)
        fm = g["final"]["hs"] - g["final"]["as"]
        rec = states.get(g["game_id"], {}).get("q", {}).get(pk)
        if q is None or fm == 0 or rec is None:
            continue
        rec = dict(rec)
        rec["home_timeouts"] = rec.get("home_timeouts", 3)
        rec["away_timeouts"] = rec.get("away_timeouts", 3)
        spread = states.get(g["game_id"], {}).get("spread")
        vals = candidate_values(b, rec, q["hs"], q["as"], spread)
        base = base_features(b, q["hs"] - q["as"], m0[g["game_id"]], states.get(g["game_id"], {}).get("st"),
                             g["home"])
        out.append({"y": int(fm > 0), "base": base, "cand": vals, "wp": q.get("wp"), "m0": m0[g["game_id"]],
                    "margin": q["hs"] - q["as"], "home": g["home"], "st": states.get(g["game_id"], {}).get("st"),
                    "season": g["season"]})
    return out


def _std(rows: List[List[float]], ref: List[List[float]]):
    """Standardize every column except the intercept (column 0), which must stay 1."""
    k = len(ref[0])
    mu = [0.0] + [sum(r[i] for r in ref) / len(ref) for i in range(1, k)]
    sd = [1.0] + [math.sqrt(sum((r[i] - mu[i]) ** 2 for r in ref) / len(ref)) or 1.0 for i in range(1, k)]
    return [[(r[i] - mu[i]) / sd[i] for i in range(k)] for r in rows], mu, sd


def _ll(w, X, y) -> float:
    s = 0.0
    for x, t in zip(X, y):
        p = min(1 - 1e-9, max(1e-9, sigmoid(sum(a * c for a, c in zip(w, x)))))
        s += -math.log(p) if t else -math.log(1 - p)
    return s / len(y)


def design(rows, names, cols_base=True):
    X = []
    for r in rows:
        x = list(r["base"]) if cols_base else list(r["base"][1:])
        x += [r["cand"][n] for n in names]
        X.append(x)
    return X


def _val_loss(train, val, names) -> float:
    X = design(train, names)
    Xs, mu, sd = _std(X, X)
    w = fit_logistic(Xs, [r["y"] for r in train], 1e-3)
    return _ll(w, _apply(design(val, names), mu, sd), [r["y"] for r in val])


def search(b: str, train, val, candidates) -> List[str]:
    """Forward selection: add the candidate that most lowers the validation log loss; stop when none helps."""
    chosen: List[str] = []
    best_val = _val_loss(train, val, [])
    while True:
        best_name, best_v = None, best_val
        for c in candidates:
            if c in chosen:
                continue
            v = _val_loss(train, val, chosen + [c])
            if v < best_v - 1e-6:
                best_name, best_v = c, v
        if best_name is None:
            break
        chosen.append(best_name)
        best_val = best_v
    return chosen


def _apply(X, mu, sd):
    return [[(r[i] - mu[i]) / sd[i] for i in range(len(r))] for r in X]


def fit_predict(train, judge, names):
    X = design(train, names)
    Xs, mu, sd = _std(X, X)
    w = fit_logistic(Xs, [r["y"] for r in train], 1e-3)
    Xj = _apply(design(judge, names), mu, sd)
    return [sigmoid(sum(a * c for a, c in zip(w, x))) for x in Xj]


def _pci(a, b):
    m, lo, hi = paired_ci(a, b)
    return {"mean": m, "ci95": [lo, hi]}


def run(boundaries, m0, states, candidates=CANDIDATES) -> dict:
    out = {"candidates": list(candidates), "boundaries": {}}
    for b, key in (("Q1", "q1"), ("H1", "q2"), ("Q3", "q3")):
        train = build(boundaries, m0, states, b, key, TRAIN)
        val = build(boundaries, m0, states, b, key, VAL)
        judge = build(boundaries, m0, states, b, key, JUDGE)
        names = search(b, train, val, candidates)
        p_final = fit_predict(train + val, judge, names)
        p_base = fit_predict(train + val, judge, [])
        y = [r["y"] for r in judge]
        nv = [r["wp"] for r in judge]
        sq_f = [(p - t) ** 2 for p, t in zip(p_final, y)]
        sq_b = [(p - t) ** 2 for p, t in zip(p_base, y)]
        sq_n = [(p - t) ** 2 for p, t in zip(nv, y)]
        ll = lambda ps: sum(-math.log(max(1e-9, p)) if t else -math.log(max(1e-9, 1 - p)) for p, t in zip(ps, y)) / len(y)
        gap, bins = bins_gap(p_final, y)
        non_market = [n for n in names if n not in MARKET]
        out["boundaries"][b] = {
            "selected": names, "selected_non_market": non_market,
            "n_train": len(train) + len(val), "n_judge": len(judge),
            "logloss_base": ll(p_base), "logloss_final": ll(p_final),
            "E1_brier_final_minus_base": _pci(sq_f, sq_b),
            "brier_final": sum(sq_f) / len(sq_f), "brier_nflverse": sum(sq_n) / len(sq_n),
            "E2_final_minus_nflverse": _pci(sq_f, sq_n),
            "E3_worst_bin_z": gap, "E3_bins": bins,
        }
    return out


def main() -> int:
    from . import pbp_state
    games = load_games()
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: d / 25.0 for gid, d in snap.items()}
    bnd = load_boundaries(range(2012, 2026))
    from . import pbp
    st_all = pbp.load(range(2012, 2026))["state"]
    states = {}
    feats = pbp_state.load(range(2012, 2026))
    for gid, rec in feats.items():
        states[gid] = {"q": rec["q"], "st": st_all.get(gid, {}), "spread": None}
    from .team_props import load_lines
    lines = load_lines()
    for gid in states:
        states[gid]["spread"] = (lines.get(gid) or {}).get("spread_line")
    no_market = [c for c in CANDIDATES if c not in MARKET]
    res = {"with_market": run(bnd, m0, states, CANDIDATES), "no_market": run(bnd, m0, states, no_market)}
    path = os.path.join(RESULTS, "nfl_feature_search.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("feature search: selected on 2012-2016 / 2017-2019, judged 2020-2025 (second look). DEVELOPMENT.")
    for label in ("with_market", "no_market"):
        print(f"-- {label}")
        for b, r in res[label]["boundaries"].items():
            e1, e2 = r["E1_brier_final_minus_base"], r["E2_final_minus_nflverse"]
            print(f"{b}  selected {r['selected']}  E1 {e1['mean']:+.4f} [{e1['ci95'][0]:+.4f},{e1['ci95'][1]:+.4f}]"
                  f"  E2 {e2['mean']:+.4f} [{e2['ci95'][0]:+.4f},{e2['ci95'][1]:+.4f}]  E3 worst z {r['E3_worst_bin_z']:.1f}")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
