"""Kalshi: resolved binary markets and their price a fixed time before close.

Uses only the documented public market-data endpoints:
    GET /markets?series_ticker=..&status=settled
    GET /series/{series}/markets/{ticker}/candlesticks

Multi-leg combo markets are excluded. The price is the midpoint of the yes bid and ask at the last hourly candle
before the target time, and it is skipped when the book is wide or the candle is stale.
"""

from __future__ import annotations

import datetime as dt
import urllib.error
from typing import Callable, Dict, List, Optional, Tuple

from .http import get_json
from .observation import Observation, clip_price

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SPORTS_SERIES = ("KXNBAGAME", "KXNFLGAME", "KXNHLGAME", "KXMLBGAME")
STALE_SECONDS = 6 * 3600


def _ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _dollars(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def is_usable(m: dict) -> bool:
    return (m.get("market_type") == "binary" and not m.get("mve_collection_ticker")
            and m.get("result") in ("yes", "no") and bool(m.get("close_time")))


def settled_markets(series: str, limit: int, fetch: Callable = get_json, page_size: int = 200) -> List[dict]:
    out: List[dict] = []
    cursor = None
    while len(out) < limit:
        params = {"series_ticker": series, "status": "settled", "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        data = fetch(f"{BASE}/markets", params)
        batch = data.get("markets", [])
        out.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break
    return out[:limit]


def price_before_close(series: str, market: dict, horizon_hours: float, max_spread: float,
                       fetch: Callable = get_json) -> Optional[Tuple[float, float]]:
    """Return (midpoint, spread) at the last candle at or before close - horizon, or None."""
    target = _ts(market["close_time"]) - horizon_hours * 3600
    data = fetch(f"{BASE}/series/{series}/markets/{market['ticker']}/candlesticks",
                 {"start_ts": int(target - 2 * 86400), "end_ts": int(target), "period_interval": 60})
    candles = [c for c in data.get("candlesticks", []) if c.get("end_period_ts", 0) <= target + 1]
    if not candles:
        return None
    c = candles[-1]
    if target - c["end_period_ts"] > STALE_SECONDS:
        return None
    bid = _dollars((c.get("yes_bid") or {}).get("close_dollars"))
    ask = _dollars((c.get("yes_ask") or {}).get("close_dollars"))
    if bid is None or ask is None or ask < bid:
        return None
    spread = ask - bid
    if spread > max_spread:
        return None
    return (bid + ask) / 2.0, spread


def iter_collect(series_list=SPORTS_SERIES, per_series: int = 150, horizon_hours: float = 24.0,
                 max_spread: float = 0.10, fetch: Callable = get_json, progress: Callable = lambda msg: None):
    """Yield observations one at a time, so a caller can save partial progress if a run is interrupted.

    One market per event, so the two sides of the same game are not counted twice."""
    for series in series_list:
        markets = [m for m in settled_markets(series, per_series * 2, fetch) if is_usable(m)]
        seen_events: Dict[str, bool] = {}
        taken = 0
        for m in markets:
            ev = m.get("event_ticker") or m["ticker"]
            if ev in seen_events or taken >= per_series:
                continue
            seen_events[ev] = True
            try:
                quote = price_before_close(series, m, horizon_hours, max_spread, fetch)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise
                continue   # no history for this market
            if quote is None:
                continue
            mid, spread = quote
            yield Observation(
                source="kalshi", market_id=m["ticker"], event_id=ev, title=m.get("title", ""),
                close_ts=_ts(m["close_time"]), horizon_hours=horizon_hours, price=clip_price(mid),
                outcome=1 if m["result"] == "yes" else 0, spread=spread,
                volume=_dollars(m.get("volume_fp")),
            )
            taken += 1
        progress(f"kalshi {series}: {taken} usable events from {len(markets)} settled markets")


def collect(*args, **kwargs) -> List[Observation]:
    return list(iter_collect(*args, **kwargs))
