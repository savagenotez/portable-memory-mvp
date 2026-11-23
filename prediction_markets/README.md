# prediction_markets

A simulation and forecasting toolkit for prediction-market style questions. It implements the four-component stat model, the VB-GPC goal-pacing controller, a next-period forecast, and a paper-trading harness that reports win rate, ROI and Brier skill.

## What this does not do

- It does not reverse engineer, decompile, scrape, or connect to any app or website. That covers Kalshi, Polymarket, Outpoll, OG.com, Fanatics Markets, DraftKings, FanDuel, BetMGM, Caesars, bet365, BetRivers, William Hill, Paddy Power, Sky Bet, Betfair, Midnite, Betano, BoyleSports, Robinhood, Qalla, Vibe Market, and the rest. Reverse engineering those services would generally break their terms of service, and it is not needed to test a model.
- It does not place bets, and it does not use your desktop or any logged-in session.
- Every number it produces comes from simulated data generated from `config.json`. Real prices are an input you supply (see "Real market data" below).

Nothing here is evidence of an edge on any real market or sportsbook. Win rate on its own is not profit: fees, vig and the price you pay decide whether a bet makes money.

## Run it

```bash
# from the repository root; standard library only (tested on Python 3.13)
python3 -m unittest discover -s prediction_markets/tests -t .   # 53 tests
python3 -m prediction_markets.run_demo                          # full run, about 25 s, writes results/latest.json
python3 -m prediction_markets.run_demo --quick                  # smoke test, a few seconds, writes nothing
```

## Layout

| File | Role |
|---|---|
| `config.json` | Every editable variable: priors, dynamics, goals, controller gains, betting policy |
| `statmodel.py` | Shared estimators: EB shrinkage, Popoviciu bound, AR(1) helpers |
| `simulate.py` | Domain simulator: `Y_t = clip(mu + trend + seasonal + venue + S_t + X_t + eps_t)` |
| `vbgpc.py` | Goal-attainment controller: feasibility, regimes, PD pacing, Monte Carlo probability |
| `forecast.py` | Next-period expected value, p10–p90 range, milestone odds |
| `markets.py` | Paper trading: EV, fractional Kelly, stake caps, Wilson win-rate interval, Brier scores, CSV loader |
| `backtest.py` | Builds synthetic market events (for tests and the demo only) |
| `run_demo.py` | Runs everything and prints the tables |
| `tests/` | Unit tests for the math, reproducibility, and a demo smoke test |
| `results/latest.json` | Output of the last full run |

## The percentages, and how far to trust them

`run_demo` prints two kinds of goal-attainment number per domain:

- **P(goal) this run**: the controller's probability at the checkpoint, for one simulated season.
- **pred avg vs realized**: over 300 simulated seasons per domain, the average predicted probability against the fraction of seasons that actually hit the goal. This is the calibration check, and it is the number to trust least.

Latest full run (`results/latest.json`):

| Domain | Regime at checkpoint | Pred avg | Realized | Brier skill vs base rate |
|---|---|---|---|---|
| sports_star (82 games, goal 25 ppg) | PD pacing | 14.2% | 10.3% | -0.330 |
| sports_role_player (goal 14.5 ppg) | PD pacing | 15.8% | 21.0% | +0.058 |
| weather_precipitation (30 days, goal 2.5 mm/day) | PD pacing | 49.9% | 36.0% | -0.061 |
| politics_poll_share (60 days, goal 0.48 avg) | PD pacing | 9.7% | 9.0% | -0.205 |
| systems_throughput (168 hours, goal 880/h) | PD pacing | 32.0% | 16.0% | -0.590 |

**Read this as a failed calibration, not a result.** Probabilities are overstated for weather and systems, and the controller adds no skill over the base rate in four of five domains. Likely causes, each of which the spec's Part 4 warns about:

- The steps are treated as Gaussian. Rainfall is skewed and bounded below, and outage shocks give throughput a thin upper tail.
- The plug-in probability uses the shrunk mean as if it were known. With 20 observations, that estimate is uncertain by about 1 point per game, and over a 62-game remainder that uncertainty is as large as the season's own noise.
- Priors are set by hand in `config.json`, and a misspecified prior moves the probability directly.

I tried integrating over the posterior of μ in a scratch experiment. It did not fix calibration (sports_star moved to 19.0% against 11.3% realized, with mixed results elsewhere), so it is not in the package. Fixing calibration is the next real task, and it needs its own evaluation.

Next-game forecast (sports_star, 18 planned shots against a reference of 15): expected 25.0 points, likely range 16.3 to 33.5, P(≥30 points) = 22.4%.

## Paper trading, with the caveats

`run_demo` runs two scenarios on the same synthetic games:

| Scenario | Bets | Win rate (95% CI) | ROI | Bankroll 1000 → | Brier skill vs market |
|---|---|---|---|---|---|
| fair_market (price = true probability, no noise) | 4,849 | 53.1% (51.7–54.5) | -0.9% | 157.59 | -0.024 |
| noisy_market (price = true probability + noise sd 0.05) | 4,946 | 52.4% (51.0–53.8) | +4.7% | 4.3 billion (arithmetic only) | -0.005 |

The fair-market row is the useful one. The model wins 53% of its bets and still loses money, because it pays an average price of 0.527 for those wins. The noisy-market row is positive only because the mispricing is built into the synthetic prices. Real markets are priced by many participants, so mispricing like that tends to be competed away. The large bankroll figure is what compounding about 5,000 correlated bets looks like on paper. It is not a forecast.

## Real market data

To evaluate a model on real prices, export your own data into CSV with these columns. Copy it from sources you are allowed to use.

```
event_id,model_prob,market_price,outcome
```

- `model_prob`: your model's probability that YES resolves, between 0 and 1
- `market_price`: the YES price, strictly between 0 and 1
- `outcome`: 1 if YES resolved, 0 if NO resolved

```bash
python3 -m prediction_markets.markets my_events.csv --fee-rate 0.02 --edge-threshold 0.03
```

Set `--fee-rate` to the fee schedule you verify on the venue. The default of 0 is a placeholder and is not realistic.

## Editing the formula and variables

- **Variables**: `config.json`. Change priors, `phi`, `sigma_eta`, `sigma_eps`, goals, `kp`, `kd`, `lock_in_buffer`, betting limits. Every domain key is validated, and an unknown key is an error.
- **Formula**: `vbgpc.py` (`step_plan` for regimes, `simulate_attainment_prob` for the Monte Carlo), `forecast.py` (action elasticity, fatigue), `markets.py` (EV, Kelly). The domain process itself is in `simulate.simulate_series`.
- After any change, run the tests and then `run_demo`. The calibration table is the check that matters.

## Deviations from the design spec

1. **Seeded Monte Carlo.** The reference draws from the global `random` module, so results change on every run. Here an explicit seeded RNG is used.
2. **`step_plan()` has no side effects.** The reference updates `prev_shrunk_mean` inside planning. Here it is updated in `record_observation`, so the trend term is the change from the previous observation.
3. **Regime 1 target.** The reference's `max(req_pace, mu - 0.25*margin)` always returns `mu - 0.25*margin`, since that term is always larger when Regime 1 applies. It ignores the required pace. The target here is `min(req_pace + lock_in_buffer*margin, mu_hat)`, which is "slightly above r_req" as the spec describes.
4. **Regime 2/3 boundary.** The spec's text puts any `r_req` between μ̂ and μ̂ + 0.75(s_max − μ̂) in both Regime 2 and Regime 3. The reference resolves this by using Regime 3 only above the high-stretch threshold. That is kept.
5. **Regime 1 variance target.** The spec says to drive σ toward σ_min. The passive domains here have no lever for that, so `variance_policy` is reported as a label only.
6. **Normal-approximation cross-check.** Added beside the Monte Carlo estimate.

## Limits

- All outcomes are simulated. Calibration is poor (see above).
- The stationarity assumption fails for trends, seasonal effects, and shocks, and the Gaussian step assumption fails for skewed and bounded stats.
- Goodhart's law applies. Pushing a person toward a numeric target can degrade the behaviour that produces the stat. The controller only reports probabilities. It does not decide what to do about them.
- Active control levers apply only where the subject has agency. For weather and similar passive systems, this is a monitor, not a controller.
