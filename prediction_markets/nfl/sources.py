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
