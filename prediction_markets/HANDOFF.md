# Handoff: prediction_markets (for Codex or any agent taking over)

Read this first. It is the state of the work when Claude usage stopped, and it is self-contained.

## Paste this to Codex

> You are continuing work in `savagenotez/portable-memory-mvp` on branch `claude/prediction-markets-algorithm-9rqoli`. Read `AGENTS.md`, `.ai-memory/context/working_context.md`, and `prediction_markets/HANDOFF.md`. Then run the test suite, the demo, and the calibration study to confirm the baseline numbers reproduce, and continue from "Next task" in the handoff. Do not reverse engineer, scrape, or connect to any betting or prediction-market app. Keep all demo output labelled as simulated.

## Where things stand

- **Repo:** `savagenotez/portable-memory-mvp`. **Branch:** `claude/prediction-markets-algorithm-9rqoli`. **Base:** `main`.
- **Draft PR:** https://github.com/savagenotez/portable-memory-mvp/pull/1
- **Pushed commits:** `540a902` (the package), `778d920` (this handoff and the calibration diagnostics from the previous round).
- **Calibration work (this round):** the calibration harness, controller variant flags, drift support, two result files, attribution diagnostics, and new tests. Check `git status` and `git log -1` to see whether it has been pushed.
- **Dependencies:** Python 3 standard library only. Tested on Python 3.13. No pytest needed.

## What the package does

`prediction_markets/` implements:

- `statmodel.py`: Empirical Bayes shrinkage, Popoviciu-bounded volatility, AR(1) helpers.
- `simulate.py`: domain simulators. Each series is `Y_t = clip(mu + trend*t + seasonal + venue + S_t + X_t + eps_t)`, with an optional outage shock. Five domains: `sports_star`, `sports_role_player`, `weather_precipitation`, `politics_poll_share`, `systems_throughput`. `known_drift(t)` gives the calendar-known part of S(t), seasonal plus venue, with trend excluded.
- `vbgpc.py`: the VB-GPC goal-attainment controller from the design spec, with feasibility checks, three regimes, and a seeded Monte Carlo. Three optional flags, all **off by default**: `dependence="ar1"`, `mu_uncertainty=True`, and `drift=` (a callable S(t)).
- `calibration.py`: the pre-registered calibration study. It runs each variant on fresh seed blocks.
- `forecast.py`, `markets.py`, `backtest.py`, `run_demo.py`: unchanged from the first round. See `README.md`.
- `config.json`: every editable variable. Priors and simulated truths there are my assumptions, not measurements.
- `diagnostics/`: `calibration_true_mean.py`, `calibration_integrated_mu.py`, and `attribution.py`, plus their results. Not used by the package.
- `results/`: `latest.json` (demo), `calibration_seedblock_912000000.json` and `calibration_seedblock_913000000.json` (studies).

## Commands

```bash
cd /home/user/portable-memory-mvp
python3 -m unittest discover -s prediction_markets/tests -t .   # expect: Ran 129 tests ... OK
python3 -m prediction_markets.run_demo                          # about 25 s, rewrites results/latest.json
python3 -m prediction_markets.calibration --seed-base 913000000 \
    --out prediction_markets/results/calibration_seedblock_913000000.json   # about 35 s
PYTHONPATH=. python3 prediction_markets/diagnostics/attribution.py          # about 8 s, diagnostics only
python3 -m prediction_markets.league.study --quick                              # branch ensemble, 4 dev leagues, about 15 s
```

Every league seed block through 9029 is spent (see the ledger below). To evaluate a change, run `python3 -m prediction_markets.league.study --scenarios all --seed-base 10000` (about 6 minutes), and add the block to the ledger.

The simulations are seeded, so the full runs should reproduce the numbers below exactly. If they don't, something changed.

**Important:** do not evaluate a new variant on seed block 912000000 or 913000000. Both have been used. Pick a new block, for example 914000000, and record it.

## Baseline numbers (from `results/latest.json`, spec-faithful defaults)

Goal attainment. "Pred avg" is the mean predicted probability over 300 simulated seasons, and "realized" is the fraction that hit the goal.

| Domain | Pred avg | Realized | Brier skill vs base rate |
|---|---|---|---|
| sports_star (goal 25 ppg, 82 games) | 14.2% | 10.3% | -0.330 |
| sports_role_player (goal 14.5 ppg) | 15.8% | 21.0% | +0.058 |
| weather_precipitation (goal 2.5 mm/day, 30 days) | 49.9% | 36.0% | -0.061 |
| politics_poll_share (goal 0.48, 60 days) | 9.7% | 9.0% | -0.205 |
| systems_throughput (goal 880/h, 168 h) | 32.0% | 16.0% | -0.590 |

Next-game forecast for `sports_star` (18 planned shots against a reference of 15): expected 25.0 points, p10–p90 16.3–33.5, P(≥30) = 22.4%.

Paper trading, synthetic only:

- **fair_market** (price = true probability): 4,849 bets, win rate 53.1% (CI 51.7–54.5), ROI -0.9%, bankroll 1000 → 157.59, max drawdown 92.3%, Brier skill vs market -0.024.
- **noisy_market** (price = true probability + noise sd 0.05): 4,946 bets, win rate 52.4%, ROI +4.7%, Brier skill vs market -0.005. The edge exists only because the noise was built into the synthetic prices.

## Branch ensemble: the learning algorithm (`prediction_markets/league/`)

Built on request: an algorithm that learns and corrects, with families of variables ("branches") scored for effectiveness, correlations between variables, and hard conditions that can trip it up. Full detail is in `league/README.md`. Two rounds so far.

- **Files:** `sim.py` (hierarchical league and nine scenarios), `features.py` (walk-forward features, proven free of future information), `model.py` (online branch ensemble, decision scores, gates, tripwires, binned calibrator, drift reset), `evaluate.py`, `study.py` (pre-registered criteria C1-C8 and H1-H4), `config.json`.
- **Round-2 final** (seeds 9000-9029, 30 leagues x 6 seasons, nine scenarios, run once on frozen code): capture of the achievable accuracy 0.489, against 0.395 for one flat model. Brier skill +5.9% (oracle 12.1%). **11 of 12 criteria pass, including C1 calibration.** Capture by season: 0.36, 0.49, 0.52, 0.56, 0.52.
- **The one failure is H4, the weather flip** (a strong effect reverses sign): capture 0.520 before, 0.375 after (ratio 0.72, needs 0.85). This is a genuine limit. More sensitive drift alarms cost more accuracy than they recover (tested on dev).
- **Round 2 changed two things, both behind switches:** a binned online calibrator (fixes C1, costs 0.9 points of capture) and an earlier drift alarm that resets branch weights to 20% and boosts the learning rate x6 (helps the flip by 1.2 points, costs 0.3 in clean runs). Net cost in clean runs: 1.1 points. The round-1 model is exactly reproducible with the switches off, and a test locks this.
- **Fast/slow learners were tried and rejected** on dev seeds (`use_fast_slow`, off): about 2.5 points of capture lost in every scenario.
- **Safeguards, honestly:** only the plausibility cap is proven necessary (without it a leaking feature "captures" 7.7x the achievable accuracy). Gates, early shrink and Platt scaling have no demonstrated benefit. Platt now costs 2.3 points of capture because the binned calibrator is also on.
- **The plausibility cap misfires under a changed environment.** It is 2x the oracle's gain on clean dev leagues. In severe_shift the achievable skill is far higher, so the cap quarantined the legitimate team branch in 17% of leagues and streak in 10%, costing about 2 points. It needs to come from a live benchmark.
- **Rules revised:** C1 (before the first final run) and H1 (before any fresh-seed run of the hard scenarios). Reasons are in `study.py` and `league/README.md`. No rule was changed after seeing results on a fresh block.
- **Dev optimism:** 0.519 on the dev leagues the model was tuned on, 0.489 on fresh ones.

### Next task (league)

1. **Make the plausibility cap adaptive.** Take it from a live benchmark instead of a fixed number. In the simulator, a strong reference model's running gain is a stand-in for a market price. Then re-check severe_shift, where the fixed cap currently misfires.
2. **Test dropping Platt now that the binned calibrator is on.** Removing Platt raised capture by 2.3 points. Evaluate calibration (C1) with Platt off, on dev seeds first.
3. **The weather flip (H4).** Ideas: a detector that watches the branch's gradient or weight sign, not just its gain; a per-branch restart of the learning-rate schedule; a hierarchical prior that favours small weights on weak interaction branches. Test each on dev seeds, then a fresh block.
4. **Retire safeguards that do not earn their cost.** Gates and early shrink have shown no benefit in any scenario. Re-test once the cap is adaptive, then decide.
5. **Real data.** The learner takes plain feature dictionaries. For real prices, build a feature builder from user-supplied CSV. There is no oracle, so use Brier skill against the base rate and against the closing price.
6. **Per-player outcomes.** The simulator already produces per-player efficiency. Extend the targets to player props.

### League seed ledger

| Seeds | Use |
|---|---|
| 1000-1039 | Dev: tuning and debugging. Not evidence. |
| 5000-5003 | One 4-league smoke test. Retired. |
| 7000-7029 | Round-1 final, core scenarios. Spent. |
| 8000-8029 | Round-1 model on the hard scenarios. Spent. |
| 9000-9029 | Round-2 final, all scenarios. Spent. |
| 10000 and up | Fresh. Use `--seed-base 10000`. |

## Real-data adapter (`prediction_markets/realdata/`)

Built after the user asked to "reverse engineer the apps". That was declined, because it would breach the platforms' terms and is not needed. This is the lawful route: only the public market-data endpoints that Kalshi and Polymarket document officially.

- **What exists:** `http.py` (GET-only, https-only, a three-host allowlist, rate-limit-header handling, retries for dropped connections), `kalshi.py`, `polymarket.py`, `calibration.py` (how well calibrated real prices were), a CLI (`python3 -m prediction_markets.realdata fetch|report`), and 28 offline tests.
- **First result** (fetched 2026-11-24, price 24 hours before close, 386 markets from 305 events): prices are about 10% better than the base rate. Kalshi (236 games) looks calibrated, slope 0.98 +/- 0.41. Polymarket (150 markets from only 69 events) looks too extreme, slope 0.57 +/- 0.30, tentatively. Details and caveats are in `realdata/README.md` and `results/market_calibration.json`.
- **Fetched data is git-ignored.** Only the summary report is committed. Do not commit fetched CSVs.
- **Be polite with the APIs.** Kalshi's candlestick endpoint costs 50 units of a shared 600-unit budget, so a run of 236 events takes about 12 minutes. The client reads the `x-ratelimit-*` headers. Do not remove that.
- **A settled market's last price is the answer.** Always sample a price a fixed time before close.
- **Do not add anything that logs in, uses private endpoints, or scrapes pages.** The host allowlist is there on purpose, and a test checks it.

### Next task (real data)

1. **A sports-stats source.** The league learner needs player, team and weather inputs. The platforms supply prices and outcomes, not stats. Pick a source that is free to use, check its terms, and build a feature builder from it.
2. **Model against market.** Once stats are in, compare the learner's probability with the market price 24 hours before close on resolved games, scored by Brier skill against both the base rate and the price. There is no oracle on real data.
3. **A larger and cleaner sample.** One market per event for Polymarket too, more series and more history, several horizons (for example 1, 6 and 24 hours). Then re-read the Polymarket slope.
4. **The listing artifact.** Check whether the first-listed side is systematically the home or away team. If so, flip to a consistent side before reading any bias into the realized-minus-price gap.

## Calibration: where it stands

**Pre-registered criterion** (in `calibration.py`'s docstring, fixed before any variant ran): for every domain, `|mean(pred) − realized| ≤ 2·SE`, with `SE = sqrt(p(1−p)/R)` and R = 500 held-out seasons per domain.

**Result: no variant passes all five domains on either seed block.** The criterion is not met.

Block 913000000 (5 variants, predicted % / realized %):

| Variant | sports star | role player | weather | politics | systems | domains passing |
|---|---|---|---|---|---|---|
| spec_plug_in | 14.3 / 11.6 ok | 19.0 / 24.4 FAIL | 51.5 / 41.0 FAIL | 8.7 / 8.8 ok | 34.4 / 15.2 FAIL | 2/5 |
| mu_uncertainty | 18.8 / 11.6 FAIL | 23.1 / 24.4 ok | 51.4 / 41.0 FAIL | 11.7 / 8.8 FAIL | 35.7 / 15.2 FAIL | 1/5 |
| ar1_momentum | 14.8 / 11.6 FAIL | 19.3 / 24.4 FAIL | 51.2 / 41.0 FAIL | 9.3 / 8.8 ok | 34.6 / 15.2 FAIL | 1/5 |
| ar1 + mu_uncertainty | 19.1 / 11.6 FAIL | 23.4 / 24.4 ok | 51.2 / 41.0 FAIL | 12.2 / 8.8 FAIL | 35.6 / 15.2 FAIL | 1/5 |
| drift_adjusted | 14.3 / 11.6 ok | 19.0 / 24.4 FAIL | 41.6 / 41.0 ok | 8.7 / 8.8 ok | 34.6 / 15.2 FAIL | 3/5 |

Block 912000000 (first study, the four structural variants): spec 3/5, mu_uncertainty 0/5, ar1 2/5, ar1 + mu 0/5. Full table in `README.md`.

Mean Brier skill, block 913000000: spec −0.233, mu_uncertainty −0.134, ar1 −0.183, ar1 + mu −0.110, drift −0.238.

**Attribution** (`diagnostics/attribution.py`, block 913000000, spec plug-in):

- Systems predicted 34.4% against 15.2% realized. With outage shocks removed, it's 53.7% against 45.0%. Shocks explain about half the gap. The rest is unexplained.
- Role player, prior as configured: predicted 19.0% against 24.4%. With the prior set to the true mean: 32.6% against 24.4%. So the prior is not the simple fix, and the direction flips.
- The controller's implied remaining mean and spread match the simulation for role player: remaining mean 868.4 predicted vs 867.6 realized; spread 43 vs 46. My unverified reading is that the shrinkage weight makes the forecast move with noise in the observed history. In this simulation the true mean is fixed, so that movement is noise.

**Weather** is explained by the seasonal timing. Over the 20 remaining days, the seasonal mean is about 0.5 mm/day lower than over the 10 observed days, which the flat baseline ignores. Adding known drift brings weather to 41.6% against 41.0%. This is **post-hoc**, found after block 912000000, and it has only been evaluated on block 913000000.

Earlier evidence, from the first round and still valid: the integrated-mu scratch experiment (now the `mu_uncertainty` flag) helped skill in some domains and worsened sports_star. The true-mean oracle (`diagnostics/calibration_true_mean.py`) matched realized for sports_star but was biased for weather because it ignored the clip at 0.

## Next task

1. **Confirm the drift result on a new block.** Run `drift_adjusted` against `spec_plug_in` on a new seed block, for example 914000000. Do not change anything else. Report the weather result. If it does not hold, say so.
2. **Decide what the controller should claim.** The current plug-in can't pass the criterion, and no flag fixes all domains. Options: (a) keep the spec-faithful controller and label its probabilities "uncalibrated" in every output, or (b) add a between-subject spread to the simulator (`true_mu` drawn per subject), so the shrinkage weight is tested against a world where it should matter. Option (b) is the honest test of the prior-strength issue. It needs a new simulator option, and the change should be documented.
3. **For systems, a shock-rate prior.** Outages at 1% per hour cannot be learned from 48 hours. Add a reference-class prior on the shock rate as a flag, then test it on a new block. Don't tune its value to the results.
4. **Keep the criterion.** It was pre-registered. If you think it's wrong for these domains, change it in writing before the next study, and say why.
5. **Update the record.** Write the outcome of each step to `README.md`, `.ai-memory/UPDATE_NOTES.md`, and this file. Record the seed block used, and say whether each result is pre-registered or post-hoc.

## Rules to keep

- **No reverse engineering, scraping, or connecting to any betting or prediction-market app or website.** Market prices come in only as CSV that the user supplies, or from the official public endpoints in `realdata/` (read-only, allowlisted hosts, no credentials). When asked to reverse engineer an app, decline and point to those.
- **Label every output as simulated.** Never present a synthetic win rate as evidence of an edge on a real market.
- **Win rate is reported only with ROI and Brier skill.** Keep the fair-market scenario as the primary one.
- **Never evaluate on a used seed block.** Blocks 912000000 and 913000000 (goal-attainment study) and league seeds 7000-7029, 8000-8029 and 9000-9029 are spent. Use a fresh one and record it.
- **Don't tune `config.json` to hit a number.** Priors are assumptions. If you change one, say why and record the before and after.
- **Keep the spec-faithful default.** Calibration variants are flags, off by default.
- **Commits and PR text must not name a model.** Use the `Claude-Session:` trailer in commits, and end PR bodies with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Do not add a `Co-Authored-By` line that names a model.
- **Do not force-push or rewrite history on this branch.** It has an open PR.
- **Keep the user's email out of commits, PRs, and any external request.**
- **Keep the memory files current.** Durable findings go in `.ai-memory/UPDATE_NOTES.md`, as `AGENTS.md` requires.

## Known gaps

- `fee_rate` is 0 in `config.json`. That is a placeholder and not realistic. The user must set it from the venue's published schedule.
- No real price data has been provided. The user said they would export their own.
- The GitHub safety-net check-in that was set for PR #1 belongs to the Claude session. Codex will not get it, so the PR needs manual checking.
- `README.md` states the current results. If you change the code, update the tables.
