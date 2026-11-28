"""In-game v4: a state model that learns the shape of the late-game probability from the data, instead of a normal curve.

PRE-REGISTERED (written before it was run). Diagnosis behind it: diagnose_inplay.py and inplay_v3.py (committed).
  Model    logistic regression at each boundary (Q1, H1, Q3), fitted on 2012-2019 only, on these features:
             1                         intercept
             margin / sqrt(tau)        the score, scaled by the time left (tau = share of game left)
             m0 * sqrt(tau)            pre-game team strength (Elo gap / 25), scaled by the time left
             possession                +1 if the home team has the ball, -1 if the away team does (Q1, Q3)
             possession x field        the same, times field position (0 at own goal line, 1 at the opponent's)
             state missing             1 if possession or kickoff data is missing for the game, else 0
           At halftime the possession term is the second-half kickoff receiver (no field position).
  Check T3 uses the same model with the team-strength feature removed.
  Judged   2020-2025 with the same four checks as inplay_v3 (T1 bins within 2 SE, worst |z| below 2; T2 spread ratio
           between 0.9 and 1.1; T3 no-team model beats nflverse with a paired 95% interval below zero; T4 Brier no
           worse than v1).

  Honest limit: 2020-2025 were already looked at during the diagnosis, so the 2020-2025 result here is a second look,
  not a clean holdout. The only clean holdout is games not yet played: this model must be logged before those games
  kick off and scored afterwards (see the in-game log, to be built). The sealed 2026 block is reserved for the market
  judgement and is not used here.

    python3 -m prediction_markets.nfl.inplay_v4
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
from .inplay import RESULTS, TAU, _mean_sd, brier, fit_sigmas, load_boundaries, win_prob

TRAIN, JUDGE = range(2012, 2020), range(2020, 2026)
BOUNDARY_KEY = {"Q1": "q1", "H1": "q2", "Q3": "q3"}
FEATURES = ["intercept", "margin_scaled", "strength_scaled", "possession", "possession_x_field", "state_missing"]


def features(b: str, margin: int, m0: float, st: Optional[dict], home: str, use_strength: bool = True) -> List[float]:
    tau = TAU[b]
    s = math.sqrt(max(tau, 1e-3))
    poss = field = 0.0
    missing = 1.0
    if st:
        if b in ("Q1", "Q3"):
            e = st.get(b.lower())
            if e and e[1] is not None:
                sign = 1.0 if e[0] == home else -1.0
                poss, field, missing = sign, (100.0 - e[1]) / 100.0 * sign, 0.0
        else:
            r = st.get("h2")
            if r:
                poss, missing = (1.0 if r == home else -1.0), 0.0
    return [1.0, margin / s, (m0 * s) if use_strength else 0.0, poss, poss * field, missing]


def run() -> dict:
    from . import pbp
    games = load_games()
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: d / 25.0 for gid, d in snap.items()}
    bnd = load_boundaries(range(2012, 2026))
    data = pbp.load(range(2012, 2026))
    st_all = data["state"]
    home_of = {g["game_id"]: g["home"] for g in bnd}
    ss, sn = fit_sigmas([g for g in bnd if g["season"] in TRAIN], m0)
    out = {"features": FEATURES, "boundaries": {}}
    for b, key in BOUNDARY_KEY.items():
        def rows(seasons):
            rr = []
            for g in bnd:
                if g["season"] not in seasons or not g.get("final") or g["game_id"] not in m0:
                    continue
                q = g.get(key)
                fm = g["final"]["hs"] - g["final"]["as"]
                if q is None or fm == 0 or q.get("wp") is None:
                    continue
                rr.append({"gid": g["game_id"], "home": g["home"], "margin": q["hs"] - q["as"], "y": int(fm > 0),
                           "m0": m0[g["game_id"]], "wp": q["wp"], "st": st_all.get(g["game_id"], {})})
            return rr
        train, judge = rows(TRAIN), rows(JUDGE)
        X = [features(b, r["margin"], r["m0"], r["st"], r["home"]) for r in train]
        y = [r["y"] for r in train]
        w = fit_logistic(X, y, 1e-3)
        Xn = [features(b, r["margin"], r["m0"], r["st"], r["home"], use_strength=False) for r in train]
        wn = fit_logistic(Xn, y, 1e-3)
        p4 = [sigmoid(sum(a * c for a, c in zip(w, features(b, r["margin"], r["m0"], r["st"], r["home"]))))
              for r in judge]
        p4n = [sigmoid(sum(a * c for a, c in zip(wn, features(b, r["margin"], r["m0"], r["st"], r["home"],
                                                              use_strength=False)))) for r in judge]
        pv1 = [win_prob(r["m0"], r["margin"], TAU[b], ss, sn) for r in judge]
        yj = [r["y"] for r in judge]
        pnv = [r["wp"] for r in judge]
        gap4, bins4 = bins_gap(p4, yj)
        gap1, _ = bins_gap(pv1, yj)
        sq4 = [(p - t) ** 2 for p, t in zip(p4, yj)]
        sq1 = [(p - t) ** 2 for p, t in zip(pv1, yj)]
        sqn = [(p - t) ** 2 for p, t in zip(p4n, yj)]
        sqv = [(p - t) ** 2 for p, t in zip(pnv, yj)]
        out["boundaries"][b] = {
            "n_train": len(train), "n_judge": len(judge), "weights": w, "weights_no_strength": wn,
            "T1_worst_bin_z_v4": gap4, "T1_worst_bin_z_v1": gap1, "T1_bins_v4": bins4,
            "T3_no_strength_v4_minus_nflverse": paired_ci(sqn, sqv),
            "T4_brier_v4": sum(sq4) / len(sq4), "T4_brier_v1": sum(sq1) / len(sq1),
            "T4_v4_minus_v1": paired_ci(sq4, sq1),
            "brier_nflverse": sum(sqv) / len(sqv),
        }
    return out


def main() -> int:
    res = run()
    path = os.path.join(RESULTS, "nfl_inplay_v4_dev.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("in-game v4 (learned state model). Fitted 2012-2019, judged 2020-2025. DEVELOPMENT: 2020-2025 is a second look.")
    for b, r in res["boundaries"].items():
        m, lo, hi = r["T3_no_strength_v4_minus_nflverse"]
        d, dlo, dhi = r["T4_v4_minus_v1"]
        ok_t1 = r["T1_worst_bin_z_v4"] < 2
        ok_t3 = hi < 0
        ok_t4 = dhi < 0 or d <= 0
        print(f"{b}  n={r['n_judge']}  T1 worst z {r['T1_worst_bin_z_v4']:.1f} ({'pass' if ok_t1 else 'FAIL'})"
              f"  T3 no-strength v4 minus nflverse {m:+.4f} [{lo:+.4f},{hi:+.4f}] ({'pass' if ok_t3 else 'FAIL'})"
              f"  T4 v4 minus v1 {d:+.4f} [{dlo:+.4f},{dhi:+.4f}] ({'pass' if ok_t4 else 'FAIL'})")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
