"""Player and pair projections: attempts, makes, percentages and yards, by game and quarter, over/under at any line.

PRE-REGISTERED (written before any player projection was scored):

  Stats per player-game
    passer     pass attempts, completions (makes out of attempts), completion %, passing yards
    receiver   targets, receptions (makes out of targets), catch %, receiving yards
    rusher     carries, rushing yards (a negative total counts as 0)
    pair       the team's primary quarterback to one receiver: targets, receptions, yards
    quarters   pass attempts, targets and carries in each quarter (league quarter shares, same size r)

  Who is projected (decided before kickoff): for each stat, players who recorded it for the team in any of the
  team's previous 3 games, minus players listed Out or Doubtful on that week's injury report. The outcome counts
  even if it is 0 (benched, inactive, injured in-game). The primary quarterback is the one with the most pass
  attempts in the team's previous game; a pair is scored only when that quarterback threw at least one pass, which
  assumes the starter is known before kickoff.

  Model
    counts   player's decayed rate shrunk toward the league mean of projected players (DecayedRate), negative
             binomial with size r. Pairs shrink toward the receiver's own rate.
    makes    attempts (as above) x make rate: player's decayed completion or catch rate, shrunk toward the league
             with fixed prior weight (60 attempts for completions, 20 targets for catches, half-life 16 games).
  Grid per stat, chosen on 2013-2019 by mean squared error (2012 is warm-up): half-life {4, 8, 16} games, k0 {1, 3, 6}.
  Size r per stat by likelihood on the same seasons.

  Scored on 2020-2025. DEVELOPMENT, not blind. Two baselines:
    league     the league mean for projected players (no player information)
    season     the player's own average so far this season (Poisson), the usual quick projection; league mean
               before his first game of the season
  Log score, and Brier for over/under at the "typical line" (the season average rounded to the nearest .5, the way
  simple prop lines are set), with paired 95% intervals, and predicted-versus-observed at that line.

    python3 -m prediction_markets.nfl.player_props evaluate
    python3 -m prediction_markets.nfl.player_props forecast 2026_13_KC_DAL

REVISION 2 (pre-registered before it was run; the rules above are the record of the first attempt, which failed):
  Why      The first attempt fitted one size per stat, pooled over all players. The fit landed on the grid edge (0.5),
           which gives a 35-attempt quarterback a standard deviation of about 50 attempts.
  Changes  (1) the size is fitted per stat and per position group (QB, RB, WR, TE, other), and falls back to the
           pooled size for a group with fewer than 200 player-game rows in the choosing window;
           (2) the size grid is (1, 1.5, 2, 3, 5, 8, 13, 25, 50, Poisson): nothing below 1;
           (3) half-life and k0 are chosen as before, by mean squared error, on the choosing window.
  Windows  choose on 2012-2017; score on 2018-2019 (the primary test). 2020-2025 is used for neither in this revision.
  Edges    a chosen size equal to 1 (the new lower edge) is reported as a warning, not hidden.
  Pass     per stat, the model's log score minus the league-only and season-average baselines, with a paired 95%
           interval. DEVELOPMENT, not blind: 2018-2019 were looked at by the strict replay.

    python3 -m prediction_markets.nfl.player_props evaluate-r2
    python3 -m prediction_markets.nfl.player_props forecast-r2 2026_13_KC_DAL

REVISION 3 (pre-registered before it was run; revision 2 is kept as the record):
  Why      A diagnostic on 2012-2017 (no rule changed) found that the lowest k0 won for every stat, even on a much
           wider grid (k0 0.1 to 100). Shrinkage was pulling each player's rate toward ONE league-wide average of all
           projected players (about 1 attempt a game), so a 35-attempt quarterback was being pulled toward 1. The
           prior was the problem, not the amount of shrinkage.
  Change   The prior for a player's rate is his position group's average rate over the projected players in that
           group (QB, RB, WR, TE, other), not the league-wide average. Sizes and the size grid are as in revision 2.
  Grid     half-life {4, 8, 16, 64} games; k0 {0.5, 1, 3, 6, 20} (wider than revision 2, fixed here in advance).
  Windows  choose on 2012-2017; score on 2020-2025. Revision 2 scored 2018-2019, so those seasons are not used again.
           2020-2025 has never been scored for player props, though it was used for the team and Elo settings.
  Edges    as in revision 2: a chosen value at a grid edge is reported as a warning.
  Pass     as in revision 2. DEVELOPMENT, not blind.

    python3 -m prediction_markets.nfl.player_props evaluate-r3
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ..stats import engine as E
from .data import Game, load_games
from .team_props import RESULTS, WARMUP, DEV, EVAL, paired, _days

GRID = [(h, k) for h in (4, 8, 16) for k in (1, 3, 6)]
SIZE_GRID = (1, 1.5, 2, 3, 5, 8, 13, 25, 50, E.POISSON)          # revision 2: nothing below 1
GROUPS = ("QB", "RB", "WR", "TE", "other")
MIN_OBS_GROUP = 200
CHOOSE_R2 = range(2012, 2018)
SCORE_R2 = range(2018, 2020)
SCORE_R3 = range(2020, 2026)
GRID3 = [(h, k) for h in (4, 8, 16, 64) for k in (0.5, 1, 3, 6, 20)]


def group(pos: str) -> str:
    return {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE"}.get(pos, "other")


def player_groups() -> Dict[str, str]:
    from .sources import load_players
    return {gs: group(v.get("position", "")) for gs, v in load_players().items()}
COUNT_STATS = ("att", "pyd", "tgt", "ryd", "car", "ruyd")
ROLE = {"att": "passer", "pyd": "passer", "cmp": "passer", "tgt": "receiver", "ryd": "receiver", "rec": "receiver",
        "car": "rusher", "ruyd": "rusher"}
MAKES = {"cmp": ("att", 60.0), "rec": ("tgt", 20.0)}          # makes stat -> (attempts stat, prior weight)
QUARTER_STATS = ("att", "tgt", "car")
LABEL = {"att": "pass attempts", "cmp": "completions", "pyd": "passing yards", "tgt": "targets", "rec": "receptions",
         "ryd": "receiving yards", "car": "carries", "ruyd": "rushing yards", "pair_tgt": "pair targets",
         "pair_rec": "pair receptions", "pair_yd": "pair yards"}
MISSING = {"Out", "Doubtful"}
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realdata", "data", "nflverse")


def load_out(seasons) -> Dict[Tuple[int, int, str], Set[str]]:
    out: Dict[Tuple[int, int, str], Set[str]] = defaultdict(set)
    for y in seasons:
        path = os.path.join(CACHE, f"injuries_{y}.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("report_status") or "") in MISSING and r.get("gsis_id"):
                    try:
                        out[(int(float(r["season"])), int(float(r["week"])), r["team"])].add(r["gsis_id"])
                    except (KeyError, ValueError):
                        continue
    return out


def player_actuals(data: dict):
    """(game, team) -> {player: stats}, and (game, team) -> {(qb, receiver): pair stats}."""
    blank = lambda: {"att": 0, "cmp": 0, "pyd": 0.0, "tgt": 0, "rec": 0, "ryd": 0.0, "car": 0, "ruyd": 0.0,
                     "q_att": [0] * 6, "q_tgt": [0] * 6, "q_car": [0] * 6}
    players: Dict[Tuple[str, str], Dict[str, dict]] = defaultdict(lambda: defaultdict(blank))
    pairs: Dict[Tuple[str, str], Dict[Tuple[str, str], dict]] = defaultdict(
        lambda: defaultdict(lambda: {"tgt": 0, "rec": 0, "yd": 0.0}))
    for gid, team, q, pas, rec, comp, yds in data["pass"]:
        p = players[(gid, team)][pas]
        p["att"] += 1
        p["cmp"] += comp
        p["pyd"] += yds
        p["q_att"][q] += 1
        if rec:
            r = players[(gid, team)][rec]
            r["tgt"] += 1
            r["rec"] += comp
            r["ryd"] += yds
            r["q_tgt"][q] += 1
            pr = pairs[(gid, team)][(pas, rec)]
            pr["tgt"] += 1
            pr["rec"] += comp
            pr["yd"] += yds
    for gid, team, q, rus, yds in data["rush"]:
        p = players[(gid, team)][rus]
        p["car"] += 1
        p["ruyd"] += yds
        p["q_car"][q] += 1
    return players, pairs


def _count(v: float) -> int:
    return max(0, int(round(v)))


class PlayerModel:
    def __init__(self, params: Dict[str, Tuple[float, float]], sizes: Optional[dict] = None,
                 groups: Optional[Dict[str, str]] = None, prior: str = "league"):
        self.params = params
        self.rate = {s: E.DecayedRate(*params[s]) for s in COUNT_STATS}
        self.pair = {s: E.DecayedRate(*params[b]) for s, b in (("tgt", "tgt"), ("rec", "tgt"), ("yd", "ryd"))}
        self.make = {s: E.DecayedRate(16, k0) for s, (_, k0) in MAKES.items()}
        self.lg = {s: E.LeagueRate(start=1.0) for s in COUNT_STATS}
        self.lg_make = {"cmp": E.LeagueRate(start=0.62), "rec": E.LeagueRate(start=0.65)}
        self.qshare = {s: [E.LeagueRate(start=0.25) for _ in range(6)] for s in QUARTER_STATS}
        self.sizes = sizes or {}                 # s -> {"pooled": r, "groups": {group: r}}
        self.groups = groups or {}               # player id -> position group
        self.prior = prior                       # "league" (revisions 1-2) or "group" (revision 3)
        self.lg_grp = {s: defaultdict(lambda: E.LeagueRate(start=1.0)) for s in COUNT_STATS}
        self.recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=3))   # team -> last 3 games' role sets
        self.primary_qb: Dict[str, str] = {}

    def eligible(self, team: str, out: Set[str]) -> Dict[str, Set[str]]:
        roles: Dict[str, Set[str]] = {"passer": set(), "receiver": set(), "rusher": set()}
        for game_roles in self.recent[team]:
            for role, ids in game_roles.items():
                roles[role] |= ids
        return {r: ids - out for r, ids in roles.items()}

    def mean(self, s: str, pid: str) -> float:
        if self.prior == "group":
            return self.rate[s].rate(pid, self.lg_grp[s][self.groups.get(pid, "other")].value)
        return self.rate[s].rate(pid, self.lg[s].value)

    def size(self, s: str, pid: Optional[str] = None) -> float:
        entry = self.sizes.get(s)
        if not entry:
            return E.POISSON
        if pid is None:
            return entry.get("pooled", E.POISSON)
        return entry.get("groups", {}).get(self.groups.get(pid, "other"), entry.get("pooled", E.POISSON))

    def make_beta(self, s: str, pid: str) -> Tuple[float, float]:
        return self.make[s].beta(pid, self.lg_make[s].value)

    def shares(self, s: str) -> List[float]:
        v = [0.0] + [self.qshare[s][q].value for q in range(1, 6)]
        tot = sum(v)
        return [x / tot for x in v]

    def pair_means(self, qb: str, rec: str) -> Dict[str, float]:
        return {"tgt": self.pair["tgt"].rate((qb, rec), self.mean("tgt", rec)),
                "yd": self.pair["yd"].rate((qb, rec), self.mean("ryd", rec))}

    def pair_beta(self, qb: str, rec: str) -> Tuple[float, float]:
        a, b = self.make_beta("rec", rec)
        prior = a / (a + b)
        s, w = self.pair["rec"].S.get((qb, rec), 0.0), self.pair["rec"].W.get((qb, rec), 0.0)
        return 20.0 * prior + s, 20.0 * (1 - prior) + max(0.0, w - s)

    def update_team_game(self, team: str, acts: Dict[str, dict], pairs: Dict[Tuple[str, str], dict],
                         elig: Dict[str, Set[str]]) -> None:
        for s in COUNT_STATS:
            ids = elig[ROLE[s]] | {p for p, a in acts.items() if a[s] > 0}
            for pid in ids:
                v = _count(acts[pid][s]) if pid in acts else 0
                self.rate[s].update(pid, v)
                if pid in elig[ROLE[s]]:
                    self.lg[s].update(v)
                    self.lg_grp[s][self.groups.get(pid, "other")].update(v)
        for s, (base, _) in MAKES.items():
            for pid, a in acts.items():
                if a[base] > 0:
                    self.make[s].update(pid, a[s], a[base])
                    self.lg_make[s].update(a[s], a[base])
        for s in QUARTER_STATS:
            for a in acts.values():
                for q in range(1, 6):
                    self.qshare[s][q].update(a[f"q_{s}"][q])
        qb = self.primary_qb.get(team)
        if qb is not None and acts.get(qb, {}).get("att", 0) > 0:
            for rec in elig["receiver"] | {r for (q, r) in pairs if q == qb}:
                pr = pairs.get((qb, rec), {"tgt": 0, "rec": 0, "yd": 0.0})
                self.pair["tgt"].update((qb, rec), pr["tgt"])
                self.pair["yd"].update((qb, rec), _count(pr["yd"]))
                if pr["tgt"] > 0:
                    self.pair["rec"].update((qb, rec), pr["rec"], pr["tgt"])
        roles = {"passer": {p for p, a in acts.items() if a["att"] > 0},
                 "receiver": {p for p, a in acts.items() if a["tgt"] > 0},
                 "rusher": {p for p, a in acts.items() if a["car"] > 0}}
        self.recent[team].append(roles)
        if roles["passer"]:
            self.primary_qb[team] = max(roles["passer"], key=lambda p: acts[p]["att"])


def _walk(games, players, pairs, outs, model: PlayerModel, on_team_game, last_season: int) -> None:
    """Walk game days in order. on_team_game(g, team, elig, model) is called BEFORE the day's results update."""
    for day in _days(games):
        if day[0].season > last_season:
            break
        todo = []
        for g in day:
            for team in (g.home, g.away):
                acts = players.get((g.game_id, team))
                if acts is None:
                    continue
                out = outs.get((g.season, g.week, team), set())
                elig = model.eligible(team, out)
                on_team_game(g, team, elig, model)
                todo.append((team, acts, pairs.get((g.game_id, team), {}), elig))
        for team, acts, prs, elig in todo:
            model.update_team_game(team, acts, prs, elig)


def choose(games, players, pairs, outs, groups: Dict[str, str], choose_seasons, grid=GRID,
           prior: str = "league") -> Tuple[dict, dict, dict]:
    """Revision 2: half-life and k0 by mean squared error, sizes per stat and per position group. Choosing window only."""
    err = {c: defaultdict(float) for c in grid}
    obs = {c: defaultdict(list) for c in grid}
    for c in grid:
        def collect(g, team, elig, m, c=c):
            if g.season not in choose_seasons:
                return
            acts = players[(g.game_id, team)]
            for s_ in COUNT_STATS:
                for pid in elig[ROLE[s_]]:
                    k = _count(acts[pid][s_]) if pid in acts else 0
                    mu = m.mean(s_, pid)
                    err[c][s_] += (mu - k) ** 2
                    obs[c][(s_, groups.get(pid, "other"))].append((mu, k))
                    obs[c][(s_, "pooled")].append((mu, k))
        _walk(games, players, pairs, outs, PlayerModel({s_: c for s_ in COUNT_STATS}, None, groups, prior), collect,
              max(choose_seasons))
    params = {s_: min(grid, key=lambda c: err[c][s_]) for s_ in COUNT_STATS}
    sizes, group_obs = {}, {}
    for s_ in COUNT_STATS:
        rows = obs[params[s_]]
        pooled = E.fit_size(rows[(s_, "pooled")], grid=SIZE_GRID)
        fitted = {}
        group_obs[s_] = {}
        for grp in GROUPS:
            r_ = rows.get((s_, grp), [])
            group_obs[s_][grp] = len(r_)
            if len(r_) >= MIN_OBS_GROUP:
                fitted[grp] = E.fit_size(r_, grid=SIZE_GRID)
        sizes[s_] = {"pooled": pooled, "groups": fitted}
    info = {"mse_per_row": {s_: {f"h{c[0]}_k{c[1]}": err[c][s_] / max(1, len(obs[c][(s_, "pooled")]))
                                 for c in grid} for s_ in COUNT_STATS},
            "group_rows": group_obs}
    return params, sizes, info


def _line(v: float) -> float:
    return math.floor(v) + 0.5


def evaluate(games: Sequence[Game], data: dict, choose_seasons=DEV, score_seasons=EVAL, grid=GRID,
             prior: str = "league") -> dict:
    from .blind import assert_not_sealed
    last = max(score_seasons)
    games = [g for g in games if g.completed and WARMUP <= g.season <= last]
    assert_not_sealed([g.game_id for g in games], "player projections")
    players, pairs = player_actuals(data)
    outs = load_out(range(WARMUP, last + 1))
    groups = player_groups()
    params, sizes, info = choose(games, players, pairs, outs, groups, choose_seasons, grid, prior)
    model = PlayerModel(params, sizes, groups, prior)
    season_avg: Dict[Tuple[int, str, str], List[float]] = defaultdict(lambda: [0.0, 0])
    S: Dict[str, Dict[str, list]] = defaultdict(lambda: {"model": [], "league": [], "season": []})
    calib: Dict[str, list] = defaultdict(lambda: [0.0, 0, 0])

    FIRST = [False]    # True while scoring a player's first game of the season (reported separately)

    def rec(key, dm: E.Dist, mu_league: float, mu_season: float, k: int, line: Optional[float]):
        dl, ds = E.nb(mu_league, E.POISSON), E.nb(mu_season, E.POISSON)
        S[f"{key} log score"]["model"].append(E.log_score(dm, k))
        S[f"{key} log score"]["league"].append(E.log_score(dl, k))
        S[f"{key} log score"]["season"].append(E.log_score(ds, k))
        part = "first game of season" if FIRST[0] else "later games"
        S[f"{key} log score, {part}"]["model"].append(E.log_score(dm, k))
        S[f"{key} log score, {part}"]["league"].append(E.log_score(dl, k))
        S[f"{key} log score, {part}"]["season"].append(E.log_score(ds, k))
        if line is not None:
            y = int(k > line)
            p = dm.prob_over(line)
            S[f"{key} over typical line (Brier)"]["model"].append(E.brier(p, y))
            S[f"{key} over typical line (Brier)"]["league"].append(E.brier(dl.prob_over(line), y))
            S[f"{key} over typical line (Brier)"]["season"].append(E.brier(ds.prob_over(line), y))
            c = calib[key]
            c[0] += p
            c[1] += y
            c[2] += 1

    def score(g, team, elig, m):
        acts = players[(g.game_id, team)]
        scoring = g.season in score_seasons
        get = lambda pid, s: (acts[pid][s] if pid in acts else 0)
        for s in COUNT_STATS + tuple(MAKES):
            role = ROLE[s]
            for pid in elig[role]:
                key = (g.season, pid, s)
                tot, n = season_avg[key]
                FIRST[0] = n == 0
                k = _count(get(pid, s))
                if scoring:
                    lg = m.lg[s].value if s in COUNT_STATS else m.lg[MAKES[s][0]].value * m.lg_make[s].value
                    mu_season = tot / n if n else lg
                    line = _line(mu_season) if n else None
                    if s in COUNT_STATS:
                        dm = E.nb(m.mean(s, pid), m.size(s, pid))
                    else:
                        base = MAKES[s][0]
                        dm = E.makes(E.nb(m.mean(base, pid), m.size(base, pid)), *m.make_beta(s, pid)).makes
                    rec(LABEL[s], dm, lg, mu_season, k, line)
                    if s in QUARTER_STATS:
                        sh = m.shares(s)
                        for q in (1, 2, 3, 4):
                            kq = acts[pid][f"q_{s}"][q] if pid in acts else 0
                            dq = E.period(m.mean(s, pid), m.size(s, pid), sh[q])
                            rec(f"{LABEL[s]}, quarter", dq, lg * sh[q], mu_season * sh[q], kq,
                                _line(mu_season * sh[q]) if n else None)
                season_avg[key][0] += k
                season_avg[key][1] += 1
        qb = m.primary_qb.get(team)
        FIRST[0] = False
        if scoring and qb is not None and get(qb, "att") > 0:
            prs = pairs.get((g.game_id, team), {})
            for r in elig["receiver"]:
                pm = m.pair_means(qb, r)
                pr = prs.get((qb, r), {"tgt": 0, "rec": 0, "yd": 0.0})
                dt = E.nb(pm["tgt"], m.size("tgt", r))
                rec(LABEL["pair_tgt"], dt, m.mean("tgt", r), m.mean("tgt", r), pr["tgt"], None)
                rec(LABEL["pair_rec"], E.makes(dt, *m.pair_beta(qb, r)).makes,
                    m.mean("tgt", r) * m.lg_make["rec"].value, m.mean("tgt", r) * m.lg_make["rec"].value,
                    pr["rec"], None)
                rec(LABEL["pair_yd"], E.nb(pm["yd"], m.size("ryd", r)), m.mean("ryd", r), m.mean("ryd", r),
                    _count(pr["yd"]), None)

    _walk(games, players, pairs, outs, model, score, last)
    res = {"label": "DEVELOPMENT, NOT BLIND. Chosen on 2013-2019, scored on 2020-2025. Lower is better. For pairs "
                    "the 'league' and 'season' references are the receiver's own overall rate (no pair information).",
           "chosen": {s: {"halflife_games": params[s][0], "k0": params[s][1], "pooled": sizes[s]["pooled"],
                          "groups": sizes[s]["groups"]} for s in COUNT_STATS},
           "grid_mse": info, "scores": {}, "calibration_at_typical_line": {}}
    for k, v in S.items():
        res["scores"][k] = {"n": len(v["model"]),
                            "model": sum(v["model"]) / len(v["model"]),
                            "minus_league": paired(v["model"], v["league"]),
                            "minus_season_average": paired(v["model"], v["season"])}
    for k, (p, y, n) in calib.items():
        res["calibration_at_typical_line"][k] = {"predicted": p / n, "observed": y / n, "n": n}
    return res


def forecast_sheet(game_id: str, games: Sequence[Game], data: dict, chosen: dict) -> dict:
    target = next(g for g in games if g.game_id == game_id)
    players, pairs = player_actuals(data)
    from .sources import load_injury_counts
    load_injury_counts([target.season], refresh=True)          # the latest injury report for this season
    outs = load_out(range(WARMUP, target.season + 1))
    params = {s: (v["halflife_games"], v["k0"]) for s, v in chosen.items()}
    model = PlayerModel(params, {s: {"pooled": v["pooled"], "groups": v["groups"]} for s, v in chosen.items()},
                        player_groups())
    past = [g for g in games if g.completed and g.gameday < target.gameday and g.season >= WARMUP]
    _walk(past, players, pairs, outs, model, lambda *a: None, target.season)
    names = data["names"]
    sheet = {"game": game_id, "note": "projected players: recorded the stat in the team's last 3 games, not listed "
                                      "Out or Doubtful"}
    for team in (target.home, target.away):
        elig = model.eligible(team, outs.get((target.season, target.week, team), set()))
        rows = {}
        for s in COUNT_STATS:
            for pid in elig[ROLE[s]]:
                d = E.nb(model.mean(s, pid), model.size(s, pid))
                rows.setdefault(names.get(pid, pid), {})[LABEL[s]] = d.summary([_line(d.mean)])
        for s, (base, _) in MAKES.items():
            for pid in elig[ROLE[s]]:
                mk = E.makes(E.nb(model.mean(base, pid), model.size(base, pid)), *model.make_beta(s, pid))
                rows.setdefault(names.get(pid, pid), {})[LABEL[s]] = mk.summary((), [_line(mk.makes.mean)])
        qb = model.primary_qb.get(team)
        if qb:
            duo = {}
            for r in elig["receiver"]:
                pm = model.pair_means(qb, r)
                dt = E.nb(pm["tgt"], model.size("tgt", r))
                duo[names.get(r, r)] = {"targets": dt.summary([_line(dt.mean)]),
                                        "receptions": E.makes(dt, *model.pair_beta(qb, r)).summary(),
                                        "yards": E.nb(pm["yd"], model.size("ryd", r)).summary()}
            rows[f"pairs with {names.get(qb, qb)}"] = duo
        sheet[team] = rows
    return sheet


def main(argv=None) -> int:
    import argparse
    from . import pbp
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.player_props")
    ap.add_argument("cmd", choices=["evaluate", "forecast", "evaluate-r2", "forecast-r2", "evaluate-r3"])
    ap.add_argument("game_id", nargs="?")
    args = ap.parse_args(argv)
    games = load_games()
    if args.cmd in ("evaluate-r2", "evaluate-r3"):
        rev3 = args.cmd == "evaluate-r3"
        if rev3:
            res = evaluate(games, pbp.load(range(WARMUP, max(SCORE_R3) + 1)), CHOOSE_R2, SCORE_R3, GRID3, "group")
            res["label"] = ("PLAYER PROPS, REVISION 3. Prior = position group average; sizes per group, grid down to 1; "
                            "chosen on 2012-2017, scored on 2020-2025. DEVELOPMENT, not blind.")
            out_path = os.path.join(RESULTS, "nfl_player_props_rev3.json")
        else:
            res = evaluate(games, pbp.load(range(WARMUP, max(SCORE_R2) + 1)), CHOOSE_R2, SCORE_R2)
            res["label"] = ("PLAYER PROPS, REVISION 2. Sizes chosen per position group on 2012-2017 (grid down to 1); "
                            "scored on 2018-2019. DEVELOPMENT, not blind.")
            out_path = os.path.join(RESULTS, "nfl_player_props_rev2.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(res["label"])
        for s_, v in res["chosen"].items():
            edge = [g_ for g_, r_ in v["groups"].items() if r_ <= 1] + (["pooled"] if v["pooled"] <= 1 else [])
            print(f"  {LABEL[s_]:<16} half-life {v['halflife_games']}, k0 {v['k0']}, pooled size {v['pooled']:g}, "
                  f"groups {{{', '.join(f'{g_} {r_:g}' for g_, r_ in v['groups'].items())}}}"
                  + (f"   WARNING at grid edge: {edge}" if edge else ""))
        for k, v in res["scores"].items():
            a, b = v["minus_league"], v["minus_season_average"]
            print(f"  {k:<44} n={v['n']:>6}  minus league {a['model_minus_baseline']:+.4f} "
                  f"[{a['ci95'][0]:+.4f},{a['ci95'][1]:+.4f}]  minus season avg {b['model_minus_baseline']:+.4f} "
                  f"[{b['ci95'][0]:+.4f},{b['ci95'][1]:+.4f}]")
        for k, v in res["calibration_at_typical_line"].items():
            print(f"  calibration {k:<30} predicted over {v['predicted']:.3f}  observed {v['observed']:.3f}")
        print("wrote", out_path)
        return 0
    if args.cmd == "forecast-r2":
        with open(os.path.join(RESULTS, "nfl_player_props_rev2.json"), encoding="utf-8") as fh:
            saved = json.load(fh)
        target = next(g for g in games if g.game_id == args.game_id)
        print(json.dumps(forecast_sheet(args.game_id, load_games(refresh=True),
                                        pbp.load_through(target.season, WARMUP), saved["chosen"]), indent=1))
        return 0
    raise SystemExit("revision 1 is retired; use evaluate-r2 and forecast-r2")


if __name__ == "__main__":
    raise SystemExit(main())
