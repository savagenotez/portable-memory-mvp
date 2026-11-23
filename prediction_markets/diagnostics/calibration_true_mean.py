import random
from prediction_markets.simulate import load_config, load_domain_specs, simulate_series
from prediction_markets.vbgpc import GoalAttainmentController, SubjectProfile

cfg = load_config()
specs = {s.key: s for s in load_domain_specs(cfg)}
REPS = 300
for key in ["sports_star", "weather_precipitation", "systems_throughput"]:
    spec = specs[key]
    rem = spec.total_periods - spec.observed_periods
    mu_true_rem = sum(spec.deterministic_mean(t) for t in range(spec.observed_periods, spec.total_periods)) / rem
    plugin, oracle, outs = [], [], []
    for r in range(REPS):
        rep = simulate_series(spec, random.Random(100000 + r))
        h = rep[: spec.observed_periods]
        c = GoalAttainmentController(
            SubjectProfile(spec.prior_mean, spec.prior_strength, spec.stat_min, spec.stat_max),
            goal=spec.goal, total_steps=spec.total_periods, trials=1000, seed=r)
        for y in h:
            c.record_observation(y)
        plugin.append(c.attainment_probability())
        _, sd = c.estimate_parameters()
        oracle.append(c.normal_approx_prob(sum(h), rem, mu_true_rem, sd))
        outs.append(1.0 if sum(rep) >= spec.goal else 0.0)
    n = len(outs)
    print(f"{key:<24} plug-in avg {100*sum(plugin)/n:5.1f}%   true-mean avg {100*sum(oracle)/n:5.1f}%   realized {100*sum(outs)/n:5.1f}%")
