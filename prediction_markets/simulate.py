"""Simulated fields: each domain generates a series from the four-component decomposition.

    Y_t = clip( mu + trend*t + seasonal(t) + venue(t) + S_t + X_t + eps_t ,  stat_min, stat_max )

with S_t ~ N(0, exog_sd^2) (opponent, pollster, or conditions noise), X_t an AR(1) process,
eps_t ~ N(0, sigma_eps^2), and an optional outage shock that replaces Y_t with shock_value.

Parameters live in config.json. Edit them there.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, fields
from typing import List, Optional

from .statmodel import ar1_stationary_sd, clip

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(HERE, "config.json")


@dataclass(frozen=True)
class DomainSpec:
    key: str
    field: str
    unit: str
    description: str
    stat_min: float
    stat_max: float
    true_mu: float            # hidden truth used only by the simulator
    prior_mean: float         # reference-class prior the controller starts from
    prior_strength: float     # n0 for shrinkage
    phi: float
    sigma_eta: float
    sigma_eps: float
    exog_sd: float = 0.0
    seasonal_amp: float = 0.0
    seasonal_period: float = 0.0
    trend_per_period: float = 0.0
    venue_effect: float = 0.0
    shock_prob: float = 0.0
    shock_value: float = 0.0
    total_periods: int = 1
    observed_periods: int = 1
    goal_average: float = 0.0  # goal = goal_average * total_periods (averages become totals)
    milestone: float = 0.0     # single-period threshold used for milestone odds

    @property
    def goal(self) -> float:
        return self.goal_average * self.total_periods

    @property
    def total_sd(self) -> float:
        """Approximate per-period sd of Y_t around its deterministic mean."""
        ar_sd = ar1_stationary_sd(self.phi, self.sigma_eta)
        return math.sqrt(self.sigma_eps ** 2 + ar_sd ** 2 + self.exog_sd ** 2)

    def deterministic_mean(self, t: int) -> float:
        """mu + trend + seasonal + venue, without the stochastic components."""
        m = self.true_mu + self.trend_per_period * t
        if self.seasonal_amp and self.seasonal_period > 0:
            m += self.seasonal_amp * math.sin(2.0 * math.pi * t / self.seasonal_period)
        m += self.venue_effect if t % 2 == 0 else -self.venue_effect
        return m


def load_config(path: Optional[str] = None) -> dict:
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_domain_specs(cfg: Optional[dict] = None) -> List[DomainSpec]:
    cfg = cfg or load_config()
    known = {f.name for f in fields(DomainSpec)} - {"key"}
    specs = []
    for key, raw in cfg["domains"].items():
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"domain {key!r}: unknown config keys {sorted(unknown)}")
        specs.append(DomainSpec(key=key, **raw))
    return specs


def simulate_series(spec: DomainSpec, rng, n_periods: Optional[int] = None) -> List[float]:
    """Generate one realisation of the domain. Deterministic for a given rng state."""
    n = spec.total_periods if n_periods is None else n_periods
    x = rng.gauss(0.0, ar1_stationary_sd(spec.phi, spec.sigma_eta))
    out: List[float] = []
    for t in range(n):
        if t > 0:
            x = spec.phi * x + rng.gauss(0.0, spec.sigma_eta)
        y = spec.deterministic_mean(t) + x + rng.gauss(0.0, spec.exog_sd) + rng.gauss(0.0, spec.sigma_eps)
        if spec.shock_prob > 0.0 and rng.random() < spec.shock_prob:
            y = spec.shock_value
        out.append(clip(y, spec.stat_min, spec.stat_max))
    return out
