"""Connect a Kalshi NFL price to its nflverse game.

Kalshi event ids look like KXNFLGAME-26NOV22MINSF: yy, month, day, then two team codes. The market id ends with the
team the YES side is about (for example ...-SF means "San Francisco wins"). Team codes differ between sources in
places, so KALSHI_TO_NFL maps the known differences. Unmatched codes are reported, not guessed.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Sequence, Tuple

from ..realdata.observation import Observation
from .data import Game

KALSHI_TO_NFL = {"JAC": "JAX", "LAR": "LA"}   # Kalshi -> nflverse; found by checking unmatched events
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}


def parse_event(event_id: str) -> Optional[Tuple[str, str]]:
    """Return (iso_date, teams_block) or None if the id does not parse."""
    try:
        body = event_id.split("-", 1)[1]
        yy, mon, dd, teams = body[:2], body[2:5], body[5:7], body[7:]
        date = dt.date(2000 + int(yy), MONTHS[mon], int(dd)).isoformat()
    except (IndexError, KeyError, ValueError):
        return None
    return date, teams


def _alias(code: str) -> str:
    return KALSHI_TO_NFL.get(code, code)


def match_observation(obs: Observation, games: Sequence[Game]) -> Optional[Tuple[Game, str]]:
    """Return (game, side) where side is "home" or "away" for the team the YES side is about, or None."""
    parsed = parse_event(obs.event_id)
    if parsed is None:
        return None
    day, teams = parsed
    side_code = _alias(obs.market_id.rsplit("-", 1)[-1])
    day_d = dt.date.fromisoformat(day)
    candidates = [g for g in games
                  if abs((dt.date.fromisoformat(g.gameday) - day_d).days) <= 1]
    for split in (2, 3):
        left, right = teams[:split], teams[split:]
        if len(right) not in (2, 3):
            continue
        pair = {_alias(left), _alias(right)}
        for g in candidates:
            if {g.home, g.away} == pair:
                if side_code == g.home:
                    return g, "home"
                if side_code == g.away:
                    return g, "away"
    return None


def match_all(observations: Sequence[Observation], games: Sequence[Game]
              ) -> Tuple[List[Tuple[Observation, Game, str]], List[Observation]]:
    matched, unmatched = [], []
    for o in observations:
        m = match_observation(o, games)
        if m is None:
            unmatched.append(o)
        else:
            matched.append((o, m[0], m[1]))
    return matched, unmatched
