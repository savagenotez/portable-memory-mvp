"""nflverse season files: weekly team stats and injury reports. Downloaded once, cached in the git-ignored data folder.

Only the nflverse release-download path is reachable (see realdata/http.py).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from ..realdata import http
from .efficiency import TeamGame, parse_team_stats
from .injuries import parse_injury_counts

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data", "nflverse")
STATS_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{y}.csv"
INJURY_URL = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{y}.csv"


def _cached(url: str, name: str, refresh: bool = False) -> Optional[str]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    try:
        text = http.get_release_text(url)
    except Exception:
        return None                       # a season with no file is reported, not guessed
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def load_team_games(seasons=range(2000, 2027), refresh: bool = False) -> Tuple[List[TeamGame], List[int]]:
    games: List[TeamGame] = []
    missing: List[int] = []
    for y in seasons:
        text = _cached(STATS_URL.format(y=y), f"stats_team_week_{y}.csv", refresh)
        if text is None:
            missing.append(y)
            continue
        games.extend(parse_team_stats(text))
    return games, missing


def load_injury_counts(seasons=range(2009, 2027), refresh: bool = False) -> Tuple[Dict, List[int]]:
    counts: Dict = {}
    missing: List[int] = []
    for y in seasons:
        text = _cached(INJURY_URL.format(y=y), f"injuries_{y}.csv", refresh)
        if text is None:
            missing.append(y)
            continue
        counts.update(parse_injury_counts(text))
    return counts, missing


SNAPS_URL = "https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{y}.csv"
PLAYERS_URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"


def load_players(refresh: bool = False) -> Dict[str, dict]:
    """gsis id -> {pfr id, position, birth date}. Positions and ids only; nothing about a game result."""
    import csv
    import io
    text = _cached(PLAYERS_URL, "players.csv", refresh)
    out: Dict[str, dict] = {}
    if text is None:
        return out
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("gsis_id"):
            out[r["gsis_id"]] = {"pfr_id": r.get("pfr_id") or "", "position": r.get("position") or "",
                                 "birth_date": r.get("birth_date") or ""}
    return out


def load_snaps(seasons, refresh_last: bool = False) -> Tuple[Dict, Dict, List[int]]:
    """Offensive snaps. Returns ({(game, team): {pfr id: (snaps, share)}}, {(game, team): team snaps}, missing)."""
    import csv
    import io
    player: Dict = {}
    team: Dict = {}
    missing: List[int] = []
    seasons = list(seasons)
    for y in seasons:
        text = _cached(SNAPS_URL.format(y=y), f"snap_counts_{y}.csv", refresh_last and y == seasons[-1])
        if text is None:
            missing.append(y)
            continue
        est: Dict = {}
        for r in csv.DictReader(io.StringIO(text)):
            try:
                snaps, pct = float(r["offense_snaps"]), float(r["offense_pct"])
            except (KeyError, ValueError):
                continue
            if snaps <= 0:
                continue
            key = (r["game_id"], r["team"])
            player.setdefault(key, {})[r["pfr_player_id"]] = (snaps, pct)
            if pct >= 0.5:
                est.setdefault(key, []).append(snaps / pct)
        for key, v in est.items():
            v.sort()
            team[key] = v[len(v) // 2]
    return player, team, missing
