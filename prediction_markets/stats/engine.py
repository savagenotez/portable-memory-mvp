"""Sport-agnostic projection engine: counts, makes out of attempts, percentages, totals, margins and over/under.

Works for any quantity that is a count per game, period or day: field goals, three-pointers, shots, aces, corners,
rainy days, storms. A continuous value (points, yards, temperature, rainfall) can be counted in whole units or
handled with NormalForecast.

    Dist            a distribution over whole numbers. Over/under at any line (push-aware), exact values, quantiles,
                    intervals, mean and spread.
    nb              negative binomial with mean mu and size r (r -> infinity is Poisson): the count model. Small r
                    means more game-to-game variation than Poisson.
    period          a count's share of a period (quarter, half, hour): mean mu*share, same size r.
    makes           attempts (a Dist) times a make probability with uncertainty (beta): makes and the percentage.
    compound        N events, each worth a random number of points (a touchdown is 6 plus 0, 1 or 2).
    add / subtract  independent sums and differences: team points to total, and to margin ("by how much").
    DecayedRate     per-entity rates that learn as results arrive, shrunk toward a prior (empirical Bayes), with
                    older games counting less. Nothing from the future can enter.

Everything here is plain Python with no third-party packages.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import NormalDist
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Tuple

TAIL = 1e-9
POISSON = 1e9          # a size at or above this is treated as Poisson


@dataclass
class Dist:
    """P(X = offset + i) = pmf[i]."""
    pmf: List[float]
    offset: int = 0

    @property
    def mean(self) -> float:
        return sum((self.offset + i) * p for i, p in enumerate(self.pmf))

    @property
    def sd(self) -> float:
        m = self.mean
        return math.sqrt(max(0.0, sum(((self.offset + i) - m) ** 2 * p for i, p in enumerate(self.pmf))))

    def prob(self, k: int) -> float:
        i = k - self.offset
        return self.pmf[i] if 0 <= i < len(self.pmf) else 0.0

    def cdf(self, x: float) -> float:
        """P(X <= x)."""
        hi = math.floor(x) - self.offset
        if hi < 0:
            return 0.0
        return min(1.0, sum(self.pmf[: hi + 1]))

    def prob_over(self, line: float) -> float:
        """P(X > line)."""
        return max(0.0, 1.0 - self.cdf(line))

    def prob_under(self, line: float) -> float:
        """P(X < line)."""
        return self.cdf(math.ceil(line) - 1)

    def over_no_push(self, line: float) -> float:
        """P(over | not a push). A whole-number line can land exactly; that outcome is refunded, so it is removed."""
        over, under = self.prob_over(line), self.prob_under(line)
        return over / (over + under) if over + under > 0 else 0.5

    def quantile(self, q: float) -> int:
        c = 0.0
        for i, p in enumerate(self.pmf):
            c += p
            if c >= q - 1e-12:
                return self.offset + i
        return self.offset + len(self.pmf) - 1

    def interval(self, level: float = 0.8) -> Tuple[int, int]:
        a = (1.0 - level) / 2.0
        return self.quantile(a), self.quantile(1.0 - a)

    def mode(self) -> Tuple[int, float]:
        i = max(range(len(self.pmf)), key=lambda j: self.pmf[j])
        return self.offset + i, self.pmf[i]

    def narrowest(self, level: float) -> Tuple[int, int, float]:
        """The narrowest range of whole numbers holding at least `level` probability: (low, high, its probability).
        Grown from the most likely value, one step at a time toward the likelier side."""
        i, _ = self.mode()
        lo = hi = i - self.offset
        mass = self.pmf[lo]
        while mass < level - 1e-12 and (lo > 0 or hi < len(self.pmf) - 1):
            left = self.pmf[lo - 1] if lo > 0 else -1.0
            right = self.pmf[hi + 1] if hi < len(self.pmf) - 1 else -1.0
            if right >= left:
                hi += 1
                mass += right
            else:
                lo -= 1
                mass += left
        return self.offset + lo, self.offset + hi, mass

    def summary(self, lines: Sequence[float] = ()) -> dict:
        lo, hi = self.interval(0.8)
        out = {"mean": round(self.mean, 3), "median": self.quantile(0.5), "interval_80": [lo, hi]}
        for line in lines:
            out[f"over_{line}"] = round(self.over_no_push(line), 4)
        return out


def _trim(pmf: List[float], offset: int) -> Dist:
    lo, hi = 0, len(pmf)
    while lo < hi - 1 and pmf[lo] < TAIL * 1e-3:
        lo += 1
    while hi > lo + 1 and pmf[hi - 1] < TAIL * 1e-3:
        hi -= 1
    seg = pmf[lo:hi]
    s = sum(seg)
    return Dist([p / s for p in seg], offset + lo)


def point(k: int = 0) -> Dist:
    return Dist([1.0], k)


def nb_logpmf(k: int, mu: float, r: float) -> float:
    """log P(K = k) for a negative binomial with mean mu and size r."""
    if mu <= 0:
        return 0.0 if k == 0 else -1e9
    if r >= POISSON:
        return k * math.log(mu) - mu - math.lgamma(k + 1)
    return (math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
            + r * math.log(r / (r + mu)) + k * math.log(mu / (r + mu)))


def nb(mu: float, r: float = POISSON, kmax: int = 5000) -> Dist:
    """Negative binomial count with mean mu and size r."""
    if mu <= 0:
        return point(0)
    if r >= POISSON:
        p0 = math.exp(-mu)
        step = lambda k: mu / (k + 1)
    else:
        q = mu / (r + mu)
        p0 = math.exp(r * math.log(r / (r + mu)))
        step = lambda k: (k + r) / (k + 1) * q
    if p0 <= 0.0:                         # very large mu: start from the log-space mode to avoid underflow
        return _nb_large(mu, r, kmax)
    pmf = [p0]
    c = p0
    k = 0
    while k < kmax and (k < mu or 1.0 - c > TAIL):
        nxt = pmf[-1] * step(k)
        pmf.append(nxt)
        c += nxt
        k += 1
    return _trim(pmf, 0)


def _nb_large(mu: float, r: float, kmax: int) -> Dist:
    sd = math.sqrt(mu + (mu * mu / r if r < POISSON else 0.0))
    lo, hi = max(0, int(mu - 12 * sd)), min(kmax, int(mu + 12 * sd) + 1)
    logs = [nb_logpmf(k, mu, r) for k in range(lo, hi + 1)]
    m = max(logs)
    return _trim([math.exp(x - m) for x in logs], lo)


def period(mu: float, r: float, share: float) -> Dist:
    """A count's part in one period: a gamma-mixed Poisson thinned by `share` keeps the same size r."""
    return nb(mu * share, r)


def add(a: Dist, b: Dist) -> Dist:
    out = [0.0] * (len(a.pmf) + len(b.pmf) - 1)
    for i, p in enumerate(a.pmf):
        if p == 0.0:
            continue
        for j, q in enumerate(b.pmf):
            out[i + j] += p * q
    return _trim(out, a.offset + b.offset)


def negate(a: Dist) -> Dist:
    return Dist(list(reversed(a.pmf)), -(a.offset + len(a.pmf) - 1))


def subtract(a: Dist, b: Dist) -> Dist:
    return add(a, negate(b))


def scale(a: Dist, value: int) -> Dist:
    """Each unit is worth `value` (e.g. made field goals to points)."""
    if value == 0:
        return point(0)
    pmf = [0.0] * ((len(a.pmf) - 1) * value + 1)
    for i, p in enumerate(a.pmf):
        pmf[i * value] = p
    return Dist(pmf, a.offset * value)


def compound(count: Dist, per_event: Dist, max_events: int = 60) -> Dist:
    """Sum of N independent events, N ~ count, each worth per_event (count must start at 0 or more)."""
    acc = point(0)
    for _ in range(count.offset):
        acc = add(acc, per_event)
    total: Dict[int, float] = defaultdict(float)
    for i, p in enumerate(count.pmf):
        if i > max_events:
            break
        if p > 0:
            for j, q in enumerate(acc.pmf):
                total[acc.offset + j] += p * q
        acc = add(acc, per_event)
    lo, hi = min(total), max(total)
    return _trim([total.get(k, 0.0) for k in range(lo, hi + 1)], lo)


def _betabinom_pmf(n: int, a: float, b: float) -> List[float]:
    """Beta-binomial pmf for m = 0..n. P(0) = G(n+b)G(a+b) / (G(b)G(a+b+n)), then a recurrence: one log-gamma call."""
    out = [math.exp(math.lgamma(n + b) + math.lgamma(a + b) - math.lgamma(b) - math.lgamma(a + b + n))]
    for m in range(n):
        out.append(out[-1] * (n - m) / (m + 1) * (m + a) / (n - m - 1 + b))
    return out


@dataclass
class MakesForecast:
    attempts: Dist
    makes: Dist
    pct_mean: float                  # expected make percentage on the attempts that happen
    _pct_source: tuple               # (alpha, beta, [(attempts, weight)]) for the lazy percentage interval
    p_no_attempt: float

    @property
    def pct_interval_80(self) -> Tuple[float, float]:
        alpha, beta, weights = self._pct_source
        mass = sum(w for _, w in weights)
        if not weights or mass <= 0:
            return float("nan"), float("nan")
        pct: Dict[float, float] = defaultdict(float)
        for n, w in weights:
            for m, pm in enumerate(_betabinom_pmf(n, alpha, beta)):
                pct[m / n] += w * pm
        items = sorted(pct.items())
        c, lo_v, hi_v = 0.0, None, items[-1][0]
        for v, p in items:
            c += p / mass
            if lo_v is None and c >= 0.1:
                lo_v = v
            if c >= 0.9:
                hi_v = v
                break
        return (lo_v if lo_v is not None else items[0][0], hi_v)

    def summary(self, attempt_lines=(), make_lines=()) -> dict:
        return {"attempts": self.attempts.summary(attempt_lines), "makes": self.makes.summary(make_lines),
                "make_pct": round(self.pct_mean, 4),
                "make_pct_interval_80": [round(x, 4) for x in self.pct_interval_80],
                "p_no_attempt": round(self.p_no_attempt, 4)}


def makes(attempts: Dist, alpha: float, beta: float) -> MakesForecast:
    """Makes out of attempts. The make probability is beta(alpha, beta): alpha/(alpha+beta) is the expected rate and
    alpha+beta is how much evidence stands behind it (more evidence, narrower). The 80% interval of the percentage
    is computed only when a summary asks for it (it is slow to compute for every player-game)."""
    made: Dict[int, float] = defaultdict(float)
    p_none = 0.0
    weights: List[Tuple[int, float]] = []
    # attempt counts with probability under 1e-6 are dropped (and the rest renormalized): a heavy tail would
    # otherwise cost hundreds of beta-binomial rows for no visible change
    keep = [(attempts.offset + i, pa) for i, pa in enumerate(attempts.pmf) if pa >= 1e-6]
    tot = sum(pa for _, pa in keep) or 1.0
    for n, pa in ((n, pa / tot) for n, pa in keep):
        if pa <= 0:
            continue
        if n <= 0:
            made[0] += pa
            p_none += pa
            continue
        weights.append((n, pa))
        for m, pm in enumerate(_betabinom_pmf(n, alpha, beta)):
            made[m] += pa * pm
    hi = max(made)
    md = _trim([made.get(k, 0.0) for k in range(hi + 1)], 0)
    return MakesForecast(attempts, md, alpha / (alpha + beta), (alpha, beta, weights), p_none)


@dataclass
class NormalForecast:
    mean: float
    sd: float

    def prob_over(self, line: float) -> float:
        return 1.0 - NormalDist(self.mean, max(self.sd, 1e-9)).cdf(line)

    def interval(self, level: float = 0.8) -> Tuple[float, float]:
        d = NormalDist(self.mean, max(self.sd, 1e-9))
        a = (1.0 - level) / 2.0
        return d.inv_cdf(a), d.inv_cdf(1.0 - a)


class DecayedRate:
    """Per-entity rate learnt from results, older games counting less, shrunk toward a prior:

        rate(key) = (k0 * prior + S) / (k0 + W),  S = decayed sum of values, W = decayed sum of exposure.

    halflife is counted in updates of that entity (games). k0 is how many games' worth of weight the prior gets."""

    def __init__(self, halflife: float, k0: float):
        self.lam = 0.5 ** (1.0 / halflife)
        self.k0 = k0
        self.S: Dict[Hashable, float] = defaultdict(float)
        self.W: Dict[Hashable, float] = defaultdict(float)

    def rate(self, key: Hashable, prior: float) -> float:
        return (self.k0 * prior + self.S[key]) / (self.k0 + self.W[key]) if key in self.W else prior

    def weight(self, key: Hashable) -> float:
        return self.W.get(key, 0.0)

    def beta(self, key: Hashable, prior: float) -> Tuple[float, float]:
        """For a make rate (values = makes, exposure = attempts): beta(alpha, beta) for the make probability."""
        s, w = self.S.get(key, 0.0), self.W.get(key, 0.0)
        return self.k0 * prior + s, self.k0 * (1.0 - prior) + max(0.0, w - s)

    def update(self, key: Hashable, value: float, exposure: float = 1.0) -> None:
        self.S[key] = self.lam * self.S[key] + value
        self.W[key] = self.lam * self.W[key] + exposure


class LeagueRate:
    """A slowly decaying league-wide average (half-life in observations), used as the prior."""

    def __init__(self, halflife: float = 2000.0, start: float = 0.0):
        self.lam = 0.5 ** (1.0 / halflife)
        self.S = 0.0
        self.W = 0.0
        self.start = start

    @property
    def value(self) -> float:
        return self.S / self.W if self.W > 0 else self.start

    def update(self, value: float, exposure: float = 1.0) -> None:
        self.S = self.lam * self.S + value
        self.W = self.lam * self.W + exposure


def fit_size(pairs: Iterable[Tuple[float, int]], grid: Sequence[float] = (1, 1.5, 2, 3, 5, 8, 13, 25, 50, 100, POISSON)
             ) -> float:
    """Choose the negative-binomial size r with the best log likelihood over (mean, observed count) pairs."""
    pairs = list(pairs)
    best, best_r = -float("inf"), POISSON
    for r in grid:
        ll = sum(nb_logpmf(k, mu, r) for mu, k in pairs)
        if ll > best:
            best, best_r = ll, r
    return best_r


def log_score(d: Dist, k: int) -> float:
    """Negative log probability of what happened (lower is better). Floored so one surprise cannot be infinite."""
    return -math.log(max(d.prob(k), 1e-12))


def brier(p: float, y: int) -> float:
    return (p - y) ** 2
