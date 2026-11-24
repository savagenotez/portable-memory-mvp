"""Cause-and-effect projections: every projection is built from named factors, carries a confidence that must be met
before it commits to a number, explains how wide its range is, and explains each miss factor by factor.

PRE-REGISTERED (written before this model was scored):

  Stats: targets, carries and pass attempts, and the yards that come from them.

  Factors (the projection is their product, so each one's part is visible):
      volume        = team offensive snaps     team's snaps x opponent's snaps allowed, decayed and shrunk
      playing time  = player's snap share      decayed mean of his share in games he was projected for (0 if he
                                               sat), shrunk toward his position (4 games of prior weight)
      usage         = stat per snap he plays   gamma posterior: his decayed count over his decayed snaps, prior is
                                               his position's league rate with 150 snaps of weight
      efficiency    = yards per play           his decayed yards per target, carry or attempt (20 plays of weight)
      projected stat = volume x playing time x usage x exp(causes); projected yards = that x efficiency

  Causes (adjust the product; each effect is fitted on 2013-2019 by Poisson regression with the product as offset,
  and reported with its standard error, so a cause that does not matter shows it):
      favoured by          the team's closing point spread / 7 (uses the market's pre-game line as game script)
      wind                 tens of mph, outdoors only
      home                 +1 home, -1 away
      questionable         listed Questionable on that week's injury report
      age over 30          years above 30 on game day
      opponent allows      log of the opponent's rate allowed to this position, over the league rate

  Why the range is as wide as it is (variance of the count = chance + volume + playing time + usage evidence +
  cause uncertainty + unexplained):
      chance               the count's own randomness (Poisson part, = the mean)
      volume               game-to-game variation of team snaps, measured on 2013-2019
      playing time         the player's own game-to-game variation in snap share (rotation, early exits, benching)
      usage evidence       how little data stands behind his usage rate (1 / posterior shape)
      causes               uncertainty in the fitted cause effects
      unexplained          one extra term per stat, fitted on 2013-2019 by likelihood
    The count is then negative binomial with that mean and variance.

  Confidence rules (fixed now, checked for calibration on the scored seasons):
      range       the narrowest range holding at least 80% probability
      exact       an exact number only if the single most likely value has at least 50% probability
      call        over or under the line only if that side has at least 60% probability; otherwise no call
    The line is the player's season average so far rounded to the nearest .5 (no lawful source of historical prop
    lines is used).

  After each game (postmortem): the miss (actual minus projected) is split exactly across the factors with Shapley
  values (every order of swapping projected factors for actual ones, averaged), so the parts add up to the miss.

  Scored on 2020-2025 against player_props v1 on the same player-games. DEVELOPMENT, not blind.

    python3 -m prediction_markets.nfl.factors evaluate
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from ..stats import engine as E
from .data import Game, load_games
from .player_props import PlayerModel, load_out, player_actuals, _count, _line
from .team_props import DEV, EVAL, RESULTS, WARMUP, _days, load_lines, paired, weather_x

STATS = {"tgt": ("receiver", "targets", "ryd", "receiving yards"),
         "car": ("rusher", "carries", "ruyd", "rushing yards"),
         "att": ("passer", "pass attempts", "pyd", "passing yards")}
CAUSES = ["favoured by (spread / 7)", "wind outdoors (10 mph)", "home", "listed questionable", "age over 30 (years)",
          "opponent allows (log ratio)"]
FACTORS = ["volume (team snaps)", "playing time (snap share)", "usage (per snap)"]
CONF_RANGE, CONF_EXACT, CONF_CALL = 0.80, 0.50, 0.60
SHARE_K0, USAGE_B0, EFF_K0, OPP_B0 = 4.0, 150.0, 20.0, 300.0
KAPPA_GRID = (0.0, 0.02, 0.05, 0.1, 0.2, 0.35, 0.5)


def group(pos: str) -> str:
    return {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "WR": "WR", "TE": "TE"}.get(pos, "other")


def load_questionable(seasons) -> Dict[Tuple[int, int, str], set]:
    import csv
    from .player_props import CACHE
    out: Dict[Tuple[int, int, str], set] = defaultdict(set)
    for y in seasons:
        path = os.path.join(CACHE, f"injuries_{y}.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if (r.get("report_status") or "") == "Questionable" and r.get("gsis_id"):
                    try:
                        out[(int(float(r["season"])), int(float(r["week"])), r["team"])].add(r["gsis_id"])
                    except (KeyError, ValueError):
                        pass
    return out


class MeanVar:
    """Decayed mean and variance per key."""

    def __init__(self, halflife: float = 8.0):
        self.lam = 0.5 ** (1.0 / halflife)
        self.S0: Dict = defaultdict(float)
        self.S1: Dict = defaultdict(float)
        self.S2: Dict = defaultdict(float)

    def update(self, key, x: float) -> None:
        self.S0[key] = self.lam * self.S0[key] + 1.0
        self.S1[key] = self.lam * self.S1[key] + x
        self.S2[key] = self.lam * self.S2[key] + x * x

    def get(self, key, prior_mean: float, prior_var: float, k0: float) -> Tuple[float, float, float]:
        w = self.S0.get(key, 0.0)
        if w <= 0:
            return prior_mean, prior_var, 0.0
        m = self.S1[key] / w
        v = max(0.0, self.S2[key] / w - m * m)
        return (k0 * prior_mean + w * m) / (k0 + w), (k0 * prior_var + w * v) / (k0 + w), w


class FactorModel:
    def __init__(self):
        self.team_off = E.DecayedRate(8, 4)
        self.team_def = E.DecayedRate(8, 4)
        self.lg_snaps = E.LeagueRate(start=63.0)
        self.share = MeanVar(8)
        self.lg_share = {g: MeanVar(1e9) for g in ("QB", "RB", "WR", "TE", "other")}
        self.usage = {s: E.DecayedRate(16, 1.0) for s in STATS}               # S = count, W = snaps (no prior here)
        self.lg_usage = {(s, g): E.LeagueRate(start=0.05) for s in STATS for g in self.lg_share}
        self.eff = {s: E.DecayedRate(16, 1.0) for s in STATS}                 # S = yards, W = plays
        self.lg_eff = {(s, g): E.LeagueRate(start=6.0) for s in STATS for g in self.lg_share}
        self.lg_eff2 = {(s, g): E.LeagueRate(start=80.0) for s in STATS for g in self.lg_share}
        self.opp = {s: E.DecayedRate(8, 1.0) for s in STATS}                 # key (opp, group): S count, W snaps

    def volume(self, team: str, opp: str) -> float:
        L = self.lg_snaps.value
        return L * (self.team_off.rate(team, L) / L) * (self.team_def.rate(opp, L) / L)

    def playing_time(self, pid: str, g: str) -> Tuple[float, float]:
        lg = self.lg_share[g]
        pm, pv, _ = lg.get("all", 0.5, 0.1, 0.0)
        m, v, _ = self.share.get(pid, pm, pv, SHARE_K0)
        return max(m, 1e-3), v

    def usage_post(self, s: str, pid: str, g: str) -> Tuple[float, float]:
        """(mean per snap, posterior shape)."""
        prior = self.lg_usage[(s, g)].value
        a = USAGE_B0 * prior + self.usage[s].S.get(pid, 0.0)
        b = USAGE_B0 + self.usage[s].W.get(pid, 0.0)
        return a / b, a

    def efficiency(self, s: str, pid: str, g: str) -> Tuple[float, float, float]:
        """(yards per play, per-play variance, plays of evidence)."""
        prior = self.lg_eff[(s, g)].value
        w = self.eff[s].W.get(pid, 0.0)
        e = (EFF_K0 * prior + self.eff[s].S.get(pid, 0.0)) / (EFF_K0 + w)
        var = max(1.0, self.lg_eff2[(s, g)].value - prior * prior)
        return e, var, EFF_K0 + w

    def opp_log_ratio(self, s: str, opp: str, g: str) -> float:
        L = self.lg_usage[(s, g)].value
        S, W = self.opp[s].S.get((opp, g), 0.0), self.opp[s].W.get((opp, g), 0.0)
        return math.log(((OPP_B0 * L + S) / (OPP_B0 + W)) / L) if L > 0 else 0.0

    def update_team(self, team: str, opp: str, snaps: float) -> None:
        self.team_off.update(team, snaps)
        self.team_def.update(opp, snaps)
        self.lg_snaps.update(snaps)

    def update_player(self, pid: str, g: str, opp: str, share: float, snaps: float, acts: Optional[dict],
                      projected: bool) -> None:
        if projected:
            self.share.update(pid, share)
            self.lg_share[g].update("all", share)
        if snaps <= 0 or acts is None:
            return
        for s, (_, _, ys, _) in STATS.items():
            x = acts.get(s, 0)
            self.usage[s].update(pid, x, snaps)
            self.lg_usage[(s, g)].update(x, snaps)
            self.opp[s].update((opp, g), x, snaps)
            if x > 0:
                y = acts.get(ys, 0.0)
                self.eff[s].update(pid, y, x)
                self.lg_eff[(s, g)].update(y, x)
                self.lg_eff2[(s, g)].update(y * y / x, x)


def _age(birth: str, day: str) -> Optional[float]:
    try:
        b = dt.date.fromisoformat(birth[:10])
        d = dt.date.fromisoformat(day[:10])
    except ValueError:
        return None
    return (d - b).days / 365.25


def shapley(proj: Sequence[float], act: Sequence[float]) -> List[float]:
    """Exact split of prod(act) - prod(proj) across factors, averaged over every swap order."""
    n = len(proj)
    out = [0.0] * n
    perms = list(itertools.permutations(range(n)))
    for order in perms:
        cur = list(proj)
        prev = math.prod(cur)
        for i in order:
            cur[i] = act[i]
            now = math.prod(cur)
            out[i] += now - prev
            prev = now
    return [x / len(perms) for x in out]


def fit_poisson(rows: List[Tuple[float, List[float], int]], l2: float = 1e-3, iters: int = 30):
    """Poisson regression log mu = offset + b . [1, z]. Returns (b, covariance)."""
    k = len(rows[0][1]) + 1
    b = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        H = [[0.0] * k for _ in range(k)]
        for off, z, y in rows:
            x = [1.0] + z
            mu = math.exp(min(20.0, off + sum(a * c for a, c in zip(b, x))))
            for i in range(k):
                g[i] += (y - mu) * x[i]
                for j in range(k):
                    H[i][j] += mu * x[i] * x[j]
        for i in range(k):
            g[i] -= l2 * b[i]
            H[i][i] += l2
        step = _solve(H, g)
        b = [a + s for a, s in zip(b, step)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return b, _inverse(H)


def _solve(A, v):
    n = len(v)
    M = [row[:] + [v[i]] for i, row in enumerate(A)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                for c in range(i, n + 1):
                    M[r][c] -= f * M[i][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def _inverse(A):
    n = len(A)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(_solve(A, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def projection(r: dict, beta: List[float], cov, cv2_volume: float, kappa: float) -> dict:
    """Turn one row's factors and causes into a distribution, decisions, and reasons for the range."""
    x = [1.0] + r["z"]
    lin = sum(a * c for a, c in zip(beta, x))
    adj = math.exp(lin)
    mu = r["volume"] * r["share"] * r["usage"] * adj
    var_lin = sum(x[i] * cov[i][j] * x[j] for i in range(len(x)) for j in range(len(x)))
    parts = {"chance": mu,
             "volume": mu * mu * cv2_volume,
             "playing time": mu * mu * (r["share_var"] / (r["share"] ** 2)),
             "usage evidence": mu * mu / r["usage_shape"],
             "causes": mu * mu * var_lin,
             "unexplained": mu * mu * kappa}
    extra = sum(v for k, v in parts.items() if k != "chance")
    size = (mu * mu / extra) if extra > 1e-12 else E.POISSON
    contrib = {CAUSES[i]: math.exp(beta[i + 1] * r["z"][i]) for i in range(len(CAUSES))}
    return {"mu": mu, "size": size, "adj": adj, "parts": parts, "cause_multipliers": contrib,
            "var": mu + extra, "dist": None}


def dist_of(p: dict) -> E.Dist:
    if p["dist"] is None:
        p["dist"] = E.nb(p["mu"], p["size"])
    return p["dist"]


def yards_projection(r: dict, p: dict) -> dict:
    """Yards = plays x yards per play. Variance: yards per play varies play to play (chance), the play count varies
    (all of the count's sources), and the yards-per-play rate is itself uncertain (efficiency evidence)."""
    mu, var_n = p["mu"], p["var"]
    e, ve, n_e = r["eff"], r["eff_var"], r["eff_n"]
    m = mu * e
    parts = {"chance": mu * ve + p["parts"]["chance"] * e * e}
    for k, v in p["parts"].items():
        if k != "chance":
            parts[k] = v * e * e
    parts["efficiency evidence"] = m * m * (ve / (e * e)) / n_e if e > 0 else 0.0
    var = sum(parts.values())
    size = (m * m / (var - m)) if var > m + 1e-9 else E.POISSON
    return {"mu": m, "size": size, "parts": parts, "dist": None, "adj": p["adj"], "eff": e}


def decide(d: E.Dist, line: Optional[float]) -> dict:
    lo, hi, mass = d.narrowest(CONF_RANGE)
    mode, pm = d.mode()
    out = {"range": [lo, hi], "range_probability": mass, "most_likely": mode, "most_likely_probability": pm,
           "exact": mode if pm >= CONF_EXACT else None}
    if line is not None:
        p_over = d.over_no_push(line)
        side, conf = ("over", p_over) if p_over >= 0.5 else ("under", 1 - p_over)
        out.update({"line": line, "confidence": conf, "call": side if conf >= CONF_CALL else None})
    return out


def explain(name: str, stat_label: str, r: dict, p: dict, dec: dict) -> str:
    parts = p["parts"]
    tot = sum(parts.values())
    width = ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in sorted(parts.items(), key=lambda kv: -kv[1]) if v / tot >= 0.01)
    causes = ", ".join(f"{k} x{m:.2f}" for k, m in p["cause_multipliers"].items() if abs(m - 1) >= 0.01) or "none"
    call = (f"call {dec['call']} {dec['line']} at {100 * dec['confidence']:.0f}% confidence" if dec.get("call")
            else f"no call on {dec.get('line')}: {100 * dec.get('confidence', 0):.0f}% is below {100 * CONF_CALL:.0f}%"
            if dec.get("line") is not None else "no line")
    exact = (f"exact {dec['exact']} ({100 * dec['most_likely_probability']:.0f}%)" if dec["exact"] is not None
             else f"no exact number: the likeliest value, {dec['most_likely']}, has only "
                  f"{100 * dec['most_likely_probability']:.0f}%")
    return (f"{name} {stat_label}: projected {p['mu']:.1f} = {r['volume']:.0f} team snaps x {100 * r['share']:.0f}% "
            f"snap share x {r['usage']:.3f} per snap x {p['adj']:.2f} causes ({causes}). "
            f"80% range {dec['range'][0]}-{dec['range'][1]}; {exact}; {call}. "
            f"Range width from: {width}.")


def postmortem(name: str, stat_label: str, r: dict, p: dict, actual: int, act_factors: Tuple[float, float, float]
               ) -> dict:
    proj = (r["volume"], r["share"], r["usage"] * p["adj"])
    # every factor is set to its actual value; a player who did not play keeps his projected usage
    act = (act_factors[0], act_factors[1], act_factors[2] if act_factors[2] is not None else proj[2])
    split = shapley(proj, act)
    miss = actual - p["mu"]
    chance = miss - sum(split)                     # zero unless usage was not observable
    names = FACTORS
    order = sorted(range(3), key=lambda i: -abs(split[i]))
    main = names[order[0]]
    text = (f"{name} {stat_label}: projected {p['mu']:.1f}, actual {actual} ({miss:+.1f}). "
            f"Volume {proj[0]:.0f} -> {act[0]:.0f} snaps ({split[0]:+.1f}); snap share {100 * proj[1]:.0f}% -> "
            f"{100 * act[1]:.0f}% ({split[1]:+.1f}); usage {proj[2]:.3f} -> {act[2]:.3f} per snap ({split[2]:+.1f}). "
            f"Largest factor: {main}.")
    return {"miss": miss, "by_factor": dict(zip(names, split)), "residual": chance, "largest": main, "text": text}


def build_rows(games: Sequence[Game], data: dict, lines: dict, v1_params: dict) -> Tuple[list, list]:
    """One walk, 2012-2025. Returns (team rows, player rows) with projected and actual factors. No fitting here."""
    from .sources import load_players, load_snaps
    seasons = range(WARMUP, max(EVAL) + 1)
    players, pairs = player_actuals(data)
    outs = load_out(seasons)
    quest = load_questionable(seasons)
    snap_p, snap_t, _ = load_snaps(seasons)
    info = load_players()
    pfr = {gs: v["pfr_id"] for gs, v in info.items()}
    v1 = PlayerModel({s: (v["halflife_games"], v["k0"]) for s, v in v1_params.items()},
                     {s: v["size"] for s, v in v1_params.items()})
    fm = FactorModel()
    team_rows, rows = [], []
    for day in _days(games):
        if day[0].season > max(EVAL):
            break
        todo = []
        for g in day:
            w = lines.get(g.game_id, {})
            wind, _ = weather_x(w)
            for team, opp, home in ((g.home, g.away, 1), (g.away, g.home, -1)):
                acts = players.get((g.game_id, team))
                tsnaps = snap_t.get((g.game_id, team))
                if acts is None:
                    continue
                out = outs.get((g.season, g.week, team), set())
                elig = v1.eligible(team, out)
                vol = fm.volume(team, opp)
                if tsnaps:
                    team_rows.append({"season": g.season, "proj": vol, "act": tsnaps})
                spread = w.get("spread_line")
                fav = (spread if home == 1 else -spread) / 7.0 if spread is not None else 0.0
                psnaps = snap_p.get((g.game_id, team), {})
                for s, (role, label, ys, ylabel) in STATS.items():
                    for pid in elig[role]:
                        grp = group(info.get(pid, {}).get("position", ""))
                        share, share_var = fm.playing_time(pid, grp)
                        usage, shape = fm.usage_post(s, pid, grp)
                        eff, eff_var, eff_n = fm.efficiency(s, pid, grp)
                        age = _age(info.get(pid, {}).get("birth_date", ""), g.gameday)
                        z = [fav, wind, float(home if not g.neutral else 0), float(pid in quest.get((g.season, g.week, team), ())),
                             max(0.0, (age or 0.0) - 30.0), fm.opp_log_ratio(s, opp, grp)]
                        a = acts.get(pid)
                        k = _count(a[s]) if a else 0
                        yards = _count(a[ys]) if a else 0
                        sn, sh = psnaps.get(pfr.get(pid, ""), (0.0, 0.0))
                        rows.append({"season": g.season, "game": g.game_id, "team": team, "pid": pid, "stat": s,
                                     "group": grp, "volume": vol, "share": share, "share_var": share_var,
                                     "usage": usage, "usage_shape": shape, "eff": eff, "eff_var": eff_var,
                                     "eff_n": eff_n, "z": z, "y": k, "yards": yards,
                                     "act_volume": tsnaps, "act_share": sh if tsnaps else None,
                                     "act_usage": (k / sn) if sn > 0 else None,
                                     "v1_mu": v1.mean(s, pid), "v1_size": v1.size(s),
                                     "v1_yd_mu": v1.mean(ys, pid), "v1_yd_size": v1.size(ys),
                                     "has_snaps": bool(tsnaps) and pfr.get(pid, "") != ""})
                todo.append((g, team, opp, acts, pairs.get((g.game_id, team), {}), elig, tsnaps, psnaps))
        for g, team, opp, acts, prs, elig, tsnaps, psnaps in todo:
            v1.update_team_game(team, acts, prs, elig)
            if not tsnaps:
                continue
            fm.update_team(team, opp, tsnaps)
            projected = set().union(*elig.values())
            seen = set()
            for pid in projected | set(acts):
                p = pfr.get(pid, "")
                if not p or pid in seen:
                    continue
                seen.add(pid)
                sn, sh = psnaps.get(p, (0.0, 0.0))
                grp = group(info.get(pid, {}).get("position", ""))
                fm.update_player(pid, grp, opp, sh, sn, acts.get(pid), pid in projected)
    return team_rows, rows


def evaluate(games: Sequence[Game], data: dict, lines: dict, v1_params: dict) -> dict:
    from .blind import assert_not_sealed
    games = [g for g in games if g.completed and WARMUP <= g.season <= max(EVAL)]
    assert_not_sealed([g.game_id for g in games], "factor model")
    team_rows, rows = build_rows(games, data, lines, v1_params)
    rows = [r for r in rows if r["has_snaps"]]
    dev_t = [t for t in team_rows if t["season"] in DEV]
    cv2_volume = sum((t["act"] / t["proj"] - 1.0) ** 2 for t in dev_t) / len(dev_t)
    res = {"label": "DEVELOPMENT, NOT BLIND. Causes and spread terms fitted on 2013-2019, scored on 2020-2025, "
                    "against player_props v1 on the same player-games.",
           "rules": {"range": CONF_RANGE, "exact": CONF_EXACT, "call": CONF_CALL},
           "volume_cv": math.sqrt(cv2_volume), "stats": {}}
    examples = []
    for s, (role, label, ys, ylabel) in STATS.items():
        dev = [r for r in rows if r["stat"] == s and r["season"] in DEV]
        ev = [r for r in rows if r["stat"] == s and r["season"] in EVAL]
        beta, cov = fit_poisson([(math.log(max(1e-9, r["volume"] * r["share"] * r["usage"])), r["z"], r["y"])
                                 for r in dev])
        best = None
        for kappa in KAPPA_GRID:
            ll = 0.0
            for r in dev:
                p = projection(r, beta, cov, cv2_volume, kappa)
                ll += E.nb_logpmf(r["y"], p["mu"], p["size"])
            if best is None or ll > best[0]:
                best = (ll, kappa)
        kappa = best[1]
        se = [math.sqrt(max(0.0, cov[i][i])) for i in range(len(beta))]
        stat = {"n_dev": len(dev), "n_scored": len(ev), "unexplained_kappa": kappa,
                "causes": {CAUSES[i]: {"effect_per_unit": math.exp(beta[i + 1]), "log_effect": beta[i + 1],
                                       "se": se[i + 1], "z": beta[i + 1] / se[i + 1] if se[i + 1] > 0 else 0.0}
                           for i in range(len(CAUSES))},
                "intercept_multiplier": math.exp(beta[0])}
        ls_f, ls_v1, cover, exact, calls, width_parts = [], [], [], [], [], defaultdict(float)
        y_ls_f, y_ls_v1, y_cover, y_calls, y_width = [], [], [], [], defaultdict(float)
        y_miss_mass = defaultdict(float)
        y_avg: Dict[Tuple[int, str], List[float]] = defaultdict(lambda: [0.0, 0])
        miss_mass, miss_count = defaultdict(float), defaultdict(int)
        season_avg: Dict[Tuple[int, str], List[float]] = defaultdict(lambda: [0.0, 0])
        for r in sorted(ev, key=lambda r: (r["game"], r["pid"])):
            p = projection(r, beta, cov, cv2_volume, kappa)
            d = dist_of(p)
            ls_f.append(E.log_score(d, r["y"]))
            ls_v1.append(E.log_score(E.nb(r["v1_mu"], r["v1_size"]), r["y"]))
            tot, n = season_avg[(r["season"], r["pid"])]
            line = _line(tot / n) if n else None
            dec = decide(d, line)
            inside = dec["range"][0] <= r["y"] <= dec["range"][1]
            cover.append((dec["range_probability"], int(inside)))
            if dec["exact"] is not None:
                exact.append((dec["most_likely_probability"], int(r["y"] == dec["exact"])))
            if dec.get("call"):
                won = (r["y"] > line) if dec["call"] == "over" else (r["y"] < line)
                calls.append((dec["confidence"], int(won)))
            tp = sum(p["parts"].values())
            for k_, v in p["parts"].items():
                width_parts[k_] += v / tp
            if not inside and r["act_volume"]:
                pm = postmortem(r["pid"], label, r, p, r["y"], (r["act_volume"], r["act_share"], r["act_usage"]))
                for f, v in pm["by_factor"].items():
                    miss_mass[f] += abs(v)
                miss_count[pm["largest"]] += 1
                if r["season"] == max(EVAL) and len(examples) < 400:
                    examples.append({"stat": label, "game": r["game"], "pid": r["pid"], "postmortem": pm["text"],
                                     "projection": explain(r["pid"], label, r, p, dec), "abs_miss": abs(pm["miss"])})
            season_avg[(r["season"], r["pid"])][0] += r["y"]
            season_avg[(r["season"], r["pid"])][1] += 1
            # yards
            py = yards_projection(r, p)
            dy = dist_of(py)
            y_ls_f.append(E.log_score(dy, r["yards"]))
            y_ls_v1.append(E.log_score(E.nb(r["v1_yd_mu"], r["v1_yd_size"]), r["yards"]))
            t2, n2 = y_avg[(r["season"], r["pid"])]
            yline = _line(t2 / n2) if n2 else None
            dy_dec = decide(dy, yline)
            y_in = dy_dec["range"][0] <= r["yards"] <= dy_dec["range"][1]
            y_cover.append((dy_dec["range_probability"], int(y_in)))
            if dy_dec.get("call"):
                y_calls.append((dy_dec["confidence"], int((r["yards"] > yline) if dy_dec["call"] == "over"
                                                          else (r["yards"] < yline))))
            tpy = sum(py["parts"].values())
            for k_, v in py["parts"].items():
                y_width[k_] += v / tpy
            if not y_in and r["act_volume"]:
                proj4 = (r["volume"], r["share"], r["usage"] * p["adj"], r["eff"])
                act_e = (r["yards"] / r["y"]) if r["y"] > 0 else r["eff"]
                act4 = (r["act_volume"], r["act_share"], r["act_usage"] if r["act_usage"] is not None else proj4[2],
                        act_e)
                for f, v in zip(FACTORS + ["efficiency (yards per play)"], shapley(proj4, act4)):
                    y_miss_mass[f] += abs(v)
            y_avg[(r["season"], r["pid"])][0] += r["yards"]
            y_avg[(r["season"], r["pid"])][1] += 1
        n = len(ev)
        mm = sum(miss_mass.values()) or 1.0
        nm = sum(miss_count.values()) or 1
        bucket = lambda xs, lo, hi: [y for c, y in xs if lo <= c < hi]
        stat.update({
            "log_score_factor": sum(ls_f) / n, "log_score_v1": sum(ls_v1) / n,
            "factor_minus_v1": paired(ls_f, ls_v1),
            "range_80": {"claimed": sum(c for c, _ in cover) / n, "actual_coverage": sum(y for _, y in cover) / n},
            "exact_numbers": {"issued_share": len(exact) / n,
                              "claimed": (sum(c for c, _ in exact) / len(exact)) if exact else None,
                              "hit_rate": (sum(y for _, y in exact) / len(exact)) if exact else None},
            "calls": {"issued_share": len(calls) / n, "claimed": (sum(c for c, _ in calls) / len(calls)) if calls else None,
                      "hit_rate": (sum(y for _, y in calls) / len(calls)) if calls else None,
                      "by_confidence": {f"{lo:.2f}-{hi:.2f}": {"n": len(b), "hit_rate": sum(b) / len(b)}
                                        for lo, hi in ((0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01))
                                        for b in [bucket(calls, lo, hi)] if b}},
            "range_width_sources": {k_: v / n for k_, v in width_parts.items()},
            "misses_outside_range": {"share_of_projections": 1 - sum(y for _, y in cover) / n,
                                     "share_of_miss_by_factor": {k_: v / mm for k_, v in miss_mass.items()},
                                     "largest_factor_count_share": {k_: v / nm for k_, v in miss_count.items()}}})
        res["stats"][label] = stat
        ym = sum(y_miss_mass.values()) or 1.0
        res["stats"][ylabel] = {
            "n_scored": n, "log_score_factor": sum(y_ls_f) / n, "log_score_v1": sum(y_ls_v1) / n,
            "factor_minus_v1": paired(y_ls_f, y_ls_v1),
            "range_80": {"claimed": sum(c for c, _ in y_cover) / n, "actual_coverage": sum(y for _, y in y_cover) / n},
            "calls": {"issued_share": len(y_calls) / n,
                      "claimed": (sum(c for c, _ in y_calls) / len(y_calls)) if y_calls else None,
                      "hit_rate": (sum(y for _, y in y_calls) / len(y_calls)) if y_calls else None,
                      "by_confidence": {f"{lo:.2f}-{hi:.2f}": {"n": len(b), "hit_rate": sum(b) / len(b)}
                                        for lo, hi in ((0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01))
                                        for b in [bucket(y_calls, lo, hi)] if b}},
            "range_width_sources": {k_: v / n for k_, v in y_width.items()},
            "misses_outside_range": {"share_of_projections": 1 - sum(y for _, y in y_cover) / n,
                                     "share_of_miss_by_factor": {k_: v / ym for k_, v in y_miss_mass.items()}}}
    examples.sort(key=lambda e: -e["abs_miss"])
    res["largest_misses_2025"] = examples[:12]
    return res


def main(argv=None) -> int:
    from . import pbp
    games = load_games()
    with open(os.path.join(RESULTS, "nfl_player_props_dev.json"), encoding="utf-8") as fh:
        v1 = json.load(fh)["chosen"]
    res = evaluate(games, pbp.load(range(WARMUP, max(EVAL) + 1)), load_lines(), v1)
    path = os.path.join(RESULTS, "nfl_factors_dev.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(res["label"], f"team snaps vary {100 * res['volume_cv']:.1f}% game to game")
    for label, st in res["stats"].items():
        d = st["factor_minus_v1"]
        print(f"\n{label}: log score factor {st['log_score_factor']:.4f} vs v1 {st['log_score_v1']:.4f}, "
              f"diff {d['model_minus_baseline']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] n={d['n']}")
        for c, v in st.get("causes", {}).items():
            print(f"   cause {c:<30} x{v['effect_per_unit']:.3f} per unit  (z {v['z']:+.1f})")
        print(f"   80% range: claimed {st['range_80']['claimed']:.3f}, held {st['range_80']['actual_coverage']:.3f}")
        e, c = st.get("exact_numbers"), st["calls"]
        if e:
            print(f"   exact numbers issued {100 * e['issued_share']:.1f}%  claimed {e['claimed']}  hit {e['hit_rate']}")
        print(f"   calls issued {100 * c['issued_share']:.1f}%  claimed {c['claimed']}  hit {c['hit_rate']}  "
              f"by confidence {c['by_confidence']}")
        print("   range width from:", {k: round(v, 3) for k, v in st["range_width_sources"].items()})
        print("   misses outside the range, share of miss by factor:",
              {k: round(v, 3) for k, v in st["misses_outside_range"]["share_of_miss_by_factor"].items()})
    print("\nlargest 2025 misses:")
    for e in res["largest_misses_2025"][:4]:
        print("  ", e["projection"])
        print("  ", e["postmortem"])
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
