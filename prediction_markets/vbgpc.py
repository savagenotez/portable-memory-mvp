"""VB-GPC: Variance-Bounded Goal-Attainment & Pacing controller.

Port of the reference implementation in the design spec. Differences from the
reference are deliberate and are listed in README.md under "Deviations":

  * Monte Carlo draws come from an explicit seeded RNG, so results reproduce.
  * step_plan() is side-effect free. The trend term is updated when an
    observation is recorded, so repeated planning calls do not change state.
  * Regime 1 target is req_pace + lock_in_buffer * margin, capped at mu_hat.
    The reference's max(req_pace, mu - 0.25 * margin) always returns the
    second term, so it ignores the required pace.
  * A closed-form normal approximation is returned beside the Monte Carlo
    estimate as a cross-check.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from .statmodel import clip, norm_cdf, shrunk_baseline


@dataclass
class SubjectProfile:
    prior_mean: float        # reference-class mean (mu_0)
    prior_strength: float    # equivalent sample size for shrinkage (n_0)
    stat_min: float          # hard lower bound per period (s_min)
    stat_max: float          # hard upper bound per period (s_max)

    def __post_init__(self) -> None:
        if not self.stat_max > self.stat_min:
            raise ValueError("stat_max must be greater than stat_min")
        if self.prior_strength < 0:
            raise ValueError("prior_strength must be non-negative")


class GoalAttainmentController:
    def __init__(
        self,
        profile: SubjectProfile,
        goal: float,
        total_steps: int,
        kp: float = 0.85,
        kd: float = 0.20,
        lock_in_buffer: float = 0.5,
        trials: int = 5000,
        seed: int = 0,
    ):
        if total_steps <= 0:
            raise ValueError("total_steps must be positive")
        self.profile = profile
        self.goal = float(goal)
        self.total_steps = int(total_steps)
        self.kp = kp
        self.kd = kd
        self.lock_in_buffer = lock_in_buffer
        self.trials = trials
        self.rng = random.Random(seed)
        self.history: List[float] = []
        self.prev_shrunk_mean: float = profile.prior_mean

    @property
    def remaining(self) -> int:
        return max(0, self.total_steps - len(self.history))

    def record_observation(self, observed_stat: float) -> None:
        # Remember the baseline as it stood before this observation, for the trend term.
        self.prev_shrunk_mean = self.estimate_parameters()[0]
        p = self.profile
        self.history.append(clip(observed_stat, p.stat_min, p.stat_max))

    def estimate_parameters(self) -> tuple:
        """Return (mu_hat, sigma_hat): EB-shrunk mean and Popoviciu-clamped sd."""
        p = self.profile
        return shrunk_baseline(self.history, p.prior_mean, p.prior_strength, p.stat_min, p.stat_max)

    def simulate_attainment_prob(
        self,
        current_total: float,
        remaining_steps: int,
        mean: float,
        std: float,
        trials: int | None = None,
    ) -> float:
        """Monte Carlo P(C_T >= goal) for a random walk with clipped Gaussian steps."""
        if remaining_steps <= 0:
            return 1.0 if current_total >= self.goal else 0.0
        n_trials = trials or self.trials
        lo, hi = self.profile.stat_min, self.profile.stat_max
        gauss = self.rng.gauss
        hits = 0
        for _ in range(n_trials):
            total = current_total
            for _ in range(remaining_steps):
                v = gauss(mean, std)
                total += lo if v < lo else (hi if v > hi else v)
            if total >= self.goal:
                hits += 1
        return hits / n_trials

    def normal_approx_prob(self, current_total: float, remaining_steps: int, mean: float, std: float) -> float:
        """Unclipped normal approximation to P(C_T >= goal). Cross-check only."""
        if remaining_steps <= 0:
            return 1.0 if current_total >= self.goal else 0.0
        z = (self.goal - current_total - remaining_steps * mean) / (std * math.sqrt(remaining_steps))
        return 1.0 - norm_cdf(z)

    def attainment_probability(self, trials: int | None = None) -> float:
        mu_hat, sigma_hat = self.estimate_parameters()
        return self.simulate_attainment_prob(sum(self.history), self.remaining, mu_hat, sigma_hat, trials)

    def step_plan(self) -> dict:
        """Feasibility check, attainment probability, regime and next-period target."""
        p = self.profile
        lo, hi = p.stat_min, p.stat_max
        remaining = self.remaining
        current_total = sum(self.history)
        remaining_goal = self.goal - current_total

        if remaining <= 0:
            hit = current_total >= self.goal
            return {
                "status": "GOAL_REACHED" if hit else "HORIZON_EXPIRED",
                "current_total": current_total,
                "probability": 1.0 if hit else 0.0,
            }

        req_pace = remaining_goal / remaining
        min_reachable = current_total + remaining * lo
        max_reachable = current_total + remaining * hi

        if self.goal > max_reachable:
            return {
                "status": "MATHEMATICALLY_INFEASIBLE",
                "required_pace": req_pace,
                "max_possible_total": max_reachable,
                "probability": 0.0,
            }
        if self.goal <= min_reachable:
            return {
                "status": "GUARANTEED",
                "required_pace": req_pace,
                "target_next_step": lo,
                "probability": 1.0,
            }

        mu_hat, sigma_hat = self.estimate_parameters()
        z_score = (remaining_goal - remaining * mu_hat) / (sigma_hat * math.sqrt(remaining))
        prob = self.simulate_attainment_prob(current_total, remaining, mu_hat, sigma_hat)
        approx = self.normal_approx_prob(current_total, remaining, mu_hat, sigma_hat)

        margin = 0.5 * sigma_hat / math.sqrt(remaining)
        high_stretch = mu_hat + 0.75 * (hi - mu_hat)

        if req_pace <= mu_hat - margin:
            regime = "LOCK_IN_LOW_VARIANCE"
            variance_policy = "minimize"
            raw_target = min(req_pace + self.lock_in_buffer * margin, mu_hat)
        elif req_pace <= high_stretch:
            regime = "PD_PACING_CONTROL"
            variance_policy = "neutral"
            trend = mu_hat - self.prev_shrunk_mean
            raw_target = mu_hat + self.kp * (req_pace - mu_hat) - self.kd * trend
        else:
            regime = "TAIL_SEEKING_HIGH_VARIANCE"
            variance_policy = "maximize_upside"
            raw_target = hi

        return {
            "status": "ACTIVE",
            "regime": regime,
            "variance_policy": variance_policy,
            "remaining_steps": remaining,
            "shrunk_mean": mu_hat,
            "bounded_std": sigma_hat,
            "required_pace": req_pace,
            "difficulty_z": z_score,
            "probability": prob,
            "normal_approx_probability": approx,
            "recommended_next_target": clip(raw_target, lo, hi),
        }
