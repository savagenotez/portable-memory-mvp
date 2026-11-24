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

## First results (fetched 2026-11-24, prices 24 hours before close)

Kalshi: 236 sports games (NBA, NFL, NHL and MLB game-winner series, one market per game, books no wider than 10 cents). Polymarket: 150 closed two-outcome markets with volume of at least $20,000. Full tables are in `prediction_markets/results/market_calibration.json`.

| Source | Markets (events) | Mean price | Realized | Brier skill vs base rate | Calibration slope (1.00 = perfect) |
|---|---|---|---|---|---|
| Both | 386 (305) | 45.7% | 50.8% | +10.3% | 0.74 +/- 0.25 |
| Kalshi | 236 (236) | 49.0% | 54.2% | +9.8% | 0.98 +/- 0.41 |
| Polymarket | 150 (69) | 40.5% | 45.3% | +9.5% | 0.57 +/- 0.30 |

How to read it:

- **Prices carry real information.** About 10% better than guessing the base rate, on both platforms.
- **Kalshi looks calibrated, within wide bounds.** The slope of 0.98 is consistent with 1.0, but the interval spans roughly 0.6 to 1.4.
- **Polymarket looks too extreme, tentatively.** A slope of 0.57 means the high and low prices were more extreme than outcomes justified. The 0-10% bin is the clearest case: 5 of 15 happened, against a mean price of 4.7%. But those 150 markets come from only 69 events, and markets within one event are correlated, so the real uncertainty is larger than the printed interval.
- **Realized sits about 5 points above price on both.** The tracked side is the first one listed, which is arbitrary, so this may be a listing artifact and not a market bias. It is not statistically significant on Kalshi (1.6 standard errors).
- **Nothing here is a statement about the league learner.** It shows how informative real prices are, so how high the bar is, in a different setting from the simulation.

## Sports-stats sources (checked 2026-11-24)

The platforms supply prices and outcomes, not the player and team stats a model needs. These are the free candidates checked so far.

| Source | Access | Terms, as found | Verdict |
|---|---|---|---|
| **nflverse** game data (`nfldata` repository, `data/games.csv`) | Free bulk download, no key | Packages are MIT-licensed. The underlying NFL data belongs to its owners. FTN charting data is CC-BY-SA 4.0. Terms for the schedule files are unresolved | **Recommended.** Verified: 7,548 games from 1999 to 2026, final scores, rest days, temperature, wind, roof, surface, closing spread and moneyline |
| MLB Stats API (`statsapi.mlb.com`) | Keyless | Responses carry an MLB Advanced Media copyright notice. Secondary sources describe personal, non-commercial use. Not checked against the notice itself | **Not used.** MLB publishes no documentation for these endpoints, so they belong with the private endpoints this package excludes |
| balldontlie | API key, free account | The free tier is 5 requests per minute. Sources disagree on whether it includes stats. Terms not checked | **Unresolved.** Check the plans endpoint with a free key before deciding |

Points to remember with the nflverse choice:

- **Closing lines are bookmaker prices.** Using them as the benchmark is analysis of published data. It is not betting, and it is not a source of stats.
- **Redistribution is not cleared.** Personal research use looks fine. Anything published or commercial needs its own check of the NFL and FTN terms.
- **Adding it means a new host.** The reader would need `raw.githubusercontent.com` on the allowlist in `http.py`. That is a deliberate expansion of the boundary, so it should be approved first.

## Rate limits

Kalshi's candlestick endpoint costs 50 units of a 600-unit budget per call, and the budget looked shared across callers. The client reads the `x-ratelimit-*` headers, waits for the reset when the budget is low, and waits and retries on a 429. It never retries blindly. In practice that is about 3 to 5 seconds per Kalshi event. The 236-event run above took 12 minutes. A persistent 429 stops the run with an error.

## Limits of the report

- **One time point.** Prices are taken at one horizon before close (24 hours by default). It says nothing about earlier or later prices.
- **Sample size.** Each probability bin holds a few dozen markets at most, and some hold under ten, so the intervals are wide. Read it as a rough benchmark, not a verdict.
- **Dependence.** Polymarket markets from the same event (moneyline, spread, total) are correlated. The report prints the event count, and the effective sample is closer to that.
- **Selection.** Only liquid Kalshi books and cleanly resolved Polymarket markets are kept. Voided and multi-outcome markets are dropped.
- **Arbitrary side.** For two-team Polymarket markets, the tracked outcome is whichever team is listed first.
- **In-sample baseline.** The base-rate comparison is fitted on the same data, which flatters the baseline slightly.
- **Real data is not the simulation.** Nothing here shows that the league learner would beat these prices.
