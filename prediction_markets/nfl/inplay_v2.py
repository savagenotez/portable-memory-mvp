"""In-game v2: adds who has the ball and where, and tries the closing spread as the pre-game prior.

PRE-REGISTERED (written before v2 was scored; v1 is inplay.py and stays unchanged):

  State term added to the expected final margin (home minus away):
    end of Q1 and Q3   s * (a + b * f)   s = +1 if the home team has the ball, -1 if the away team does;
                                         f = field position, 0 at the offence's own goal line, 1 at the opponent's.
    halftime           s2 * c            s2 = +1 if the home team receives the second-half kickoff.
  a, b and c are fitted by least squares on 2012-2019, on the part of the final margin that the score and the
  pre-game prior do not explain. Then the two uncertainty terms are refitted on 2012-2019 as in v1.

  Two pre-game priors, each fitted separately:
    elo     the Elo gap / 25 points, as in v1 (no market information)
    line    the closing point spread from the nflverse games file. This uses the market's pre-game line, so it
            measures what the in-game part adds to the line, not a model independent of the market.

  Scored at the end of Q1, at halftime and at the end of Q3 on 2020-2025 against v1, nflverse's in-game probability
  and the spread-based probability, with paired 95% intervals. DEVELOPMENT, not blind: v1 was scored on the same
  games.

    python3 -m prediction_markets.nfl.inplay_v2
"""

from __future__ import annotations

import json
import math
import os
import random
from typing import Dict, List, Optional, Tuple

from .features import replay_elo
from .inplay import JUDGE, RESULTS, TAU, TRAIN, _phi, brier, fit_sigmas, load_boundaries, win_prob

BOUNDARY_KEY = {"Q1": "q1", "H1": "q2", "Q3": "q3"}


def state_x(b: str, home: str, st: Optional[dict]) -> Optional[List[float]]:
    """Regressors for the state term, home-signed. None when the state is unknown."""
    if not st:
        return None
    if b in ("Q1", "Q3"):
        s = st.get(b.lower())
        if not s or s[1] is None:
            return None
        sign = 1.0 if s[0] == home else -1.0
        f = (100.0 - s[1]) / 100.0
        return [sign, sign * f, 0.0]
    r = st.get("h2")
    if not r:
        return None
    return [0.0, 0.0, 1.0 if r == home else -1.0]


def _lstsq(X: List[List[float]], y: List[float]) -> List[float]:
    n = len(X[0])
    A = [[sum(x[i] * x[j] for x in X) + (1e-6 if i == j else 0.0) for j in range(n)] for i in range(n)]
    v = [sum(x[i] * t for x, t in zip(X, y)) for i in range(n)]
    for i in range(n):                                       # Gauss-Jordan
        p = A[i][i]
        for j in range(n):
            A[i][j] /= p
        v[i] /= p
        for k in range(n):
            if k != i:
                f = A[k][i]
                for j in range(n):
                    A[k][j] -= f * A[i][j]
                v[k] -= f * v[i]
    return v


def evaluate(boundaries: List[dict], games, states: Dict[str, dict], spread: Dict[str, Optional[float]]) -> dict:
    from .blind import assert_not_sealed
    assert_not_sealed([g["game_id"] for g in boundaries], "in-game v2")
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    priors = {"elo": {gid: d / 25.0 for gid, d in snap.items()},
              "line": {gid: s for gid, s in spread.items() if s is not None}}
    v1_sig = fit_sigmas([g for g in boundaries if g["season"] in TRAIN], priors["elo"])
    out = {"label": "IN-GAME v2, DEVELOPMENT, NOT BLIND. Fitted on 2012-2019, scored on 2020-2025.", "variants": {}}
    for name, m0 in priors.items():
        # 1. state coefficients on dev
        X, y = [], []
        for g in boundaries:
            if g["season"] not in TRAIN or g.get("final") is None or g["game_id"] not in m0:
                continue
            fm = g["final"]["hs"] - g["final"]["as"]
            for b, key in BOUNDARY_KEY.items():
                q = g.get(key)
                x = state_x(b, g["home"], states.get(g["game_id"]))
                if q is None or x is None:
                    continue
                X.append(x)
                y.append(fm - (q["hs"] - q["as"]) - m0[g["game_id"]] * TAU[b])
        coef = _lstsq(X, y)
        # 2. uncertainty on dev, with the state term folded into the margin
        shifted = []
        for g in boundaries:
            if g["season"] not in TRAIN or g["game_id"] not in m0:
                continue
            h = dict(g)
            for b, key in BOUNDARY_KEY.items():
                q, x = g.get(key), state_x(b, g["home"], states.get(g["game_id"]))
                if q is not None and x is not None:
                    adj = sum(c * v for c, v in zip(coef, x))
                    h[key] = {**q, "hs": q["hs"] + adj}
            shifted.append(h)
        ss, sn = fit_sigmas(shifted, m0)
        # 3. score on the judged seasons
        rows = {b: {"v2": [], "v1": [], "nflverse": [], "spread": [], "y": []} for b in BOUNDARY_KEY}
        for g in boundaries:
            if g["season"] not in JUDGE or g.get("final") is None or g["game_id"] not in m0 \
                    or g["game_id"] not in priors["elo"]:
                continue
            fm = g["final"]["hs"] - g["final"]["as"]
            if fm == 0:
                continue
            yv = int(fm > 0)
            for b, key in BOUNDARY_KEY.items():
                q = g.get(key)
                x = state_x(b, g["home"], states.get(g["game_id"]))
                if q is None or x is None or q.get("wp") is None or q.get("vw") is None:
                    continue
                margin = q["hs"] - q["as"]
                adj = sum(c * v for c, v in zip(coef, x))
                rows[b]["v2"].append(win_prob(m0[g["game_id"]], margin + adj, TAU[b], ss, sn))
                rows[b]["v1"].append(win_prob(priors["elo"][g["game_id"]], margin, TAU[b], *v1_sig))
                rows[b]["nflverse"].append(q["wp"])
                rows[b]["spread"].append(q["vw"])
                rows[b]["y"].append(yv)
        res = {"state_coefficients": {"a_possession": coef[0], "b_field_position": coef[1],
                                      "c_second_half_kickoff": coef[2], "n_dev": len(y)},
               "fitted": {"s_strength": ss, "s_noise": sn}, "boundaries": {}}
        for b, v in rows.items():
            sq = lambda k: [(p - t) ** 2 for p, t in zip(v[k], v["y"])]
            res["boundaries"][b] = {"n": len(v["y"]), **{f"brier_{k}": brier(v[k], v["y"]) for k in
                                                         ("v2", "v1", "nflverse", "spread")},
                                    **{f"v2_minus_{k}": _paired(sq("v2"), sq(k)) for k in ("v1", "nflverse", "spread")}}
        out["variants"][name] = res
    return out


def _paired(a, b, n=2000, seed=5):
    d = [x - y for x, y in zip(a, b)]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return {"mean": sum(d) / len(d), "ci95": [boots[int(0.025 * n)], boots[int(0.975 * n) - 1]], "n": len(d)}


def main(argv=None) -> int:
    from . import pbp
    from .data import load_games
    from .team_props import load_lines
    seasons = range(min(TRAIN), max(JUDGE) + 1)
    data = pbp.load(seasons)
    lines = load_lines()
    res = evaluate(load_boundaries(seasons), load_games(), data["state"],
                   {gid: v["spread_line"] for gid, v in lines.items()})
    path = os.path.join(RESULTS, "nfl_inplay_v2_dev.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(res["label"])
    for name, v in res["variants"].items():
        c = v["state_coefficients"]
        print(f"prior = {name}: possession {c['a_possession']:+.2f} + {c['b_field_position']:+.2f} x field position, "
              f"second-half kickoff {c['c_second_half_kickoff']:+.2f} points; sigmas {v['fitted']}")
        for b, r in v["boundaries"].items():
            parts = "  ".join(f"minus {k} {r[f'v2_minus_{k}']['mean']:+.4f} [{r[f'v2_minus_{k}']['ci95'][0]:+.4f},"
                              f"{r[f'v2_minus_{k}']['ci95'][1]:+.4f}]" for k in ("v1", "nflverse", "spread"))
            print(f"  {b}  n={r['n']}  v2 {r['brier_v2']:.4f}  v1 {r['brier_v1']:.4f}  nflverse {r['brier_nflverse']:.4f}"
                  f"  spread-based {r['brier_spread']:.4f}   {parts}")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
