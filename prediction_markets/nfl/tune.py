"""Improve the NFL model on historical game outcomes, not on the market games.

The 146 Kalshi games were used to diagnose the model, so they cannot also test changes to it. Historical game
outcomes (completed games, 2005 to 2025) are a much larger, separate sample, so model choices are made there.
The market is only compared against the fresh games the model has not seen.

PRE-REGISTERED RULES (fixed before any variant was scored):

  Variants (7):
    V0  baseline        Elo K 20, home advantage 65; features [elo, rest, division]
    V1  K 12            V0 with Elo K = 12
    V2  K 30            V0 with Elo K = 30
    V3  home adv 48     V0 with home advantage = 48
    V4  + short, bye    V0 plus short-rest difference (rest <= 4 days) and bye difference (rest >= 13 days)
    V5  + indoor        V0 plus an indoor venue flag (roof dome or closed)
    V6  + all flags     V0 plus short, bye and indoor

  Walk-forward: for each season S, the logistic model is fit ONCE on completed games from seasons before S
  (a simplification: in-season games from earlier weeks are not added until the next season).
  Elo is updated game by game, and each game's value is read before its own result is applied.

  Selection: the variant with the lowest mean log loss on seasons 2005-2019 (dev).
  Adoption: the selected variant replaces V0 only if, on seasons 2020-2025 (holdout), the mean log-loss gain over
  V0 has a 95% bootstrap interval entirely below zero. Otherwise V0 is kept.
  2026 is excluded from both, because the market diagnosis used it.

    python3 -m prediction_markets.nfl.tune              # writes results/nfl_tune.json
"""

from __future__ import annotations

import json
import math
import os
import random
from collections import defaultdict
from typing import Dict, List, Sequence

from .data import Game, load_games
from .features import fit_logistic, replay_elo, sigmoid

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
DEV = range(2005, 2020)
HOLDOUT = range(2020, 2026)

# Adopted on 2026-11-24 by the rule above (holdout gain -0.0025, interval -0.0042 to -0.0009). The model
# defaults in features.py are unchanged, so the published 146-game numbers still reproduce. Use this setting
# for the next model. K=30 is the top of the grid, so a larger K has not been tested.
ADOPTED_SETTINGS = {"k": 30.0, "home_adv": 65.0}

VARIANTS: Dict[str, dict] = {
    "V0": {"k": 20.0, "home_adv": 65.0, "flags": ()},
    "V1": {"k": 12.0, "home_adv": 65.0, "flags": ()},
    "V2": {"k": 30.0, "home_adv": 65.0, "flags": ()},
    "V3": {"k": 20.0, "home_adv": 48.0, "flags": ()},
    "V4": {"k": 20.0, "home_adv": 65.0, "flags": ("short", "bye")},
    "V5": {"k": 20.0, "home_adv": 65.0, "flags": ("indoor",)},
    "V6": {"k": 20.0, "home_adv": 65.0, "flags": ("short", "bye", "indoor")},
}


def is_indoor(g: Game) -> int:
    return 1 if g.roof in ("dome", "closed") else 0


def features(g: Game, elo_diff: float, flags: Sequence[str]) -> List[float]:
    """Pre-game features. 'indoor' is a venue flag (the roof is the same for both sides), not a difference."""
    x = [1.0, elo_diff / 100.0, max(-7.0, min(7.0, float(g.rest_home - g.rest_away))) / 7.0, float(g.div_game)]
    if "short" in flags:
        x.append(float((g.rest_home <= 4) - (g.rest_away <= 4)))
    if "bye" in flags:
        x.append(float((g.rest_home >= 13) - (g.rest_away >= 13)))
    if "indoor" in flags:
        x.append(float(is_indoor(g)))
    return x


def walk_forward(games: Sequence[Game], variant: dict) -> Dict[str, float]:
    """Pre-game home-win probability for every completed game in DEV or HOLDOUT seasons."""
    snap = replay_elo(games, variant["k"], variant["home_adv"], 1.0 / 3.0)
    flags = variant["flags"]
    by_season: Dict[int, List[Game]] = defaultdict(list)
    for g in games:
        if g.completed and g.home_won is not None:
            by_season[g.season].append(g)
    out: Dict[str, float] = {}
    train_X: List[List[float]] = []
    train_y: List[int] = []
    for season in sorted(by_season):
        if season in DEV or season in HOLDOUT:
            if train_X:
                w = fit_logistic(train_X, train_y, 1e-3)
                for g in by_season[season]:
                    x = features(g, snap[g.game_id], flags)
                    out[g.game_id] = sigmoid(sum(a * b for a, b in zip(w, x)))
        for g in by_season[season]:
            train_X.append(features(g, snap[g.game_id], flags))
            train_y.append(g.home_won)
    return out


def losses(probs: Dict[str, float], games: Sequence[Game], seasons) -> Dict[str, float]:
    out = {}
    for g in games:
        if g.game_id in probs and g.season in seasons and g.home_won is not None:
            p = min(1 - 1e-9, max(1e-9, probs[g.game_id]))
            y = g.home_won
            out[g.game_id] = -math.log(p) if y else -math.log(1 - p)
    return out


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_gain(a: Dict[str, float], b: Dict[str, float], n: int = 2000, seed: int = 11):
    """Mean of (a - b) over shared games, with a 95% bootstrap interval. Negative means a is better."""
    keys = sorted(set(a) & set(b))
    diffs = [a[k] - b[k] for k in keys]
    rng = random.Random(seed)
    boots = sorted(mean(rng.choice(diffs) for _ in diffs) for _ in range(n))
    return mean(diffs), boots[int(0.025 * n)], boots[int(0.975 * n) - 1], len(keys)


def run(games: Sequence[Game]) -> dict:
    result = {"variants": {}, "rules": "see module docstring"}
    dev_loss: Dict[str, float] = {}
    probs_by_variant: Dict[str, Dict[str, float]] = {}
    for name, v in VARIANTS.items():
        probs = walk_forward(games, v)
        probs_by_variant[name] = probs
        dev = losses(probs, games, DEV)
        hold = losses(probs, games, HOLDOUT)
        dev_loss[name] = mean(dev.values())
        result["variants"][name] = {"settings": {"k": v["k"], "home_adv": v["home_adv"], "flags": list(v["flags"])},
                                    "dev_log_loss": dev_loss[name], "dev_games": len(dev),
                                    "holdout_log_loss": mean(hold.values()), "holdout_games": len(hold)}
    selected = min(dev_loss, key=dev_loss.get)
    result["selected_on_dev"] = selected
    base_hold = losses(probs_by_variant["V0"], games, HOLDOUT)
    sel_hold = losses(probs_by_variant[selected], games, HOLDOUT)
    gain, lo, hi, n = bootstrap_gain(sel_hold, base_hold)
    adopt = selected != "V0" and hi < 0
    result["holdout_comparison"] = {"selected": selected, "baseline": "V0", "games": n,
                                    "log_loss_gain_selected_minus_V0": gain, "ci95": [lo, hi],
                                    "adopt_selected": adopt, "decision": selected if adopt else "V0"}
    return result


def main() -> int:
    games = load_games()
    res = run(games)
    print(f"{'variant':<8}{'k':>5}{'home':>6}{'flags':<26}{'dev log loss':>14}{'holdout log loss':>18}")
    for name, v in res["variants"].items():
        s = v["settings"]
        print(f"{name:<8}{s['k']:>5.0f}{s['home_adv']:>6.0f}{','.join(s['flags']) or '-':<26}"
              f"{v['dev_log_loss']:>14.4f}{v['holdout_log_loss']:>18.4f}")
    h = res["holdout_comparison"]
    print(f"\nselected on dev: {res['selected_on_dev']}")
    print(f"holdout gain vs V0 (negative = better): {h['log_loss_gain_selected_minus_V0']:+.4f}  "
          f"95% [{h['ci95'][0]:+.4f}, {h['ci95'][1]:+.4f}] over {h['games']} games")
    print(f"decision: keep {h['decision']}")
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "nfl_tune.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
