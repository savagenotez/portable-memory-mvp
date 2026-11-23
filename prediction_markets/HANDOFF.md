# Handoff: prediction_markets (for Codex or any agent taking over)

Read this first. It is the state of the work when Claude usage stopped, and it is self-contained.

## Paste this to Codex

> You are continuing work in `savagenotez/portable-memory-mvp` on branch `claude/prediction-markets-algorithm-9rqoli`. Read `AGENTS.md`, `.ai-memory/context/working_context.md`, and `prediction_markets/HANDOFF.md`. Then run the test suite and the demo to confirm the baseline numbers reproduce, and continue from "Next task" in the handoff. Do not reverse engineer, scrape, or connect to any betting or prediction-market app. Keep all demo output labelled as simulated.

## Where things stand

- **Repo:** `savagenotez/portable-memory-mvp`. **Branch:** `claude/prediction-markets-algorithm-9rqoli`. **Base:** `main`.
- **Draft PR:** https://github.com/savagenotez/portable-memory-mvp/pull/1 (open, draft, `mergeable_state: clean`, no reviews, no status checks reported).
- **Pushed commit:** `540a902` "Add prediction-markets simulation and goal-pacing package". Everything in `prediction_markets/` is in that commit.
- **Uncommitted when this file was written:** `prediction_markets/HANDOFF.md`, `prediction_markets/diagnostics/`, and the update to `.ai-memory/UPDATE_NOTES.md`. Check `git status` and `git log -1` for whether they have been pushed.
- **Dependencies:** Python 3 standard library only. Tested on Python 3.13. No pytest needed.

## What the package does

`prediction_markets/` implements:

- `statmodel.py`: Empirical Bayes shrinkage, Popoviciu-bounded volatility, AR(1) helpers.
- `simulate.py`: domain simulators. Each series is `Y_t = clip(mu + trend*t + seasonal + venue + S_t + X_t + eps_t)`, with an optional outage shock. Five domains: `sports_star`, `sports_role_player`, `weather_precipitation`, `politics_poll_share`, `systems_throughput`.
- `vbgpc.py`: the VB-GPC goal-attainment controller from the design spec, with feasibility checks, three regimes, and a seeded Monte Carlo.
- `forecast.py`: next-period expected value, p10–p90 range, milestone odds.
- `markets.py`: paper trading with EV, fractional Kelly with stake cap, Wilson win-rate interval, Brier skill, and a CSV loader for real prices.
- `backtest.py`: synthetic market events, for tests and the demo only.
- `run_demo.py`: prints the tables and writes `results/latest.json`.
- `config.json`: every editable variable. Priors and simulated truths there are my assumptions, not measurements.
- `README.md`: user-facing docs, including deviations from the spec.

## Commands

```bash
cd /home/user/portable-memory-mvp
python3 -m unittest discover -s prediction_markets/tests -t .   # expect: Ran 53 tests ... OK
python3 -m prediction_markets.run_demo                          # about 25 s, rewrites results/latest.json
python3 -m prediction_markets.run_demo --quick                  # a few seconds, writes nothing
```

The simulations are seeded, so a full run should reproduce the numbers below exactly. If they don't, something changed.

## Baseline numbers (from `results/latest.json`)

Goal attainment. "Pred avg" is the mean predicted probability over 300 simulated seasons, and "realized" is the fraction of those seasons that hit the goal.

| Domain | Pred avg | Realized | Brier skill vs base rate |
|---|---|---|---|
| sports_star (goal 25 ppg, 82 games) | 14.2% | 10.3% | -0.330 |
| sports_role_player (goal 14.5 ppg) | 15.8% | 21.0% | +0.058 |
| weather_precipitation (goal 2.5 mm/day, 30 days) | 49.9% | 36.0% | -0.061 |
| politics_poll_share (goal 0.48, 60 days) | 9.7% | 9.0% | -0.205 |
| systems_throughput (goal 880/h, 168 h) | 32.0% | 16.0% | -0.590 |

Every domain sits in regime `PD_PACING_CONTROL` at its checkpoint. Regimes 1 and 3 are covered only by unit tests, not by the demo.

Next-game forecast for `sports_star` (18 planned shots against a reference of 15): expected 25.0 points, p10–p90 16.3–33.5, P(≥30) = 22.4%.

Paper trading, synthetic only:

- **fair_market** (price = true probability): 4,849 bets, win rate 53.1% (CI 51.7–54.5), ROI -0.9%, bankroll 1000 → 157.59, max drawdown 92.3%, Brier skill vs market -0.024.
- **noisy_market** (price = true probability + noise sd 0.05): 4,946 bets, win rate 52.4%, ROI +4.7%, Brier skill vs market -0.005. The edge exists only because the noise was built into the synthetic prices.

## The open problem: calibration

The plug-in goal-attainment probability is poorly calibrated on simulated data. This is the main task, and it decides whether any percentage this package reports can be trusted.

### Evidence so far

Two scripts in `prediction_markets/diagnostics/` reproduce these. Run them from the repo root with `PYTHONPATH=.`.

- `calibration_true_mean.py`: compares the plug-in probability with a normal approximation that uses the true mean for the remaining periods. Results from 300 replicates:

  | Domain | Plug-in | True-mean normal approx | Realized |
  |---|---|---|---|
  | sports_star | 14.5% | 9.9% | 11.3% |
  | weather_precipitation | 52.4% | 21.3% | 42.3% |
  | systems_throughput | 29.2% | 38.7% | 10.7% |

  The weather true-mean figure is not valid. It ignores the clip at 0 mm, which raises the realized mean.

- `calibration_integrated_mu.py`: integrates the probability over the posterior of mu, with sd = sigma_hat / sqrt(n + n0), inside each Monte Carlo trial.

  | Domain | Plug-in (skill) | Integrated (skill) | Realized |
  |---|---|---|---|
  | sports_star | 14.5% (-0.168) | 19.0% (-0.085) | 11.3% |
  | sports_role_player | 19.2% (-0.040) | 23.6% (+0.055) | 20.3% |
  | weather_precipitation | 52.4% (-0.026) | 51.9% (+0.058) | 42.3% |
  | politics_poll_share | 9.7% (+0.005) | 12.4% (+0.034) | 8.3% |
  | systems_throughput | 29.2% (-1.162) | 31.0% (-0.942) | 10.7% |

  Integrating over mu did not fix calibration. It helped skill in three domains and made sports_star worse. It is not in the package.

- Sports-star parameters, averaged over the same 300 replicates: mean mu_hat 23.33 (sd across replicates 1.14), mean sigma_hat 6.80, realized mean per game 23.93. The shrinkage pulls the estimate down because the prior is 22 and the truth is 24.

### Hypotheses, none confirmed

1. **Gaussian steps are wrong.** Systems has outage shocks that give a thin upper tail, so the normal approximation overstates high-goal probabilities. Weather rainfall is skewed and clipped at 0.
2. **Plug-in ignores mu uncertainty.** Over 62 remaining games, mu uncertainty is about the same size as the total's own noise. Integrating over it did not help, so this may not be the whole story.
3. **Prior misspecification.** The sports priors (22 vs true 24) and the systems prior (900 vs an effective mean near 871 once shocks are included) are hand-set in `config.json`.
4. **i.i.d. sigma.** The controller treats the remaining steps as independent, so it uses a variance of about `n * sigma_hat^2`. For AR(1) momentum, the variance of a sum of n terms is about `n * Var(X) * (1 + phi) / (1 - phi)` for large n, which is larger than the i.i.d. figure. The controller ignores that inflation.

### Next task

1. **Define the target.** Propose a calibration criterion before changing anything. For example, pred avg within about 2 standard errors of realized across all five domains, and positive Brier skill. Use the existing 300-replicate protocol, and keep the replicate seeds separate from the seeds used to set any parameter.
2. **Test candidate fixes one at a time, behind flags.** Good candidates are the AR-aware variance of the sum (hypothesis 4), and a skew-aware or empirical-residual step distribution (hypothesis 1). Keep the spec-faithful plug-in as the default unless a change clearly passes the criterion on fresh seeds.
3. **Do not tune `config.json` to hit the numbers.** Priors are assumptions. If you change one, say why and record the before and after numbers.
4. **Write the result to `README.md` and `.ai-memory/UPDATE_NOTES.md`.** Include which hypotheses were tested, and which passed or failed.

## Rules to keep

- **No reverse engineering, scraping, or connecting to any betting or prediction-market app or website.** The user explicitly rejected this. Market prices come in only as CSV that the user supplies.
- **Label every output as simulated.** Never present a synthetic win rate as evidence of an edge on a real market.
- **Win rate is reported only with ROI and Brier skill.** Keep the fair-market scenario as the primary one.
- **Commits and PR text must not name a model.** The Claude attribution rules forbid model names in commits and PRs. Use the `Claude-Session:` trailer in commits, and end PR bodies with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Do not add a `Co-Authored-By` line that names a model.
- **Do not force-push or rewrite history on this branch.** It has an open PR.
- **Keep the user's email out of commits, PRs, and any external request.**
- **Keep the memory files current.** Durable findings go in `.ai-memory/UPDATE_NOTES.md`, as `AGENTS.md` requires.

## Known gaps

- `fee_rate` is 0 in `config.json`. That is a placeholder and not realistic. The user must set it from the venue's published schedule.
- No real price data has been provided. The user said they would export their own.
- The GitHub safety-net check-in that was set for PR #1 belongs to the Claude session. Codex will not get it, so the PR needs manual checking.
- `README.md` in the package states all current results. If you change the code, update the tables.
