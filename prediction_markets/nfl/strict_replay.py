"""Strict replay: old games run as if live, with a cleaner holdout than the earlier development tests.

PRE-REGISTERED (written before this replay was run; it does not change any earlier pre-registered test):

  Choose on   2012-2017 only: the team model's half-life / k0 grid and size r (mean squared error on game TD and
              field-goal-attempt means), and the in-game sigmas.
  Score on    2018-2019 only. Nothing from 2018-2019 is used to choose anything.
  As if live  every forecast uses only games on EARLIER game days (kickoff time is not in the data, so a game is
              never given anything from its own day). Checked by a leak test: changing a game's result must not
              change the forecast made for that game.
  Not included  2020-2025 (already used to choose settings, so not a clean holdout), 2026 sealed games (blind test),
              and the player model (too slow to repeat here; its earlier result stands and is labelled development).
  Market      no historical prices exist for these seasons, so there is no market comparison here.

    python3 -m prediction_markets.nfl.strict_replay
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Sequence

from ..stats import engine as E
from .data import Game, load_games
from .inplay import TAU, _phi, brier, fit_sigmas, load_boundaries, win_prob
from .features import replay_elo
from .team_props import GRID, LINES, RESULTS, TeamModel, _days, fit_kick_model, load_lines, paired, team_actuals

WARMUP = 2012
CHOOSE = range(2012, 2018)       # choose settings here only
SCORE = range(2018, 2020)        # score here only


def choose(games: Sequence[Game], acts, lines) -> dict:
    """Grid and sizes from CHOOSE only. Walks the choose seasons, never the score seasons."""
    err = {c: 0.0 for c in GRID}
    pairs = {c: {"td": [], "fga": []} for c in GRID}
    for c in GRID:
        m = TeamModel(*c)
        for day in _days(games):
            if day[0].season not in CHOOSE:
                break
            for g in day:
                if (g.game_id, g.home) in acts and (g.game_id, g.away) in acts:
                    mu = m.means(g.home, g.away)
                    for s in ("td", "fga"):
                        for side, t in (("home", g.home), ("away", g.away)):
                            k = sum(acts[(g.game_id, t)][s][1:])
                            err[c] += (mu[(s, side)] - k) ** 2
                            pairs[c][s].append((mu[(s, side)], k))
            for g in day:
                m.update(g, acts, lines.get(g.game_id))
    best = min(GRID, key=lambda c: err[c])
    sizes = {s: E.fit_size(pairs[best][s]) for s in ("td", "fga")}
    return {"halflife_games": best[0], "k0": best[1], "size_td": sizes["td"], "size_fga": sizes["fga"],
            "mse": {f"h{c[0]}_k{c[1]}": err[c] for c in GRID}}


def team_replay(games: Sequence[Game], acts, lines) -> dict:
    chosen = choose(games, acts, lines)
    train = [g for g in games if g.season in CHOOSE]
    kick = fit_kick_model(train, acts, lines)            # uses CHOOSE seasons only (2013+ inside dev range)
    m = TeamModel(chosen["halflife_games"], chosen["k0"],
                  {"td": chosen["size_td"], "fga": chosen["size_fga"]}, kick)
    base = TeamModel(chosen["halflife_games"], chosen["k0"],
                     {"td": chosen["size_td"], "fga": chosen["size_fga"]}, None)
    S: Dict[str, Dict[str, list]] = defaultdict(lambda: {"model": [], "base": []})
    for day in _days(games):
        if day[0].season in SCORE:
            for g in day:
                a_h, a_a = acts.get((g.game_id, g.home)), acts.get((g.game_id, g.away))
                if a_h is None or a_a is None or a_h["points"] is None or a_a["points"] is None:
                    continue
                w = lines.get(g.game_id)
                fm = m.forecast(g.home, g.away, w)
                fb = base.forecast(g.home, g.away, w, league_only=True)
                for side, a in (("home", a_h), ("away", a_a)):
                    pts = a["points"]
                    S["team points, game"]["model"].append(E.log_score(fm[(side, "game")]["points"], sum(pts[1:])))
                    S["team points, game"]["base"].append(E.log_score(fb[(side, "game")]["points"], sum(pts[1:])))
                    for q in (1, 2, 3, 4):
                        S["team points, quarter"]["model"].append(E.log_score(fm[(side, f"Q{q}")]["points"], pts[q]))
                        S["team points, quarter"]["base"].append(E.log_score(fb[(side, f"Q{q}")]["points"], pts[q]))
                    S["touchdowns, game"]["model"].append(E.log_score(fm[(side, "game")]["td"], sum(a["td"][1:])))
                    S["touchdowns, game"]["base"].append(E.log_score(fb[(side, "game")]["td"], sum(a["td"][1:])))
                    S["field-goal attempts, game"]["model"].append(
                        E.log_score(fm[(side, "game")]["fg"].attempts, sum(a["fga"][1:])))
                    S["field-goal attempts, game"]["base"].append(
                        E.log_score(fb[(side, "game")]["fg"].attempts, sum(a["fga"][1:])))
                    for line in LINES["points"]:
                        S[f"team points, game over {line} (Brier)"]["model"].append(
                            E.brier(fm[(side, "game")]["points"].prob_over(line), int(sum(pts[1:]) > line)))
                        S[f"team points, game over {line} (Brier)"]["base"].append(
                            E.brier(fb[(side, "game")]["points"].prob_over(line), int(sum(pts[1:]) > line)))
                total = g.home_score + g.away_score
                S["game total"]["model"].append(E.log_score(fm["total"], total))
                S["game total"]["base"].append(E.log_score(fb["total"], total))
                S["game margin"]["model"].append(E.log_score(fm["margin"], g.home_score - g.away_score))
                S["game margin"]["base"].append(E.log_score(fb["margin"], g.home_score - g.away_score))
        for g in day:
            m.update(g, acts, lines.get(g.game_id))
            base.update(g, acts, lines.get(g.game_id))
    out = {}
    for k, v in S.items():
        out[k] = {"n": len(v["model"]), "model_minus_league_only": paired(v["model"], v["base"])}
    return {"chosen": chosen, "kick_model_fit_on": f"{min(CHOOSE)}-{max(CHOOSE)}", "scores": out}


def inplay_replay(boundaries: List[dict], games: Sequence[Game]) -> dict:
    snap = replay_elo(games, 30.0, 65.0, 1.0 / 3.0)
    m0 = {gid: diff / 25.0 for gid, diff in snap.items()}
    s_ss, s_sn = fit_sigmas([g for g in boundaries if g["season"] in CHOOSE], m0)
    out = {"fitted_on": f"{min(CHOOSE)}-{max(CHOOSE)}", "sigmas": {"s_strength": s_ss, "s_noise": s_sn},
           "boundaries": {}}
    rows = {b: {"model": [], "prior": [], "nflverse": [], "y": []} for b in ("Q1", "H1", "Q3")}
    for g in boundaries:
        if g["season"] not in SCORE or g.get("final") is None or g["game_id"] not in m0:
            continue
        fm = g["final"]["hs"] - g["final"]["as"]
        if fm == 0:
            continue
        y = int(fm > 0)
        for b, key in (("Q1", "q1"), ("H1", "q2"), ("Q3", "q3")):
            q = g.get(key)
            if q is None or q.get("wp") is None:
                continue
            margin = q["hs"] - q["as"]
            rows[b]["model"].append(win_prob(m0[g["game_id"]], margin, TAU[b], s_ss, s_sn))
            rows[b]["prior"].append(win_prob(m0[g["game_id"]], 0.0, 1.0, s_ss, s_sn))
            rows[b]["nflverse"].append(q["wp"])
            rows[b]["y"].append(y)
    for b, v in rows.items():
        n = len(v["y"])
        if n == 0:                                  # FINAL is the outcome, not a forecast: not scored
            continue
        sq = lambda xs: [(p - t) ** 2 for p, t in zip(xs, v["y"])]
        out["boundaries"][b] = {"n": n, "brier_model": brier(v["model"], v["y"]),
                                "brier_pregame_prior": brier(v["prior"], v["y"]),
                                "brier_nflverse": brier(v["nflverse"], v["y"]),
                                "model_minus_nflverse": paired(sq(v["model"]), sq(v["nflverse"]))}
    return out


def leak_check(games: Sequence[Game], acts, lines, probe_day_index: int = 40) -> dict:
    """Change one day's results and confirm the forecast for that same day is unchanged."""
    days = list(_days(games))
    target_day = days[probe_day_index]
    target = target_day[0]
    def forecast_at(changed: bool) -> float:
        a = dict(acts)
        if changed:
            for g in target_day:
                for t in (g.home, g.away):
                    if (g.game_id, t) in a:
                        a[(g.game_id, t)] = {**a[(g.game_id, t)], "td": [0, 9, 9, 9, 9, 9]}
        m = TeamModel(8, 8, {"td": E.POISSON, "fga": E.POISSON})
        for day in days[:probe_day_index]:
            for g in day:
                m.update(g, a, lines.get(g.game_id))
        return m.forecast(target.home, target.away, lines.get(target.game_id))[("home", "game")]["points"].mean
    same = forecast_at(False) == forecast_at(True)
    return {"game_day": target.gameday, "forecast_unchanged_by_that_days_results": same}


def main(argv=None) -> int:
    from . import pbp
    games_all = load_games()
    games = [g for g in games_all if g.completed and WARMUP <= g.season <= max(SCORE)]
    lines = load_lines()
    data = pbp.load(range(WARMUP, max(SCORE) + 1))
    boundaries = load_boundaries(range(WARMUP, max(SCORE) + 1))
    acts = team_actuals(data, boundaries)
    leak = leak_check(games, acts, lines)
    res = {"label": "STRICT REPLAY, DEVELOPMENT. Chosen on 2012-2017, scored on 2018-2019. Not blind; no market "
                    "prices exist for these seasons.",
           "leak_check": leak,
           "team": team_replay(games, acts, lines),
           "inplay": inplay_replay(boundaries, games)}
    path = os.path.join(RESULTS, "nfl_strict_replay.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(res["label"])
    print("leak check:", leak)
    print("team chosen:", res["team"]["chosen"]["halflife_games"], res["team"]["chosen"]["k0"])
    for k, v in res["team"]["scores"].items():
        d = v["model_minus_league_only"]
        print(f"  {k:<40} n={v['n']:>5}  model minus league-only {d['model_minus_baseline']:+.4f} "
              f"[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]")
    for b, r in res["inplay"]["boundaries"].items():
        d = r["model_minus_nflverse"]
        print(f"  in-game {b}  n={r['n']}  model {r['brier_model']:.4f}  prior {r['brier_pregame_prior']:.4f}  "
              f"nflverse {r['brier_nflverse']:.4f}  model minus nflverse {d['model_minus_baseline']:+.4f} "
              f"[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]")
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
