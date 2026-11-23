import math, random
from prediction_markets.simulate import load_config, load_domain_specs, simulate_series
from prediction_markets.vbgpc import GoalAttainmentController, SubjectProfile
from prediction_markets.statmodel import clip

class Integrated(GoalAttainmentController):
    def attainment_probability(self, trials=None):
        mu_hat, sigma_hat = self.estimate_parameters()
        n, n0 = len(self.history), self.profile.prior_strength
        mu_sd = sigma_hat / math.sqrt(n + n0) if (n + n0) > 0 else 0.0
        n_trials = trials or self.trials
        lo, hi = self.profile.stat_min, self.profile.stat_max
        gauss = self.rng.gauss
        current, rem, hits = sum(self.history), self.remaining, 0
        for _ in range(n_trials):
            mu = gauss(mu_hat, mu_sd)
            total = current
            for _ in range(rem):
                v = gauss(mu, sigma_hat)
                total += lo if v < lo else (hi if v > hi else v)
            if total >= self.goal:
                hits += 1
        return hits / n_trials

cfg = load_config(); specs = {s.key: s for s in load_domain_specs(cfg)}
REPS = 300
for key in ["sports_star", "sports_role_player", "weather_precipitation", "politics_poll_share", "systems_throughput"]:
    spec = specs[key]
    plugin, integ, outs = [], [], []
    for r in range(REPS):
        rep = simulate_series(spec, random.Random(100000 + r))
        h = rep[: spec.observed_periods]
        prof = SubjectProfile(spec.prior_mean, spec.prior_strength, spec.stat_min, spec.stat_max)
        c = GoalAttainmentController(prof, goal=spec.goal, total_steps=spec.total_periods, trials=1000, seed=r)
        ci = Integrated(prof, goal=spec.goal, total_steps=spec.total_periods, trials=1000, seed=r)
        for y in h:
            c.record_observation(y); ci.record_observation(y)
        plugin.append(c.attainment_probability())
        integ.append(ci.attainment_probability())
        outs.append(1.0 if sum(rep) >= spec.goal else 0.0)
    n = len(outs)
    def brier(p): return sum((a-b)**2 for a,b in zip(p,outs))/n
    base = sum(outs)/n; clim = base*(1-base)
    print(f"{key:<22} plug-in {100*sum(plugin)/n:5.1f}% (skill {1-brier(plugin)/clim:+.3f})  "
          f"integrated {100*sum(integ)/n:5.1f}% (skill {1-brier(integ)/clim:+.3f})  realized {100*base:5.1f}%")
