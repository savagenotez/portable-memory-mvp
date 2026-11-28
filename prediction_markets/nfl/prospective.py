"""Prospective test: record the model's forecast and the market price before kickoff, score after the game.

Only games that have not been played yet can test the model against the market honestly. This module makes that
possible without any tuning on the results:

  snapshot   on each run, record every open Kalshi NFL market: the bid, ask and midpoint, the time to close, and the
             model's probability for the same team. The model is fixed (ADOPTED_SETTINGS in tune.py), and it uses
             only games played before the target game day.
  score      once the games are final, take for each event the latest snapshot at least 24 hours before close,
             and compare the model with the midpoint on the same games. Only snapshots logged before kickoff count.

Rules (fixed before any prospective game was logged):
  * one market per event (the two sides of one game are not separate evidence);
  * books wider than 10 cents are skipped, as in realdata/kalshi.py;
  * the model is frozen; no change is made to it while the log is collected;
  * the decision is made once, after the first 100 scored games: the model counts as ahead of the market only if the
    95% interval for (model minus market) Brier is entirely below zero. Even then, this is not a profit claim:
    fees, depth and bet sizing are not modelled.

    python3 -m prediction_markets.nfl.prospective snapshot
    python3 -m prediction_markets.nfl.prospective score
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import statistics as st
from typing import Callable, Dict, List, Optional

from ..realdata import http
from ..realdata.observation import Observation
from .data import Game, load_games
from .features import walk_forward_home_prob
from .match import match_observation
from .tune import ADOPTED_SETTINGS

BASE = "https://api.elections.kalshi.com/trade-api/v2"
RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
LOG = os.path.join(RESULTS, "prospective_snapshots.jsonl")
SCORES = os.path.join(RESULTS, "prospective_scores.json")
MODEL_VERSION = "elo_k30_logit_hist_v1"
MAX_SPREAD = 0.10
HORIZON_HOURS = 24.0
DECISION_AFTER = 100


def parse_utc(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def open_nfl_markets(fetch: Callable = http.get_json) -> List[dict]:
    out: List[dict] = []
    cursor = None
    while True:
        params = {"series_ticker": "KXNFLGAME", "status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = fetch(f"{BASE}/markets", params)
        batch = data.get("markets", [])
        out.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            return out


def _quote(m: dict):
    try:
        bid = float(m.get("yes_bid_dollars"))
        ask = float(m.get("yes_ask_dollars"))
    except (TypeError, ValueError):
        return None, None, None
    if not (0.0 < bid < ask):
        return bid, ask, None
    mid = (bid + ask) / 2.0 if (ask - bid) <= MAX_SPREAD else None
    return bid, ask, mid


def snapshot_rows(markets: List[dict], games: List[Game], now: dt.datetime, team_games=None,
                  injuries=None) -> List[dict]:
    """One row per open market that matches a game. Each model's probability is for the team the market is about.

    'model' is the base model (K 30, rest, division). 'model_v3' is the frozen v3 (adds efficiency and injuries),
    recorded only when the team stats and injury counts are supplied."""
    placeholder = lambda m: Observation("kalshi", m["ticker"], m["event_ticker"], m.get("title", ""), 0.0,
                                        HORIZON_HOURS, 0.5, 0)
    matched = []
    for m in markets:
        hit = match_observation(placeholder(m), games)
        if hit is not None:
            matched.append((m, hit[0], hit[1]))
    if not matched:
        return []
    targets = {g.game_id for _, g, _ in matched}
    p_home = walk_forward_home_prob(games, targets, dict(ADOPTED_SETTINGS))
    p_v3 = {}
    if team_games is not None and injuries is not None:
        from .model_v3 import v3_home_probs
        p_v3 = v3_home_probs(games, team_games, injuries, targets)
    rows = []
    for m, g, side in matched:
        close = parse_utc(m["close_time"])
        hours = (close - now).total_seconds() / 3600.0
        if hours < 0 or hours > 96:
            continue
        bid, ask, mid = _quote(m)
        ph = p_home[g.game_id]
        rows.append({
            "ts": now.isoformat(), "market_id": m["ticker"], "event_id": m["event_ticker"],
            "game_id": g.game_id, "gameday": g.gameday, "side": side,
            "hours_to_close": round(hours, 3), "bid": bid, "ask": ask, "mid": mid,
            "model": ph if side == "home" else 1.0 - ph, "model_version": MODEL_VERSION,
            "model_v3": (p_v3[g.game_id] if side == "home" else 1.0 - p_v3[g.game_id]) if g.game_id in p_v3 else None,
        })
    return rows


def _season_files():
    """Team stats and injuries: cached history, with the current season always re-downloaded."""
    from .sources import load_injury_counts, load_team_games
    tg_old, _ = load_team_games(range(2000, 2026))
    tg_now, _ = load_team_games([2026], refresh=True)
    inj_old, _ = load_injury_counts(range(2009, 2026))
    inj_now, _ = load_injury_counts([2026], refresh=True)
    inj_old.update(inj_now)
    return tg_old + tg_now, inj_old


def run_snapshot(path: str = LOG, fetch: Callable = http.get_json) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    games = load_games(refresh=True)
    team_games, injuries = _season_files()
    rows = snapshot_rows(open_nfl_markets(fetch), games, now, team_games, injuries)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return len(rows)


def load_log(path: str = LOG) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def choose_snapshot(rows: List[dict]) -> Optional[dict]:
    """The latest snapshot logged at least HORIZON_HOURS before close, with a usable midpoint."""
    usable = [r for r in rows if r.get("mid") is not None and r["hours_to_close"] >= HORIZON_HOURS]
    return min(usable, key=lambda r: r["hours_to_close"]) if usable else None


def score(log: List[dict], games: List[Game]) -> dict:
    by_game = {g.game_id: g for g in games}
    by_market: Dict[str, List[dict]] = {}
    for r in log:
        by_market.setdefault(r["market_id"], []).append(r)
    per_event: Dict[str, dict] = {}
    for market_id in sorted(by_market):
        snap = choose_snapshot(by_market[market_id])
        if snap is None:
            continue
        g = by_game.get(snap["game_id"])
        if g is None or not g.completed:
            continue
        if g.home_won is None:
            continue
        team_won = (g.home_won == 1) if snap["side"] == "home" else (g.home_won == 0)
        ev = snap["event_id"]
        if ev in per_event:       # one market per event: keep the first sorted ticker
            continue
        per_event[ev] = {"market_id": market_id, "game_id": g.game_id, "gameday": g.gameday, "side": snap["side"],
                         "model": snap["model"], "model_v3": snap.get("model_v3"),
                         "market": snap["mid"], "outcome": int(team_won),
                         "hours_before_close": snap["hours_to_close"]}
    rows = list(per_event.values())
    n = len(rows)
    result = {"model_version": MODEL_VERSION, "scored_games": n, "decision_after": DECISION_AFTER,
              "rule": "model counts as ahead only if the 95% interval of (model minus market) Brier is below zero",
              "rows": rows}
    if n == 0:
        result["status"] = "no scored games yet"
        return result
    d = [(r["model"] - r["outcome"]) ** 2 - (r["market"] - r["outcome"]) ** 2 for r in rows]
    rng = random.Random(3)
    boots = sorted(st.mean(rng.choice(d) for _ in d) for _ in range(2000))
    m = st.mean(d)
    lo, hi = boots[49], boots[1949]
    result.update({"brier_model": st.mean((r["model"] - r["outcome"]) ** 2 for r in rows),
                   "brier_market": st.mean((r["market"] - r["outcome"]) ** 2 for r in rows),
                   "model_minus_market_brier": m, "ci95": [lo, hi]})
    if n >= DECISION_AFTER:
        result["decision"] = "model ahead of market" if hi < 0 else "not shown to beat the market"
    else:
        result["decision"] = f"not yet: {n} of {DECISION_AFTER} games scored"
    return result


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.prospective")
    ap.add_argument("cmd", choices=["snapshot", "score"])
    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        n = run_snapshot()
        print(f"logged {n} snapshot rows to {LOG}")
        return 0
    games = load_games(refresh=True)
    res = score(load_log(), games)
    os.makedirs(RESULTS, exist_ok=True)
    with open(SCORES, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(f"scored games: {res['scored_games']}  decision: {res.get('decision', res.get('status'))}")
    if "brier_model" in res:
        lo, hi = res["ci95"]
        print(f"Brier model {res['brier_model']:.4f}  market {res['brier_market']:.4f}  "
              f"difference {res['model_minus_market_brier']:+.4f}  95% [{lo:+.4f}, {hi:+.4f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
