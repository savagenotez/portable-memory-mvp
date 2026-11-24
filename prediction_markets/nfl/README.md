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
