"""Hierarchical league simulator.

Regions contain conferences, conferences contain teams, teams contain players.

Hidden truth per game (the model never sees these):
    margin_mean = S_home - S_away + home_advantage + rest_effect * (rest_h - rest_a)
                  + weather_style_effect * (style_h - style_a) * wind_z      (outdoor games only)
    S_team      = region + conference + team + player_scale * sum(w_p * talent_p) + form
    margin      = margin_mean + N(0, game_sd)
    p_true      = Phi(margin_mean / game_sd)        <- the oracle probability, the best any model can do

Observable to a model: scores, per-player efficiency readings (noisy talent plus a form signal),
availability, rest days, weather, team style, region/conference membership, and decoy columns.

Scenarios modify this world to build hard conditions:
    clean              no traps
    spurious_decoy     a feature that tracks true strength early, then becomes pure noise
    leakage_trap       a feature that leaks the game outcome
    duplicate_branch   a branch that is a near-copy of the team branch
    regime_shift       hidden team strengths jump mid-season
Harder conditions:
    reversal_decoy     a feature that tracks true strength early, then flips sign every season
    haystack           36 extra pure-noise columns in 9 branches, so false signals have many places to appear
    severe_shift       two large hidden shocks to 70% of teams, with part of the player talent redrawn
    weather_flip       a strong style x wind effect that reverses sign partway through
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, fields
from typing import Dict, List, Optional, Tuple

SQRT2 = math.sqrt(2.0)


def phi_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / SQRT2))


CORE_SCENARIOS = ("clean", "spurious_decoy", "leakage_trap", "duplicate_branch", "regime_shift")
HARD_SCENARIOS = ("reversal_decoy", "haystack", "severe_shift", "weather_flip")
SCENARIOS = CORE_SCENARIOS + HARD_SCENARIOS


@dataclass(frozen=True)
class LeagueConfig:
    regions: int = 3
    conferences_per_region: int = 2
    teams_per_conference: int = 4
    players_per_team: int = 5
    rounds_per_season: int = 34
    seasons: int = 4
    play_prob: float = 0.88
    same_conference_pref: float = 0.4
    indoor_fraction: float = 0.33
    # strength components, in margin points
    region_sd: float = 1.0
    conference_sd: float = 1.5
    team_sd: float = 3.0
    player_scale: float = 5.0
    replacement_talent: float = -0.5
    usage_weights: Tuple[float, ...] = (0.35, 0.25, 0.20, 0.12, 0.08)
    # game dynamics
    home_advantage: float = 2.5
    rest_effect: float = 0.6
    form_phi: float = 0.9
    form_sd: float = 0.5
    style_sd: float = 1.0
    weather_style_effect: float = 1.2
    game_sd: float = 12.0
    injury_prob: float = 0.01
    injury_days: int = 6
    efficiency_noise_sd: float = 1.5
    efficiency_form_coupling: float = 0.4
    # carryover between seasons
    team_carryover: float = 0.85
    team_refresh_sd: float = 1.2
    talent_carryover: float = 0.9
    talent_refresh_sd: float = 0.45
    # scenario settings
    scenario: str = "clean"
    shift_season: int = 2
    shift_round: int = 10
    shift_sd: float = 3.0
    spurious_until_season: int = 2
    spurious_strength: float = 0.7
    leak_strength: float = 0.9
    # harder scenarios
    severe_shifts: Tuple[Tuple[int, int], ...] = ((2, 10), (4, 5))
    severe_fraction: float = 0.7
    severe_shift_sd: float = 6.0
    severe_talent_reshuffle: float = 0.3
    haystack_columns: int = 36
    weather_flip_season: int = 3
    weather_flip_effect: float = 3.0
    aux_seed: int = 0

    @property
    def n_teams(self) -> int:
        return self.regions * self.conferences_per_region * self.teams_per_conference

    @property
    def n_conferences(self) -> int:
        return self.regions * self.conferences_per_region


def config_from_dict(raw: dict) -> LeagueConfig:
    known = {f.name for f in fields(LeagueConfig)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown league config keys: {sorted(unknown)}")
    raw = dict(raw)
    if "usage_weights" in raw:
        raw["usage_weights"] = tuple(raw["usage_weights"])
    if "severe_shifts" in raw:
        raw["severe_shifts"] = tuple(tuple(x) for x in raw["severe_shifts"])
    return LeagueConfig(**raw)


@dataclass(frozen=True)
class TeamStatic:
    idx: int
    region: int
    conference: int
    style: float
    indoor: bool
    usage_weights: Tuple[float, ...]


@dataclass
class Game:
    idx: int
    season: int
    round: int
    day: int
    home: int
    away: int
    # pre-game observables
    rest_home: int
    rest_away: int
    temp: float
    wind: float
    precip: float
    indoor: bool
    avail_home: Tuple[bool, ...]
    avail_away: Tuple[bool, ...]
    decoy_noise: Tuple[float, float, float, float]
    spurious: float
    leak: float
    # post-game observables
    home_pts: float
    away_pts: float
    home_win: int
    eff_home: Tuple[Optional[float], ...]
    eff_away: Tuple[Optional[float], ...]
    # truth, used only for scoring
    p_true: float
    margin_mean: float
    # extra observable noise columns, present only in the haystack scenario
    decoy_extra: Tuple[float, ...] = ()


@dataclass
class LeagueData:
    config: LeagueConfig
    teams: List[TeamStatic]
    games: List[Game]
    shift_game_index: Optional[int] = None
    meta: Dict[str, float] = field(default_factory=dict)
    shift_game_indices: List[int] = field(default_factory=list)


def _make_pairs(cfg: LeagueConfig, rng: random.Random, conference_of: List[int]) -> List[Tuple[int, int]]:
    playing = [t for t in range(cfg.n_teams) if rng.random() < cfg.play_prob]
    rng.shuffle(playing)
    pairs: List[Tuple[int, int]] = []
    pool = playing[:]
    while len(pool) >= 2:
        a = pool.pop()
        same = [t for t in pool if conference_of[t] == conference_of[a]]
        if same and rng.random() < cfg.same_conference_pref:
            b = rng.choice(same)
        else:
            b = rng.choice(pool)
        pool.remove(b)
        pairs.append((a, b) if rng.random() < 0.5 else (b, a))
    return pairs


def simulate_league(cfg: LeagueConfig, rng: random.Random) -> LeagueData:
    if cfg.scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {cfg.scenario!r}; choose from {SCENARIOS}")
    n = cfg.n_teams
    per_conf = cfg.teams_per_conference
    conference_of = [t // per_conf for t in range(n)]
    region_of = [c // cfg.conferences_per_region for c in conference_of]

    region_eff = [rng.gauss(0.0, cfg.region_sd) for _ in range(cfg.regions)]
    conf_eff = [rng.gauss(0.0, cfg.conference_sd) for _ in range(cfg.n_conferences)]
    team_eff = [rng.gauss(0.0, cfg.team_sd) for _ in range(n)]
    region_temp = [4.0 + 8.0 * r for r in range(cfg.regions)]

    teams: List[TeamStatic] = []
    talent: List[List[float]] = []
    for t in range(n):
        teams.append(TeamStatic(
            idx=t, region=region_of[t], conference=conference_of[t],
            style=rng.gauss(0.0, cfg.style_sd),
            indoor=rng.random() < cfg.indoor_fraction,
            usage_weights=cfg.usage_weights[: cfg.players_per_team],
        ))
        talent.append([rng.gauss(0.0, 1.0) for _ in range(cfg.players_per_team)])

    form = [0.0] * n
    form_stat_sd = cfg.form_sd / math.sqrt(1.0 - cfg.form_phi ** 2)
    form = [rng.gauss(0.0, form_stat_sd) for _ in range(n)]
    injured_until = [[-1] * cfg.players_per_team for _ in range(n)]
    last_day = [-3] * n

    games: List[Game] = []
    day = 0
    shift_game_indices: List[int] = []
    severe = cfg.scenario == "severe_shift"
    shift_points = (set(cfg.severe_shifts) if severe
                    else ({(cfg.shift_season, cfg.shift_round)} if cfg.scenario == "regime_shift" else set()))

    for season in range(cfg.seasons):
        if season > 0:
            for t in range(n):
                team_eff[t] = cfg.team_carryover * team_eff[t] + rng.gauss(0.0, cfg.team_refresh_sd)
                talent[t] = [cfg.talent_carryover * x + rng.gauss(0.0, cfg.talent_refresh_sd) for x in talent[t]]
        for rnd in range(cfg.rounds_per_season):
            if (season, rnd) in shift_points:
                fraction = cfg.severe_fraction if severe else 0.5
                shock_sd = cfg.severe_shift_sd if severe else cfg.shift_sd
                for t in range(n):
                    if rng.random() < fraction:
                        team_eff[t] += rng.gauss(0.0, shock_sd)
                if severe:
                    for t in range(n):
                        if rng.random() < cfg.severe_talent_reshuffle:
                            talent[t] = [rng.gauss(0.0, 1.0) for _ in range(cfg.players_per_team)]
                shift_game_indices.append(len(games))
            for t in range(n):
                for p in range(cfg.players_per_team):
                    if injured_until[t][p] <= day and rng.random() < cfg.injury_prob:
                        injured_until[t][p] = day + cfg.injury_days
            for h, a in _make_pairs(cfg, rng, conference_of):
                games.append(_play(cfg, rng, len(games), season, rnd, day, h, a, teams, talent, team_eff,
                                   conf_eff, region_eff, conference_of, region_of, region_temp, form,
                                   injured_until, last_day))
                last_day[h] = day
                last_day[a] = day
            for t in range(n):
                form[t] = cfg.form_phi * form[t] + rng.gauss(0.0, cfg.form_sd)
            day += 1
    return LeagueData(config=cfg, teams=teams, games=games,
                      shift_game_index=shift_game_indices[0] if shift_game_indices else None,
                      shift_game_indices=shift_game_indices)


def _play(cfg, rng, idx, season, rnd, day, h, a, teams, talent, team_eff, conf_eff, region_eff,
          conference_of, region_of, region_temp, form, injured_until, last_day) -> Game:
    avail_h = tuple(injured_until[h][p] <= day for p in range(cfg.players_per_team))
    avail_a = tuple(injured_until[a][p] <= day for p in range(cfg.players_per_team))

    def strength(t: int, avail: Tuple[bool, ...]) -> float:
        w = teams[t].usage_weights
        player_part = sum(
            w[p] * (talent[t][p] if avail[p] else cfg.replacement_talent) for p in range(cfg.players_per_team)
        )
        return (region_eff[region_of[t]] + conf_eff[conference_of[t]] + team_eff[t]
                + cfg.player_scale * player_part + form[t])

    rest_h = min(3, day - last_day[h])
    rest_a = min(3, day - last_day[a])
    indoor = teams[h].indoor
    if indoor:
        temp, wind, precip = 21.0, 0.0, 0.0
        wind_z = 0.0
    else:
        temp = region_temp[region_of[h]] + rng.gauss(0.0, 6.0)
        wind = abs(rng.gauss(10.0, 6.0))
        precip = rng.expovariate(1.0 / 2.0)
        wind_z = (wind - 10.0) / 6.0

    if cfg.scenario == "weather_flip":
        weather_effect = cfg.weather_flip_effect * (1.0 if season < cfg.weather_flip_season else -1.0)
    else:
        weather_effect = cfg.weather_style_effect
    margin_mean = (
        strength(h, avail_h) - strength(a, avail_a) + cfg.home_advantage
        + cfg.rest_effect * (rest_h - rest_a)
        + weather_effect * (teams[h].style - teams[a].style) * wind_z
    )
    margin = margin_mean + rng.gauss(0.0, cfg.game_sd)
    total = rng.gauss(200.0, 12.0)
    p_true = phi_cdf(margin_mean / cfg.game_sd)

    def efficiency(t: int, avail: Tuple[bool, ...]) -> Tuple[Optional[float], ...]:
        return tuple(
            (talent[t][p] + cfg.efficiency_form_coupling * form[t] + rng.gauss(0.0, cfg.efficiency_noise_sd))
            if avail[p] else None
            for p in range(cfg.players_per_team)
        )

    eff_h = efficiency(h, avail_h)
    eff_a = efficiency(a, avail_a)
    decoy = tuple(rng.gauss(0.0, 1.0) for _ in range(4))
    home_win = 1 if margin > 0 else 0

    z_mu = margin_mean / 6.5
    if season < cfg.spurious_until_season:
        s = cfg.spurious_strength
        spurious = s * z_mu + math.sqrt(1.0 - s * s) * rng.gauss(0.0, 1.0)
    else:
        noise = rng.gauss(0.0, 1.0)
        if cfg.scenario == "reversal_decoy":
            s = cfg.spurious_strength
            # the sign alternates every season after the break: -, +, -, +, ...
            sign = -1.0 if (season - cfg.spurious_until_season) % 2 == 0 else 1.0
            spurious = sign * s * z_mu + math.sqrt(1.0 - s * s) * noise
        else:
            spurious = noise
    s_leak = cfg.leak_strength
    leak = s_leak * (2.0 * home_win - 1.0) + math.sqrt(1.0 - s_leak * s_leak) * rng.gauss(0.0, 1.0)
    if cfg.scenario == "haystack":
        aux = random.Random(cfg.aux_seed * 1_000_003 + idx)
        extra = tuple(aux.gauss(0.0, 1.0) for _ in range(cfg.haystack_columns))
    else:
        extra = ()

    return Game(
        idx=idx, season=season, round=rnd, day=day, home=h, away=a,
        rest_home=rest_h, rest_away=rest_a, temp=temp, wind=wind, precip=precip, indoor=indoor,
        avail_home=avail_h, avail_away=avail_a, decoy_noise=decoy, spurious=spurious, leak=leak,
        home_pts=(total + margin) / 2.0, away_pts=(total - margin) / 2.0, home_win=home_win,
        eff_home=eff_h, eff_away=eff_a, p_true=p_true, margin_mean=margin_mean,
        decoy_extra=extra,
    )
