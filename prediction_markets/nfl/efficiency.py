"""Team efficiency from nflverse weekly team stats: expected points added (EPA) per play, walk-forward.

Pre-game only. A game's team ratings use games from EARLIER DAYS only. Games played on the same day are not used
for each other, because none of them has been played when the price is taken 24 hours before kickoff.

Per team-game:
    off_pp  = (passing_epa + rushing_epa) / plays, plays = attempts + carries + sacks_suffered
    net_pp  = off_pp(team) - off_pp(opponent)         the opponent's offence is this team's defence allowed
A team's rating before a game is the decayed mean of its earlier net_pp, shrunk toward 0 (league average):
    rating  = S / (W + K0),  S and W are exponentially decayed sums with half-life HALFLIFE games.

PRE-REGISTERED settings: HALFLIFE in {10, 20} games, K0 = 3 games-equivalent. Chosen on dev seasons only (see tune).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .data import Game

K0 = 3.0


@dataclass(frozen=True)
class TeamGame:
    season: int
    week: int
    game_id: str
    team: str
    opponent: str
    plays: float
    epa: float

    @property
    def off_pp(self) -> float:
        return self.epa / self.plays if self.plays > 0 else 0.0


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def parse_team_stats(text: str) -> List[TeamGame]:
    out: List[TeamGame] = []
    for r in csv.DictReader(io.StringIO(text)):
        plays = _f(r.get("attempts")) + _f(r.get("carries")) + _f(r.get("sacks_suffered"))
        epa = _f(r.get("passing_epa")) + _f(r.get("rushing_epa"))
        out.append(TeamGame(season=int(_f(r.get("season"))), week=int(_f(r.get("week"))), game_id=r["game_id"],
                            team=r["team"], opponent=r["opponent_team"], plays=plays, epa=epa))
    return out


def net_per_play(team_games: Iterable[TeamGame]) -> Dict[Tuple[str, str], float]:
    """(game_id, team) -> net EPA per play, where the opponent's offence is subtracted."""
    tg = list(team_games)
    off = {(t.game_id, t.team): t.off_pp for t in tg}
    out = {}
    for t in tg:
        opp = off.get((t.game_id, t.opponent))
        if opp is not None:
            out[(t.game_id, t.team)] = t.off_pp - opp
    return out


def efficiency_diffs(games: Sequence[Game], team_games: Iterable[TeamGame], halflife: float,
                     k0: float = K0) -> Dict[str, float]:
    """game_id -> home rating minus away rating, using only games from earlier days."""
    net = net_per_play(team_games)
    lam = 0.5 ** (1.0 / halflife)
    S: Dict[str, float] = defaultdict(float)
    W: Dict[str, float] = defaultdict(float)
    out: Dict[str, float] = {}
    by_day: Dict[str, List[Game]] = defaultdict(list)
    for g in games:
        by_day[g.gameday].append(g)
    for day in sorted(by_day):
        day_games = by_day[day]
        for g in day_games:
            out[g.game_id] = (S[g.home] / (W[g.home] + k0)) - (S[g.away] / (W[g.away] + k0))
        # update only after the whole day has been read, so same-day games never inform each other
        for g in day_games:
            for team in (g.home, g.away):
                x = net.get((g.game_id, team))
                if x is None:
                    continue
                S[team] = lam * S[team] + x
                W[team] = lam * W[team] + 1.0
    return out
