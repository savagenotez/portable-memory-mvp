"""Diagnostic (no rule changed): why the in-game model beats nflverse early but not at the end of Q3.

TRUSTWORTHY means, fixed before this was run, at each boundary (Q1, H1, Q3):
  T1  calibrated: in every bin of predicted probability, the observed rate is within 2 standard errors
  T2  the residual spread of the final margin matches the model's spread (the sigma model is right in shape)
  T3  the advantage over nflverse does not come from the pre-game team strength alone (removing it keeps the edge)
  T4  the advantage over nflverse survives the state of the game (possession and field position)

Data: 2012-2025 in-game boundaries. This is diagnosis, not a new test: it uses the same fitted sigmas as v1.
"""
from __future__ import annotations

import json
import math
import os
import random
from collections import defaultdict

from .data import load_games
from .features import replay_elo
from .inplay import RESULTS, TAU, _phi, load_boundaries, win_prob

KEYS = {"Q1": "q1", "H1": "q2", "Q3": "q3"}


def bins_gap(p, y, n_bins=10):
    buckets = defaultdict(lambda: [0.0, 0.0, 0])
    for pi, yi in zip(p, y):
        b = min(n_bins - 1, int(pi * n_bins))
        buckets[b][0] += pi
        buckets[b][1] += yi
        buckets[b][2] += 1
    worst, detail = 0.0, []
    for b in sorted(buckets):
        sp, sy, n = buckets[b]
        pm, om = sp / n, sy / n
        se = math.sqrt(max(pm * (1 - pm), 1e-6) / n)
        z = (om - pm) / se
        worst = max(worst, abs(z))
        detail.append((round(pm, 2), round(om, 2), n, round(z, 1)))
    return worst, detail


def paired_ci(a, b, n=2000, seed=3):
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return sum(d) / len(d), boots[int(0.025 * n)], boots[int(0.975 * n) - 1]


def main() -> int:
    with open(os.path.join(RESULTS, "nfl_inplay_dev.json"), encoding="utf-8") as fh:
        fitted = json.load(fh)["fitted"]
    ss, sn = fitted["s_strength"], fitted["s_noise"]
    games = load_games()
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: d / 25.0 for gid, d in snap.items()}
    rows = [g for g in load_boundaries(range(2012, 2026)) if g.get("final") and g["game_id"] in m0]
    out = {"fitted": fitted, "boundaries": {}}
    for b, key in KEYS.items():
        tau = TAU[b]
        recs = []
        for g in rows:
            q = g.get(key)
            fm = g["final"]["hs"] - g["final"]["as"]
            if q is None or fm == 0 or q.get("wp") is None:
                continue
            margin = q["hs"] - q["as"]
            recs.append({"season": g["season"], "y": int(fm > 0), "fm": fm, "margin": margin,
                         "m0": m0[g["game_id"]], "wp": q["wp"],
                         "model": win_prob(m0[g["game_id"]], margin, tau, ss, sn),
                         "no_team": win_prob(0.0, margin, tau, ss, sn)})
        y = [r["y"] for r in recs]
        gap_m, det_m = bins_gap([r["model"] for r in recs], y)
        gap_n, det_n = bins_gap([r["wp"] for r in recs], y)
        resid = [r["fm"] - r["margin"] - r["m0"] * tau for r in recs]
        mean_r = sum(resid) / len(resid)
        sd_emp = math.sqrt(sum((x - mean_r) ** 2 for x in resid) / (len(resid) - 1))
        sd_model = math.sqrt(ss * ss * tau * tau + sn * sn * tau)
        sq_m = [(r["model"] - t) ** 2 for r, t in zip(recs, y)]
        sq_n = [(r["wp"] - t) ** 2 for r, t in zip(recs, y)]
        sq_nt = [(r["no_team"] - t) ** 2 for r, t in zip(recs, y)]
        out["boundaries"][b] = {
            "n": len(recs),
            "brier_model": sum(sq_m) / len(sq_m), "brier_nflverse": sum(sq_n) / len(sq_n),
            "brier_model_without_team_strength": sum(sq_nt) / len(sq_nt),
            "T1_worst_bin_z_model": gap_m, "T1_worst_bin_z_nflverse": gap_n,
            "T1_bins_model": det_m, "T1_bins_nflverse": det_n,
            "T2_sd_residual_empirical": sd_emp, "T2_sd_model": sd_model,
            "T3_model_minus_nflverse_without_team_strength": paired_ci(sq_nt, sq_n),
            "T3_model_minus_nflverse": paired_ci(sq_m, sq_n),
        }
        r = out["boundaries"][b]
        print(f"{b}  n={r['n']}  model {r['brier_model']:.4f}  nflverse {r['brier_nflverse']:.4f}  "
              f"model with no team strength {r['brier_model_without_team_strength']:.4f}")
        print(f"   T1 worst bin z: model {gap_m:.1f}, nflverse {gap_n:.1f}  (trustworthy if under 2)")
        print(f"   T2 residual sd empirical {sd_emp:.2f} vs model {sd_model:.2f}")
        m, lo, hi = r["T3_model_minus_nflverse_without_team_strength"]
        print(f"   T3 no-team model minus nflverse {m:+.4f} [{lo:+.4f}, {hi:+.4f}]")
        m, lo, hi = r["T3_model_minus_nflverse"]
        print(f"   T3 full model minus nflverse      {m:+.4f} [{lo:+.4f}, {hi:+.4f}]")
    path = os.path.join(RESULTS, "nfl_inplay_diagnosis.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
