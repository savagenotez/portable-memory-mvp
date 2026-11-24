"""nflverse game data: download once, cache locally, parse."""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from typing import List, Optional

from ..realdata import http

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data",
                          "nflverse_games.csv")


@dataclass
class Game:
    game_id: str
    season: int
    week: int
    gameday: str                 # ISO date, YYYY-MM-DD
    home: str
    away: str
    home_score: Optional[int]    # None until the game is played
    away_score: Optional[int]
    rest_home: int               # days of rest before this game
    rest_away: int
    div_game: int
    neutral: bool

    @property
    def completed(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def home_won(self) -> Optional[int]:
        if not self.completed or self.home_score == self.away_score:
            return None
        return 1 if self.home_score > self.away_score else 0


def _int(x, default=None):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def parse_games(text: str) -> List[Game]:
    out: List[Game] = []
    for r in csv.DictReader(io.StringIO(text)):
        out.append(Game(
            game_id=r["game_id"], season=_int(r["season"]), week=_int(r.get("week"), 0), gameday=r["gameday"],
            home=r["home_team"], away=r["away_team"],
            home_score=_int(r.get("home_score")), away_score=_int(r.get("away_score")),
            rest_home=_int(r.get("home_rest"), 7), rest_away=_int(r.get("away_rest"), 7),
            div_game=_int(r.get("div_game"), 0), neutral=(r.get("location", "") == "Neutral"),
        ))
    return sorted(out, key=lambda g: (g.gameday, g.game_id))


def load_games(refresh: bool = False, path: str = CACHE_PATH) -> List[Game]:
    if refresh or not os.path.exists(path):
        text = http.get_text(GAMES_URL)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    return parse_games(text)
