"""Compact play-by-play tables from nflverse, one cached file per season (git-ignored).

Kept per season, so the projection models never re-read the 19 MB raw files:

    fg     [game, team, quarter, distance, made]            + kicker id     every field goal attempt
    xp     [game, team, quarter, good]                                      every extra point attempt
    two    [game, team, quarter, success]                                   every two-point attempt
    td     [game, team, quarter]                                            every touchdown, by scoring team
    pass   [game, team, quarter, passer, receiver, complete, yards]        every pass (sacks excluded)
    rush   [game, team, quarter, rusher, yards]                             every designed run (kneels kept)
    names  player id -> name
    state  game -> {"q1": [team with ball, yards to goal, down, distance], "q3": [...], "h2": team receiving}
    weather game -> [temperature, wind, roof]

Two-point tries are not counted as passes or runs, as in the official statistics. Player ids are the league's
gsis ids, which the injury reports also use.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from typing import Dict, Iterable, List

from ..realdata import http

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data", "nflverse")
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.csv.gz"


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def compact(rows: Iterable[dict]) -> dict:
    out = {"fg": [], "xp": [], "two": [], "td": [], "pass": [], "rush": [], "names": {}, "state": {}, "weather": {}}
    names = out["names"]
    last_q: Dict[tuple, tuple] = {}
    first_q3: Dict[str, tuple] = {}
    for r in rows:
        gid = r.get("game_id")
        qtr = r.get("qtr")
        if not gid or qtr not in ("1", "2", "3", "4", "5"):
            continue
        q = int(qtr)
        team = r.get("posteam") or ""
        pid = _num(r.get("play_id"), 0.0)
        if gid not in out["weather"]:
            out["weather"][gid] = [_num(r.get("temp")), _num(r.get("wind")), r.get("roof") or ""]
        if team and q in (1, 3) and r.get("play_type") not in ("", None, "no_play"):
            key = (gid, q)
            if key not in last_q or pid > last_q[key][0]:
                last_q[key] = (pid, [team, _num(r.get("yardline_100")), _num(r.get("down")), _num(r.get("ydstogo"))])
        if team and q == 3 and (gid not in first_q3 or pid < first_q3[gid][0]):
            first_q3[gid] = (pid, team)
        two = r.get("two_point_attempt") == "1"
        if r.get("field_goal_attempt") == "1" and team:
            kid = r.get("kicker_player_id") or ""
            out["fg"].append([gid, team, q, _num(r.get("kick_distance"), 0.0), int(r.get("field_goal_result") == "made"),
                              kid])
            if kid:
                names[kid] = r.get("kicker_player_name") or kid
        if r.get("extra_point_attempt") == "1" and team:
            out["xp"].append([gid, team, q, int(r.get("extra_point_result") == "good")])
        if two and team:
            out["two"].append([gid, team, q, int(r.get("two_point_conv_result") == "success")])
        if r.get("touchdown") == "1" and r.get("td_team"):
            out["td"].append([gid, r["td_team"], q])
        if two or not team:
            continue
        if r.get("pass_attempt") == "1" and r.get("sack") != "1":
            pas, rec = r.get("passer_player_id") or "", r.get("receiver_player_id") or ""
            if pas:
                names[pas] = r.get("passer_player_name") or pas
            if rec:
                names[rec] = r.get("receiver_player_name") or rec
            if pas:
                out["pass"].append([gid, team, q, pas, rec, int(r.get("complete_pass") == "1"),
                                    _num(r.get("passing_yards"), 0.0) or 0.0])
        elif r.get("rush_attempt") == "1":
            rus = r.get("rusher_player_id") or ""
            if rus:
                names[rus] = r.get("rusher_player_name") or rus
                out["rush"].append([gid, team, q, rus, _num(r.get("rushing_yards"), 0.0) or 0.0])
    for (gid, q), (_, st) in last_q.items():
        out["state"].setdefault(gid, {})[f"q{q}"] = st
    for gid, (_, team) in first_q3.items():
        out["state"].setdefault(gid, {})["h2"] = team
    return out


def load_season(y: int, refresh: bool = False) -> dict:
    path = os.path.join(CACHE, f"pbp_compact_{y}.json")
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    raw = http.get_release_bytes(PBP_URL.format(y=y))
    rows = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw)), encoding="utf-8"))
    data = compact(rows)
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    return data


def load(seasons: Iterable[int], refresh: bool = False) -> dict:
    merged = {"fg": [], "xp": [], "two": [], "td": [], "pass": [], "rush": [], "names": {}, "state": {}, "weather": {}}
    for y in seasons:
        d = load_season(y, refresh)
        for k in ("fg", "xp", "two", "td", "pass", "rush"):
            merged[k].extend(d[k])
        for k in ("names", "state", "weather"):
            merged[k].update(d[k])
    return merged


def load_through(season: int, first: int = 2012) -> dict:
    """History from the cache, and the given season re-downloaded (it may still be in progress)."""
    data = load(range(first, season))
    cur = load_season(season, refresh=True)
    for k in ("fg", "xp", "two", "td", "pass", "rush"):
        data[k].extend(cur[k])
    for k in ("names", "state", "weather"):
        data[k].update(cur[k])
    return data


if __name__ == "__main__":
    import sys
    seasons = range(int(sys.argv[1]), int(sys.argv[2]) + 1) if len(sys.argv) > 2 else range(2012, 2026)
    for y in seasons:
        d = load_season(y)
        print(y, {k: len(d[k]) for k in ("fg", "td", "pass", "rush", "state")}, flush=True)
