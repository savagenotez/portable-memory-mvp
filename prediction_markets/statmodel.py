"""Shared estimators for the four-component model.

Observed stat:  Y_t = mu + S(t) + X_t + eps_t, clipped to [stat_min, stat_max]

  mu     latent baseline (true talent / partisan lean / climate normal)
  S(t)   known or exogenous context (opponent, venue, season, national environment)
  X_t    AR(1) momentum: X_t = phi * X_{t-1} + eta_t
  eps_t  irreducible per-period noise

This module holds the estimators the rest of the package relies on:
Empirical Bayes shrinkage, Popoviciu-bounded volatility, AR(1) helpers and
small numeric utilities. Standard library only.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple


def clip(x: float, lo: float, hi: float) -> float:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def popoviciu_max_std(stat_min: float, stat_max: float) -> float:
    """Popoviciu's bound: a variable confined to [a, b] has sd <= (b - a) / 2."""
    if not stat_max > stat_min:
        raise ValueError("stat_max must be greater than stat_min")
    return (stat_max - stat_min) / 2.0


def eb_weight(n: float, tau2: float, sigma2: float) -> float:
    """Empirical Bayes weight B = tau^2 / (tau^2 + sigma^2 / n).

    B -> 0 when n is small (trust the reference-class prior).
    B -> 1 when n is large (trust the subject's own record).
    """
    if n <= 0 or tau2 <= 0:
        return 0.0
    return tau2 / (tau2 + sigma2 / n)


def eb_shrink(sample_mean: float, n: float, prior_mean: float, tau2: float, sigma2: float) -> float:
    """Shrink a raw sample mean toward the prior mean: mu0 + B * (ybar - mu0)."""
    return prior_mean + eb_weight(n, tau2, sigma2) * (sample_mean - prior_mean)


def shrunk_baseline(
    history: Sequence[float],
    prior_mean: float,
    prior_strength: float,
    stat_min: float,
    stat_max: float,
) -> Tuple[float, float]:
    """Return (mu_hat, sigma_hat) for an observed history.

    mu_hat uses the prior-strength form of EB shrinkage,
        mu_hat = (n * ybar + n0 * mu0) / (n + n0),   where n0 = sigma^2 / tau^2.
    sigma_hat is the sample standard deviation clamped by Popoviciu's bound.
    With no observations, returns the prior mean and half the Popoviciu bound.
    """
    max_std = popoviciu_max_std(stat_min, stat_max)
    n = len(history)
    if n == 0:
        return prior_mean, 0.5 * max_std

    ybar = sum(history) / n
    total_weight = n + prior_strength
    mu_hat = (n * ybar + prior_strength * prior_mean) / total_weight if total_weight > 0 else ybar

    if n == 1:
        emp_std = 0.5 * max_std
    else:
        var = sum((x - ybar) ** 2 for x in history) / (n - 1)
        emp_std = math.sqrt(var)

    sigma_hat = max(min(emp_std, max_std), 1e-6)
    return mu_hat, sigma_hat


def ar1_stationary_sd(phi: float, sigma_eta: float) -> float:
    """Stationary standard deviation of X_t = phi * X_{t-1} + eta_t, eta ~ N(0, sigma_eta^2)."""
    if not -1.0 < phi < 1.0:
        raise ValueError("AR(1) needs |phi| < 1 for a stationary variance")
    return sigma_eta / math.sqrt(1.0 - phi * phi)
