"""Injury counts from the weekly injury reports (nflverse), pre-game.

Feature per team-week: the number of players ruled OUT or DOUBTFUL at key positions. The official report for a game
week is published before the 24-hour cutoff for almost every game (Friday for Sunday games).

PRE-REGISTERED key positions: QB, WR, TE, OL (T, G, C, OL), DL (DE, DT, DL), CB, S, LB.
Counts are only used from seasons with injury data (2009 onward).
"""

from __future__ import annotations

import csv
import io
from typing import Dict, Tuple

KEY_POSITIONS = {"QB", "WR", "TE", "T", "G", "C", "OL", "DE", "DT", "DL", "CB", "S", "LB"}
MISSING = {"Out", "Doubtful"}


def parse_injury_counts(text: str) -> Dict[Tuple[int, int, str], int]:
    counts: Dict[Tuple[int, int, str], int] = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            season, week = int(float(r["season"])), int(float(r["week"]))
        except (KeyError, TypeError, ValueError):
            continue
        key = (season, week, r.get("team", ""))
        counts.setdefault(key, 0)
        if (r.get("position") or "") in KEY_POSITIONS and (r.get("report_status") or "") in MISSING:
            counts[key] += 1
    return counts


def injury_diff(counts: Dict[Tuple[int, int, str], int], season: int, week: int, home: str, away: str) -> float:
    """Home minus away missing key players. Negative means the home side is more depleted."""
    return float(counts.get((season, week, away), 0) - counts.get((season, week, home), 0))
