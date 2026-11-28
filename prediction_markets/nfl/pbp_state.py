"""In-game state features from play-by-play, snapshotted at the end of Q1, Q2 (halftime) and Q3.

Everything here comes from plays that happened BEFORE the snapshot. Nothing from a later play is used. Per team:
  plays, yards per play, EPA per play, pass rate, turnovers, first downs, drives, and the timeouts left at the snapshot.
Cached per season (git-ignored): realdata/data/nflverse/state_feats_{y}.json
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from typing import Dict, Iterable

from ..realdata import http
from .inplay import PBP_URL

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data", "nflverse")
PERIODS = ("1", "2", "3")


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _acc():
    return {"plays": 0, "yards": 0.0, "epa": 0.0, "pass_plays": 0, "turnovers": 0, "first_downs": 0,
            "drives": set()}


def snapshot_rows(rows: Iterable[dict]) -> list:
    """Walk the plays in order. At the last play of each quarter (1, 2, 3) store the state of both teams then."""
    team: Dict[tuple, dict] = {}
    timeouts: Dict[str, tuple] = {}
    meta: Dict[str, dict] = {}
    snap: Dict[tuple, dict] = {}
    for r in rows:
        gid, qtr = r.get("game_id"), r.get("qtr")
        if not gid or qtr not in ("1", "2", "3", "4", "5"):
            continue
        meta.setdefault(gid, {"season": int(_num(r.get("season"), 0)), "week": int(_num(r.get("week"), 0)),
                              "home": r.get("home_team", ""), "away": r.get("away_team", "")})
        off = r.get("posteam") or ""
        if off and r.get("play_type") in ("pass", "run"):
            a = team.setdefault((gid, off), _acc())
            a["plays"] += 1
            a["yards"] += _num(r.get("yards_gained"))
            a["epa"] += _num(r.get("epa"))
            if r.get("play_type") == "pass":
                a["pass_plays"] += 1
            if r.get("interception") == "1" or r.get("fumble_lost") == "1":
                a["turnovers"] += 1
            if r.get("first_down") == "1":
                a["first_downs"] += 1
            if r.get("drive"):
                a["drives"].add(r["drive"])
        timeouts[gid] = (_num(r.get("home_timeouts_remaining"), 3), _num(r.get("away_timeouts_remaining"), 3))
        if qtr in PERIODS:
            m = meta[gid]
            h = team.get((gid, m["home"]), _acc())
            a = team.get((gid, m["away"]), _acc())
            snap[(gid, qtr)] = {"home": _flat(h), "away": _flat(a), "home_timeouts": timeouts[gid][0],
                                "away_timeouts": timeouts[gid][1]}
    out = []
    for gid in sorted(meta):
        q = {qtr: snap[(gid, qtr)] for qtr in PERIODS if (gid, qtr) in snap}
        if not q:
            continue
        m = meta[gid]
        out.append({"game_id": gid, "season": m["season"], "week": m["week"], "home": m["home"], "away": m["away"],
                    "q": q})
    return out


def _flat(a: dict) -> dict:
    plays = a["plays"]
    return {"plays": plays, "ypp": a["yards"] / plays if plays else 0.0, "epa_pp": a["epa"] / plays if plays else 0.0,
            "pass_rate": a["pass_plays"] / plays if plays else 0.0, "turnovers": a["turnovers"],
            "first_downs": a["first_downs"], "drives": len(a["drives"])}


def load_season(y: int, refresh: bool = False) -> list:
    path = os.path.join(CACHE, f"state_feats_{y}.json")
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    raw = http.get_release_bytes(PBP_URL.format(y=y))
    rows = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8"))
    recs = snapshot_rows(rows)
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(recs, fh, separators=(",", ":"))
    return recs


def load(seasons) -> Dict[str, dict]:
    out = {}
    for y in seasons:
        for rec in load_season(y):
            out[rec["game_id"]] = rec
    return out


if __name__ == "__main__":
    import sys
    seasons = range(int(sys.argv[1]), int(sys.argv[2]) + 1) if len(sys.argv) > 2 else range(2012, 2026)
    for y in seasons:
        print(y, len(load_season(y)), flush=True)
