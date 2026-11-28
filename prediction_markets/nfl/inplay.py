"""In-game predictions: the win probability and the period winner, at each quarter and half.

PRE-REGISTERED RULES (written before any in-game result was computed):

  Boundaries, scored at the end of each: Q1 (after quarter 1), H1 (end of the second quarter, halftime), Q3 (end of
  the third quarter), FINAL (end of the game). Scores come from the last play of each period.

  Model: the expected final margin for the home team is
      m0 * tau + M,      m0 = pre-game Elo gap (incl. home edge, K 30) / 25 points
  where M is the margin so far and tau is the share of the game left (0.75, 0.5, 0.25, 0).
  Uncertainty of the final margin: variance = s_strength^2 * tau^2 + s_noise^2 * tau.
  s_strength and s_noise are fitted by maximum likelihood on the 2012-2019 seasons only.
  Game win probability = Phi(mean / sd).

  Period winner (Q1, Q2, Q3, Q4 and the two halves): the same form with the period's share of the game and no score
  carried in. Judged on the 2020-2025 seasons.

  Judged against two references, both fixed in advance:
    * the pre-game prior: the Elo-based probability with no in-game information (should be beaten by any useful
      in-game model);
    * nflverse's own in-game win probability (home_wp, a published model, not the market). It uses far more
      information than this model, so beating it is not expected. It is reported to show the gap.

  Not allowed: changing the boundaries, the features, the training seasons, or the references after seeing results.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import random
import os
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from ..realdata import http
from .data import load_games
from .features import replay_elo

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data", "nflverse")
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.csv.gz"
TAU = {"Q1": 0.75, "H1": 0.5, "Q3": 0.25, "FINAL": 0.0}
SHARE = {"Q1": 0.25, "Q2": 0.25, "Q3": 0.25, "Q4": 0.25}
TRAIN = range(2012, 2020)
JUDGE = range(2020, 2026)


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _f(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def derive_boundaries(rows: Iterable[dict]) -> List[dict]:
    """One record per game: the score and nflverse's home win probability at the last play of each period."""
    last: Dict[tuple, dict] = {}
    games: Dict[str, dict] = {}
    for r in rows:
        gid = r.get("game_id")
        pid = _f(r.get("play_id"))
        qtr = r.get("qtr")
        if not gid or pid is None or qtr not in ("1", "2", "3", "4", "5"):
            continue
        hs, as_ = _f(r.get("total_home_score")), _f(r.get("total_away_score"))
        if hs is None or as_ is None:
            continue
        g = games.setdefault(gid, {"game_id": gid, "season": int(float(r["season"])), "week": int(float(r["week"])),
                                   "home": r["home_team"], "away": r["away_team"], "start_wp": None})
        if g["start_wp"] is None and _f(r.get("home_wp")) is not None:
            g["start_wp"] = _f(r.get("home_wp"))
        key = (gid, qtr)
        if key not in last or pid > last[key]["pid"]:
            last[key] = {"pid": pid, "hs": hs, "as": as_, "wp": _f(r.get("home_wp")),
                         "vw": _f(r.get("vegas_home_wp"))}
        g["final_key"] = (gid, "final")
        if "final" not in g or pid > g["final"]["pid"]:
            g["final"] = {"pid": pid, "hs": hs, "as": as_}
    out = []
    for gid, g in games.items():
        rec = dict(g)
        rec.pop("final", None)
        rec.pop("final_key", None)
        for q in ("1", "2", "3", "4"):
            v = last.get((gid, q))
            rec[f"q{q}"] = None if v is None else {"hs": v["hs"], "as": v["as"], "wp": v["wp"], "vw": v["vw"]}
        f = games[gid].get("final")
        rec["final"] = None if f is None else {"hs": f["hs"], "as": f["as"]}
        out.append(rec)
    return out


def load_boundaries(seasons: Iterable[int], refresh: bool = False) -> List[dict]:
    """Derived per-game boundaries, cached per season. The raw play-by-play is read as a stream and not kept."""
    os.makedirs(CACHE, exist_ok=True)
    out: List[dict] = []
    for y in seasons:
        path = os.path.join(CACHE, f"inplay_{y}.json")
        if os.path.exists(path) and not refresh:
            with open(path, encoding="utf-8") as fh:
                out.extend(json.load(fh))
            continue
        raw = http.get_release_bytes(PBP_URL.format(y=y))
        rows = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8"))
        recs = derive_boundaries(rows)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(recs, fh)
        out.extend(recs)
    return out


def _mean_sd(m0: float, margin: float, tau: float, s_strength: float, s_noise: float):
    mean = margin + m0 * tau
    var = (s_strength ** 2) * tau * tau + (s_noise ** 2) * tau
    return mean, math.sqrt(max(var, 1e-6))


def win_prob(m0: float, margin: float, tau: float, s_strength: float, s_noise: float) -> float:
    mean, sd = _mean_sd(m0, margin, tau, s_strength, s_noise)
    return _phi(mean / sd)


def fit_sigmas(train: List[dict], m0_by_game: Dict[str, float]):
    """Grid search for (s_strength, s_noise) by log likelihood of final margins, on training seasons only."""
    obs = []
    for g in train:
        if g.get("final") is None or g["game_id"] not in m0_by_game:
            continue
        final_margin = g["final"]["hs"] - g["final"]["as"]
        for b in ("Q1", "H1", "Q3", "FINAL"):
            q = {"Q1": g.get("q1"), "H1": g.get("q2"), "Q3": g.get("q3"), "FINAL": g.get("final")}[b]
            if q is None:
                continue
            margin = q["hs"] - q["as"]
            obs.append((m0_by_game[g["game_id"]], margin, TAU[b], final_margin))
    best = None
    grid = [4 + i for i in range(0, 14)]
    for ss in [x / 4 for x in range(0, 25)]:
        for sn in grid:
            ll = 0.0
            for m0, margin, tau, fm in obs:
                mean, sd = _mean_sd(m0, margin, tau, ss, sn)
                z = (fm - mean) / sd
                ll += -math.log(sd) - 0.5 * z * z
            if best is None or ll > best[0]:
                best = (ll, ss, sn)
    return best[1], best[2]


def brier(p: List[float], y: List[int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(p, y)) / len(y)


def _period_margins(g: dict) -> Optional[Dict[str, int]]:
    try:
        q1, q2, q3, q4, fin = g["q1"], g["q2"], g["q3"], g["q4"], g["final"]
    except KeyError:
        return None
    if None in (q1, q2, q3, q4, fin):
        return None
    m = lambda a, b: (a["hs"] - a["as"]) - (b["hs"] - b["as"]) if b is not None else None
    zero = {"hs": 0, "as": 0}
    out = {"Q1": q1["hs"] - q1["as"], "Q2": m(q2, q1), "Q3": m(q3, q2), "Q4": m(fin, q3),
           "H1": q2["hs"] - q2["as"], "H2": (fin["hs"] - fin["as"]) - (q2["hs"] - q2["as"])}
    return out


def evaluate(boundaries: List[dict], games) -> dict:
    """Fit on TRAIN, score on JUDGE. Returns Brier scores against the pre-game prior and nflverse's in-game model."""
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: diff / 25.0 for gid, diff in snap.items()}
    train = [g for g in boundaries if g["season"] in TRAIN]
    judge = [g for g in boundaries if g["season"] in JUDGE]
    s_strength, s_noise = fit_sigmas(train, m0)

    bnd = {b: {"model": [], "prior": [], "nflverse": [], "vegas": [], "y": []} for b in TAU}
    per = {p: {"model": [], "y": []} for p in ("Q1", "Q2", "Q3", "Q4", "H1", "H2")}
    for g in judge:
        if g.get("final") is None or g["game_id"] not in m0:
            continue
        fm = g["final"]["hs"] - g["final"]["as"]
        if fm == 0:
            continue
        y = 1 if fm > 0 else 0
        mm = m0[g["game_id"]]
        for b, q in (("Q1", g.get("q1")), ("H1", g.get("q2")), ("Q3", g.get("q3"))):   # FINAL is the outcome, not a forecast
            if q is None:
                continue
            margin = q["hs"] - q["as"]
            bnd[b]["model"].append(win_prob(mm, margin, TAU[b], s_strength, s_noise))
            bnd[b]["prior"].append(win_prob(mm, 0.0, 1.0, s_strength, s_noise))
            wp = q.get("wp")
            bnd[b]["nflverse"].append(wp if wp is not None else float("nan"))
            vw = q.get("vw")
            bnd[b]["vegas"].append(vw if vw is not None else float("nan"))
            bnd[b]["y"].append(y)
        pm = _period_margins(g)
        if pm is None:
            continue
        for p, share in (("Q1", .25), ("Q2", .25), ("Q3", .25), ("Q4", .25), ("H1", .5), ("H2", .5)):
            d = pm[p]
            if d is None or d == 0:
                continue
            mean = mm * share
            sd = math.sqrt((s_strength ** 2) * share * share + (s_noise ** 2) * share)
            per[p]["model"].append(_phi(mean / sd))
            per[p]["y"].append(1 if d > 0 else 0)

    def paired(a, b, n=2000, seed=7):
        d = [x - y for x, y in zip(a, b)]
        rng = random.Random(seed)
        boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
        return {"mean": sum(d) / len(d), "ci95": [boots[int(0.025 * n)], boots[int(0.975 * n) - 1]], "n": len(d)}

    def summary(d):
        out = {}
        for k, v in d.items():
            n = len(v["y"])
            if n == 0:
                continue
            row = {"n": n, "brier_model": brier(v["model"], v["y"])}
            if "prior" in v:
                row["brier_pregame_prior"] = brier(v["prior"], v["y"])
                for ref_key, out_key in (("nflverse", "nflverse"), ("vegas", "spread_based")):
                    keep = [i for i, a in enumerate(v[ref_key]) if a == a]
                    row[f"n_{out_key}"] = len(keep)
                    if not keep:
                        continue
                    yy = [v["y"][i] for i in keep]
                    mm_ = [v["model"][i] for i in keep]
                    rr_ = [v[ref_key][i] for i in keep]
                    row[f"brier_{out_key}_same_games"] = brier(rr_, yy)
                    row[f"brier_model_vs_{out_key}_games"] = brier(mm_, yy)
                    row[f"model_minus_{out_key}"] = paired(
                        [(a - c) ** 2 for a, c in zip(mm_, yy)], [(a - c) ** 2 for a, c in zip(rr_, yy)])
                pp_all = v["prior"]
                row["model_minus_prior"] = paired(
                    [(a - c) ** 2 for a, c in zip(v["model"], v["y"])], [(a - c) ** 2 for a, c in zip(pp_all, v["y"])])
            out[k] = row
        return out

    return {"label": "IN-GAME, DEVELOPMENT. Fitted on 2012-2019, scored on 2020-2025. The pre-game prior and the "
                     "nflverse in-game model are the references; the market is not part of this test.",
            "fitted": {"s_strength": s_strength, "s_noise": s_noise},
            "game_boundaries": summary(bnd), "period_winners": summary(per)}


def main(argv=None) -> int:
    import argparse
    from .data import load_games
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.inplay")
    ap.add_argument("cmd", choices=["build", "evaluate"])
    args = ap.parse_args(argv)
    if args.cmd == "build":
        recs = load_boundaries(range(2012, 2026))
        print(f"games with boundaries: {len(recs)}")
        return 0
    recs = load_boundaries(range(2012, 2026))
    games = load_games()
    res = evaluate(recs, games)
    path = os.path.join(RESULTS, "nfl_inplay_dev.json")
    os.makedirs(RESULTS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(res["label"])
    print("fitted:", res["fitted"])
    for b, row in res["game_boundaries"].items():
        print(f"  {b:<6} n={row['n']:>4}  model {row['brier_model']:.4f}  pre-game prior {row['brier_pregame_prior']:.4f}")
        for key, label in (("nflverse", "nflverse in-game"), ("spread_based", "spread-based (closing line)")):
            if f"brier_{key}_same_games" in row:
                d = row[f"model_minus_{key}"]
                print(f"         vs {label:<28} {row[f'brier_{key}_same_games']:.4f}   model minus it "
                      f"{d['mean']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]  n={d['n']}")
    for p, row in res["period_winners"].items():
        print(f"  period {p:<3} n={row['n']:>4}  model {row['brier_model']:.4f}  (coin flip = 0.2500)")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
