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
