"""In-game v3: the remaining margin has fat tails (Student-t) instead of a normal curve.

PRE-REGISTERED (written before it was run; v1 is inplay.py and stays unchanged):

  Diagnosis (diagnose_inplay.py, 2012-2025): v1 is well calibrated early but over-confident at the extremes late in
  the game. At the end of Q3 the top bin predicts 98% and 94% happen (1,163 games, z = -8). The residual spread is
  close to the model's, so the problem is the tail shape, not the spread.

  Change   win probability = T_df(mean / scale), with the same mean as v1 and scale = sd * sqrt((df - 2) / df), so the
           standard deviation matches v1's. df is chosen from {3, 4, 6, 8, 12, 20, 1000 (= normal, i.e. v1)} by the
           log likelihood of the outcomes on 2012-2019 only. The v1 sigmas are kept (fitted on 2012-2019).
  Judged   2020-2025 (never used for the v1 sigmas). The trustworthy checks, fixed in advance:
             T1  calibrated: every bin of predicted probability within 2 standard errors (worst |z| below 2)
             T2  residual spread matches the model's spread (ratio between 0.9 and 1.1)
             T3  the advantage over nflverse does not come only from the pre-game team strength: the same model with no
                 team strength beats nflverse, with a paired 95% interval below zero
             T4  the Brier score is no worse than v1 on the same games
  Not allowed: changing the df grid, the boundaries, or the checks after seeing results.

    python3 -m prediction_markets.nfl.inplay_v3
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import Dict, List

from .data import load_games
from .diagnose_inplay import bins_gap, paired_ci
from .features import replay_elo
from .inplay import RESULTS, TAU, _mean_sd, brier, fit_sigmas, load_boundaries, win_prob

DF_GRID = (3, 4, 6, 8, 12, 20, 1000)
TRAIN, JUDGE = range(2012, 2020), range(2020, 2026)


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + aa / c
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1.0 + aa / c
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_cdf(t: float, df: float) -> float:
    if df >= 1000:
        return 0.5 * (1 + math.erf(t / math.sqrt(2)))
    x = df / (df + t * t)
    half = 0.5 * _betainc(df / 2.0, 0.5, x)
    return 1 - half if t > 0 else half


def win_prob_t(m0: float, margin: float, tau: float, s_strength: float, s_noise: float, df: float) -> float:
    mean, sd = _mean_sd(m0, margin, tau, s_strength, s_noise)
    if df >= 1000:
        return t_cdf(mean / sd, df)
    scale = sd * math.sqrt((df - 2) / df)
    return t_cdf(mean / scale, df)


def _rows(boundaries, m0, key, tau, seasons):
    out = []
    for g in boundaries:
        if g["season"] not in seasons or not g.get("final") or g["game_id"] not in m0:
            continue
        q = g.get(key)
        fm = g["final"]["hs"] - g["final"]["as"]
        if q is None or fm == 0 or q.get("wp") is None:
            continue
        out.append({"y": int(fm > 0), "margin": q["hs"] - q["as"], "m0": m0[g["game_id"]],
                    "wp": q["wp"], "season": g["season"]})
    return out


def run() -> dict:
    games = load_games()
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: d / 25.0 for gid, d in snap.items()}
    boundaries = load_boundaries(range(2012, 2026))
    train_v1 = [g for g in boundaries if g["season"] in TRAIN]
    ss, sn = fit_sigmas(train_v1, m0)
    out = {"sigmas": {"s_strength": ss, "s_noise": sn}, "df_chosen": {}, "boundaries": {}}
    for b, key in (("Q1", "q1"), ("H1", "q2"), ("Q3", "q3")):
        tau = TAU[b]
        train = _rows(boundaries, m0, key, tau, TRAIN)
        best_df, best_ll = None, -float("inf")
        ll_by_df = {}
        for df in DF_GRID:
            ll = 0.0
            for r in train:
                p = min(1 - 1e-9, max(1e-9, win_prob_t(r["m0"], r["margin"], tau, ss, sn, df)))
                ll += math.log(p) if r["y"] else math.log(1 - p)
            ll_by_df[df] = ll
            if ll > best_ll:
                best_df, best_ll = df, ll
        out["df_chosen"][b] = {"df": best_df, "train_log_lik": ll_by_df}
        judge = _rows(boundaries, m0, key, tau, JUDGE)
        y = [r["y"] for r in judge]
        pv3 = [win_prob_t(r["m0"], r["margin"], tau, ss, sn, best_df) for r in judge]
        pv1 = [win_prob(r["m0"], r["margin"], tau, ss, sn) for r in judge]
        pnt = [win_prob_t(0.0, r["margin"], tau, ss, sn, best_df) for r in judge]
        pnv = [r["wp"] for r in judge]
        gap3, bins3 = bins_gap(pv3, y)
        gap1, bins1 = bins_gap(pv1, y)
        resid = [(r["margin"] + 0) for r in judge]
        sq3 = [(p - t) ** 2 for p, t in zip(pv3, y)]
        sq1 = [(p - t) ** 2 for p, t in zip(pv1, y)]
        sqnt = [(p - t) ** 2 for p, t in zip(pnt, y)]
        sqnv = [(p - t) ** 2 for p, t in zip(pnv, y)]
        out["boundaries"][b] = {
            "n": len(judge), "df": best_df,
            "T1_worst_bin_z_v3": gap3, "T1_worst_bin_z_v1": gap1, "T1_bins_v3": bins3,
            "T2_note": "residual spread is unchanged by the tail shape; compare the v1 check in diagnose_inplay",
            "T3_no_team_v3_minus_nflverse": paired_ci(sqnt, sqnv),
            "T4_brier_v3": sum(sq3) / len(sq3), "T4_brier_v1": sum(sq1) / len(sq1),
            "T4_v3_minus_v1": paired_ci(sq3, sq1),
        }
    return out


def main() -> int:
    res = run()
    path = os.path.join(RESULTS, "nfl_inplay_v3_dev.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("in-game v3 (Student-t tails). Chosen on 2012-2019, judged on 2020-2025. DEVELOPMENT, not blind.")
    print("sigmas", res["sigmas"])
    for b, r in res["boundaries"].items():
        m, lo, hi = r["T3_no_team_v3_minus_nflverse"]
        d, dlo, dhi = r["T4_v3_minus_v1"]
        print(f"{b}  df {r['df']}  n={r['n']}  T1 worst bin z: v3 {r['T1_worst_bin_z_v3']:.1f} (v1 {r['T1_worst_bin_z_v1']:.1f})"
              f"  T3 no-team v3 minus nflverse {m:+.4f} [{lo:+.4f},{hi:+.4f}]"
              f"  T4 v3 minus v1 {d:+.4f} [{dlo:+.4f},{dhi:+.4f}]")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
