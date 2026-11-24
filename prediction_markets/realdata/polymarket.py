"""Polymarket: resolved two-outcome markets and the price of the first outcome a fixed time before close.

Uses only the documented public endpoints:
    GET gamma-api /markets?closed=true       (discovery and the resolved outcome prices)
    GET clob /prices-history?market=<token>  (price history for the first outcome's token)

A market is kept only when it has exactly two outcomes and resolved cleanly to prices of 1 and 0.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
from typing import Callable, List, Optional

from .http import get_json
from .observation import Observation, clip_price

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
STALE_SECONDS = 6 * 3600


def _as_list(x):
    if isinstance(x, str):
        try:
            return json.loads(x)
        except ValueError:
            return None
    return x


def _ts(s: str) -> float:
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()


def resolved_first_outcome(m: dict) -> Optional[int]:
    """1 or 0 if the market has two outcomes and resolved cleanly, else None."""
    outcomes = _as_list(m.get("outcomes"))
    prices = _as_list(m.get("outcomePrices"))
    tokens = _as_list(m.get("clobTokenIds"))
    if not (isinstance(outcomes, list) and isinstance(prices, list) and isinstance(tokens, list)):
        return None
    if len(outcomes) != 2 or len(prices) != 2 or len(tokens) != 2:
        return None
    try:
        p = [float(x) for x in prices]
    except (TypeError, ValueError):
        return None
    if sorted(p) != [0.0, 1.0]:
        return None
    return 1 if p[0] == 1.0 else 0


def closed_markets(limit: int, min_volume: float, fetch: Callable = get_json, page_size: int = 100) -> List[dict]:
    out: List[dict] = []
    offset = 0
    while len(out) < limit:
        batch = fetch(f"{GAMMA}/markets", {"closed": "true", "limit": page_size, "offset": offset,
                                           "order": "closedTime", "ascending": "false",
                                           "volume_num_min": min_volume})
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        offset += page_size
    return out[:limit]


def price_before_close(m: dict, horizon_hours: float, fetch: Callable = get_json) -> Optional[float]:
    if not m.get("endDate"):
        return None
    target = _ts(m["endDate"]) - horizon_hours * 3600
    token = _as_list(m["clobTokenIds"])[0]
    data = fetch(f"{CLOB}/prices-history",
                 {"market": token, "startTs": int(target - 2 * 86400), "endTs": int(target), "fidelity": 60})
    points = [h for h in (data or {}).get("history", []) if h.get("t", 0) <= target + 1]
    if not points:
        return None
    last = points[-1]
    if target - last["t"] > STALE_SECONDS:
        return None
    return float(last["p"])


def collect(limit: int = 200, min_volume: float = 20000.0, horizon_hours: float = 24.0,
            fetch: Callable = get_json, progress: Callable = lambda msg: None) -> List[Observation]:
    out: List[Observation] = []
    markets = closed_markets(limit * 3, min_volume, fetch)
    considered = 0
    for m in markets:
        if len(out) >= limit:
            break
        outcome = resolved_first_outcome(m)
        if outcome is None:
            continue
        considered += 1
        try:
            price = price_before_close(m, horizon_hours, fetch)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise
            continue   # no history for this market
        if price is None or not (0.0 < price < 1.0):
            continue
        events = m.get("events") or []
        ev = str(events[0].get("id")) if events and isinstance(events[0], dict) and events[0].get("id") else str(m.get("id"))
        out.append(Observation(
            source="polymarket", market_id=str(m.get("conditionId") or m.get("id")), event_id=ev,
            title=m.get("question", ""), close_ts=_ts(m["endDate"]), horizon_hours=horizon_hours,
            price=clip_price(price), outcome=outcome, spread=None, volume=m.get("volumeNum"),
        ))
    progress(f"polymarket: {len(out)} usable markets from {considered} cleanly resolved two-outcome markets")
    return out
