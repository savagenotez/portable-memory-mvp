"""Branch ensemble: a small online network whose hidden units are variable families.

Structure (all online, standard library only):

    features of branch b --standardize--> w_b . x + bias_b = z_b        (each branch trains on its own)
    z_meta  = beta0 + sum_b a_b * g_b * z_b                             (a_b learned, g_b = gate)
    z_final = clip(alpha * kappa * z_meta + gamma)                      (alpha, gamma = online Platt scaling)
    p       = sigmoid(z_final)

Decision score of a branch, measured only on predictions made BEFORE each outcome is revealed:
    solo gain      loss(base rate) - loss(branch alone)       does it help on its own
    marginal gain  loss(model without b) - loss(model)        does the model lose without it
    score          0.5 * (t_stat(solo) + t_stat(marginal))    t-stat of the recent average gain
The gate g_b follows the score. A branch that stops earning its keep fades out but keeps learning,
so it can come back.

Tripwires (each can be switched off, to measure what it buys):
    gates              fade out branches with low or negative decision scores
    drift              if a branch's short-window gain falls well below its long-window gain,
                       boost its learning rate and halve its gate for a while
    plausibility cap   quarantine a branch whose solo gain is implausibly large (suspected leakage)
    early shrink       pull the logit toward the base rate when teams have few observed games
    platt              online calibration of the final logit
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


def sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-z)
        return 1.0 / (1.0 + e)
    e = math.exp(z)
    return e / (1.0 + e)


def logloss(p: float, y: int) -> float:
    p = min(1.0 - 1e-9, max(1e-9, p))
    return -math.log(p) if y else -math.log(1.0 - p)


def _clip(x: float, lim: float) -> float:
    return -lim if x < -lim else (lim if x > lim else x)


@dataclass(frozen=True)
class ModelConfig:
    lr0: float = 0.05
    lr_min: float = 0.01
    lr_decay_games: float = 500.0
    l2: float = 1e-3
    meta_lr: float = 0.01
    platt_lr: float = 0.003          # floor of the Platt learning rate
    platt_lr0: float = 0.003         # starting Platt learning rate; decays toward platt_lr
    platt_decay_games: float = 300.0
    logit_clip: float = 4.0
    std_halflife: float = 1500.0
    std_clip: float = 5.0
    score_halflife: float = 200.0
    short_halflife: float = 40.0
    warmup_neff: float = 80.0
    gate_slope: float = 1.5
    gate_center: float = 0.5
    gate_floor: float = 0.1
    drift_z: float = 2.5
    drift_recovery: int = 60
    drift_lr_boost: float = 3.0
    drift_gate_factor: float = 0.5
    early_shrink_n: float = 2.0
    use_gates: bool = True
    use_drift: bool = True
    use_plausibility_cap: bool = True
    use_early_shrink: bool = True
    use_platt: bool = True


class EWMAStat:
    """Exponentially weighted mean and variance with an effective sample size."""

    __slots__ = ("lam", "s1", "s2", "w1", "w2")

    def __init__(self, halflife: float):
        self.lam = 0.5 ** (1.0 / halflife)
        self.s1 = self.s2 = self.w1 = self.w2 = 0.0

    def add(self, x: float) -> None:
        lam = self.lam
        self.s1 = lam * self.s1 + x
        self.s2 = lam * self.s2 + x * x
        self.w1 = lam * self.w1 + 1.0
        self.w2 = lam * lam * self.w2 + 1.0

    @property
    def mean(self) -> float:
        return self.s1 / self.w1 if self.w1 > 0 else 0.0

    @property
    def var(self) -> float:
        if self.w1 <= 0:
            return 0.0
        m = self.s1 / self.w1
        return max(self.s2 / self.w1 - m * m, 0.0)

    @property
    def n_eff(self) -> float:
        return self.w1 * self.w1 / self.w2 if self.w2 > 0 else 0.0

    @property
    def tstat(self) -> float:
        n = self.n_eff
        if n <= 1.0:
            return 0.0
        return self.mean / math.sqrt(self.var / n + 1e-12)


class Standardizer:
    """Online per-feature z-scoring with exponential forgetting. Uses statistics from before the current row."""

    def __init__(self, n: int, halflife: float, clip: float):
        self.n = n
        self.lam = 0.5 ** (1.0 / halflife)
        self.clip = clip
        self.s1 = [0.0] * n
        self.s2 = [0.0] * n
        self.w = 0.0

    def transform(self, x: Sequence[float]) -> List[float]:
        if self.w < 5.0:
            return [0.0] * self.n
        out = []
        for i in range(self.n):
            m = self.s1[i] / self.w
            v = max(self.s2[i] / self.w - m * m, 1e-6)
            out.append(_clip((x[i] - m) / math.sqrt(v), self.clip))
        return out

    def update(self, x: Sequence[float]) -> None:
        lam = self.lam
        for i in range(self.n):
            self.s1[i] = lam * self.s1[i] + x[i]
            self.s2[i] = lam * self.s2[i] + x[i] * x[i]
        self.w = lam * self.w + 1.0


class Branch:
    def __init__(self, name: str, features: List[str], cfg: ModelConfig):
        self.name = name
        self.features = features
        n = len(features)
        self.w = [0.0] * n
        self.bias = 0.0
        self.std = Standardizer(n, cfg.std_halflife, cfg.std_clip)
        self.solo = EWMAStat(cfg.score_halflife)
        self.marg = EWMAStat(cfg.score_halflife)
        self.solo_short = EWMAStat(cfg.short_halflife)
        self.alarm_until = -1
        self.quarantined = False
        self.events: List[dict] = []


@dataclass
class Prediction:
    p: float
    z_meta: float
    z_final: float
    kappa: float
    zb: Dict[str, float]
    gates: Dict[str, float]
    xs: Dict[str, List[float]]
    raw: Dict[str, List[float]]


class BranchEnsemble:
    def __init__(self, branch_features: Dict[str, List[str]], cfg: ModelConfig = ModelConfig(),
                 plausible_gain: Optional[float] = None):
        self.cfg = cfg
        self.plausible_gain = plausible_gain
        self.branches: Dict[str, Branch] = {name: Branch(name, list(cols), cfg) for name, cols in branch_features.items()}
        k = len(self.branches)
        self.a = {name: 1.0 / k for name in self.branches}
        self.beta0 = 0.0
        self.alpha = 1.0
        self.gamma = 0.0
        self.t = 0
        self.wins = 0

    # ---- gating -------------------------------------------------------------------------
    def decision_score(self, b: Branch) -> Optional[float]:
        warm = self.cfg.warmup_neff
        if b.solo.n_eff < warm or b.marg.n_eff < warm:
            return None
        return 0.5 * (b.solo.tstat + b.marg.tstat)

    def gate(self, b: Branch) -> float:
        cfg = self.cfg
        if b.quarantined:
            return 0.0
        if not cfg.use_gates:
            g = 1.0
        else:
            score = self.decision_score(b)
            if score is None:
                g = 1.0
            else:
                g = cfg.gate_floor + (1.0 - cfg.gate_floor) * sigmoid(cfg.gate_slope * (score - cfg.gate_center))
        if self.t < b.alarm_until:
            g *= cfg.drift_gate_factor
        return g

    # ---- predict ------------------------------------------------------------------------
    def predict(self, features: Dict[str, float], context: Dict[str, float]) -> Prediction:
        cfg = self.cfg
        zb: Dict[str, float] = {}
        gates: Dict[str, float] = {}
        xs: Dict[str, List[float]] = {}
        raw: Dict[str, List[float]] = {}
        z_meta = self.beta0
        for name, b in self.branches.items():
            r = [features[f] for f in b.features]
            x = b.std.transform(r)
            z = b.bias + sum(w * v for w, v in zip(b.w, x))
            g = self.gate(b)
            zb[name], gates[name], xs[name], raw[name] = z, g, x, r
            z_meta += self.a[name] * g * z
        if cfg.use_early_shrink:
            n = context.get("min_games_total", 1e9)
            kappa = n / (n + cfg.early_shrink_n)
        else:
            kappa = 1.0
        alpha = self.alpha if cfg.use_platt else 1.0
        gamma = self.gamma if cfg.use_platt else 0.0
        z_final = _clip(alpha * kappa * z_meta + gamma, cfg.logit_clip)
        return Prediction(sigmoid(z_final), z_meta, z_final, kappa, zb, gates, xs, raw)

    # ---- update -------------------------------------------------------------------------
    def update(self, pred: Prediction, y: int) -> None:
        cfg = self.cfg
        self.t += 1
        lr = max(cfg.lr_min, cfg.lr0 / (1.0 + self.t / cfg.lr_decay_games))
        p0 = (self.wins + 1.0) / (self.t + 1.0)
        loss_base = logloss(p0, y)
        loss_full = logloss(pred.p, y)
        alpha = self.alpha if cfg.use_platt else 1.0
        gamma = self.gamma if cfg.use_platt else 0.0

        for name, b in self.branches.items():
            z = pred.zb[name]
            p_b = sigmoid(_clip(z, cfg.logit_clip))
            solo_gain = loss_base - logloss(p_b, y)
            z_abl = _clip(alpha * pred.kappa * (pred.z_meta - self.a[name] * pred.gates[name] * z) + gamma, cfg.logit_clip)
            marg_gain = logloss(sigmoid(z_abl), y) - loss_full
            b.solo.add(solo_gain)
            b.solo_short.add(solo_gain)
            b.marg.add(marg_gain)

            boost = cfg.drift_lr_boost if self.t < b.alarm_until else 1.0
            err = p_b - y
            step = lr * boost
            x = pred.xs[name]
            for i in range(len(b.w)):
                b.w[i] -= step * (err * x[i] + cfg.l2 * b.w[i])
            b.bias -= step * err
            b.std.update(pred.raw[name])

            self._tripwires(b)

        p_meta = sigmoid(_clip(pred.z_meta, cfg.logit_clip))
        err_m = p_meta - y
        for name in self.branches:
            grad = err_m * pred.gates[name] * pred.zb[name]
            self.a[name] = min(2.0, max(0.0, self.a[name] - cfg.meta_lr * grad))
        self.beta0 -= cfg.meta_lr * err_m

        if cfg.use_platt:
            err_f = pred.p - y
            plr = max(cfg.platt_lr, cfg.platt_lr0 / (1.0 + self.t / cfg.platt_decay_games))
            self.gamma -= plr * err_f
            self.alpha = min(2.0, max(0.2, self.alpha - plr * err_f * pred.kappa * pred.z_meta))

        self.wins += y

    def _tripwires(self, b: Branch) -> None:
        cfg = self.cfg
        if (cfg.use_plausibility_cap and self.plausible_gain is not None and not b.quarantined
                and b.solo.n_eff >= cfg.warmup_neff and b.solo.mean > self.plausible_gain):
            b.quarantined = True
            b.events.append({"t": self.t, "event": "quarantined", "solo_gain": b.solo.mean})
        if (cfg.use_drift and self.t >= b.alarm_until and b.solo.n_eff >= 100
                and b.solo_short.n_eff >= 20):
            se = math.sqrt(max(b.solo.var, 1e-12) / b.solo_short.n_eff)
            if b.solo_short.mean - b.solo.mean < -cfg.drift_z * se:
                b.alarm_until = self.t + cfg.drift_recovery
                b.events.append({"t": self.t, "event": "drift_alarm",
                                 "short": b.solo_short.mean, "long": b.solo.mean})

    # ---- report -------------------------------------------------------------------------
    def report(self) -> Dict[str, dict]:
        out = {}
        for name, b in self.branches.items():
            out[name] = {
                "score": self.decision_score(b),
                "solo_gain": b.solo.mean,
                "marginal_gain": b.marg.mean,
                "gate": self.gate(b),
                "weight": self.a[name],
                "quarantined": b.quarantined,
                "drift_alarms": sum(1 for e in b.events if e["event"] == "drift_alarm"),
            }
        return out


class FlatLogistic:
    """Comparison model: one online logistic regression over every feature, with no branches or gates."""

    def __init__(self, features: List[str], cfg: ModelConfig = ModelConfig()):
        self.cfg = cfg
        self.features = list(features)
        self.w = [0.0] * len(features)
        self.bias = 0.0
        self.std = Standardizer(len(features), cfg.std_halflife, cfg.std_clip)
        self.t = 0

    def predict(self, features: Dict[str, float], context: Dict[str, float]):
        r = [features[f] for f in self.features]
        x = self.std.transform(r)
        z = _clip(self.bias + sum(w * v for w, v in zip(self.w, x)), self.cfg.logit_clip)
        return sigmoid(z), x, r

    def update(self, state, y: int) -> None:
        p, x, r = state
        self.t += 1
        lr = max(self.cfg.lr_min, self.cfg.lr0 / (1.0 + self.t / self.cfg.lr_decay_games))
        err = p - y
        for i in range(len(self.w)):
            self.w[i] -= lr * (err * x[i] + self.cfg.l2 * self.w[i])
        self.bias -= lr * err
        self.std.update(r)
