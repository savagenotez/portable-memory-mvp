"""Team projections: points, touchdowns and field goals, by game, half and quarter, with over/under at any line.

PRE-REGISTERED (written before any projection was scored):

  Targets per team-game: touchdowns, field-goal attempts, field goals made and make percentage, and points, for the
  game, each half and each quarter. Per game: total points and margin (home minus away), "by how much".

  Model (all learnt walk-forward; a game day only sees earlier days):
    TD mean    league rate for home or away teams x (team's TD rate / league) x (opponent's TD-allowed rate / league).
               Team rates are decayed and shrunk toward the league (stats/engine.DecayedRate).
    FGA mean   the same, for field-goal attempts.
    FG make    the team's current kicker, shrunk toward the league (20 attempts of prior weight), then shifted for
               wind and cold (outdoors) by the per-kick model below, fitted on dev seasons.
    Per TD     6 points plus 0, 1 or 2, at the league's walk-forward extra-point and two-point frequencies.
    Points     touchdowns (compound) plus 3 x field goals made. Safeties are not modelled (about 0.1 points a game).
    Periods    league walk-forward share of TDs and FGAs in each quarter; the count keeps the same size r.
  Grid, chosen on dev seasons 2013-2019 by mean squared error of the game TD and FGA means (2012 is warm-up):
    half-life {4, 8, 16} games, prior weight k0 {2, 4, 8}. Size r for TD and FGA by likelihood on the same seasons.
  Per-kick model (when the distance is known): logistic on distance, distance squared, wind and cold (outdoors),
    fitted on 2012-2019 kicks, plus a kicker effect (shrunk residual, 20 kicks of prior weight).

  Scored on 2020-2025. This is DEVELOPMENT, not blind: those seasons have been looked at for other models.
    Game total and margin against the closing total and spread (published in the nflverse games file).
    Team, half and quarter points, TDs and field goals against a league-only baseline (the same model with no team
    information), by log score and by Brier at fixed lines, with paired 95% intervals. 80% interval coverage.

    python3 -m prediction_markets.nfl.team_props evaluate
    python3 -m prediction_markets.nfl.team_props forecast 2026_13_KC_DAL      # an upcoming game
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from ..stats import engine as E
from .data import CACHE_PATH, Game, load_games
from .features import fit_logistic, sigmoid

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
WARMUP, DEV, EVAL = 2012, range(2013, 2020), range(2020, 2026)
GRID = [(h, k) for h in (4, 8, 16) for k in (2, 4, 8)]
KICKER_K0 = 20.0
DRIVE_K0 = 10.0                                  # prior weight, in scoring drives, for a team's touchdown share
STATS = ("td", "fga", "sd")
QUARTERS = (1, 2, 3, 4, 5)                      # 5 is overtime
LINES = {"points": (17.5, 20.5, 23.5, 27.5), "half": (3.5, 7.5, 10.5, 13.5, 17.5),
         "quarter": (0.5, 3.5, 6.5, 7.5, 10.5), "td": (1.5, 2.5, 3.5), "fga": (1.5, 2.5), "fgm": (1.5,)}


# ---- data -------------------------------------------------------------------------------------------------------

def load_lines(path: str = CACHE_PATH) -> Dict[str, dict]:
    out = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            f = lambda k: float(r[k]) if r.get(k) not in (None, "", "NA") else None
            out[r["game_id"]] = {"total_line": f("total_line"), "spread_line": f("spread_line"),
                                 "temp": f("temp"), "wind": f("wind"), "roof": r.get("roof") or ""}
    return out


def weather_x(w: Optional[dict]) -> Tuple[float, float]:
    """(wind in tens of mph, cold) outdoors; both 0 under a roof or when unknown."""
    if not w or w.get("roof") not in ("outdoors", "open"):
        return 0.0, 0.0
    wind = (w.get("wind") or 0.0) / 10.0
    cold = 1.0 if (w.get("temp") is not None and w["temp"] < 40) else 0.0
    return wind, cold


def team_actuals(data: dict, boundaries: Sequence[dict]) -> Dict[Tuple[str, str], dict]:
    """(game, team) -> counts by quarter and points by quarter."""
    out: Dict[Tuple[str, str], dict] = defaultdict(lambda: {"td": [0] * 6, "fga": [0] * 6, "fgm": [0] * 6, "xp": 0,
                                                            "two": 0, "kicker": None, "kicks": [], "points": None})
    for gid, team, q, *_ in data["td"]:
        out[(gid, team)]["td"][q] += 1
    for gid, team, q, dist, made, kid in data["fg"]:
        a = out[(gid, team)]
        a["fga"][q] += 1
        a["fgm"][q] += made
        a["kicks"].append((dist, made, kid))
    for gid, team, q, good in data["xp"]:
        out[(gid, team)]["xp"] += good
    for gid, team, q, ok in data["two"]:
        out[(gid, team)]["two"] += ok
    for a in out.values():
        a["sd"] = [t + f for t, f in zip(a["td"], a["fgm"])]          # scoring drives: touchdowns + field goals made
        ks = [k for _, _, k in a["kicks"] if k]
        a["kicker"] = max(set(ks), key=ks.count) if ks else None
    for b in boundaries:
        if not all(b.get(k) for k in ("q1", "q2", "q3", "q4", "final")):
            continue
        for side, team, key in (("home", b["home"], "hs"), ("away", b["away"], "as")):
            cum = [0, b["q1"][key], b["q2"][key], b["q3"][key], b["q4"][key], b["final"][key]]
            out[(b["game_id"], team)]["points"] = [None] + [int(cum[i] - cum[i - 1]) for i in range(1, 6)]
    return out


# ---- per-kick model ----------------------------------------------------------------------------------------------

def kick_x(dist: float, wind: float, cold: float, weather: bool = True) -> List[float]:
    d = dist / 10.0
    return [1.0, d, d * d, wind, cold] if weather else [1.0, d, d * d]


def fit_kick_model(games: Sequence[Game], acts, lines) -> dict:
    X, Xd, y = [], [], []
    for g in games:
        if g.season > max(DEV):
            continue
        wind, cold = weather_x(lines.get(g.game_id))
        for team in (g.home, g.away):
            for dist, made, _ in acts.get((g.game_id, team), {}).get("kicks", []):
                X.append(kick_x(dist, wind, cold))
                Xd.append(kick_x(dist, 0, 0, weather=False))
                y.append(made)
    return {"weather": fit_logistic(X, y, 1e-3), "distance_only": fit_logistic(Xd, y, 1e-3), "n_dev_kicks": len(y)}


def _logit(p: float) -> float:
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


# ---- the model ---------------------------------------------------------------------------------------------------

class TeamModel:
    def __init__(self, halflife: float, k0: float, sizes: Optional[dict] = None, kick: Optional[dict] = None,
                 drives: bool = False):
        self.off = {s: E.DecayedRate(halflife, k0) for s in STATS}
        self.dfn = {s: E.DecayedRate(halflife, k0) for s in STATS}
        self.lg = {s: E.LeagueRate(start=st) for s, st in (("td", 2.5), ("fga", 1.9), ("sd", 4.1))}
        self.side = {(s, side): E.LeagueRate(start=self.lg[s].start) for s in STATS for side in ("home", "away")}
        self.qcount = {s: [E.LeagueRate(start=0.2) for _ in range(6)] for s in STATS}
        self.drives = drives
        self.td_share = E.DecayedRate(halflife, DRIVE_K0)       # team's touchdowns per scoring drive
        self.lg_td_share = E.LeagueRate(start=0.6)
        self.kicker = E.DecayedRate(16, KICKER_K0)
        self.lg_make = E.LeagueRate(start=0.84)
        self.team_kicker: Dict[str, str] = {}
        self.bonus = {"xp": E.LeagueRate(start=0.92), "two": E.LeagueRate(start=0.03)}
        self.sizes = {"td": E.POISSON, "fga": E.POISSON, "sd": E.POISSON, **(sizes or {})}
        self.kick = kick
        self.resid = E.DecayedRate(40, KICKER_K0)       # kicker's make rate above the per-kick model

    # shares of a game's count in each quarter (and overtime)
    def shares(self, s: str) -> List[float]:
        v = [0.0] + [self.qcount[s][q].value for q in QUARTERS]
        tot = sum(v)
        return [x / tot for x in v]

    def means(self, home: str, away: str, league_only: bool = False) -> Dict[Tuple[str, str], float]:
        out = {}
        for s in STATS:
            L = self.lg[s].value
            for side, t, o in (("home", home, away), ("away", away, home)):
                base = self.side[(s, side)].value
                if league_only:
                    out[(s, side)] = base
                else:
                    out[(s, side)] = base * (self.off[s].rate(t, L) / L) * (self.dfn[s].rate(o, L) / L)
        return out

    def make_beta(self, team: str, wind: float, cold: float, league_only: bool = False) -> Tuple[float, float]:
        prior = self.lg_make.value
        kid = None if league_only else self.team_kicker.get(team)
        a, b = self.kicker.beta(kid, prior) if kid else (KICKER_K0 * prior, KICKER_K0 * (1 - prior))
        if self.kick is not None:
            w = self.kick["weather"]
            shift = w[3] * wind + w[4] * cold
            n = a + b
            p = sigmoid(_logit(a / n) + shift)
            a, b = p * n, (1 - p) * n
        return a, b

    def per_td(self) -> E.Dist:
        xp, two = self.bonus["xp"].value, self.bonus["two"].value
        return E.Dist([max(0.0, 1 - xp - two), xp, two], 6)

    def per_drive(self, team: str, league_only: bool = False) -> E.Dist:
        """Points from one scoring drive: a field goal (3), or a touchdown (6, 7 or 8)."""
        L = self.lg_td_share.value
        t = L if league_only else self.td_share.rate(team, L)
        b = self.per_td().pmf
        return E.Dist([1 - t, 0.0, 0.0, t * b[0], t * b[1], t * b[2]], 3)

    def forecast(self, home: str, away: str, weather: Optional[dict] = None, league_only: bool = False) -> dict:
        mu = self.means(home, away, league_only)
        wind, cold = weather_x(weather)
        sh = {s: self.shares(s) for s in STATS}
        bonus = self.per_td()
        out: dict = {}
        periods = {"game": list(QUARTERS), "H1": [1, 2], "H2": [3, 4], "Q1": [1], "Q2": [2], "Q3": [3], "Q4": [4]}
        for side, team in (("home", home), ("away", away)):
            a, b = self.make_beta(team, wind, cold, league_only)
            drive = self.per_drive(team, league_only) if self.drives else None
            for name, qs in periods.items():
                td = E.period(mu[("td", side)], self.sizes["td"], sum(sh["td"][q] for q in qs))
                fga = E.period(mu[("fga", side)], self.sizes["fga"], sum(sh["fga"][q] for q in qs))
                fg = E.makes(fga, a, b)
                if self.drives:
                    sd = E.period(mu[("sd", side)], self.sizes["sd"], sum(sh["sd"][q] for q in qs))
                    pts = E.compound(sd, drive)
                else:
                    pts = E.add(E.compound(td, bonus), E.scale(fg.makes, 3))
                out[(side, name)] = {"td": td, "fg": fg, "points": pts}
        out["total"] = E.add(out[("home", "game")]["points"], out[("away", "game")]["points"])
        out["margin"] = E.subtract(out[("home", "game")]["points"], out[("away", "game")]["points"])
        return out

    def kick_prob(self, dist: float, kicker: Optional[str], wind: float, cold: float, use_weather=True,
                  use_kicker=True) -> float:
        w = self.kick["weather"] if use_weather else self.kick["distance_only"]
        p = sigmoid(sum(a * b for a, b in zip(w, kick_x(dist, wind, cold, use_weather))))
        if use_kicker and kicker and kicker in self.resid.W:
            p = min(0.999, max(0.01, p + self.resid.rate(kicker, 0.0)))
        return p

    def update(self, g: Game, acts: dict, weather: Optional[dict]) -> None:
        wind, cold = weather_x(weather)
        rows = []
        for side, team, opp in (("home", g.home, g.away), ("away", g.away, g.home)):
            a = acts.get((g.game_id, team))
            if a is None:
                return                                   # no play-by-play for this game: skip it entirely
            rows.append((side, team, opp, a))
        for side, team, opp, a in rows:
            for s in STATS:
                n = sum(a[s][1:])
                self.off[s].update(team, n)
                self.dfn[s].update(opp, n)
                self.lg[s].update(n)
                self.side[(s, side)].update(n)
                for q in QUARTERS:
                    self.qcount[s][q].update(a[s][q])
            tds = sum(a["td"][1:])
            sds = sum(a["sd"][1:])
            if sds:
                self.td_share.update(team, tds, sds)
                self.lg_td_share.update(tds, sds)
            self.bonus["xp"].update(a["xp"], tds)
            self.bonus["two"].update(a["two"], tds)
            fga, fgm = sum(a["fga"][1:]), sum(a["fgm"][1:])
            self.lg_make.update(fgm, fga)
            if a["kicker"]:
                self.team_kicker[team] = a["kicker"]
            for dist, made, kid in a["kicks"]:
                if kid:
                    self.kicker.update(kid, made, 1.0)
                    if self.kick is not None:
                        p = self.kick_prob(dist, None, wind, cold, use_kicker=False)
                        self.resid.update(kid, made - p, 1.0)


def _days(games: Sequence[Game]):
    by: Dict[str, List[Game]] = defaultdict(list)
    for g in games:
        by[g.gameday].append(g)
    for d in sorted(by):
        yield by[d]


def choose_grid(games, acts, lines) -> Tuple[Tuple[float, float], dict, Dict[str, list]]:
    """Dev-only choice of half-life and k0 (mean squared error of the game TD and FGA means), then size r."""
    err = {c: 0.0 for c in GRID}
    pairs = {c: {"td": [], "fga": [], "sd": []} for c in GRID}
    for c in GRID:
        m = TeamModel(*c)
        for day in _days(games):
            if day[0].season > max(DEV):
                break
            for g in day:
                if g.season in DEV and (g.game_id, g.home) in acts and (g.game_id, g.away) in acts:
                    mu = m.means(g.home, g.away)
                    for s in STATS:
                        for side, t in (("home", g.home), ("away", g.away)):
                            k = sum(acts[(g.game_id, t)][s][1:])
                            if s != "sd":                         # the grid is chosen on TD and FGA only
                                err[c] += (mu[(s, side)] - k) ** 2
                            pairs[c][s].append((mu[(s, side)], k))
            for g in day:
                m.update(g, acts, lines.get(g.game_id))
    best = min(GRID, key=lambda c: err[c])
    sizes = {s: E.fit_size(pairs[best][s]) for s in STATS}
    return best, sizes, {"mse": {f"h{c[0]}_k{c[1]}": err[c] for c in GRID}}


def paired(a: List[float], b: List[float], n: int = 2000, seed: int = 11) -> dict:
    d = [x - y for x, y in zip(a, b)]
    if not d:
        return {"n": 0}
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return {"model_minus_baseline": sum(d) / len(d), "ci95": [boots[int(0.025 * n)], boots[int(0.975 * n) - 1]],
            "n": len(d), "model_better": boots[int(0.975 * n) - 1] < 0}


def evaluate(games: Sequence[Game], data: dict, boundaries, lines) -> dict:
    from .blind import assert_not_sealed
    games = [g for g in games if g.completed and WARMUP <= g.season <= max(EVAL)]
    assert_not_sealed([g.game_id for g in games], "team projections")
    acts = team_actuals(data, boundaries)
    kick = fit_kick_model(games, acts, lines)
    (h, k0), sizes, grid_info = choose_grid(games, acts, lines)
    m = TeamModel(h, k0, sizes, kick)
    S: Dict[str, Dict[str, list]] = defaultdict(lambda: {"model": [], "base": []})   # paired score lists
    calib: Dict[str, list] = defaultdict(lambda: [0.0, 0, 0])    # sum of predicted P(over), observed overs, n
    market = {"total": {"model": [], "coin": [], "mae_model": [], "mae_line": []},
              "margin": {"model": [], "coin": [], "mae_model": [], "mae_line": []}}
    kicks = {"distance_only": [], "weather": [], "weather_kicker": []}

    def score(key: str, dm: E.Dist, db: E.Dist, k: int, lines_: Sequence[float]):
        S[f"{key} log score"]["model"].append(E.log_score(dm, k))
        S[f"{key} log score"]["base"].append(E.log_score(db, k))
        for line in lines_:
            y = int(k > line)
            p = dm.prob_over(line)
            S[f"{key} over {line} (Brier)"]["model"].append(E.brier(p, y))
            S[f"{key} over {line} (Brier)"]["base"].append(E.brier(db.prob_over(line), y))
            c = calib[f"{key} over {line}"]
            c[0] += p
            c[1] += y
            c[2] += 1

    for day in _days(games):
        for g in day:
            a_h, a_a = acts.get((g.game_id, g.home)), acts.get((g.game_id, g.away))
            if g.season not in EVAL or a_h is None or a_a is None or a_h["points"] is None or a_a["points"] is None:
                continue
            w = lines.get(g.game_id)
            fm = m.forecast(g.home, g.away, w)
            fb = m.forecast(g.home, g.away, w, league_only=True)
            for side, a in (("home", a_h), ("away", a_a)):
                pts = a["points"]
                score("team points, game", fm[(side, "game")]["points"], fb[(side, "game")]["points"],
                      sum(pts[1:]), LINES["points"])
                for hname, qs in (("H1", (1, 2)), ("H2", (3, 4))):
                    score("team points, half", fm[(side, hname)]["points"], fb[(side, hname)]["points"],
                          sum(pts[q] for q in qs), LINES["half"])
                for q in (1, 2, 3, 4):
                    score("team points, quarter", fm[(side, f"Q{q}")]["points"], fb[(side, f"Q{q}")]["points"],
                          pts[q], LINES["quarter"])
                score("touchdowns, game", fm[(side, "game")]["td"], fb[(side, "game")]["td"], sum(a["td"][1:]),
                      LINES["td"])
                score("field-goal attempts, game", fm[(side, "game")]["fg"].attempts,
                      fb[(side, "game")]["fg"].attempts, sum(a["fga"][1:]), LINES["fga"])
                score("field goals made, game", fm[(side, "game")]["fg"].makes, fb[(side, "game")]["fg"].makes,
                      sum(a["fgm"][1:]), LINES["fgm"])
                for q in (1, 2, 3, 4):
                    score("field-goal attempts, quarter", fm[(side, f"Q{q}")]["fg"].attempts,
                          fb[(side, f"Q{q}")]["fg"].attempts, a["fga"][q], (0.5,))
            total = g.home_score + g.away_score
            margin = g.home_score - g.away_score
            score("game total", fm["total"], fb["total"], total, ())
            score("game margin", fm["margin"], fb["margin"], margin, ())
            if w and w.get("total_line") is not None and total != w["total_line"]:
                market["total"]["model"].append(E.brier(fm["total"].over_no_push(w["total_line"]),
                                                        int(total > w["total_line"])))
                market["total"]["coin"].append(0.25)
                market["total"]["mae_model"].append(abs(fm["total"].mean - total))
                market["total"]["mae_line"].append(abs(w["total_line"] - total))
            if w and w.get("spread_line") is not None and margin != w["spread_line"]:
                market["margin"]["model"].append(E.brier(fm["margin"].over_no_push(w["spread_line"]),
                                                         int(margin > w["spread_line"])))
                market["margin"]["coin"].append(0.25)
                market["margin"]["mae_model"].append(abs(fm["margin"].mean - margin))
                market["margin"]["mae_line"].append(abs(w["spread_line"] - margin))
            wind, cold = weather_x(w)
            for a in (a_h, a_a):
                for dist, made, kid in a["kicks"]:
                    kicks["distance_only"].append(E.brier(m.kick_prob(dist, kid, 0, 0, False, False), made))
                    kicks["weather"].append(E.brier(m.kick_prob(dist, kid, wind, cold, True, False), made))
                    kicks["weather_kicker"].append(E.brier(m.kick_prob(dist, kid, wind, cold, True, True), made))
        for g in day:
            m.update(g, acts, lines.get(g.game_id))

    res = {"label": "DEVELOPMENT, NOT BLIND. Chosen on 2013-2019, scored on 2020-2025, seasons already looked at "
                    "for other models. Lower is better for every score.",
           "chosen": {"halflife_games": h, "k0": k0, "size_td": sizes["td"], "size_fga": sizes["fga"],
                      "size_sd": sizes["sd"]},
           "grid": grid_info, "kick_model": kick,
           "vs_league_only_baseline": {k: paired(v["model"], v["base"]) for k, v in S.items()},
           "calibration_at_lines": {k: {"predicted": v[0] / v[2], "observed": v[1] / v[2], "n": v[2]}
                                    for k, v in calib.items()},
           "vs_closing_lines": {}, "per_kick_brier": {}}
    for key, v in market.items():
        n = len(v["model"])
        res["vs_closing_lines"][key] = {
            "n": n, "brier_model_over_line": sum(v["model"]) / n, "brier_line_as_coin_flip": 0.25,
            "model_minus_line": paired(v["model"], v["coin"]),
            "mae_model_mean": sum(v["mae_model"]) / n, "mae_closing_line": sum(v["mae_line"]) / n,
            "mae_model_minus_line": paired(v["mae_model"], v["mae_line"])}
    base = kicks["distance_only"]
    for k, v in kicks.items():
        res["per_kick_brier"][k] = {"brier": sum(v) / len(v), "n": len(v),
                                    "minus_distance_only": paired(v, base) if k != "distance_only" else None}
    return res


DRIVES_RULE = ("Points from scoring drives (v2) against touchdowns and field goals counted separately (v1). Written "
               "before either stage was run. Stage 1, dev seasons 2013-2019: v2 goes forward only if its quarter-"
               "points log score is better than v1 with the 95% interval below zero. Stage 2, run once, on the 2026 "
               "games already played (never used for any projection): v2 replaces v1 for points only if the same test "
               "passes there. The calibration gap for 'team scores in the quarter' is reported at both stages.")


def compare_drives(games: Sequence[Game], data: dict, boundaries, lines, chosen: dict, kick: dict,
                   seasons: Sequence[int]) -> dict:
    """v1 and v2 walked forward together from 2012; scored only on `seasons`."""
    from .blind import assert_not_sealed
    games = [g for g in games if g.completed and g.season >= WARMUP and g.season <= max(seasons)]
    assert_not_sealed([g.game_id for g in games], "points-model comparison")
    acts = team_actuals(data, boundaries)
    sizes = {"td": chosen["size_td"], "fga": chosen["size_fga"], "sd": chosen["size_sd"]}
    models = {v: TeamModel(chosen["halflife_games"], chosen["k0"], sizes, kick, drives=(v == "v2"))
              for v in ("v1", "v2")}
    ls: Dict[str, Dict[str, list]] = defaultdict(lambda: {"v1": [], "v2": []})
    cal: Dict[str, Dict[str, list]] = defaultdict(lambda: {"v1": [0.0, 0, 0], "v2": [0.0, 0, 0]})
    for day in _days(games):
        for g in day:
            a_h, a_a = acts.get((g.game_id, g.home)), acts.get((g.game_id, g.away))
            if g.season not in seasons or a_h is None or a_a is None or a_h["points"] is None \
                    or a_a["points"] is None:
                continue
            w = lines.get(g.game_id)
            for v, m in models.items():
                f = m.forecast(g.home, g.away, w)
                for side, a in (("home", a_h), ("away", a_a)):
                    pts = a["points"]
                    items = [("game", f[(side, "game")]["points"], sum(pts[1:]), LINES["points"])]
                    items += [("half", f[(side, h)]["points"], sum(pts[q] for q in qs), LINES["half"])
                              for h, qs in (("H1", (1, 2)), ("H2", (3, 4)))]
                    items += [("quarter", f[(side, f"Q{q}")]["points"], pts[q], LINES["quarter"]) for q in (1, 2, 3, 4)]
                    for level, d, k, lines_ in items:
                        ls[f"team points, {level}"][v].append(E.log_score(d, k))
                        for line in lines_:
                            c = cal[f"team points, {level} over {line}"][v]
                            c[0] += d.prob_over(line)
                            c[1] += int(k > line)
                            c[2] += 1
                total = g.home_score + g.away_score
                ls["game total"][v].append(E.log_score(f["total"], total))
                ls["game margin"][v].append(E.log_score(f["margin"], g.home_score - g.away_score))
        for g in day:
            for m in models.values():
                m.update(g, acts, lines.get(g.game_id))
    out = {"rule": DRIVES_RULE, "seasons": [min(seasons), max(seasons)], "log_score": {}, "calibration": {}}
    for k, v in ls.items():
        out["log_score"][k] = {"v1": sum(v["v1"]) / len(v["v1"]), "v2": sum(v["v2"]) / len(v["v2"]),
                               "v2_minus_v1": paired(v["v2"], v["v1"])}
    for k, v in cal.items():
        out["calibration"][k] = {name: {"predicted": c[0] / c[2], "observed": c[1] / c[2], "n": c[2]}
                                 for name, c in v.items()}
    q = out["log_score"]["team points, quarter"]["v2_minus_v1"]
    out["passes"] = bool(q["ci95"][1] < 0)
    return out


def forecast_sheet(game_id: str, games: Sequence[Game], data: dict, boundaries, lines, chosen: dict,
                   kick: dict) -> dict:
    """Projection for one game, using every completed game before its day."""
    target = next(g for g in games if g.game_id == game_id)
    acts = team_actuals(data, boundaries)
    sizes = {"td": chosen["size_td"], "fga": chosen["size_fga"], "sd": chosen.get("size_sd", E.POISSON)}
    m = TeamModel(chosen["halflife_games"], chosen["k0"], sizes, kick, drives=chosen.get("points_model") == "v2")
    for day in _days([g for g in games if g.completed and g.gameday < target.gameday and g.season >= WARMUP]):
        for g in day:
            m.update(g, acts, lines.get(g.game_id))
    w = lines.get(game_id, {})
    f = m.forecast(target.home, target.away, w)
    sheet = {"game": game_id, "home": target.home, "away": target.away,
             "closing_total": w.get("total_line"), "closing_spread_home": w.get("spread_line"),
             "total_points": f["total"].summary([w["total_line"]] if w.get("total_line") else []),
             "home_margin": f["margin"].summary([w["spread_line"]] if w.get("spread_line") is not None else [])}
    for side, team in (("home", target.home), ("away", target.away)):
        part = {}
        for name in ("game", "H1", "H2", "Q1", "Q2", "Q3", "Q4"):
            lines_ = LINES["points"] if name == "game" else LINES["half"] if name.startswith("H") else LINES["quarter"]
            p = f[(side, name)]
            part[name] = {"points": p["points"].summary(lines_), "touchdowns": p["td"].summary(LINES["td"]),
                          "field_goals": p["fg"].summary(LINES["fga"], LINES["fgm"])}
        sheet[team] = part
    return sheet


def main(argv=None) -> int:
    import argparse
    from . import pbp
    from .inplay import load_boundaries
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.team_props")
    ap.add_argument("cmd", choices=["evaluate", "forecast", "drives-dev", "drives-2026"])
    ap.add_argument("game_id", nargs="?")
    args = ap.parse_args(argv)
    games = load_games()
    lines = load_lines()
    out_path = os.path.join(RESULTS, "nfl_team_props_dev.json")
    if args.cmd == "evaluate":
        data = pbp.load(range(WARMUP, max(EVAL) + 1))
        res = evaluate(games, data, load_boundaries(range(WARMUP, max(EVAL) + 1)), lines)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(res["label"])
        print("chosen:", res["chosen"])
        for k, v in res["vs_league_only_baseline"].items():
            print(f"  {k:<42} model minus league-only {v['model_minus_baseline']:+.4f} "
                  f"[{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]  n={v['n']}")
        worst = max(res["calibration_at_lines"].items(), key=lambda kv: abs(kv[1]["predicted"] - kv[1]["observed"]))
        print(f"  calibration: largest gap between predicted and observed over-rate is {worst[0]}: "
              f"{worst[1]['predicted']:.3f} predicted vs {worst[1]['observed']:.3f} observed")
        for k, v in res["vs_closing_lines"].items():
            d = v["model_minus_line"]
            print(f"  {k} vs closing line: Brier {v['brier_model_over_line']:.4f} vs 0.25, diff "
                  f"{d['model_minus_baseline']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}];  MAE model "
                  f"{v['mae_model_mean']:.2f} vs line {v['mae_closing_line']:.2f}  (n={v['n']})")
        print("  per-kick Brier:", {k: round(v["brier"], 4) for k, v in res["per_kick_brier"].items()})
        print("wrote", out_path)
        return 0
    with open(out_path, encoding="utf-8") as fh:
        saved = json.load(fh)
    if args.cmd.startswith("drives"):
        stage = args.cmd.split("-")[1]
        seasons = DEV if stage == "dev" else [2026]
        path = os.path.join(RESULTS, f"nfl_points_drives_{stage}.json")
        if stage == "2026" and os.path.exists(path):
            print(f"{path} exists: stage 2 runs once")
            return 1
        data = pbp.load(range(WARMUP, max(seasons) + 1), refresh=False) if stage == "dev" else \
            {**pbp.load(range(WARMUP, 2026))}
        bnd = load_boundaries(range(WARMUP, max(seasons) + 1))
        if stage == "2026":
            new = pbp.load_season(2026, refresh=True)
            for k in ("fg", "xp", "two", "td", "pass", "rush"):
                data[k] = data[k] + new[k]
            for k in ("names", "state", "weather"):
                data[k] = {**data[k], **new[k]}
            bnd = load_boundaries(range(WARMUP, 2026)) + load_boundaries([2026], refresh=True)
        res = compare_drives(games, data, bnd, lines, saved["chosen"], saved["kick_model"], seasons)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
        print(res["rule"])
        for k, v in res["log_score"].items():
            d = v["v2_minus_v1"]
            print(f"  {k:<22} log score v1 {v['v1']:.4f}  v2 {v['v2']:.4f}  v2 minus v1 {d['model_minus_baseline']:+.4f} "
                  f"[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]  n={d['n']}")
        c = res["calibration"]["team points, quarter over 0.5"]
        print(f"  team scores in the quarter: observed {c['v1']['observed']:.3f}; predicted v1 {c['v1']['predicted']:.3f}, "
              f"v2 {c['v2']['predicted']:.3f}")
        print("  passes:", res["passes"], " wrote", path)
        return 0
    games = load_games(refresh=True)
    target = next(g for g in games if g.game_id == args.game_id)
    data = pbp.load_through(target.season, WARMUP)
    bnd = load_boundaries(range(WARMUP, target.season)) + load_boundaries([target.season], refresh=True)
    sheet = forecast_sheet(args.game_id, games, data, bnd, load_lines(), saved["chosen"], saved["kick_model"])
    print(json.dumps(sheet, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
