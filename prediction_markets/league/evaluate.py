"""Run models over simulated leagues and score them.

All predictions are prequential: each game is predicted BEFORE its outcome is revealed, then learned from.
Metrics are computed after a warm-up period (by default the first season), and the cold start is reported separately.

Reference points on the same games:
    base rate  online home-win rate. The model must beat this to have any skill.
    oracle     the true probability from the simulator. This is the best any model can do.
    capture    (brier_base - brier_model) / (brier_base - brier_oracle): the share of the achievable gain captured.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .features import Row
from .model import BranchEnsemble, FlatLogistic, ModelConfig, logloss


def run_ensemble(rows: Sequence[Row], branch_features: Dict[str, List[str]], cfg: ModelConfig,
                 plausible_gain: Optional[float] = None) -> Tuple[List[float], BranchEnsemble]:
    model = BranchEnsemble(branch_features, cfg, plausible_gain)
    preds: List[float] = []
    for r in rows:
        pr = model.predict(r.features, r.context)
        preds.append(pr.p)
        model.update(pr, r.y)
    return preds, model


def run_flat(rows: Sequence[Row], features: List[str], cfg: ModelConfig) -> List[float]:
    model = FlatLogistic(features, cfg)
    preds: List[float] = []
    for r in rows:
        state = model.predict(r.features, r.context)
        preds.append(state[0])
        model.update(state, r.y)
    return preds


def run_base_rate(rows: Sequence[Row]) -> List[float]:
    wins = 0
    preds: List[float] = []
    for i, r in enumerate(rows):
        preds.append((wins + 1.0) / (i + 2.0))
        wins += r.y
    return preds


def first_index_of_season(rows: Sequence[Row], seasons: Sequence[int], season: int) -> int:
    for i, s in enumerate(seasons):
        if s >= season:
            return i
    return len(rows)


def sq_errors(preds: Sequence[float], rows: Sequence[Row]) -> List[float]:
    return [(p - r.y) ** 2 for p, r in zip(preds, rows)]


def log_losses(preds: Sequence[float], rows: Sequence[Row]) -> List[float]:
    return [logloss(p, r.y) for p, r in zip(preds, rows)]


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def ci95(xs: Sequence[float]) -> Tuple[float, float, float]:
    """Mean and 95% interval across leagues."""
    n = len(xs)
    m = mean(xs)
    if n < 2:
        return m, m, m
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    half = 1.96 * sd / math.sqrt(n)
    return m, m - half, m + half


def capture(brier_base: float, brier_model: float, brier_oracle: float) -> float:
    gap = brier_base - brier_oracle
    return (brier_base - brier_model) / gap if gap > 0 else float("nan")


# ---- calibration slices ------------------------------------------------------------------

SliceFn = Callable[[Dict[str, float], float], bool]

SLICES: Dict[str, SliceFn] = {
    "season_games_0_2": lambda c, p: c["min_games_season"] <= 2,
    "season_games_3_9": lambda c, p: 3 <= c["min_games_season"] <= 9,
    "season_games_10_plus": lambda c, p: c["min_games_season"] >= 10,
    "cross_conference": lambda c, p: c["cross_conf"] == 1.0,
    "same_conference": lambda c, p: c["cross_conf"] == 0.0,
    "windy_outdoor": lambda c, p: c["outdoor"] == 1.0 and c["wind_z"] > 1.0,
    "calm_or_indoor": lambda c, p: not (c["outdoor"] == 1.0 and c["wind_z"] > 1.0),
    "big_streak_gap": lambda c, p: c["streak_gap"] >= 4,
    "small_streak_gap": lambda c, p: c["streak_gap"] < 4,
    "predicted_below_40": lambda c, p: p < 0.4,
    "predicted_40_to_60": lambda c, p: 0.4 <= p <= 0.6,
    "predicted_above_60": lambda c, p: p > 0.6,
}


def calibration_row(preds: Sequence[float], ys: Sequence[int]) -> dict:
    n = len(ys)
    if n == 0:
        return {"n": 0}
    mp = sum(preds) / n
    realized = sum(ys) / n
    se = math.sqrt(max(realized * (1.0 - realized), 1e-12) / n)
    gap = mp - realized
    return {"n": n, "predicted": mp, "realized": realized, "gap": gap, "se": se,
            "gap_in_se": gap / se if se > 0 else float("nan"), "passes": abs(gap) <= 2.0 * se}


def slice_table(samples: Sequence[Tuple[Dict[str, float], float, int]], min_n: int) -> Dict[str, dict]:
    """samples: (context, predicted probability, outcome) pooled over leagues."""
    out: Dict[str, dict] = {}
    for name, fn in SLICES.items():
        sel = [(p, y) for c, p, y in samples if fn(c, p)]
        row = calibration_row([p for p, _ in sel], [y for _, y in sel])
        row["evaluated"] = row["n"] >= min_n
        out[name] = row
    out["overall"] = dict(calibration_row([p for _, p, _ in samples], [y for _, _, y in samples]), evaluated=True)
    return out


def slice_pass_rate(table: Dict[str, dict]) -> Tuple[int, int]:
    evaluated = [v for k, v in table.items() if k != "overall" and v.get("evaluated")]
    return sum(1 for v in evaluated if v["passes"]), len(evaluated)
