"""Pre-registered test: does team efficiency (EPA per play) or key-player injuries add to the adopted model on history?

PRE-REGISTERED RULES (written before any historical efficiency or injury data was loaded):

  Base         the adopted model: Elo K 30, home advantage 65, logistic on [elo, rest, division] (tune.py V2).
  E10          base + efficiency difference, half-life 10 games        (efficiency.py)
  E20          base + efficiency difference, half-life 20 games
  INJ          base + injury difference (key positions, Out or Doubtful), on seasons 2010 onward only

  Dev / holdout: dev = 2005-2019 (INJ: 2010-2019); holdout = 2020-2025 (all candidates).
  Selection:     between E10 and E20, the one with the lower dev log loss.
  Adoption:      the selected efficiency variant, and separately INJ, is adopted only if its holdout log-loss gain
                 over base has a 95% bootstrap interval entirely below zero. The base model is otherwise kept.
  Not allowed:   changing the candidate list, the half-lives, or the seasons after seeing results.

    python3 -m prediction_markets.nfl.tune_eff --stats path/to/stats_dir --injuries path/to/injuries_dir
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Sequence

from .data import Game
from .efficiency import TeamGame, efficiency_diffs
from .features import fit_logistic, replay_elo, sigmoid
from .injuries import injury_diff
from .tune import DEV, HOLDOUT, features as base_features, ADOPTED_SETTINGS

INJ_DEV = range(2010, 2020)
INJ_SEASONS = range(2010, 2026)


def _walk(games: Sequence[Game], extra_fn: Optional[Callable[[Game], float]], eval_seasons,
          train_from: int = 2000) -> Dict[str, float]:
    """Walk-forward: fit once per season on earlier completed games from seasons >= train_from, predict the season.

    train_from matters: a candidate must not be trained on seasons where its feature has no data (those rows would
    carry a zero that means "unknown", not "none")."""
    snap = replay_elo(games, ADOPTED_SETTINGS["k"], ADOPTED_SETTINGS["home_adv"], 1.0 / 3.0)
    by_season: Dict[int, List[Game]] = defaultdict(list)
    for g in games:
        if g.completed and g.home_won is not None:
            by_season[g.season].append(g)
    out: Dict[str, float] = {}
    train_X: List[List[float]] = []
    train_y: List[int] = []

    def row(g: Game) -> List[float]:
        x = base_features(g, snap[g.game_id], ())
        if extra_fn is not None:
            x.append(extra_fn(g))
        return x

    for season in sorted(by_season):
        if season < train_from:
            continue
        if season in eval_seasons and train_X:
            w = fit_logistic(train_X, train_y, 1e-3)
            for g in by_season[season]:
                out[g.game_id] = sigmoid(sum(a * b for a, b in zip(w, row(g))))
        for g in by_season[season]:
            train_X.append(row(g))
            train_y.append(g.home_won)
    return out


def _losses(probs: Dict[str, float], games: Sequence[Game], seasons) -> Dict[str, float]:
    out = {}
    for g in games:
        if g.game_id in probs and g.season in seasons and g.home_won is not None:
            p = min(1 - 1e-9, max(1e-9, probs[g.game_id]))
            out[g.game_id] = -math.log(p) if g.home_won else -math.log(1 - p)
    return out


def _gain(a: Dict[str, float], b: Dict[str, float], n: int = 2000, seed: int = 21):
    keys = sorted(set(a) & set(b))
    diffs = [a[k] - b[k] for k in keys]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return sum(diffs) / len(diffs), boots[int(0.025 * n)], boots[int(0.975 * n) - 1], len(keys)


def run(games: Sequence[Game], team_games: Sequence[TeamGame], injury_counts: dict) -> dict:
    from .blind import assert_not_sealed
    assert_not_sealed([g.game_id for g in games if g.season in set(DEV) | set(HOLDOUT)], "efficiency tuning")
    eff10 = efficiency_diffs(games, team_games, halflife=10)
    eff20 = efficiency_diffs(games, team_games, halflife=20)
    all_seasons = set(DEV) | set(HOLDOUT)
    base = _walk(games, None, all_seasons)
    e10 = _walk(games, lambda g: eff10.get(g.game_id, 0.0), all_seasons)
    e20 = _walk(games, lambda g: eff20.get(g.game_id, 0.0), all_seasons)
    inj = _walk(games, lambda g: injury_diff(injury_counts, g.season, g.week, g.home, g.away),
                set(INJ_DEV) | set(HOLDOUT), train_from=2010)
    base_inj = _walk(games, None, set(INJ_DEV) | set(HOLDOUT), train_from=2010)

    def dev_mean(p, seasons):
        vals = _losses(p, games, seasons).values()
        return sum(vals) / len(vals) if vals else float("nan")

    dev10, dev20 = dev_mean(e10, DEV), dev_mean(e20, DEV)
    selected = "E10" if dev10 <= dev20 else "E20"
    chosen = e10 if selected == "E10" else e20
    eff_gain = _gain(_losses(chosen, games, HOLDOUT), _losses(base, games, HOLDOUT))
    inj_gain = _gain(_losses(inj, games, HOLDOUT), _losses(base_inj, games, HOLDOUT))
    return {
        "rules": "see module docstring",
        "dev_log_loss": {"E10": dev10, "E20": dev20},
        "selected_efficiency": selected,
        "efficiency_holdout_gain": {"mean": eff_gain[0], "ci95": [eff_gain[1], eff_gain[2]], "games": eff_gain[3],
                                     "adopt": eff_gain[2] < 0},
        "injury_holdout_gain": {"mean": inj_gain[0], "ci95": [inj_gain[1], inj_gain[2]], "games": inj_gain[3],
                                "adopt": inj_gain[2] < 0},
    }
