# league: a branch ensemble that learns and corrects

This subpackage is a learning algorithm, not just a simulation. It predicts which team wins a game by combining several families of variables, called **branches**. Each branch has its own online learner and a **decision score** that measures whether the branch is earning its place. Hard-condition tests try to trip it up.

Everything here is simulated. It does not connect to, scrape, or reverse engineer any betting or prediction-market service, and nothing here is evidence of an edge on a real market.

## The idea in plain language

Think of a panel of specialists. One reads team records, one reads individual players, one reads the schedule, one reads conferences and regions, one reads streaks, one reads the weather, one reads combinations such as "a running team in high wind." A manager combines their opinions.

After every game the system does the same loop:

1. **Predict** the game before the result is known.
2. **Compare** the prediction with what happened.
3. **Learn.** Each specialist adjusts, and the manager adjusts how much to trust each one.
4. **Score** each specialist on two questions: does it help on its own, and does the panel get worse without it? A specialist who stops helping gets quieter but keeps learning, so it can come back.

Safeguards watch for the ways this can go wrong: a specialist who has secretly seen the answer, one whose usefulness vanishes, early-season games with little data, a relationship that reverses, and a panel that is too sure of itself.

## The simulated league

Regions contain conferences, conferences contain teams, and teams contain players. Hidden truth drives each game:

- team, conference and region strength, plus year-to-year drift
- individual player talent weighted by usage, injuries, and a hidden "form" that persists for a while
- home advantage, rest days, and weather that matters only through team style (for example, wind favours some styles)
- a known true win probability, called the **oracle**, which is the best any model could do

The model sees only scores, noisy per-player efficiency readings, availability, rest, weather, style, and group membership. Features for each game are built **only from earlier games**. A test proves this by changing every later result and checking that earlier features do not move.

## Branches

| Branch | What it reads |
|---|---|
| team | net rating, win rate, points for and against |
| player | roster talent from individual readings, star availability, recent form |
| schedule | rest, back-to-back games, number of games played, season progress |
| geo | conference and region strength, cross-conference and same-region flags |
| streak | current streak and recent margins |
| weather | temperature, wind, precipitation, indoor flag |
| interaction | crossed effects: team style x weather, rest x strength |
| decoy_noise | four pure-noise columns. Their score should stay near zero |

Scenario extras: `news` (a decoy feature), `leak` (contains the game outcome), `team_dup` (a near-copy of the team branch), and `haystack_0`-`haystack_8` (36 pure-noise columns).

## The hard conditions

| Scenario | The trap |
|---|---|
| spurious_decoy | A feature tracks true strength for two seasons, then turns to noise |
| leakage_trap | A feature contains the game outcome |
| duplicate_branch | A branch is a near-copy of the team branch |
| regime_shift | Hidden team strengths jump once mid-season |
| reversal_decoy | A feature tracks true strength, then flips its sign every season |
| haystack | 36 extra noise columns, so false signals have many places to appear |
| severe_shift | Two large shocks to 70% of teams, with part of the player talent redrawn |
| weather_flip | A strong style x wind effect reverses sign partway through |

## Safeguards, and what each one did (round-2 model, seeds 9000-9029)

All of these can be switched off in `ModelConfig`, so their value can be measured. Change in capture when the safeguard is removed, clean runs:

| Safeguard | What it does | Result |
|---|---|---|
| plausibility cap | quarantines a branch whose solo gain is implausibly large | **Essential against leakage.** Without it, the leak "captures" 7.7x the achievable accuracy. **But it misfires** (see below) |
| binned calibrator | online correction by predicted-probability bin | Fixes the calibration defect (C1). Costs about 0.9 points of capture |
| drift alarm, reset and boost | on a collapse in a branch's recent gain, shrink its weights to 20% and raise its learning rate x6 | Helps the weather flip by 1.2 points. Fires about once per league across all branches in clean runs (mostly player and interaction), costing about 0.3 points |
| calibration scaling (Platt) | online correction of the final logit | Costs 2.3 points of capture now that the binned calibrator is also on |
| gates | fade branches with low decision scores | No demonstrated benefit anywhere. Costs about 0.3 points in clean runs and 0.6 points in the weather flip |
| early-season shrink | pulls toward the base rate when little has been seen | No measurable effect |

**The plausibility cap misfires when the environment changes.** The cap is 2x the oracle's gain on clean dev leagues (0.136 nats per game). In the severe-shift scenario, the achievable skill is much higher (oracle skill 20.9% against 12.1%), so the cap quarantined the legitimate team branch in 17% of leagues and the streak branch in 10%. That cost about 2 points. A fixed cap needs to be replaced by one taken from a live benchmark, which in real use would be a market price.

## Run it

```bash
python3 -m unittest discover -s prediction_markets/tests -t .   # 101 tests
python3 -m prediction_markets.league.study --quick --scenarios all   # 4 dev leagues, about 45 s, writes nothing
python3 -m prediction_markets.league.study --scenarios all --seed-base 10000   # about 6 minutes, writes results/
```

`--scenarios` accepts `core` (the original five), `hard` (clean plus the four new ones), `all`, or a comma-separated list. **Seed block 10000 is the next fresh one.** Every block in the ledger below is spent. Do not run a final study repeatedly while changing the code.

## Results

"Capture" is the share of the achievable accuracy gain over the base rate. 1.0 would match the oracle. Capture needs an oracle, so it is a simulation-only measure.

### Round 2 final: seeds 9000-9029, 30 leagues x 6 seasons, all nine scenarios, scored from season 1

Capture by scenario, with the round-1 model run on the same leagues:

| Scenario | Round 2 (v2) | Round 1 (v1) | All safeguards off | One flat model |
|---|---|---|---|---|
| clean | 0.489 | 0.500 | 0.522 | 0.395 |
| spurious_decoy | 0.491 | 0.502 | 0.520 | 0.380 |
| leakage_trap | 0.493 | 0.502 | 7.690 | 7.172 |
| duplicate_branch | 0.514 | 0.525 | 0.547 | 0.374 |
| regime_shift | 0.493 | 0.505 | 0.523 | 0.413 |
| reversal_decoy | 0.495 | 0.500 | 0.518 | 0.381 |
| haystack | 0.466 | 0.475 | 0.495 | 0.018 |
| severe_shift | 0.568 | 0.573 | 0.601 | 0.537 |
| weather_flip | 0.438 | 0.435 | 0.449 | 0.354 |

Brier skill against the base rate is +5.9% (95% interval 5.1% to 6.7%). The oracle's is 12.1%. The ensemble beats the flat model by 0.0028 Brier (95% interval 0.0022 to 0.0034).

**It learns.** Capture by season: 0.36, 0.49, 0.52, 0.56, 0.52.

**The branch structure is what protects it.** On the 70-column haystack the flat model captures 1.8% of the achievable accuracy, against 46.6% for the branch ensemble. After the weather flip the flat model captures 4.5%, against 37.5%.

**Pre-registered criteria: 11 of 12 pass.**

| | Criterion | Result |
|---|---|---|
| C1 | clean calibration: overall within 2 SE, every slice within 3 SE | **PASS.** Overall +0.98 SE. Worst slice (predicted 40-60%) +2.65 SE |
| C2 | clean skill positive, and not worse than the flat model | PASS |
| C3 | capture in the last two seasons at least the first two | PASS (0.42 to 0.54) |
| C4 | spurious feature: capture after it breaks at least 0.95x clean | PASS (0.510 vs 0.521) |
| C5 | leakage: no fake skill, leak branch quarantined | PASS (quarantined in 100% of leagues) |
| C6 | duplicate branch: capture at least 0.95x clean, calibration holds | PASS |
| C7 | regime shift: capture recovers | PASS (0.45 before, 0.40 right after, 0.47 later) |
| C8 | team branch score above 2, noise branch below 1 | PASS (+2.89 and -0.87) |
| H1 | alternating decoy: capture at least 0.90x clean | PASS (0.514 vs 0.521) |
| H2 | haystack: capture at least 0.90x clean, no false discovery | PASS (0.466 vs 0.489). Worst noise-branch score -0.56 |
| H3 | severe shifts: capture recovers after each shock | PASS (shock 1: 0.45, 0.34, 0.53. Shock 2: 0.68, 0.51, 0.68) |
| H4 | weather flip: capture in the 300 games after at least 0.85x the 300 before | **FAIL.** 0.520 before, 0.375 after (ratio 0.72) |

**Calibration, same clean games, round 1 against round 2.** Round 1 fails C1 on these games: overall +1.99 SE, and the predicted 40-60% slice at +3.82 SE. Round 2 passes: +0.98 SE overall, and the same slice at +2.65 SE. The defect is reduced, not gone. Games predicted at 40-60% are still over-predicted for the home team by 0.8 points.

**What round 2 cost.** Clean-run capture fell from 0.500 to 0.489. The calibrator costs 0.9 points. The drift change costs 0.3 points.

**Branch decision scores (clean, mean over leagues).**

| Branch | Score | Gate | Reading |
|---|---|---|---|
| team | +2.89 | 0.98 | Does most of the work |
| player | +1.60 | 0.88 | Clearly useful |
| streak | +1.37 | 0.89 | Mostly repeats what team record already says |
| geo | +0.70 | 0.78 | Small |
| interaction | +0.35 | 0.72 | Not proven |
| weather | -0.34 | 0.58 | Not proven |
| schedule | -0.66 | 0.50 | Not proven |
| decoy_noise | -0.87 | 0.47 | Correctly scored as useless |

Rest days and the style x wind effect are real in the simulation, but they are small. About 1,000 games per league cannot separate them from noise, so their scores sit near zero. The system is saying "not proven," which is the honest answer at that sample size.

### Round 1, for the record

- **Core scenarios, seeds 7000-7029 (round-1 model).** Capture 0.483, against 0.387 for the flat model. 7 of 8 criteria pass. C1 failed: the predicted 40-60% slice was over-predicted by 1.2 points (3.98 SE).
- **Hard scenarios, seeds 8000-8029 (round-1 model).** H1, H2, H3 pass. H4 fails (0.484 before the flip, 0.302 after, ratio 0.62). C1 fails again on the same slice (3.93 SE), so the defect is real. Files: `results/league_study_seeds7000_core.json` and `results/league_study_seeds8000_hard.json`.

### Rules that were changed, and why

- **C1** was revised once before the first final run, from "90% of 12 slices within 2 SE" to "every slice within 3 SE". The first rule fails a perfectly calibrated model about 10% of the time.
- **H1** was revised once, before any fresh-seed run of the hard scenarios. A dev run showed that a permanent sign reversal is relearnable, so a high gate is correct and the first rule was ill-posed. H1 became an alternating sign, which cannot be settled into.
- No rule was changed after seeing results on a fresh seed block.

## What the study does not show

- **The weather flip is not fixed.** A relationship that reverses is the one trap that genuinely hurts. The drift alarm helps a little, and more sensitive alarms cost more accuracy than they recover. A flat model is far worse (4.5%), but 0.375 against 0.520 is still a 28% loss.
- **The safeguards cost accuracy.** With every safeguard off, clean capture is 0.522 against 0.489. Only the plausibility cap is proven necessary, and it needs a live benchmark.
- **Dev results are optimistic.** The same model scored 0.519 on the 40 dev leagues it was tuned on and 0.489 on fresh ones. Use the fresh number.
- **The calibrator leaves a small defect.** The 40-60% slice is still 0.8 points high.
- **Everything is simulated.** The league was built to have learnable structure. Real leagues may not.
- **Fast and slow learners were tried and rejected.** Two learners per branch, mixed by recent performance, cost about 2.5 points of capture on dev seeds in every scenario to help one. The switch (`use_fast_slow`) remains, off.

## Seed ledger

| Seeds | Use |
|---|---|
| 1000-1039 | Dev. Tuning and debugging. Not evidence. |
| 5000-5003 | One 4-league smoke test. Retired. |
| 7000-7029 | Round-1 final, core scenarios. Spent. |
| 8000-8029 | Round-1 model on the hard scenarios. Spent. |
| 9000-9029 | Round-2 final, all scenarios. Spent. |
| 10000 and up | Fresh. |

Hyperparameters were tuned on dev seeds only: learning rate (0.03 falling to 0.005), gate center 0 and floor 0.3, a decaying Platt rate (0.05 down to 0.003), a drift alarm at z = 2.0 with a weight reset to 20% and a learning-rate boost of 6, and a binned calibrator with a prior of 200 games.

## Editing and extending

- **Variables:** `config.json` (three sections: `league`, `model`, `study`). Unknown keys are rejected.
- **Add a branch:** add its columns to `features.py` (`BASE_BRANCHES` and `features_for`), and the learner picks it up. Its decision score then tells you whether it earns its place.
- **Add a hard condition:** add a scenario name in `sim.py`, its features in `features.py`, and a pass rule in `study.judge`. Write the rule down before running it on a fresh seed block.
- **Add a safeguard or change:** add a switch to `ModelConfig`. Include it in `study.variants`, so its value is measured on the same leagues.
- After any change: run the tests, then the dev study, then a final study on a **new** seed block. Record the block in the ledger above.
