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

Several safeguards watch for the ways this can go wrong: a specialist who has secretly seen the answer, one whose usefulness vanishes, early-season games with little data, and a panel that is too sure of itself.

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

Scenario extras: `news` (a feature that tracks true strength early and then turns to noise), `leak` (contains the game outcome), `team_dup` (a near-copy of the team branch).

## Tripwires, and what each one did

All five can be switched off in `ModelConfig`, so their value can be measured.

| Tripwire | What it does | What it bought in the final study |
|---|---|---|
| plausibility cap | quarantines a branch whose solo gain is implausibly large | **Essential.** Without it, the leak "captures" 8.0x the achievable accuracy. With it, 0.49 |
| calibration scaling (Platt) | online correction of the final logit | Buys calibration. Costs about 1.6 points of accuracy |
| gates | fade branches with low decision scores | No measurable benefit. Costs about 0.7 points |
| early-season shrink | pulls toward the base rate when little has been seen | No measurable effect. Costs about 0.2 points |
| drift boost | raises learning rate if a branch's recent gain collapses | **Effectively inert.** It fired about once in 30 leagues and moved capture by at most 0.0003 |

## Run it

```bash
python3 -m unittest discover -s prediction_markets/tests -t .   # 87 tests
python3 -m prediction_markets.league.study --quick              # 4 dev leagues, about 15 s, writes nothing
python3 -m prediction_markets.league.study --dev                # 16 dev leagues, about 1 minute, writes nothing
python3 -m prediction_markets.league.study                      # FINAL seeds, about 2 minutes, writes results/league_study.json
```

Do not run the final study repeatedly while changing the code. Seeds 7000-7029 have been used once (see the seed ledger).

## Results (final, seeds 7000-7029, 30 leagues x 6 seasons, scored from season 1)

**Accuracy.** "Capture" is the share of the achievable accuracy gain over the base rate. 1.0 would match the oracle. Capture needs an oracle, so it is a simulation-only measure.

| Model | Capture (clean) |
|---|---|
| Branch ensemble (all tripwires on) | 0.483 |
| Branch ensemble (tripwires off) | 0.509 |
| One flat model over every variable | 0.387 |

Brier skill against the base rate is +5.7% (95% interval 4.7% to 6.6%). The oracle's is 11.7%. The ensemble beats the flat model by 0.0028 Brier (95% interval 0.0022 to 0.0033).

**It learns.** Capture by season: 0.39, 0.45, 0.52, 0.54, 0.52. It improves for about four seasons and then flattens.

**Branch decision scores (clean, mean over leagues).**

| Branch | Score | Gate | Reading |
|---|---|---|---|
| team | +2.71 | 0.98 | Does most of the work |
| player | +1.73 | 0.92 | Clearly useful |
| streak | +1.36 | 0.88 | Mostly repeats what team record already says |
| geo | +0.65 | 0.77 | Small |
| interaction | +0.28 | 0.69 | Not proven |
| weather | -0.20 | 0.61 | Not proven |
| schedule | -0.66 | 0.51 | Not proven |
| decoy_noise | -0.63 | 0.51 | Correctly scored as useless |

Rest days and the style x wind effect are real in the simulation, but they are small. About 1,000 games per league cannot separate them from noise, so their scores sit near zero. The system is saying "not proven," which is the honest answer at that sample size.

**Pre-registered criteria.**

| | Criterion | Result |
|---|---|---|
| C1 | clean calibration: overall within 2 SE, every slice within 3 SE | **FAIL** |
| C2 | clean skill positive, and not worse than the flat model | PASS |
| C3 | capture in the last two seasons at least the first two (0.42 to 0.53) | PASS |
| C4 | spurious feature: capture after it breaks at least 0.95x clean (0.492 vs 0.507) | PASS |
| C5 | leakage trap: no fake skill, leak branch quarantined (quarantined in 100% of leagues) | PASS |
| C6 | duplicate branch: capture at least 0.95x clean, calibration holds | PASS |
| C7 | regime shift: capture recovers (0.42 before, 0.38 right after, 0.49 later) | PASS |
| C8 | team branch score above 2, noise branch below 1 | PASS |

**C1 failed, and the reason is specific.** Overall calibration is fine (57.5% predicted against 57.2% realized, 1.5 SE). Eleven of twelve slices are within 3 SE. The failing slice is games the model thinks are close to even: it predicts 52.7% and 51.5% happen, a 1.2-point over-prediction for the home team, at 4.0 SE. Games predicted above 60% are 0.7 points too low (2.3 SE). This is a small but real defect in the middle of the probability range.

C1 was revised once before the final run. The first draft required 90% of slices within 2 SE, which a perfectly calibrated model fails about 10% of the time. It was replaced by "every slice within 3 SE". The revision came from the dev-seed analysis, not from the final results.

## What the study does not show

- **The hard conditions were not very hard.** The spurious feature and the regime shift barely hurt the learner. Plain online learning handled them about as well as the full set of tripwires (capture 0.509 with every tripwire off). The only trap that broke the system was leakage, and the plausibility cap stopped it. Harder traps are the next step. Candidates: faster and larger shifts, decoys that correlate with several branches at once, and drift in the weather interaction.
- **The tripwires cost accuracy.** With all five off, capture is 0.509 in the clean case against 0.483 with them on. The cap is worth keeping on its own. The others have not earned their cost yet.
- **Dev results are optimistic.** The same model scored 0.528 on the dev seeds it was tuned on. The final seeds give 0.483. Use the final number.
- **The plausibility cap is set from the oracle.** It is 2x the oracle's log-loss gain on dev leagues (0.136 nats per game). Real data has no oracle. The practical analogue is a bound from a strong external benchmark, such as a market price.
- **Everything is simulated.** The league was built to have learnable structure. Real leagues may not.

## Seed ledger

| Seeds | Use |
|---|---|
| 1000-1015 | Dev. Used for tuning hyperparameters and for debugging. Not evidence. |
| 5000-5003 | One 4-league smoke test, before the final block was moved. Retired. |
| 7000-7029 | Final study. Run once, on frozen code. |

Hyperparameters tuned on dev seeds only: learning rate (0.03 falling to 0.005), gate center 0 and floor 0.3, and a decaying Platt rate (0.05 down to 0.003). The Platt change fixed an under-confident slope of 1.14 on dev data, at a cost of under one point of capture.

## Editing and extending

- **Variables:** `config.json` (three sections: `league`, `model`, `study`). Unknown keys are rejected.
- **Add a branch:** add its columns to `features.py` (`BASE_BRANCHES` and `features_for`), and the learner picks it up. Its decision score then tells you whether it earns its place.
- **Add a hard condition:** add a scenario name in `sim.py` and a pass rule in `study.judge`. Write the rule down before running it on a fresh seed block.
- **Add a tripwire:** add a switch to `ModelConfig` and include it in `study.TRIPWIRE_FLAGS`, so its value is measured.
- After any change: run the tests, then the dev study, then a final study on a **new** seed block. Record the block in the ledger above.
