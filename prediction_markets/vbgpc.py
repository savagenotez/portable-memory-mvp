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
from typing import Callable, List, Optional, Sequence

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


def estimate_phi(history: Sequence[float], cap: float = 0.95) -> float:
    """Lag-1 autocorrelation of the observed history, clamped to [0, cap].

    Used only by the optional AR(1) dependence variant. The default controller ignores it.
    """
    n = len(history)
    if n < 3:
        return 0.0
    m = sum(history) / n
    dev = [x - m for x in history]
    denom = sum(d * d for d in dev)
    if denom <= 0.0:
        return 0.0
    num = sum(dev[t] * dev[t - 1] for t in range(1, n))
    return min(cap, max(0.0, num / denom))


class GoalAttainmentController:
    """VB-GPC controller.

    Calibration variants (all off by default, so the spec-faithful behaviour is unchanged):
      dependence="ar1"     : steps follow an AR(1) around the baseline, with phi estimated
                             from history and the last observed residual as the starting state.
      mu_uncertainty=True  : each Monte Carlo trial draws mu from its posterior,
                             N(mu_hat, sigma_hat^2 / (n + n0)).
      drift=callable       : known deterministic drift S(t), indexed by period. The baseline is
                             estimated from the de-drifted history, and each future period is
                             forecast as mu_hat + S(t) instead of a flat mu_hat.
    """

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
        dependence: str = "iid",
        mu_uncertainty: bool = False,
        drift: Optional[Callable[[int], float]] = None,
    ):
        if total_steps <= 0:
            raise ValueError("total_steps must be positive")
        if dependence not in ("iid", "ar1"):
            raise ValueError("dependence must be 'iid' or 'ar1'")
        self.profile = profile
        self.goal = float(goal)
        self.total_steps = int(total_steps)
        self.kp = kp
        self.kd = kd
        self.lock_in_buffer = lock_in_buffer
        self.trials = trials
        self.rng = random.Random(seed)
        self.dependence = dependence
        self.mu_uncertainty = mu_uncertainty
        self.drift = drift
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

    def _residuals(self) -> List[float]:
        """History with the known drift removed (identity when no drift is supplied)."""
        if self.drift is None:
            return list(self.history)
        return [y - self.drift(t) for t, y in enumerate(self.history)]

    def _future_offsets(self) -> List[float]:
        """Known drift S(t) for each remaining period (zeros when no drift is supplied)."""
        if self.drift is None:
            return [0.0] * self.remaining
        n = len(self.history)
        return [self.drift(t) for t in range(n, n + self.remaining)]

    def estimate_parameters(self) -> tuple:
        """Return (mu_hat, sigma_hat): EB-shrunk baseline and Popoviciu-clamped sd."""
        p = self.profile
        return shrunk_baseline(self._residuals(), p.prior_mean, p.prior_strength, p.stat_min, p.stat_max)

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
        if self.dependence == "iid" and not self.mu_uncertainty and self.drift is None:
            return self.simulate_attainment_prob(sum(self.history), self.remaining, mu_hat, sigma_hat, trials)
        return self._variant_probability(mu_hat, sigma_hat, trials)

    def _variant_probability(self, mu_hat: float, sigma_hat: float, trials: int | None = None) -> float:
        """Monte Carlo with optional AR(1) dependence, posterior draws of mu, and known drift."""
        n_trials = trials or self.trials
        lo, hi = self.profile.stat_min, self.profile.stat_max
        remaining = self.remaining
        current_total = sum(self.history)
        if remaining <= 0:
            return 1.0 if current_total >= self.goal else 0.0

        n = len(self.history)
        n0 = self.profile.prior_strength
        mu_sd = sigma_hat / math.sqrt(n + n0) if (self.mu_uncertainty and n + n0 > 0) else 0.0
        offsets = self._future_offsets()
        residuals = self._residuals()

        if self.dependence == "ar1":
            phi = estimate_phi(residuals)
            x0 = residuals[-1] - mu_hat
        else:
            phi = 0.0
            x0 = 0.0
        innov_sd = sigma_hat * math.sqrt(1.0 - phi * phi)

        gauss = self.rng.gauss
        hits = 0
        for _ in range(n_trials):
            mu = gauss(mu_hat, mu_sd) if mu_sd > 0.0 else mu_hat
            x = x0
            total = current_total
            for j in range(remaining):
                x = phi * x + gauss(0.0, innov_sd)
                v = mu + offsets[j] + x
                total += lo if v < lo else (hi if v > hi else v)
            if total >= self.goal:
                hits += 1
        return hits / n_trials

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
        # Expected per-period mean over the remaining horizon: baseline plus average known drift.
        offsets = self._future_offsets()
        mu_eff = mu_hat + (sum(offsets) / remaining if remaining else 0.0)
        z_score = (remaining_goal - remaining * mu_eff) / (sigma_hat * math.sqrt(remaining))
        prob = self.attainment_probability()
        approx = self.normal_approx_prob(current_total, remaining, mu_eff, sigma_hat)

        margin = 0.5 * sigma_hat / math.sqrt(remaining)
        high_stretch = mu_eff + 0.75 * (hi - mu_eff)

        if req_pace <= mu_eff - margin:
            regime = "LOCK_IN_LOW_VARIANCE"
            variance_policy = "minimize"
            raw_target = min(req_pace + self.lock_in_buffer * margin, mu_eff)
        elif req_pace <= high_stretch:
            regime = "PD_PACING_CONTROL"
            variance_policy = "neutral"
            trend = mu_hat - self.prev_shrunk_mean
            raw_target = mu_eff + self.kp * (req_pace - mu_eff) - self.kd * trend
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
            "expected_future_mean": mu_eff,
            "bounded_std": sigma_hat,
            "required_pace": req_pace,
            "difficulty_z": z_score,
            "probability": prob,
            "normal_approx_probability": approx,
            "recommended_next_target": clip(raw_target, lo, hi),
        }
