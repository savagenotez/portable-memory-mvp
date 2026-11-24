# realdata: official public market data, read-only

This is the lawful route to real prices. It does **not** reverse engineer, decompile, scrape, or log in to any app or website. It calls only the public market-data endpoints that Kalshi and Polymarket document officially, sends no credentials, and honours the servers' rate limits.

## What it does

- **Fetches** resolved markets and the price a fixed number of hours before each one closed.
  - **Kalshi:** sports game-winner series (NBA, NFL, NHL, MLB by default). One market per game. Multi-leg combo markets are excluded. The price is the midpoint of the yes bid and ask from the last hourly candle before the target time. Books wider than 10 cents and stale candles are skipped.
  - **Polymarket:** closed two-outcome markets that resolved cleanly to 1 and 0. The price is the last point in the price history before the target time. The tracked outcome is the first one listed.
- **Reports how well calibrated those real prices were.** This is the benchmark any model has to beat: a price of 0.70 should be followed by a yes about 70% of the time.

## What it does not do

- It does not place bets, use accounts, or touch any private endpoint.
- It does not include a model. A model-versus-market comparison needs a sports-stats source for the model's inputs. The platforms supply prices and outcomes, not player or team stats. That source is not wired in yet.
- Fetched data is not committed. `prediction_markets/realdata/data/` is git-ignored. Only the summary report goes in the repo.

## Hosts it will talk to

The client refuses anything else (a test checks this), and refuses plain http:

| Host | Used for |
|---|---|
| `api.elections.kalshi.com` | Kalshi markets and candlesticks |
| `gamma-api.polymarket.com` | Polymarket market discovery and resolution |
| `clob.polymarket.com` | Polymarket price history |

Check each platform's current terms, rate limits and your own eligibility before using it. The docs are at [docs.kalshi.com](https://docs.kalshi.com/) and [docs.polymarket.com](https://docs.polymarket.com/getting-started/api).

## Run it

```bash
python3 -m prediction_markets.realdata fetch --source kalshi --per-series 60 --horizon-hours 24 \
    --out prediction_markets/realdata/data/kalshi_24h.csv          # slow: see "Rate limits"
python3 -m prediction_markets.realdata fetch --source polymarket --limit 150 --horizon-hours 24 \
    --out prediction_markets/realdata/data/polymarket_24h.csv
python3 -m prediction_markets.realdata report \
    --csv prediction_markets/realdata/data/kalshi_24h.csv prediction_markets/realdata/data/polymarket_24h.csv \
    --out prediction_markets/results/market_calibration.json
```

## Rate limits

Kalshi's candlestick endpoint costs 50 units of a 600-unit budget per call, and the budget looked shared across callers. The client reads the `x-ratelimit-*` headers, waits for the reset when the budget is low, and waits and retries on a 429. It never retries blindly. In practice that is about 5 seconds per Kalshi event, so 240 events take about 20 minutes. A persistent 429 stops the run with an error.

## Limits of the report

- **One time point.** Prices are taken at one horizon before close (24 hours by default). It says nothing about earlier or later prices.
- **Sample size.** Each probability bin holds a few dozen markets at these sample sizes, so the intervals are wide. Read it as a rough benchmark.
- **Selection.** Only liquid Kalshi books and cleanly resolved Polymarket markets are kept. Voided and multi-outcome markets are dropped.
- **Arbitrary side.** For two-team Polymarket markets, the tracked outcome is whichever team is listed first.
- **In-sample baseline.** The base-rate comparison is fitted on the same data, which flatters the baseline slightly.
- **Real data is not the simulation.** Nothing here shows that the league learner would beat these prices.
