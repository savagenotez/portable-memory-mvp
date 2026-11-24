"""Pre-game features and the walk-forward model.

PRE-REGISTERED settings, from public Elo methodology (flat home advantage and season regression), fixed before
any comparison against market prices was run:

    Elo:   start 1500, K = 20, home advantage 65 points (not at neutral sites), a third of the gap to 1500 closed
           at each new season. Standard expected-score update with no margin-of-victory term.
    Model: logistic regression on [1, elo_diff/100, rest_diff/7, div_game]. Refit before each game day, using only
           completed games played before that day. L2 = 0.001.

Deliberately EXCLUDED, because they are not known about 24 hours before kickoff:
    * temperature and wind (the recorded values are game-time, not forecasts; using them would be look-ahead)
    * betting spread, moneyline and total (they are the market; using them would make the model a copy of it)
    * final scores of the game being predicted (obviously)
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .data import Game

PRE_REGISTERED = {"k": 20.0, "home_adv": 65.0, "season_regression": 1.0 / 3.0, "rest_cap": 7.0, "l2": 1e-3}
FEATURE_NAMES = ["intercept", "elo_diff_100", "rest_diff_norm", "div_game"]


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def replay_elo(games: Sequence[Game], k: float = 20.0, home_adv: float = 65.0,
               season_regression: float = 1.0 / 3.0) -> Dict[str, float]:
    """Walk the games in time order. Return each game's PRE-game Elo difference, home side first.

    A game's value is read before its own result is applied, so it uses only earlier games.
    """
    ratings: Dict[str, float] = defaultdict(lambda: 1500.0)
    snapshot: Dict[str, float] = {}
    prev_season = None
    for g in games:
        if prev_season is not None and g.season != prev_season:
            for team in list(ratings):
                ratings[team] = ratings[team] * (1.0 - season_regression) + 1500.0 * season_regression
        prev_season = g.season
        diff = ratings[g.home] - ratings[g.away] + (0.0 if g.neutral else home_adv)
        snapshot[g.game_id] = diff
        if g.completed:
            s = 0.5 if g.home_score == g.away_score else (1.0 if g.home_score > g.away_score else 0.0)
            expected = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
            ratings[g.home] += k * (s - expected)
            ratings[g.away] -= k * (s - expected)
    return snapshot


def feature_vector(g: Game, elo_diff: float, rest_cap: float = 7.0) -> List[float]:
    rest = max(-rest_cap, min(rest_cap, float(g.rest_home - g.rest_away)))
    return [1.0, elo_diff / 100.0, rest / rest_cap, float(g.div_game)]


def fit_logistic(X: List[List[float]], y: List[int], l2: float = 1e-3, iters: int = 30) -> List[float]:
    """Newton-Raphson for L2-regularised logistic regression (intercept included, lightly penalised too)."""
    k = len(X[0])
    w = [0.0] * k
    for _ in range(iters):
        grad = [-l2 * wi for wi in w]
        hess = [[(l2 if i == j else 0.0) for j in range(k)] for i in range(k)]
        for xi, yi in zip(X, y):
            p = sigmoid(sum(a * b for a, b in zip(w, xi)))
            wt = p * (1.0 - p)
            for i in range(k):
                grad[i] += (yi - p) * xi[i]
                for j in range(k):
                    hess[i][j] += wt * xi[i] * xi[j]
        step = _solve(hess, grad)
        w = [a + b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    return w


def _solve(A: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for j in range(c, n + 1):
                    M[r][j] -= f * M[c][j]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def walk_forward_home_prob(games: Sequence[Game], target_ids: Set[str], settings: Optional[dict] = None
                           ) -> Dict[str, float]:
    """P(home wins) for each target game, from a model fit only on completed games played before that day."""
    s = dict(PRE_REGISTERED, **(settings or {}))
    snap = replay_elo(games, s["k"], s["home_adv"], s["season_regression"])
    target_days = sorted({g.gameday for g in games if g.game_id in target_ids})
    by_day: Dict[str, List[Game]] = defaultdict(list)
    for g in games:
        by_day[g.gameday].append(g)
    out: Dict[str, float] = {}
    train_X: List[List[float]] = []
    train_y: List[int] = []
    played_before = [g for g in games if g.completed]
    cursor = 0
    for day in target_days:
        while cursor < len(played_before) and played_before[cursor].gameday < day:
            g = played_before[cursor]
            if g.home_won is not None:
                train_X.append(feature_vector(g, snap[g.game_id], s["rest_cap"]))
                train_y.append(g.home_won)
            cursor += 1
        if not train_X:
            # No completed games before this day, so there is nothing to learn from. Say 50/50, do not guess.
            for g in by_day[day]:
                if g.game_id in target_ids:
                    out[g.game_id] = 0.5
            continue
        w = fit_logistic(train_X, train_y, s["l2"])
        for g in by_day[day]:
            if g.game_id in target_ids:
                x = feature_vector(g, snap[g.game_id], s["rest_cap"])
                out[g.game_id] = sigmoid(sum(a * b for a, b in zip(w, x)))
    return out
