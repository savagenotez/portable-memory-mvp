"""Walk-forward feature builder.

Features for game g are computed ONLY from games before g. The builder reads a game's
outcome-dependent fields in observe(), which is called after the row for that game is made.
tests/test_league_features.py checks this causality property directly.

Branches (families of variables):
    team         record-based strength: net rating, win rate, points for and against
    player       roster talent from individual efficiency readings, star availability, recent form
    schedule     rest, back-to-back, number of games played, season progress
    geo          conference and region strength estimates, cross-conference and same-region flags
    streak       current streak and recent margins
    weather      raw weather and indoor flag (main effects only)
    interaction  crossed effects: team style x weather, rest x strength
    decoy_noise  pure noise columns. Their branch score should stay near zero.
Scenario extras:
    news         spurious_decoy: tracks true strength early, then becomes noise
    leak         leakage_trap: contains the game outcome
    team_dup     duplicate_branch: near-copy of the team branch
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Dict, List

from .sim import Game, LeagueData

BASE_BRANCHES: Dict[str, List[str]] = {
    "team": ["net_diff", "win_diff", "pf_diff", "pa_diff"],
    "player": ["roster_diff", "top_diff", "depth_diff", "star_out_home", "star_out_away", "eff_recent_diff"],
    "schedule": ["rest_diff", "b2b_home", "b2b_away", "log_games_min", "season_progress"],
    "geo": ["conf_diff", "region_diff", "cross_conf", "same_region"],
    "streak": ["streak_diff", "last5_diff", "last10_diff"],
    "weather": ["temp_z", "wind_z", "precip_z", "indoor"],
    "interaction": ["style_wind", "style_precip", "style_temp", "rest_x_net"],
    "decoy_noise": ["n1", "n2", "n3", "n4"],
}

EXTRA_BRANCHES: Dict[str, Dict[str, List[str]]] = {
    "spurious_decoy": {"news": ["spurious"]},
    "leakage_trap": {"leak": ["leak"]},
    "duplicate_branch": {"team_dup": ["dup_net_diff", "dup_win_diff", "dup_pf_diff", "dup_pa_diff"]},
}


def branches_for(scenario: str) -> Dict[str, List[str]]:
    out = {name: list(cols) for name, cols in BASE_BRANCHES.items()}
    for name, cols in EXTRA_BRANCHES.get(scenario, {}).items():
        out[name] = list(cols)
    return out


@dataclass(frozen=True)
class FeatureConfig:
    team_halflife: float = 20.0
    player_halflife: float = 60.0
    recent_halflife: float = 8.0
    group_halflife: float = 60.0
    team_prior_n: float = 4.0
    player_prior_n: float = 4.0
    group_prior_n: float = 10.0
    replacement_prior: float = -0.5


@dataclass
class Row:
    idx: int
    features: Dict[str, float]
    context: Dict[str, float]
    y: int
    p_true: float


def _decay(halflife: float) -> float:
    return 0.5 ** (1.0 / halflife)


class FeatureBuilder:
    def __init__(self, league: LeagueData, cfg: FeatureConfig = FeatureConfig()):
        self.league = league
        self.cfg = cfg
        n = league.config.n_teams
        pl = league.config.players_per_team
        self.lam_team = _decay(cfg.team_halflife)
        self.lam_player = _decay(cfg.player_halflife)
        self.lam_recent = _decay(cfg.recent_halflife)
        self.lam_group = _decay(cfg.group_halflife)
        self.t_margin = [0.0] * n
        self.t_win = [0.0] * n
        self.t_pf = [0.0] * n
        self.t_pa = [0.0] * n
        self.t_w = [0.0] * n
        self.games_total = [0] * n
        self.games_season = [0] * n
        self.season_seen = [-1] * n
        self.streak = [0] * n
        self.recent_margins = [deque(maxlen=10) for _ in range(n)]
        self.p_s = [[0.0] * pl for _ in range(n)]
        self.p_w = [[0.0] * pl for _ in range(n)]
        self.rec_s = [0.0] * n
        self.rec_w = [0.0] * n
        self.long_s = [0.0] * n
        self.long_w = [0.0] * n
        self.conf_s = [0.0] * league.config.n_conferences
        self.conf_w = [0.0] * league.config.n_conferences
        self.reg_s = [0.0] * league.config.regions
        self.reg_w = [0.0] * league.config.regions

    # ---- per-team readouts -------------------------------------------------------------
    def _net(self, t: int) -> float:
        return self.t_margin[t] / (self.t_w[t] + self.cfg.team_prior_n)

    def _win(self, t: int) -> float:
        n0 = self.cfg.team_prior_n
        return (self.t_win[t] + 0.5 * n0) / (self.t_w[t] + n0) - 0.5

    def _pf(self, t: int) -> float:
        n0 = self.cfg.team_prior_n
        return (self.t_pf[t] + 100.0 * n0) / (self.t_w[t] + n0) - 100.0

    def _pa(self, t: int) -> float:
        n0 = self.cfg.team_prior_n
        return (self.t_pa[t] + 100.0 * n0) / (self.t_w[t] + n0) - 100.0

    def _tau(self, t: int, p: int, available: bool) -> float:
        if not available:
            return self.cfg.replacement_prior
        return self.p_s[t][p] / (self.p_w[t][p] + self.cfg.player_prior_n)

    def _roster(self, t: int, avail) -> float:
        w = self.league.teams[t].usage_weights
        return sum(w[p] * self._tau(t, p, avail[p]) for p in range(len(w)))

    def _recent_eff(self, t: int) -> float:
        return self.rec_s[t] / (self.rec_w[t] + 2.0) - self.long_s[t] / (self.long_w[t] + 2.0)

    def _last(self, t: int, k: int) -> float:
        m = list(self.recent_margins[t])[-k:]
        return sum(m) / (len(m) + 3.0)

    def _group(self, s: float, w: float) -> float:
        return s / (w + self.cfg.group_prior_n)

    # ---- features for one game ----------------------------------------------------------
    def features_for(self, g: Game) -> Dict[str, float]:
        h, a = g.home, g.away
        th, ta = self.league.teams[h], self.league.teams[a]
        cap = lambda x, lim: max(-lim, min(lim, x))

        net_diff = self._net(h) - self._net(a)
        win_diff = self._win(h) - self._win(a)
        pf_diff = self._pf(h) - self._pf(a)
        pa_diff = self._pa(h) - self._pa(a)

        top_h = self._tau(h, 0, g.avail_home[0])
        top_a = self._tau(a, 0, g.avail_away[0])
        depth_h = sum(self._tau(h, p, g.avail_home[p]) for p in range(2, len(g.avail_home))) / max(1, len(g.avail_home) - 2)
        depth_a = sum(self._tau(a, p, g.avail_away[p]) for p in range(2, len(g.avail_away))) / max(1, len(g.avail_away) - 2)
        rest_diff = float(g.rest_home - g.rest_away)

        outdoor = 0.0 if g.indoor else 1.0
        wind_z = (g.wind - 10.0) / 6.0 * outdoor
        precip_z = (g.precip - 2.0) / 3.0 * outdoor
        temp_z = (g.temp - 12.0) / 8.0 * outdoor
        style_diff = th.style - ta.style

        feats = {
            "net_diff": net_diff, "win_diff": win_diff, "pf_diff": pf_diff, "pa_diff": pa_diff,
            "roster_diff": self._roster(h, g.avail_home) - self._roster(a, g.avail_away),
            "top_diff": top_h - top_a, "depth_diff": depth_h - depth_a,
            "star_out_home": 0.0 if g.avail_home[0] else 1.0,
            "star_out_away": 0.0 if g.avail_away[0] else 1.0,
            "eff_recent_diff": self._recent_eff(h) - self._recent_eff(a),
            "rest_diff": rest_diff,
            "b2b_home": 1.0 if g.rest_home == 1 else 0.0,
            "b2b_away": 1.0 if g.rest_away == 1 else 0.0,
            "log_games_min": math.log1p(min(self.games_total[h], self.games_total[a])),
            "season_progress": g.round / max(1, self.league.config.rounds_per_season),
            "conf_diff": self._group(self.conf_s[th.conference], self.conf_w[th.conference])
                         - self._group(self.conf_s[ta.conference], self.conf_w[ta.conference]),
            "region_diff": self._group(self.reg_s[th.region], self.reg_w[th.region])
                           - self._group(self.reg_s[ta.region], self.reg_w[ta.region]),
            "cross_conf": 1.0 if th.conference != ta.conference else 0.0,
            "same_region": 1.0 if th.region == ta.region else 0.0,
            "streak_diff": float(cap(self.streak[h], 8) - cap(self.streak[a], 8)),
            "last5_diff": self._last(h, 5) - self._last(a, 5),
            "last10_diff": self._last(h, 10) - self._last(a, 10),
            "temp_z": temp_z, "wind_z": wind_z, "precip_z": precip_z, "indoor": 1.0 - outdoor,
            "style_wind": style_diff * wind_z, "style_precip": style_diff * precip_z,
            "style_temp": style_diff * temp_z, "rest_x_net": rest_diff * net_diff,
            "n1": g.decoy_noise[0], "n2": g.decoy_noise[1], "n3": g.decoy_noise[2], "n4": g.decoy_noise[3],
            "spurious": g.spurious,
            "leak": g.leak,
            "dup_net_diff": net_diff + 0.05 * g.decoy_noise[0],
            "dup_win_diff": win_diff + 0.05 * g.decoy_noise[1],
            "dup_pf_diff": pf_diff + 0.05 * g.decoy_noise[2],
            "dup_pa_diff": pa_diff + 0.05 * g.decoy_noise[3],
        }
        return feats

    def context_for(self, g: Game) -> Dict[str, float]:
        h, a = g.home, g.away
        th, ta = self.league.teams[h], self.league.teams[a]
        outdoor = 0.0 if g.indoor else 1.0
        return {
            "season": float(g.season),
            "round": float(g.round),
            "min_games_total": float(min(self.games_total[h], self.games_total[a])),
            "min_games_season": float(min(self._season_games(h, g.season), self._season_games(a, g.season))),
            "cross_conf": 1.0 if th.conference != ta.conference else 0.0,
            "wind_z": (g.wind - 10.0) / 6.0 * outdoor,
            "outdoor": outdoor,
            "streak_gap": float(abs(max(-8, min(8, self.streak[h])) - max(-8, min(8, self.streak[a])))),
        }

    def _season_games(self, t: int, season: int) -> int:
        return self.games_season[t] if self.season_seen[t] == season else 0

    # ---- update after the outcome is known ----------------------------------------------
    def observe(self, g: Game) -> None:
        margin = g.home_pts - g.away_pts
        for t, m, win, pf, pa, eff, avail in (
            (g.home, margin, g.home_win, g.home_pts, g.away_pts, g.eff_home, g.avail_home),
            (g.away, -margin, 1 - g.home_win, g.away_pts, g.home_pts, g.eff_away, g.avail_away),
        ):
            lam = self.lam_team
            self.t_margin[t] = lam * self.t_margin[t] + m
            self.t_win[t] = lam * self.t_win[t] + win
            self.t_pf[t] = lam * self.t_pf[t] + pf
            self.t_pa[t] = lam * self.t_pa[t] + pa
            self.t_w[t] = lam * self.t_w[t] + 1.0
            self.games_total[t] += 1
            if self.season_seen[t] != g.season:
                self.season_seen[t] = g.season
                self.games_season[t] = 0
            self.games_season[t] += 1
            if win:
                self.streak[t] = self.streak[t] + 1 if self.streak[t] > 0 else 1
            else:
                self.streak[t] = self.streak[t] - 1 if self.streak[t] < 0 else -1
            self.recent_margins[t].append(m)

            readings = []
            for p, e in enumerate(eff):
                if e is None:
                    continue
                self.p_s[t][p] = self.lam_player * self.p_s[t][p] + e
                self.p_w[t][p] = self.lam_player * self.p_w[t][p] + 1.0
                readings.append(e)
            if readings:
                avg = sum(readings) / len(readings)
                self.rec_s[t] = self.lam_recent * self.rec_s[t] + avg
                self.rec_w[t] = self.lam_recent * self.rec_w[t] + 1.0
                self.long_s[t] = self.lam_player * self.long_s[t] + avg
                self.long_w[t] = self.lam_player * self.long_w[t] + 1.0

            team = self.league.teams[t]
            self.conf_s[team.conference] = self.lam_group * self.conf_s[team.conference] + m
            self.conf_w[team.conference] = self.lam_group * self.conf_w[team.conference] + 1.0
            self.reg_s[team.region] = self.lam_group * self.reg_s[team.region] + m
            self.reg_w[team.region] = self.lam_group * self.reg_w[team.region] + 1.0


def build_rows(league: LeagueData, cfg: FeatureConfig = FeatureConfig()) -> List[Row]:
    """One pass in time order. Each row is made BEFORE the game's outcome is observed."""
    builder = FeatureBuilder(league, cfg)
    rows: List[Row] = []
    for g in league.games:
        feats = builder.features_for(g)
        ctx = builder.context_for(g)
        rows.append(Row(idx=g.idx, features=feats, context=ctx, y=g.home_win, p_true=g.p_true))
        builder.observe(g)
    return rows
