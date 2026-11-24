# prediction_markets

A simulation and forecasting toolkit for prediction-market style questions. It implements the four-component stat model, the VB-GPC goal-pacing controller, a next-period forecast, a calibration study for the controller's probabilities, and a paper-trading harness that reports win rate, ROI and Brier skill.

## What this does not do

- It does not reverse engineer, decompile, scrape, or connect to any app or website. That covers Kalshi, Polymarket, Outpoll, OG.com, Fanatics Markets, DraftKings, FanDuel, BetMGM, Caesars, bet365, BetRivers, William Hill, Paddy Power, Sky Bet, Betfair, Midnite, Betano, BoyleSports, Robinhood, Qalla, Vibe Market, and the rest. Reverse engineering those services would generally break their terms of service, and it is not needed to test a model.
- It does not place bets, and it does not use your desktop or any logged-in session.
- Every number it produces comes from simulated data generated from `config.json`. Real prices are an input you supply (see "Real market data" below).

Nothing here is evidence of an edge on any real market or sportsbook. Win rate on its own is not profit: fees, vig and the price you pay decide whether a bet makes money.

## Run it

```bash
# from the repository root; standard library only (tested on Python 3.13)
python3 -m unittest discover -s prediction_markets/tests -t .   # 129 tests
python3 -m prediction_markets.run_demo                          # full run, about 25 s, writes results/latest.json
python3 -m prediction_markets.run_demo --quick                  # smoke test, a few seconds, writes nothing
python3 -m prediction_markets.calibration --seed-base 913000000 \
    --out prediction_markets/results/calibration_seedblock_913000000.json   # about 35 s
```

## Layout

| File | Role |
|---|---|
| `config.json` | Every editable variable: priors, dynamics, goals, controller gains, betting policy |
| `statmodel.py` | Shared estimators: EB shrinkage, Popoviciu bound, AR(1) helpers |
| `simulate.py` | Domain simulator: `Y_t = clip(mu + trend + seasonal + venue + S_t + X_t + eps_t)`. `known_drift(t)` gives the calendar-known part of S(t) |
| `vbgpc.py` | Goal-attainment controller: feasibility, regimes, PD pacing, Monte Carlo probability. Optional variants: AR(1) dependence, mu uncertainty, known drift. All off by default |
| `forecast.py` | Next-period expected value, p10–p90 range, milestone odds |
| `markets.py` | Paper trading: EV, fractional Kelly, stake caps, Wilson win-rate interval, Brier scores, CSV loader |
| `backtest.py` | Builds synthetic market events (for tests and the demo only) |
| `run_demo.py` | Runs everything and prints the tables |
| `calibration.py` | Pre-registered calibration study across the controller variants |
| `diagnostics/` | Scripts behind the calibration findings. Not evaluations, and not used by the package |
| `realdata/` | Read-only adapter for the public market-data endpoints Kalshi and Polymarket document officially, plus a calibration report on real prices. See `realdata/README.md` |
| `league/` | A learning algorithm: hierarchical league simulator, branch ensemble with decision scores, tripwires, and a pre-registered study. See `league/README.md` |
| `tests/` | Unit tests for the math, reproducibility, variants, and smoke tests |
| `results/` | `latest.json` (demo), `calibration_seedblock_*.json` (study, one file per seed block) |

## The branch ensemble

The goal-attainment controller below is one tool. `league/` is a separate learning algorithm that combines families of variables (players, teams, conferences, streaks, weather, and crossed effects), scores each family, and is tested against hard conditions. On fresh simulated leagues it captures 49% of the achievable accuracy, against 40% for a single flat model, and 11 of 12 pre-registered criteria pass, including calibration. The one it fails is a relationship that reverses partway through (capture falls from 0.52 to 0.38). It was tested against eight kinds of trap. Details are in `league/README.md`.

## The percentages, and how far to trust them

`run_demo` prints two kinds of goal-attainment number per domain:

- **P(goal) this run**: the controller's probability at the checkpoint, for one simulated season.
- **pred avg vs realized**: over 300 simulated seasons per domain, the average predicted probability against the fraction of seasons that actually hit the goal. This is the calibration check, and it is the number to trust least.

Latest full demo run (`results/latest.json`, spec-faithful defaults):

| Domain | Regime at checkpoint | Pred avg | Realized | Brier skill vs base rate |
|---|---|---|---|---|
| sports_star (82 games, goal 25 ppg) | PD pacing | 14.2% | 10.3% | -0.330 |
| sports_role_player (goal 14.5 ppg) | PD pacing | 15.8% | 21.0% | +0.058 |
| weather_precipitation (30 days, goal 2.5 mm/day) | PD pacing | 49.9% | 36.0% | -0.061 |
| politics_poll_share (60 days, goal 0.48 avg) | PD pacing | 9.7% | 9.0% | -0.205 |
| systems_throughput (168 hours, goal 880/h) | PD pacing | 32.0% | 16.0% | -0.590 |

Next-game forecast (sports_star, 18 planned shots against a reference of 15): expected 25.0 points, likely range 16.3 to 33.5, P(≥30 points) = 22.4%.

## Calibration study

### Pre-registered criterion

Fixed before any variant was run, and not changed afterwards:

> A variant passes if, for every domain, the average predicted probability over R held-out simulated seasons is within two standard errors of the realized hit rate: `|mean(pred) − realized| ≤ 2·SE`, where `SE = sqrt(p(1−p)/R)` and `p` is the realized rate.

Evaluation uses R = 500 seasons per domain, with the MC trial count set to 200 per prediction. Averaging over seasons cancels most of the MC noise, so the MC count does not bias the average. Brier skill against the base rate is reported but is not part of the pass rule.

### Seed blocks

- **912000000**: the first study. It covered the four structural variants.
- **913000000**: the second study. It covered all five variants. The drift variant was added after the first block's results, so its first evaluation is this block. That makes the drift result post-hoc, and it should be confirmed on a new block before anyone relies on it.

Neither block was used to choose `config.json` values.

### Results (predicted % / realized %)

Block 912000000:

| Variant | sports star | role player | weather | politics | systems | domains passing |
|---|---|---|---|---|---|---|
| spec_plug_in | 13.1 / 10.6 ok | 18.7 / 18.8 ok | 51.4 / 43.8 FAIL | 9.1 / 8.6 ok | 32.7 / 12.4 FAIL | 3/5 |
| mu_uncertainty | 17.6 / 10.6 FAIL | 23.0 / 18.8 FAIL | 51.5 / 43.8 FAIL | 12.0 / 8.6 FAIL | 33.7 / 12.4 FAIL | 0/5 |
| ar1_momentum | 13.6 / 10.6 FAIL | 19.1 / 18.8 ok | 51.1 / 43.8 FAIL | 9.7 / 8.6 ok | 32.2 / 12.4 FAIL | 2/5 |
| ar1 + mu_uncertainty | 18.0 / 10.6 FAIL | 23.3 / 18.8 FAIL | 51.2 / 43.8 FAIL | 12.5 / 8.6 FAIL | 33.3 / 12.4 FAIL | 0/5 |

Block 913000000:

| Variant | sports star | role player | weather | politics | systems | domains passing |
|---|---|---|---|---|---|---|
| spec_plug_in | 14.3 / 11.6 ok | 19.0 / 24.4 FAIL | 51.5 / 41.0 FAIL | 8.7 / 8.8 ok | 34.4 / 15.2 FAIL | 2/5 |
| mu_uncertainty | 18.8 / 11.6 FAIL | 23.1 / 24.4 ok | 51.4 / 41.0 FAIL | 11.7 / 8.8 FAIL | 35.7 / 15.2 FAIL | 1/5 |
| ar1_momentum | 14.8 / 11.6 FAIL | 19.3 / 24.4 FAIL | 51.2 / 41.0 FAIL | 9.3 / 8.8 ok | 34.6 / 15.2 FAIL | 1/5 |
| ar1 + mu_uncertainty | 19.1 / 11.6 FAIL | 23.4 / 24.4 ok | 51.2 / 41.0 FAIL | 12.2 / 8.8 FAIL | 35.6 / 15.2 FAIL | 1/5 |
| drift_adjusted | 14.3 / 11.6 ok | 19.0 / 24.4 FAIL | 41.6 / 41.0 ok | 8.7 / 8.8 ok | 34.6 / 15.2 FAIL | 3/5 |

Mean Brier skill against base rate, block 913000000: spec −0.233, mu_uncertainty −0.134, ar1 −0.183, ar1 + mu −0.110, drift −0.238.

**No variant passes all five domains on either block.** The criterion is not met.

### Attribution diagnostics

`prediction_markets/diagnostics/attribution.py` changes one property of a domain and reruns the spec plug-in on block 913000000. These are diagnostics, not fixes.

| Check | Predicted | Realized | Gap |
|---|---|---|---|
| systems, as configured | 34.4% | 15.2% | +19.2 pts |
| systems, outage shocks removed | 53.7% | 45.0% | +8.7 pts |
| role player, as configured | 19.0% | 24.4% | −5.4 pts |
| role player, prior set to the true mean | 32.6% | 24.4% | +8.2 pts |

- **Systems.** Outage shocks explain about half the gap, not all of it. The rest is still unexplained. The shock rate (1% per hour) is also not observable in 48 hours, so no controller that sees only observed history can learn the outage tail. It would need a reference-class prior on the shock rate.
- **Role player.** Moving the prior to the true mean makes the overprediction larger, not smaller. The controller's implied mean and spread match the simulation: remaining mean 868.4 predicted against 867.6 realized, and spread 43 predicted against 46 realized. My reading, not yet verified, is that the plug-in uses the shrunk mean as if it were known, and the shrinkage weight n/(n+n₀) makes the forecast move with sampling noise in the observed history. In this simulation the true mean is fixed, so that movement is noise. The fix is about how the prior's strength relates to between-subject spread, which this simulation does not vary.

### What the study supports

- **Weather.** A calendar-known drift term fixes the overprediction on block 913000000, bringing the prediction to 41.6% against 41.0% realized. The cause is that the flat baseline ignored the seasonal timing. Over the 20 remaining days, the seasonal mean is about 0.5 mm/day lower than over the 10 observed days. This is post-hoc and needs a new seed block to confirm. It also needs the seasonal schedule to be known in advance, so it stays off by default.
- **Mean uncertainty** helps the role player on block 913000000 but overpredicts the other domains, so it is not a general fix.
- **Brier skill** does not improve for any variant. Mean skill is −0.11 at best, against −0.23 for the spec default.
- **Systems** is the hardest domain. Outage tails are not identifiable from 48 observed hours.

The controller's probabilities should not be treated as calibrated. Four things would move this forward: a between-subject prior that varies in the simulation, a reference-class prior on shock rates, a confirmation of the drift result on a new block, and a decision on whether the criterion itself is right for these domains.

Next-game forecast and paper trading below are unaffected, because they use the default settings.

## Paper trading, with the caveats

`run_demo` runs two scenarios on the same synthetic games:

| Scenario | Bets | Win rate (95% CI) | ROI | Bankroll 1000 → | Brier skill vs market |
|---|---|---|---|---|---|
| fair_market (price = true probability, no noise) | 4,849 | 53.1% (51.7–54.5) | -0.9% | 157.59 | -0.024 |
| noisy_market (price = true probability + noise sd 0.05) | 4,946 | 52.4% (51.0–53.8) | +4.7% | 4.3 billion (arithmetic only) | -0.005 |

The fair-market row is the useful one. The model wins 53% of its bets and still loses money, because it pays an average price of 0.527 for those wins. The noisy-market row is positive only because the mispricing is built into the synthetic prices. Real markets are priced by many participants, so mispricing like that tends to be competed away. The large bankroll figure is what compounding about 5,000 correlated bets looks like on paper. It is not a forecast.

## Real market data

To pull resolved-market prices from Kalshi and Polymarket's **official public APIs** (read-only, no reverse engineering), see `realdata/README.md`. A first run on 386 real markets found prices about 10% better than the base rate, with Kalshi consistent with calibrated and Polymarket tentatively too extreme.

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
- **Formula**: `vbgpc.py` (`step_plan` for regimes, `attainment_probability` for the Monte Carlo, `estimate_phi` for AR(1)), `forecast.py` (action elasticity, fatigue), `markets.py` (EV, Kelly). The domain process itself is in `simulate.simulate_series`.
- **Calibration variants**: `calibration.VARIANTS`. A new variant is a dictionary of controller flags, so it can be added without touching the default path.
- After any change, run the tests, then `run_demo`, then the calibration study on a **new** seed block. The calibration table is the check that matters.

## Deviations from the design spec

1. **Seeded Monte Carlo.** The reference draws from the global `random` module, so results change on every run. Here an explicit seeded RNG is used.
2. **`step_plan()` has no side effects.** The reference updates `prev_shrunk_mean` inside planning. Here it is updated in `record_observation`, so the trend term is the change from the previous observation.
3. **Regime 1 target.** The reference's `max(req_pace, mu - 0.25*margin)` always returns `mu - 0.25*margin`, since that term is always larger when Regime 1 applies. It ignores the required pace. The target here is `min(req_pace + lock_in_buffer*margin, mu_hat)`, which is "slightly above r_req" as the spec describes.
4. **Regime 2/3 boundary.** The spec's text puts any `r_req` between μ̂ and μ̂ + 0.75(s_max − μ̂) in both Regime 2 and Regime 3. The reference resolves this by using Regime 3 only above the high-stretch threshold. That is kept.
5. **Regime 1 variance target.** The spec says to drive σ toward σ_min. The passive domains here have no lever for that, so `variance_policy` is reported as a label only.
6. **Normal-approximation cross-check.** Added beside the Monte Carlo estimate.
7. **Calibration variants, off by default.** `dependence="ar1"`, `mu_uncertainty=True`, and `drift=` change the controller. None is the default, so `run_demo` and the spec-faithful controller are unchanged. The drift variant needs the seasonal schedule to be known in advance.

## Limits

- All outcomes are simulated. Calibration is not passing on the pre-registered criterion (see above).
- The stationarity assumption fails for trends, seasonal effects, and shocks, and the Gaussian step assumption fails for skewed and bounded stats.
- Goodhart's law applies. Pushing a person toward a numeric target can degrade the behaviour that produces the stat. The controller only reports probabilities. It does not decide what to do about them.
- Active control levers apply only where the subject has agency. For weather and similar passive systems, this is a monitor, not a controller.
