# NFL model: feature outline

This is what the model's inputs must be, and why. It is built from public sports-modeling methods: Elo team ratings, rest and travel, home field, and efficiency measures. The apps' internal models are not public, and I have not tried to infer them.

## The one rule

**Every feature must be knowable about 24 hours before kickoff.** The market prices we compare against are taken at that point. A feature that uses something revealed later, such as the final score, the actual game-time weather, or the closing line, makes the test unfair in the model's favour, or turns the model into a copy of the market.

## Features

| # | Feature | Definition | Known before kickoff? | Status |
|---|---|---|---|---|
| 1 | **Team strength (Elo)** | Each team's rating from earlier games only: start 1500, home advantage 65 points at non-neutral sites, a third of the gap to 1500 closed each season. K = 20 in the diagnosis model; **K = 30 adopted** from historical tuning | Yes | **Built** (`features.py`, `tune.py`) |
| 2 | **Rest difference** | Home rest days minus away rest days, capped at +/-7 | Yes | **Built** |
| 3 | **Division game** | 1 if the two teams are in the same division | Yes | **Built** |
| 4 | **Short week** | 1 if a team has 4 days of rest or less, per side | Yes | Tested on history: no gain (under 0.001 log loss) |
| 5 | **Bye week** | 1 if a team's previous game was 13 or more days earlier | Yes | Tested on history: no gain |
| 6 | **Roof** | Indoor venue (dome or closed roof) | Yes (fixed by venue) | Tested on history: no gain |
| 7 | **Starting quarterback** | Each side's starter, from the announced depth chart | Yes, usually by Wednesday before a Sunday game. **Not reliably known 24 hours out** | Not built. Needs the injury and depth-chart history first |
| 8 | **Efficiency (EPA per play)** | Rolling expected points added per play, from play-by-play data | Yes, from earlier games | Not built. Needs the play-by-play file |
| 9 | **Weather** | Temperature and wind | **Not as recorded.** The game file holds game-time values. Only forecasts are knowable in advance | **Excluded.** Use only with an archived forecast |
| 10 | **Market prices** (spread, moneyline, total) | Closing lines | **Not allowed in the model.** They are the benchmark | **Excluded by design.** Used only to score |

## Build order

1. Confirm the current model (features 1 to 3) on more games before adding anything.
2. Add one feature at a time (4, 5, 6), each pre-registered and tested on a fresh set of games. Keep it only if it improves the Brier score on those games, and say so if it doesn't.
3. Efficiency (8) needs the play-by-play file. Fetch it, check its terms, and add it as its own step.
4. Starting quarterback (7) and weather (9) are the hard ones. Each needs an archive of what was known at the time, not what was recorded afterwards.

## What a fair test needs

- **Walk-forward only.** Each game is predicted from games played before its own day.
- **Fresh games for every new feature.** Never tune on the games you will report.
- **Scored against the price, on the same games.** Brier score, the difference with a bootstrap interval, and a calibration slope.
- **Report negative results.** The current model is worse than the market on the first 60 games, and that stays in the record.
