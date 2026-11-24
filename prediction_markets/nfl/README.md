# NFL: model against market

Scores a simple pre-game NFL model against Kalshi's price for the same games, 24 hours before kickoff.
Feature outline and the rule every input must follow: [FEATURES.md](FEATURES.md).

## Result (146 games, Kalshi NFL game-winner markets, 2026 season to date)

| | Brier | Skill vs base rate | Calibration slope (1.00 = calibrated) |
|---|---|---|---|
| Model (Elo, rest, division) | 0.2157 | +12.4% | 1.11 +/- 0.52 |
| Kalshi price | 0.2108 | +14.4% | 1.00 +/- 0.45 |

- **Model minus market:** +0.0049 Brier, 95% interval **-0.012 to +0.022**. The interval includes zero, so the test does not separate them.
- **Agreement:** every matched game's Kalshi outcome matches its final score (146 of 146).
- **Read it as:** on these games, the simple model is roughly as good as the price. It does not show an edge, and it does not rule one out either.

The first 60 games alone looked clearly worse for the model (+0.028, interval +0.005 to +0.051). That gap shrank on the larger set, which is the reason not to read small samples. The earlier result is kept in the record.

## Tuning on historical outcomes (`tune.py`)

The 146 market games were used to diagnose the model, so they cannot also test changes to it. Model choices were made on completed games from 2005 to 2025 instead (about 6,800 games), with rules written first (see the module docstring).

| Variant | Dev log loss (2005-2019) | Holdout log loss (2020-2025) |
|---|---|---|
| V0 baseline (K 20, home advantage 65) | 0.6347 | 0.6455 |
| V1 K 12 | 0.6369 | 0.6492 |
| V2 K 30 | **0.6331** (selected) | **0.6430** |
| V3 home advantage 48 | 0.6347 | 0.6450 |
| V4 + short rest, bye week | 0.6349 | 0.6454 |
| V5 + indoor venue | 0.6348 | 0.6454 |
| V6 + all three flags | 0.6350 | 0.6453 |

- **Adopted: K = 30.** Holdout gain against V0 is -0.0025 log loss per game, 95% interval -0.0042 to -0.0009, over 1,688 games. The rule was met, but the gain is small.
- **The flags add nothing.** Short rest, bye weeks and the indoor venue each move the log loss by under 0.001.
- **K = 30 is the top of the grid.** A larger K may do better, but that has not been tested, and testing it needs a new holdout.
- **Re-check on the 146 market games (a re-check, not validation):** the K = 30 model's gap to the market is +0.0039 (interval -0.0126 to +0.0203), against +0.0049 for K = 20. Still not separable from the market. The saved file is `results/nfl_recheck_k30.json`.

Run: `python3 -m prediction_markets.nfl.tune` (about 10 seconds; writes `results/nfl_tune.json`).

## The weakness, tested on history (negative result)

The 146-game diagnosis suggested the model is overconfident. On 1999 to 2025 outcomes, that does not hold:

- A single calibration scale fitted on 2005-2019 is best at **1.00**, which is no change.
- On the 2020-2025 holdout, the scaled model gains **0.0000** log loss per game (interval -0.0000 to +0.0000).

So the overconfidence seen on 146 games is not a general fault in the model. It is either noise in a small sample or specific to 2026. Nothing in that finding was used to change the model.

## Prospective test (fresh games only)

The only honest test of beating the market is games the model has not seen. `prospective.py` records, for each open Kalshi NFL market, the model's probability and the price, and scores them after the game:

- `python3 -m prediction_markets.nfl.prospective snapshot`: log the open markets (in the 96 hours before close).
- `python3 -m prediction_markets.nfl.prospective score`: for each game, use the latest snapshot at least 24 hours before close. Only finished games count.

Rules, fixed before any prospective game was logged: one market per event; books wider than 10 cents are skipped; the model is frozen; the decision is made once, after 100 scored games, and the model counts as ahead only if the 95% interval for its Brier difference is entirely below zero. This is not a profit claim. Fees, depth and bet sizing are not modelled.

Status: the log has started (`results/prospective_snapshots.jsonl`, first snapshot 2026-11-24). Nothing is scored yet.

## Blind test (`blind.py`)

Which games are blind:

- **Not blind:** 1999 to 2025 outcomes (used to pick K = 30), the 146 Kalshi games (used for the diagnosis), and the 2026 games already played (also in the diagnosis set). These can still be used for development, but they cannot judge a new change.
- **Blind:** the 109 2026 games not yet played when the block was sealed (`results/blind_manifest.json`, SHA-256 hash committed). No score for them exists in the data yet, so no model has seen their results.

Enforcement: tuning and selection code calls `assert_not_sealed()` on the games it scores, so a sealed game cannot enter a tuning set. `judge()` refuses to run until 100 sealed games with usable prices have settled, and it only uses the pre-registered slices in `blind.py`. Each slice's result is adjusted with Holm across all slices, so the slices cannot be searched for a lucky one.

Realistic timing: the regular season may not supply 100 priced, settled sealed games. If it does not, the judgement waits, and the sealed block is not reopened or re-sealed.

## Model v3 (frozen): efficiency and injuries

v3 adds two features that each passed the pre-registered history test: EPA per play over a 10-game half-life (from the nflverse weekly team stats), and key-position injuries (Out or Doubtful, from the weekly report). The definition is frozen in `model_v3.py`, before any sealed 2026 outcome exists.

Development result on history (2020-2025 holdout, which was already used to choose K = 30, so this is not blind):

- v3 against the base model with the same 2010 training window (the fair comparison): **-0.0061** log loss per game, 95% interval -0.0119 to -0.0007, over 1,688 games.
- v3 against the base model trained from 2005: -0.0070 (-0.0129 to -0.0016). The difference between the two comparisons is the training window, so the fair line is the one to quote.

The blind judgement compares v3 with the market and with the base model, on the sealed 2026 games that have a price and a v3 forecast (`blind.judge`). It has not run yet.

## Blind test status

The prospective logger records both models for each open market. A daily scheduled run was requested but was refused by the automatic permission check, so it is not running. Until it is set up, snapshots must be taken by hand: `python3 -m prediction_markets.nfl.prospective snapshot`, then `score`.

## In-game predictions (quarters and halves)

`inplay.py` predicts the win probability at the end of Q1, at halftime and at the end of Q3, and the winner of each quarter and half. It uses the pre-game Elo gap (points, /25) and the score so far. Two uncertainty terms are fitted on 2012-2019; the results below are on 2020-2025, the same seasons as the earlier holdout, so they are development results, not blind. Pre-registered in the module docstring.

Win probability at each boundary (1,684 games, Brier, lower is better; "model minus" is negative when the model is better, with a 95% interval on the paired difference):

| Boundary | Model | Pre-game prior | nflverse in-game (no team strength) | Model minus nflverse | Spread-based (closing line) | Model minus spread-based |
|---|---|---|---|---|---|---|
| End of Q1 | 0.2053 | 0.2275 | 0.2145 | **-0.0091** [-0.0143, -0.0042] | 0.1894 | **+0.0160** [+0.0105, +0.0215] |
| Halftime | 0.1605 | 0.2275 | 0.1650 | **-0.0044** [-0.0072, -0.0017] | 0.1506 | **+0.0099** [+0.0062, +0.0136] |
| End of Q3 | 0.1293 | 0.2275 | 0.1268 | +0.0024 [-0.0013, +0.0060] | 0.1194 | **+0.0098** [+0.0056, +0.0138] |

How to read it:

- **Against the pre-game prior, the in-game information helps a lot** at every boundary.
- **Against nflverse's in-game model, which does not know team strength, the model is better early** (end of Q1 and halftime), and level by the end of Q3. The early advantage comes from knowing the teams.
- **Against the spread-based probability (built from the closing line), the model is clearly worse at every boundary.** The closing line includes injuries, news and quarterback information that this model does not have. That fits the earlier market results. The spread-based probability is published closing-line data, not a price this system trades against.
- **The period-winner predictions are only slightly better than a coin flip** (Brier 0.237 to 0.246, against 0.250).
- **Fitted parameters:** the strength uncertainty fits at zero, the lower edge of its grid, so the data give the pre-game prior no extra uncertainty beyond game noise. That is a finding to check, not a setting to trust.

Quarter and half markets on Kalshi: the first-quarter winner series had no settled history. First-half team-total markets do have history, but they are points markets, so they need a points model before they can be compared. Polymarket has no quarter or half markets open.

## Where the model falls behind (post hoc, read with caution)

- **Concentrated in 11 games.** These are the games where the model and the price disagreed by 20 points or more. They account for the whole shortfall: 2.16 of the 0.72 total squared-error difference. The other 135 games favour the model slightly (-0.011 Brier, 95% interval -0.024 to +0.002).
- **What those 11 look like.** The model had the team it favoured at 45-69%, while the price had it at 15-39%. The price side was closer: the model expected about 6.1 of those teams to win, the market about 4.6, and 2 won.
- **Large home edges.** The home side rated 85 or more Elo points ahead was 30 games. The model averaged 71% for those teams, the market 66%, and they won 57%. Here the model's Brier score is worse (0.232 against 0.208).
- **Mid-range overconfidence.** Where the model said 50-60%, the teams won 41%. The model is too confident in its middle range, and the price is closer to the outcomes.
- **Factors that show nothing.** Rest difference, division games, week of the season, and the price range each leave a shortfall whose interval includes zero.

The likely cause, not yet tested, is that Elo is slow to notice what the price already reflects, such as injuries, quarterback changes and roster news. Those are the features listed as not built in FEATURES.md.

These splits were chosen after seeing the results, across many groups, on 146 games. Treat them as where to look next, not as findings. The next test should use fresh games.

## Caveats

- 146 games is a small sample for a Brier difference this size. The interval is the honest answer, not the point estimate.
- One season to date, one horizon (24 hours before close).
- The model has no injury, quarterback or efficiency information. Those are the features listed as "not built" in FEATURES.md.
- A Kalshi price is one trade's view, not the sportsbook's. The comparison says nothing about sportsbook prices.

## Reproduce

```bash
python3 -m prediction_markets.realdata fetch --source kalshi --series KXNFLGAME --per-series 150 \
    --horizon-hours 24 --out prediction_markets/realdata/data/kalshi_nfl_24h.csv     # about 4 minutes
python3 -m prediction_markets.nfl compare --kalshi prediction_markets/realdata/data/kalshi_nfl_24h.csv \
    --out prediction_markets/results/nfl_model_vs_market.json
```

The comparison is deterministic: the bootstrap uses a fixed seed.
