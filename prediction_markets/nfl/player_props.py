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
    def __init__(self, params: Dict[str, Tuple[float, float]], sizes: Optional[Dict[str, float]] = None):
        self.params = params
        self.rate = {s: E.DecayedRate(*params[s]) for s in COUNT_STATS}
        self.pair = {s: E.DecayedRate(*params[b]) for s, b in (("tgt", "tgt"), ("rec", "tgt"), ("yd", "ryd"))}
        self.make = {s: E.DecayedRate(16, k0) for s, (_, k0) in MAKES.items()}
        self.lg = {s: E.LeagueRate(start=1.0) for s in COUNT_STATS}
        self.lg_make = {"cmp": E.LeagueRate(start=0.62), "rec": E.LeagueRate(start=0.65)}
        self.qshare = {s: [E.LeagueRate(start=0.25) for _ in range(6)] for s in QUARTER_STATS}
        self.sizes = sizes or {}
        self.recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=3))   # team -> last 3 games' role sets
        self.primary_qb: Dict[str, str] = {}

    def eligible(self, team: str, out: Set[str]) -> Dict[str, Set[str]]:
        roles: Dict[str, Set[str]] = {"passer": set(), "receiver": set(), "rusher": set()}
        for game_roles in self.recent[team]:
            for role, ids in game_roles.items():
                roles[role] |= ids
        return {r: ids - out for r, ids in roles.items()}

    def mean(self, s: str, pid: str) -> float:
        return self.rate[s].rate(pid, self.lg[s].value)

    def size(self, s: str) -> float:
        return self.sizes.get(s, E.POISSON)

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


def choose(games, players, pairs, outs) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, float], dict]:
    err = {c: defaultdict(float) for c in GRID}
    obs = {c: defaultdict(list) for c in GRID}
    for c in GRID:
        def collect(g, team, elig, m, c=c):
            if g.season not in DEV:
                return
            acts = players[(g.game_id, team)]
            for s in COUNT_STATS:
                for pid in elig[ROLE[s]]:
                    k = _count(acts[pid][s]) if pid in acts else 0
                    mu = m.mean(s, pid)
                    err[c][s] += (mu - k) ** 2
                    obs[c][s].append((mu, k))
        _walk(games, players, pairs, outs, PlayerModel({s: c for s in COUNT_STATS}), collect, max(DEV))
    params = {s: min(GRID, key=lambda c: err[c][s]) for s in COUNT_STATS}
    sizes = {s: E.fit_size(obs[params[s]][s], grid=(0.5, 1, 1.5, 2, 3, 5, 8, 13, 25, 50, E.POISSON))
             for s in COUNT_STATS}
    info = {s: {f"h{c[0]}_k{c[1]}": err[c][s] / max(1, len(obs[c][s])) for c in GRID} for s in COUNT_STATS}
    return params, sizes, info


def _line(v: float) -> float:
    return math.floor(v) + 0.5


def evaluate(games: Sequence[Game], data: dict) -> dict:
    from .blind import assert_not_sealed
    games = [g for g in games if g.completed and WARMUP <= g.season <= max(EVAL)]
    assert_not_sealed([g.game_id for g in games], "player projections")
    players, pairs = player_actuals(data)
    outs = load_out(range(WARMUP, max(EVAL) + 1))
    params, sizes, info = choose(games, players, pairs, outs)
    model = PlayerModel(params, sizes)
    season_avg: Dict[Tuple[int, str, str], List[float]] = defaultdict(lambda: [0.0, 0])
    S: Dict[str, Dict[str, list]] = defaultdict(lambda: {"model": [], "league": [], "season": []})
    calib: Dict[str, list] = defaultdict(lambda: [0.0, 0, 0])

    def rec(key, dm: E.Dist, mu_league: float, mu_season: float, k: int, line: Optional[float]):
        dl, ds = E.nb(mu_league, E.POISSON), E.nb(mu_season, E.POISSON)
        S[f"{key} log score"]["model"].append(E.log_score(dm, k))
        S[f"{key} log score"]["league"].append(E.log_score(dl, k))
        S[f"{key} log score"]["season"].append(E.log_score(ds, k))
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
        scoring = g.season in EVAL
        get = lambda pid, s: (acts[pid][s] if pid in acts else 0)
        for s in COUNT_STATS + tuple(MAKES):
            role = ROLE[s]
            for pid in elig[role]:
                key = (g.season, pid, s)
                tot, n = season_avg[key]
                k = _count(get(pid, s))
                if scoring:
                    lg = m.lg[s].value if s in COUNT_STATS else m.lg[MAKES[s][0]].value * m.lg_make[s].value
                    mu_season = tot / n if n else lg
                    line = _line(mu_season) if n else None
                    if s in COUNT_STATS:
                        dm = E.nb(m.mean(s, pid), m.size(s))
                    else:
                        base = MAKES[s][0]
                        dm = E.makes(E.nb(m.mean(base, pid), m.size(base)), *m.make_beta(s, pid)).makes
                    rec(LABEL[s], dm, lg, mu_season, k, line)
                    if s in QUARTER_STATS:
                        sh = m.shares(s)
                        for q in (1, 2, 3, 4):
                            kq = acts[pid][f"q_{s}"][q] if pid in acts else 0
                            dq = E.period(m.mean(s, pid), m.size(s), sh[q])
                            rec(f"{LABEL[s]}, quarter", dq, lg * sh[q], mu_season * sh[q], kq,
                                _line(mu_season * sh[q]) if n else None)
                season_avg[key][0] += k
                season_avg[key][1] += 1
        qb = m.primary_qb.get(team)
        if scoring and qb is not None and get(qb, "att") > 0:
            prs = pairs.get((g.game_id, team), {})
            for r in elig["receiver"]:
                pm = m.pair_means(qb, r)
                pr = prs.get((qb, r), {"tgt": 0, "rec": 0, "yd": 0.0})
                dt = E.nb(pm["tgt"], m.size("tgt"))
                rec(LABEL["pair_tgt"], dt, m.mean("tgt", r), m.mean("tgt", r), pr["tgt"], None)
                rec(LABEL["pair_rec"], E.makes(dt, *m.pair_beta(qb, r)).makes,
                    m.mean("tgt", r) * m.lg_make["rec"].value, m.mean("tgt", r) * m.lg_make["rec"].value,
                    pr["rec"], None)
                rec(LABEL["pair_yd"], E.nb(pm["yd"], m.size("ryd")), m.mean("ryd", r), m.mean("ryd", r),
                    _count(pr["yd"]), None)

    _walk(games, players, pairs, outs, model, score, max(EVAL))
    res = {"label": "DEVELOPMENT, NOT BLIND. Chosen on 2013-2019, scored on 2020-2025. Lower is better. For pairs "
                    "the 'league' and 'season' references are the receiver's own overall rate (no pair information).",
           "chosen": {s: {"halflife_games": params[s][0], "k0": params[s][1], "size": sizes[s]} for s in COUNT_STATS},
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
    model = PlayerModel(params, {s: v["size"] for s, v in chosen.items()})
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
                d = E.nb(model.mean(s, pid), model.size(s))
                rows.setdefault(names.get(pid, pid), {})[LABEL[s]] = d.summary([_line(d.mean)])
        for s, (base, _) in MAKES.items():
            for pid in elig[ROLE[s]]:
                mk = E.makes(E.nb(model.mean(base, pid), model.size(base)), *model.make_beta(s, pid))
                rows.setdefault(names.get(pid, pid), {})[LABEL[s]] = mk.summary((), [_line(mk.makes.mean)])
        qb = model.primary_qb.get(team)
        if qb:
            duo = {}
            for r in elig["receiver"]:
                pm = model.pair_means(qb, r)
                dt = E.nb(pm["tgt"], model.size("tgt"))
                duo[names.get(r, r)] = {"targets": dt.summary([_line(dt.mean)]),
                                        "receptions": E.makes(dt, *model.pair_beta(qb, r)).summary(),
                                        "yards": E.nb(pm["yd"], model.size("ryd")).summary()}
            rows[f"pairs with {names.get(qb, qb)}"] = duo
        sheet[team] = rows
    return sheet


def main(argv=None) -> int:
    import argparse
    from . import pbp
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.player_props")
    ap.add_argument("cmd", choices=["evaluate", "forecast"])
    ap.add_argument("game_id", nargs="?")
    args = ap.parse_args(argv)
    games = load_games()
    out_path = os.path.join(RESULTS, "nfl_player_props_dev.json")
    if args.cmd == "evaluate":
        res = evaluate(games, pbp.load(range(WARMUP, max(EVAL) + 1)))
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(res["label"])
        for s, v in res["chosen"].items():
            print(f"  {LABEL[s]:<16} half-life {v['halflife_games']}, k0 {v['k0']}, size {v['size']:g}")
        for k, v in res["scores"].items():
            a, b = v["minus_league"], v["minus_season_average"]
            print(f"  {k:<44} n={v['n']:>6}  minus league {a['model_minus_baseline']:+.4f} "
                  f"[{a['ci95'][0]:+.4f},{a['ci95'][1]:+.4f}]  minus season avg {b['model_minus_baseline']:+.4f} "
                  f"[{b['ci95'][0]:+.4f},{b['ci95'][1]:+.4f}]")
        for k, v in res["calibration_at_typical_line"].items():
            print(f"  calibration {k:<30} predicted over {v['predicted']:.3f}  observed {v['observed']:.3f}")
        print("wrote", out_path)
        return 0
    with open(out_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    games = load_games(refresh=True)
    target = next(g for g in games if g.game_id == args.game_id)
    print(json.dumps(forecast_sheet(args.game_id, games, pbp.load_through(target.season, WARMUP),
                                    saved["chosen"]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
