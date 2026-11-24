"""Command line for the read-only real-data tools.

    python3 -m prediction_markets.realdata fetch --source kalshi --out prediction_markets/realdata/data/kalshi.csv
    python3 -m prediction_markets.realdata fetch --source polymarket --out prediction_markets/realdata/data/polymarket.csv
    python3 -m prediction_markets.realdata report --csv prediction_markets/realdata/data/*.csv --out prediction_markets/results/market_calibration.json

Fetched CSVs stay out of the repository (see .gitignore). Only the summary report is meant to be committed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import calibration, kalshi, polymarket
from .observation import read_csv, write_csv


def _fetch(args) -> int:
    t0 = time.time()
    say = lambda msg: print(msg, flush=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    obs = []
    try:
        if args.source == "kalshi":
            series = tuple(s.strip() for s in args.series.split(",") if s.strip())
            stream = kalshi.iter_collect(series, args.per_series, args.horizon_hours, args.max_spread, progress=say)
        else:
            stream = polymarket.iter_collect(args.limit, args.min_volume, args.horizon_hours, progress=say)
        for o in stream:
            obs.append(o)
            if len(obs) % 10 == 0:
                write_csv(args.out, obs)   # checkpoint, so an interruption loses little
    finally:
        write_csv(args.out, obs)
        print(f"wrote {len(obs)} observations to {args.out} in {time.time() - t0:.0f}s", flush=True)
    return 0


def _report(args) -> int:
    obs = []
    for path in args.csv:
        obs += read_csv(path)
    rep = calibration.report(obs)
    print(calibration.format_report(rep))
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2)
        print(f"\nWrote {args.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="prediction_markets.realdata")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="pull resolved markets with a pre-close price from an official public API")
    f.add_argument("--source", choices=("kalshi", "polymarket"), required=True)
    f.add_argument("--series", default=",".join(kalshi.SPORTS_SERIES), help="Kalshi series tickers, comma separated")
    f.add_argument("--per-series", type=int, default=150, help="Kalshi: events per series")
    f.add_argument("--limit", type=int, default=200, help="Polymarket: markets to keep")
    f.add_argument("--min-volume", type=float, default=20000.0, help="Polymarket: minimum market volume")
    f.add_argument("--horizon-hours", type=float, default=24.0, help="how long before close the price is taken")
    f.add_argument("--max-spread", type=float, default=0.10, help="Kalshi: skip books wider than this")
    f.add_argument("--out", required=True)
    f.set_defaults(func=_fetch)
    r = sub.add_parser("report", help="calibration of the market prices themselves")
    r.add_argument("--csv", nargs="+", required=True)
    r.add_argument("--out", default=None)
    r.set_defaults(func=_report)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
