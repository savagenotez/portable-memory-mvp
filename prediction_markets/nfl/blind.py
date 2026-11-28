"""Blind test: games the system cannot see until the judgement is made.

What is sealed
  The manifest lists every 2026 NFL game that was not yet played when it was sealed. Those games have no scores in
  the data file, so no model can learn from them. The manifest is committed with a SHA-256 hash, so the list cannot
  be edited afterwards without the hash changing.

What is enforced
  * Tuning and selection code calls assert_not_sealed() on the games it scores. A sealed game may be used only by
    judge(), and only after it has been played.
  * judge() refuses to run until the prospective decision rule can be applied: at least MIN_JUDGED priced games
    settled, and each slice has been pre-registered (SLICES below). Slices cannot be added after seeing results.

Why the historical seasons are not blind
  2020-2025 were used to choose K = 30, and 2026 games were used to diagnose the model. Those games can still be used
  for development, but any judgement of a new feature needs games from this sealed block.

    python3 -m prediction_markets.nfl.blind seal        # write and commit the manifest, once
    python3 -m prediction_markets.nfl.blind judge       # run only after enough sealed games have been played
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import random
import statistics as st
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .data import Game, load_games
from .prospective import load_log, score as prospective_score

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
MANIFEST = os.path.join(RESULTS, "blind_manifest.json")
JUDGEMENT = os.path.join(RESULTS, "blind_judgement.json")
MIN_JUDGED = 100
ALPHA = 0.05


class SealedGameError(RuntimeError):
    pass


def _sha(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def seal(games: Sequence[Game], season: int = 2026, path: Optional[str] = None, now: Optional[str] = None) -> dict:
    path = path or MANIFEST
    if os.path.exists(path):
        raise SealedGameError(f"manifest already exists at {path}; a sealed block is never re-sealed")
    ids = sorted(g.game_id for g in games if g.season == season and not g.completed)
    body = {"sealed_at": now or dt.datetime.now(dt.timezone.utc).isoformat(), "season": season,
            "game_ids": ids, "rule": "games not yet played at sealing; scores unknown to every model"}
    body["sha256"] = _sha({k: body[k] for k in ("sealed_at", "season", "game_ids", "rule")})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2)
    return body


def sealed_ids(path: Optional[str] = None) -> frozenset:
    path = path or MANIFEST
    if not os.path.exists(path):
        return frozenset()
    with open(path, encoding="utf-8") as fh:
        m = json.load(fh)
    if _sha({k: m[k] for k in ("sealed_at", "season", "game_ids", "rule")}) != m["sha256"]:
        raise SealedGameError("sealed manifest has been altered: hash does not match")
    return frozenset(m["game_ids"])


def assert_not_sealed(game_ids: Iterable[str], purpose: str, path: Optional[str] = None) -> None:
    """Call before any tuning, selection or training. Raises if a sealed game would be used."""
    hit = sorted(set(game_ids) & sealed_ids(path or MANIFEST))
    if hit:
        raise SealedGameError(f"{purpose} may not use sealed games; found {len(hit)}, e.g. {hit[:3]}")


# ---- pre-registered slices (fixed; no additions after seeing results) ---------------------------------------
SLICES: Dict[str, Callable[[dict], bool]] = {
    "division game": lambda r: r["div"] == 1,
    "non-division game": lambda r: r["div"] == 0,
    "YES team had more rest": lambda r: r["rest"] > 0,
    "YES team had less rest": lambda r: r["rest"] < 0,
    "YES team had equal rest": lambda r: r["rest"] == 0,
    "YES team is home": lambda r: r["side"] == "home",
    "YES team is away": lambda r: r["side"] == "away",
    "price below 0.35": lambda r: r["market"] < 0.35,
    "price 0.35 to 0.65": lambda r: 0.35 <= r["market"] <= 0.65,
    "price above 0.65": lambda r: r["market"] > 0.65,
    "model and price within 0.05": lambda r: abs(r["model"] - r["market"]) < 0.05,
    "model and price 0.20 apart or more": lambda r: abs(r["model"] - r["market"]) >= 0.20,
    "indoor venue": lambda r: r["indoor"] == 1,
    "outdoor venue": lambda r: r["indoor"] == 0,
    "first half of season": lambda r: r["week"] <= 9,
    "second half of season": lambda r: r["week"] > 9,
}


def _normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def holm(pvals: Dict[str, float]) -> Dict[str, float]:
    """Holm step-down adjusted p-values: controls the family-wise error rate across the slices."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj: Dict[str, float] = {}
    running = 0.0
    for i, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[name] = running
    return adj


def blind_spots(rows: List[dict], seed: int = 9) -> dict:
    """Model-minus-market Brier by pre-registered slice, with Holm-adjusted p-values across all slices."""
    out, pvals = {}, {}
    rng = random.Random(seed)
    for name, pred in SLICES.items():
        sel = [r for r in rows if pred(r)]
        if len(sel) < 10:
            out[name] = {"n": len(sel), "note": "too few games"}
            continue
        d = [(r["model"] - r["outcome"]) ** 2 - (r["market"] - r["outcome"]) ** 2 for r in sel]
        m = st.mean(d)
        se = st.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
        z = m / se if se and se > 0 else 0.0
        pvals[name] = _normal_two_sided_p(z)
        out[name] = {"n": len(sel), "model_minus_market_brier": m, "ci95": [m - 1.96 * se, m + 1.96 * se]}
    adj = holm(pvals)
    for name, p in adj.items():
        out[name]["holm_p"] = p
        out[name]["blind_spot"] = bool(p < ALPHA)
        out[name]["direction"] = "model worse" if out[name]["model_minus_market_brier"] > 0 else "model better"
    return {"slices": out, "family": len(pvals), "alpha": ALPHA, "rng_seed": seed}


def judge(log_path: str, games: Sequence[Game], path: Optional[str] = None) -> dict:
    """Judge the sealed block. Refuses to run before the pre-registered sample size is reached."""
    path = path or JUDGEMENT
    sealed = sealed_ids()
    if not sealed:
        raise SealedGameError("no manifest: seal the block before judging")
    res = prospective_score(load_log(log_path), games)
    if res.get("scored_games", 0) < MIN_JUDGED:
        return {"status": "not yet", "scored_games": res.get("scored_games", 0), "needed": MIN_JUDGED}
    scored_ids = {r["game_id"] for r in res["rows"]}
    if not scored_ids <= sealed:
        raise SealedGameError("judged games must come from the sealed block")
    by_game = {g.game_id: g for g in games}
    rows = []
    for r in res["rows"]:
        if r.get("model_v3") is None:                     # judge only games where the frozen v3 has a forecast
            continue
        g = by_game[r["game_id"]]
        side = r["side"]                                  # the team the YES market is about
        rest = (g.rest_home - g.rest_away) if side == "home" else (g.rest_away - g.rest_home)
        rows.append({"model": r["model_v3"], "model_base": r["model"], "market": r["market"],
                     "outcome": r["outcome"], "side": side,
                     "div": g.div_game, "rest": rest, "indoor": 1 if g.roof in ("dome", "closed") else 0,
                     "week": g.week})
    if len(rows) < MIN_JUDGED:
        return {"status": "not yet", "scored_games": len(rows), "needed": MIN_JUDGED,
                "note": "games with both a price and a v3 forecast"}
    d_v3 = [(r["model"] - r["outcome"]) ** 2 - (r["market"] - r["outcome"]) ** 2 for r in rows]
    d_base = [(r["model_base"] - r["outcome"]) ** 2 - (r["market"] - r["outcome"]) ** 2 for r in rows]
    d_vs = [(r["model"] - r["outcome"]) ** 2 - (r["model_base"] - r["outcome"]) ** 2 for r in rows]
    rng = random.Random(41)
    def ci(xs):
        boots = sorted(st.mean(rng.choice(xs) for _ in xs) for _ in range(2000))
        return [boots[49], boots[1949]]
    out = {"status": "judged", "scored_games": len(rows),
           "v3_minus_market_brier": {"mean": st.mean(d_v3), "ci95": ci(d_v3)},
           "base_minus_market_brier": {"mean": st.mean(d_base), "ci95": ci(d_base)},
           "v3_minus_base_brier": {"mean": st.mean(d_vs), "ci95": ci(d_vs)},
           "v3_ahead_of_market": ci(d_v3)[1] < 0,
           "blind": blind_spots(rows)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl.blind")
    ap.add_argument("cmd", choices=["seal", "judge"])
    args = ap.parse_args(argv)
    games = load_games(refresh=True)
    if args.cmd == "seal":
        m = seal(games)
        print(f"sealed {len(m['game_ids'])} games, hash {m['sha256'][:16]}..., manifest {MANIFEST}")
        return 0
    from .prospective import LOG
    out = judge(LOG, games)
    print(json.dumps({k: v for k, v in out.items() if k != "blind"}, indent=2))
    if out.get("status") == "judged":
        flagged = [k for k, v in out["blind"]["slices"].items() if v.get("blind_spot")]
        print("blind spots (Holm-adjusted, pre-registered slices):", flagged or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
