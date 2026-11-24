"""Model v3, FROZEN before any sealed 2026 outcome exists.

v3 = logistic regression on [intercept, Elo difference (K 30, home advantage 65)/100, rest difference/7,
division game, efficiency difference (EPA per play, 10-game half-life), injury difference (key positions Out or
Doubtful)]. Trained, for each game day, on completed games from 2010 onward that were played before that day.

This combines two features that each passed the pre-registered rule on history. The combination itself was not
tested on history before it was frozen here. Its first real test is the sealed 2026 block, judged against the base
model and the market.

    python3 -m prediction_markets.nfl.model_v3 --dev     # development on history (not blind), writes results
"""

from __future__ import annotations

import json
import math
import os
import random
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence

from .data import Game
from .efficiency import TeamGame, efficiency_diffs
from .features import fit_logistic, replay_elo, sigmoid
from .injuries import injury_diff
from .tune import ADOPTED_SETTINGS

FROZEN = {"name": "v3", "k": 30.0, "home_adv": 65.0, "eff_halflife": 10, "train_from": 2010,
          "features": ["intercept", "elo_diff_100", "rest_diff_norm", "division", "efficiency_diff", "injury_diff"]}


def v3_home_probs(games: Sequence[Game], team_games: Sequence[TeamGame], injury_counts: dict,
                  targets: Iterable[str], use_eff: bool = True, use_inj: bool = True) -> Dict[str, float]:
    """use_eff / use_inj switch the two new features off, for the fair ablation: same training window, base features only."""
    targets = set(targets)
    snap = replay_elo(games, FROZEN["k"], FROZEN["home_adv"], 1.0 / 3.0)
    eff = efficiency_diffs(games, team_games, halflife=FROZEN["eff_halflife"])

    def row(g: Game) -> List[float]:
        rest = max(-7.0, min(7.0, float(g.rest_home - g.rest_away)))
        return [1.0, snap[g.game_id] / 100.0, rest / 7.0, float(g.div_game),
                eff.get(g.game_id, 0.0) if use_eff else 0.0,
                injury_diff(injury_counts, g.season, g.week, g.home, g.away) if use_inj else 0.0]

    played = sorted((g for g in games if g.completed and g.home_won is not None and g.season >= FROZEN["train_from"]),
                    key=lambda g: (g.gameday, g.game_id))
    days = sorted({g.gameday for g in games if g.game_id in targets})
    out: Dict[str, float] = {}
    X: List[List[float]] = []
    y: List[int] = []
    i = 0
    for day in days:
        while i < len(played) and played[i].gameday < day:
            X.append(row(played[i]))
            y.append(played[i].home_won)
            i += 1
        if not X:
            continue
        w = fit_logistic(X, y, 1e-3)
        for g in games:
            if g.gameday == day and g.game_id in targets:
                out[g.game_id] = sigmoid(sum(a * b for a, b in zip(w, row(g))))
    return out


def _losses(p: Dict[str, float], games: Sequence[Game], seasons) -> Dict[str, float]:
    out = {}
    for g in games:
        if g.game_id in p and g.season in seasons and g.home_won is not None:
            q = min(1 - 1e-9, max(1e-9, p[g.game_id]))
            out[g.game_id] = -math.log(q) if g.home_won else -math.log(1 - q)
    return out


def _gain(a: Dict[str, float], b: Dict[str, float], n: int = 2000, seed: int = 31):
    keys = sorted(set(a) & set(b))
    d = [a[k] - b[k] for k in keys]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return sum(d) / len(d), boots[int(0.025 * n)], boots[int(0.975 * n) - 1], len(keys)


def dev_evaluation(games: Sequence[Game], team_games, injury_counts) -> dict:
    from .tune import walk_forward, HOLDOUT
    holdout = set(HOLDOUT)
    targets = [g.game_id for g in games if g.season in holdout and g.completed]
    v3 = v3_home_probs(games, team_games, injury_counts, targets)
    base_all = walk_forward(games, dict(ADOPTED_SETTINGS, flags=(), k=ADOPTED_SETTINGS["k"]))
    base_2010 = v3_home_probs(games, team_games, injury_counts, targets, use_eff=False, use_inj=False)
    gain_all = _gain(_losses(v3, games, holdout), _losses(base_all, games, holdout))
    gain_fair = _gain(_losses(v3, games, holdout), _losses(base_2010, games, holdout))
    def fmt(g):
        return {"mean": g[0], "ci95": [g[1], g[2]], "games": g[3]}
    return {"label": "DEVELOPMENT ON HISTORY, NOT BLIND. The 2020-2025 holdout was used to choose K = 30.",
            "frozen_definition": FROZEN,
            "v3_minus_base_all_seasons_training": fmt(gain_all),
            "v3_minus_base_same_window_2010_training": fmt(gain_fair),
            "note": "The fair comparison is the second line: same 2010 training window, base features only."}


def main(argv=None) -> int:
    import argparse
    from .data import load_games
    from .sources import load_injury_counts, load_team_games
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.model_v3")
    ap.add_argument("--dev", action="store_true")
    args = ap.parse_args(argv)
    games = load_games(refresh=True)
    team_games, _ = load_team_games(range(2000, 2027), refresh=True)
    injuries, _ = load_injury_counts(range(2009, 2027), refresh=True)
    res = dev_evaluation(games, team_games, injuries)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "nfl_v3_dev.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(res["label"])
    for key, name in (("v3_minus_base_all_seasons_training", "vs base trained from 2005"),
                      ("v3_minus_base_same_window_2010_training", "vs base, same 2010 window (fair)")):
        g = res[key]
        print(f"v3 {name}: {g['mean']:+.5f}  95% [{g['ci95'][0]:+.5f}, {g['ci95'][1]:+.5f}]  ({g['games']} games)")
    print(f"wrote {os.path.normpath(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
