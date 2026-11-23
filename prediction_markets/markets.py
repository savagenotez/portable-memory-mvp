"""Paper trading: compare a model probability with a price and track a virtual bankroll.

Contract model: a binary contract priced at `price` in (0, 1) pays 1 if it resolves YES.
Buying a stake S at price c buys S/c contracts. A winning stake returns a profit of
S * (1 - c) / c * (1 - fee_rate). A losing stake loses S.

  EV per unit staked = p * (1 - c) / c * (1 - fee) - (1 - p)
  Kelly fraction     = EV-based optimal fraction of bankroll, clipped at 0

Real prices are NOT fetched here. Supply them yourself as CSV (see README.md).
Win rate alone is not profit: always read it together with ROI and Brier skill.

    python -m prediction_markets.markets events.csv [--fee-rate 0.02] [--edge-threshold 0.03]
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class MarketEvent:
    event_id: str
    model_prob: float     # model P(YES)
    market_price: float   # price of YES, strictly between 0 and 1
    outcome: int          # 1 if YES resolved, 0 if NO resolved


@dataclass(frozen=True)
class BetPolicy:
    bankroll: float = 1000.0
    kelly_fraction: float = 0.25       # fractional Kelly multiplier
    max_stake_fraction: float = 0.05   # hard cap per bet, as a fraction of current bankroll
    edge_threshold: float = 0.03       # minimum EV per unit staked before betting
    fee_rate: float = 0.0              # fee on winnings; set from the venue's published schedule


def net_payout_ratio(price: float, fee_rate: float = 0.0) -> float:
    """Profit per unit staked if the contract wins."""
    return (1.0 - price) / price * (1.0 - fee_rate)


def ev_per_unit(p: float, price: float, fee_rate: float = 0.0) -> float:
    b = net_payout_ratio(price, fee_rate)
    return p * b - (1.0 - p)


def kelly_fraction(p: float, price: float, fee_rate: float = 0.0) -> float:
    b = net_payout_ratio(price, fee_rate)
    return max(0.0, (p * b - (1.0 - p)) / b)


def choose_bet(p_yes: float, price_yes: float, policy: BetPolicy) -> Optional[Tuple[str, float, float]]:
    """Return (side, side_probability, side_price) when the best side clears the edge threshold."""
    ev_yes = ev_per_unit(p_yes, price_yes, policy.fee_rate)
    ev_no = ev_per_unit(1.0 - p_yes, 1.0 - price_yes, policy.fee_rate)
    if ev_yes >= ev_no:
        side, ev, p, c = "YES", ev_yes, p_yes, price_yes
    else:
        side, ev, p, c = "NO", ev_no, 1.0 - p_yes, 1.0 - price_yes
    if ev <= policy.edge_threshold:
        return None
    return side, p, c


def wilson_interval(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def paper_trade(events: Iterable[MarketEvent], policy: BetPolicy) -> dict:
    bankroll = policy.bankroll
    peak = bankroll
    max_drawdown = 0.0
    n_events = 0
    bets = wins = 0
    staked = pnl = price_sum = 0.0
    model_sq = market_sq = 0.0

    for e in events:
        n_events += 1
        model_sq += (e.model_prob - e.outcome) ** 2
        market_sq += (e.market_price - e.outcome) ** 2

        choice = choose_bet(e.model_prob, e.market_price, policy)
        if choice is None:
            continue
        side, p_side, c_side = choice
        f = kelly_fraction(p_side, c_side, policy.fee_rate)
        stake = min(policy.kelly_fraction * f * bankroll, policy.max_stake_fraction * bankroll)
        if stake <= 0.0:
            continue

        won = (e.outcome == 1) if side == "YES" else (e.outcome == 0)
        bets += 1
        staked += stake
        price_sum += c_side
        if won:
            wins += 1
            profit = stake * (1.0 - c_side) / c_side * (1.0 - policy.fee_rate)
        else:
            profit = -stake
        pnl += profit
        bankroll += profit
        peak = max(peak, bankroll)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - bankroll) / peak)

    model_brier = model_sq / n_events if n_events else None
    market_brier = market_sq / n_events if n_events else None
    skill = None
    if market_brier:
        skill = 1.0 - model_brier / market_brier
    ci = wilson_interval(wins, bets) if bets else None

    return {
        "events": n_events,
        "bets": bets,
        "wins": wins,
        "win_rate": wins / bets if bets else None,
        "win_rate_ci95": list(ci) if ci else None,
        "mean_price_paid": price_sum / bets if bets else None,
        "staked": staked,
        "pnl": pnl,
        "roi": pnl / staked if staked else None,
        "start_bankroll": policy.bankroll,
        "final_bankroll": bankroll,
        "max_drawdown": max_drawdown,
        "brier_model": model_brier,
        "brier_market": market_brier,
        "brier_skill_vs_market": skill,
    }


REQUIRED_COLUMNS = ("event_id", "model_prob", "market_price", "outcome")


def events_from_rows(rows: Iterable[dict]) -> List[MarketEvent]:
    """Validate and convert dict rows (e.g. from csv.DictReader)."""
    events: List[MarketEvent] = []
    for line_no, row in enumerate(rows, start=2):
        missing = [c for c in REQUIRED_COLUMNS if c not in row or row[c] in (None, "")]
        if missing:
            raise ValueError(f"row {line_no}: missing {missing}")
        p = float(row["model_prob"])
        c = float(row["market_price"])
        y = int(row["outcome"])
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"row {line_no}: model_prob must be in [0, 1]")
        if not 0.0 < c < 1.0:
            raise ValueError(f"row {line_no}: market_price must be strictly between 0 and 1")
        if y not in (0, 1):
            raise ValueError(f"row {line_no}: outcome must be 0 or 1")
        events.append(MarketEvent(str(row["event_id"]), p, c, y))
    return events


def load_events_csv(path: str) -> List[MarketEvent]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {sorted(missing)}")
        return events_from_rows(reader)


def _main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Paper-trade a CSV of model probabilities against market prices.")
    ap.add_argument("csv_path")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--kelly", type=float, default=0.25)
    ap.add_argument("--max-stake", type=float, default=0.05)
    ap.add_argument("--edge-threshold", type=float, default=0.03)
    ap.add_argument("--fee-rate", type=float, default=0.0)
    args = ap.parse_args(argv)
    policy = BetPolicy(args.bankroll, args.kelly, args.max_stake, args.edge_threshold, args.fee_rate)
    result = paper_trade(load_events_csv(args.csv_path), policy)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
