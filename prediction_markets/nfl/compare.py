"""Model against market: the same NFL games, scored on the same outcomes.

For each matched game, the model's probability and the market's price (24 hours before kickoff) both refer to the
team the YES side is about. Scores are Brier and log loss, compared on the same games. The uncertainty in the
difference comes from a bootstrap over games.

Nothing here is a statement about profit. A model that is worse than the price can still look fine on some games,
and the sample here is a few dozen games.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Sequence

from ..realdata.calibration import fit_calibration
from ..realdata.observation import Observation
from .data import Game
from .features import walk_forward_home_prob
from .match import match_all


def _logloss(p: float, y: int) -> float:
    p = min(1 - 1e-9, max(1e-9, p))
    return -math.log(p) if y else -math.log(1 - p)


def compare(observations: Sequence[Observation], games: Sequence[Game], bootstrap: int = 2000,
            seed: int = 1, settings=None) -> Dict:
    matched, unmatched = match_all(observations, games)
    if not matched:
        return {"matched": 0, "unmatched": len(unmatched)}
    targets = {g.game_id for _, g, _ in matched}
    p_home = walk_forward_home_prob(games, targets, settings)

    rows: List[dict] = []
    for obs, g, side in matched:
        ph = p_home[g.game_id]
        p_side = ph if side == "home" else 1.0 - ph
        team_won = (g.home_won == 1) if side == "home" else (g.home_won == 0)
        rows.append({"market_id": obs.market_id, "gameday": g.gameday, "side": side,
                     "model": p_side, "market": obs.price, "outcome": obs.outcome,
                     "agrees_with_score": int(team_won) == obs.outcome})

    n = len(rows)
    y = [r["outcome"] for r in rows]
    bm = [(r["model"] - r["outcome"]) ** 2 for r in rows]
    bk = [(r["market"] - r["outcome"]) ** 2 for r in rows]
    diffs = [a - b for a, b in zip(bm, bk)]     # negative means the model beat the market

    rng = random.Random(seed)
    boots = []
    for _ in range(bootstrap):
        idx = [rng.randrange(n) for _ in range(n)]
        boots.append(sum(diffs[i] for i in idx) / n)
    boots.sort()
    lo, hi = boots[int(0.025 * bootstrap)], boots[int(0.975 * bootstrap) - 1]

    base = sum(y) / n
    brier_base = sum((base - o) ** 2 for o in y) / n

    def calib(key):
        obs_like = [Observation("nfl", r["market_id"], r["gameday"], "", 0.0, 24.0, r[key], r["outcome"])
                    for r in rows]
        return fit_calibration(obs_like)

    return {
        "matched": n,
        "unmatched": len(unmatched),
        "unmatched_ids": [o.market_id for o in unmatched],
        "agreement_with_score": sum(r["agrees_with_score"] for r in rows) / n,
        "brier_model": sum(bm) / n,
        "brier_market": sum(bk) / n,
        "brier_base_rate": brier_base,
        "model_skill_vs_base": 1 - (sum(bm) / n) / brier_base if brier_base else None,
        "market_skill_vs_base": 1 - (sum(bk) / n) / brier_base if brier_base else None,
        "model_minus_market_brier": sum(diffs) / n,
        "model_minus_market_ci95": [lo, hi],
        "logloss_model": sum(_logloss(r["model"], r["outcome"]) for r in rows) / n,
        "logloss_market": sum(_logloss(r["market"], r["outcome"]) for r in rows) / n,
        "calibration_model": calib("model"),
        "calibration_market": calib("market"),
        "rows": rows,
    }
