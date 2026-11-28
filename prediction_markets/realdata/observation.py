"""One resolved market, with the price observed a fixed time before it closed."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from typing import List, Optional


@dataclass(frozen=True)
class Observation:
    source: str                 # "kalshi" or "polymarket"
    market_id: str
    event_id: str
    title: str
    close_ts: float             # scheduled close, unix seconds
    horizon_hours: float        # how long before close the price was taken
    price: float                # implied probability of the tracked outcome, in (0, 1)
    outcome: int                # 1 if the tracked outcome happened
    spread: Optional[float] = None
    volume: Optional[float] = None


def clip_price(p: float) -> float:
    return min(0.99, max(0.01, p))


def write_csv(path: str, observations: List[Observation]) -> None:
    names = [f.name for f in fields(Observation)]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=names)
        w.writeheader()
        for o in observations:
            w.writerow(asdict(o))


def read_csv(path: str) -> List[Observation]:
    out: List[Observation] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(Observation(
                source=row["source"], market_id=row["market_id"], event_id=row["event_id"], title=row["title"],
                close_ts=float(row["close_ts"]), horizon_hours=float(row["horizon_hours"]),
                price=float(row["price"]), outcome=int(row["outcome"]),
                spread=float(row["spread"]) if row.get("spread") not in (None, "") else None,
                volume=float(row["volume"]) if row.get("volume") not in (None, "") else None,
            ))
    return out
