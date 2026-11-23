"""Synthetic market events for paper-trading tests and the demo.

THESE ARE NOT REAL MARKET PRICES. The "market" here is built from the true simulated
process plus noise, so it is an informed stress test of the bet mechanics, not a
benchmark of any real venue.

For each simulated game t after a warm-up:
  model_prob   = P(Y_t >= milestone | shrunk history)            (what our model knows)
  market_price = clip(P(Y_t >= milestone | true mean, true sd) + noise)
  outcome      = 1 if the simulated Y_t >= milestone else 0
"""

from __future__ import annotations

import random
from typing import List

from .forecast import milestone_probability
from .markets import MarketEvent
from .simulate import DomainSpec, simulate_series
from .statmodel import clip, shrunk_baseline


def synthetic_sports_events(
    spec: DomainSpec,
    *,
    warmup: int,
    market_noise_sd: float,
    seasons: int,
    seed: int,
) -> List[MarketEvent]:
    if spec.milestone <= 0:
        raise ValueError(f"{spec.key} has no milestone configured")
    master = random.Random(seed)
    events: List[MarketEvent] = []
    for s in range(seasons):
        rng = random.Random(master.randrange(2 ** 31))
        series = simulate_series(spec, rng)
        for t in range(warmup, spec.total_periods):
            mu_hat, sd_hat = shrunk_baseline(
                series[:t], spec.prior_mean, spec.prior_strength, spec.stat_min, spec.stat_max
            )
            model_p = milestone_probability(mu_hat, sd_hat, spec.milestone, spec.stat_min, spec.stat_max)
            oracle_p = milestone_probability(
                spec.deterministic_mean(t), spec.total_sd, spec.milestone, spec.stat_min, spec.stat_max
            )
            price = clip(oracle_p + rng.gauss(0.0, market_noise_sd), 0.02, 0.98)
            outcome = 1 if series[t] >= spec.milestone else 0
            events.append(
                MarketEvent(event_id=f"{spec.key}-s{s}-g{t}", model_prob=model_p, market_price=price, outcome=outcome)
            )
    return events
