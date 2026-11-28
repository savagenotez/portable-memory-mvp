"""Part 3: predict the next period from planned actions and conditions.

    expected = clip( mu_hat * (planned / reference)^elasticity + conditions_shift - fatigue )
    fatigue  = fatigue_drag * max(0, recent_workload - baseline_workload)

mu_hat and sigma_hat come from the Empirical Bayes shrinkage in statmodel.py.
The range and milestone odds come from a clipped-Gaussian Monte Carlo around `expected`.
"""

from __future__ import annotations

import random
from typing import Optional, Sequence

from .statmodel import clip, norm_cdf, shrunk_baseline


def milestone_probability(mean: float, sd: float, milestone: float, stat_min: float, stat_max: float) -> float:
    """Exact P(clip(N(mean, sd^2)) >= milestone) for a bounded single period."""
    if milestone <= stat_min:
        return 1.0
    if milestone > stat_max:
        return 0.0
    return 1.0 - norm_cdf((milestone - mean) / sd)


def forecast_next_period(
    history: Sequence[float],
    *,
    prior_mean: float,
    prior_strength: float,
    stat_min: float,
    stat_max: float,
    planned_actions: float,
    reference_actions: float,
    action_elasticity: float = 0.7,
    conditions_shift: float = 0.0,
    recent_workload: float = 0.0,
    baseline_workload: float = 0.0,
    fatigue_drag: float = 0.0,
    milestone: Optional[float] = None,
    trials: int = 5000,
    rng: Optional[random.Random] = None,
) -> dict:
    if reference_actions <= 0:
        raise ValueError("reference_actions must be positive")
    if planned_actions < 0:
        raise ValueError("planned_actions must be non-negative")
    if not 0.0 <= action_elasticity <= 1.0:
        raise ValueError("action_elasticity should be between 0 (no effect) and 1 (linear)")

    mu_hat, sigma_hat = shrunk_baseline(history, prior_mean, prior_strength, stat_min, stat_max)
    action_multiplier = (planned_actions / reference_actions) ** action_elasticity if planned_actions > 0 else 0.0
    fatigue = fatigue_drag * max(0.0, recent_workload - baseline_workload)
    expected = clip(mu_hat * action_multiplier + conditions_shift - fatigue, stat_min, stat_max)

    rng = rng or random.Random(0)
    draws = sorted(clip(rng.gauss(expected, sigma_hat), stat_min, stat_max) for _ in range(trials))
    low = draws[int(0.1 * (trials - 1))]
    high = draws[int(0.9 * (trials - 1))]

    out = {
        "shrunk_baseline": mu_hat,
        "bounded_std": sigma_hat,
        "action_multiplier": action_multiplier,
        "fatigue_drag_applied": fatigue,
        "expected": expected,
        "likely_range_p10": low,
        "likely_range_p90": high,
    }
    if milestone is not None:
        out["milestone"] = milestone
        out["milestone_probability"] = milestone_probability(expected, sigma_hat, milestone, stat_min, stat_max)
        out["milestone_probability_mc"] = sum(1 for d in draws if d >= milestone) / trials
    return out
