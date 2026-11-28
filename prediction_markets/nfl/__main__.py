"""    python3 -m prediction_markets.nfl compare --kalshi prediction_markets/realdata/data/kalshi_nfl_24h.csv \
        --out prediction_markets/results/nfl_model_vs_market.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from ..realdata.observation import read_csv
from .compare import compare
from .data import load_games


def _print(rep: dict) -> None:
    if not rep.get("matched"):
        print(f"no matched games (unmatched {rep.get('unmatched', 0)})")
        return
    lo, hi = rep["model_minus_market_ci95"]
    c_m, c_k = rep["calibration_model"], rep["calibration_market"]
    print(f"matched {rep['matched']} games   unmatched {rep['unmatched']}   agreement with final score "
          f"{100 * rep['agreement_with_score']:.1f}%")
    print(f"Brier   model {rep['brier_model']:.4f}   market {rep['brier_market']:.4f}   "
          f"base rate {rep['brier_base_rate']:.4f}")
    print(f"skill vs base rate   model {100 * rep['model_skill_vs_base']:+.1f}%   "
          f"market {100 * rep['market_skill_vs_base']:+.1f}%")
    print(f"model minus market Brier {rep['model_minus_market_brier']:+.4f}   95% interval [{lo:+.4f}, {hi:+.4f}]"
          f"  (below zero = model better)")
    print(f"log loss   model {rep['logloss_model']:.4f}   market {rep['logloss_market']:.4f}")
    print(f"calibration slope   model {c_m['slope']:.2f} +/- {1.96 * c_m['slope_se']:.2f}   "
          f"market {c_k['slope']:.2f} +/- {1.96 * c_k['slope_se']:.2f}   (1.00 = calibrated)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prediction_markets.nfl")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="score the NFL model against Kalshi prices on the same games")
    c.add_argument("--kalshi", required=True, help="CSV from `realdata fetch --source kalshi --series KXNFLGAME`")
    c.add_argument("--refresh", action="store_true", help="re-download the nflverse game file")
    c.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    games = load_games(refresh=args.refresh)
    obs = [o for o in read_csv(args.kalshi) if o.event_id.startswith("KXNFLGAME")]
    rep = compare(obs, games)
    _print(rep)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
