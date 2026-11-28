"""Demo runner: simulate each field, check goal-attainment percentages, forecast a next game,
and paper-trade synthetic prices.

    python -m prediction_markets.run_demo            # full run (tens of seconds)
    python -m prediction_markets.run_demo --quick    # smoke test (a few seconds, no file written)

Every number comes from simulated data generated from config.json.
Nothing is fetched from any betting or prediction-market service.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from typing import Dict, List, Tuple

from .backtest import synthetic_sports_events
from .forecast import forecast_next_period
from .markets import BetPolicy, paper_trade
from .simulate import DomainSpec, load_config, load_domain_specs, simulate_series
from .vbgpc import GoalAttainmentController, SubjectProfile

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT_OUT = os.path.join(RESULTS_DIR, "latest.json")

DISCLAIMER = (
    "SIMULATED DATA ONLY. Probabilities are model outputs on series generated from config.json. "
    "Paper-trading uses synthetic prices. Nothing here is evidence of an edge on any real market or sportsbook."
)


def make_controller(spec: DomainSpec, ctrl_cfg: dict, seed: int, trials: int | None = None) -> GoalAttainmentController:
    profile = SubjectProfile(
        prior_mean=spec.prior_mean,
        prior_strength=spec.prior_strength,
        stat_min=spec.stat_min,
        stat_max=spec.stat_max,
    )
    return GoalAttainmentController(
        profile,
        goal=spec.goal,
        total_steps=spec.total_periods,
        kp=ctrl_cfg["kp"],
        kd=ctrl_cfg["kd"],
        lock_in_buffer=ctrl_cfg["lock_in_buffer"],
        trials=trials or ctrl_cfg["trials"],
        seed=seed,
    )


def run_domain(spec: DomainSpec, ctrl_cfg: dict, replicates: int, seed: int) -> Tuple[dict, List[float]]:
    """Live checkpoint on one simulated run, plus calibration over many replicates."""
    series = simulate_series(spec, random.Random(seed))
    live = make_controller(spec, ctrl_cfg, seed=seed)
    for y in series[: spec.observed_periods]:
        live.record_observation(y)
    plan = live.step_plan()

    preds: List[float] = []
    outcomes: List[float] = []
    for r in range(replicates):
        rep = simulate_series(spec, random.Random(seed * 100003 + r + 1))
        ctrl = make_controller(spec, ctrl_cfg, seed=seed + r + 1, trials=ctrl_cfg["calibration_trials"])
        for y in rep[: spec.observed_periods]:
            ctrl.record_observation(y)
        preds.append(ctrl.attainment_probability())
        outcomes.append(1.0 if sum(rep) >= spec.goal else 0.0)

    n = len(preds)
    base_rate = sum(outcomes) / n
    brier = sum((p - o) ** 2 for p, o in zip(preds, outcomes)) / n
    brier_climatology = base_rate * (1.0 - base_rate)
    skill = 1.0 - brier / brier_climatology if brier_climatology > 0 else None

    report = {
        "field": spec.field,
        "unit": spec.unit,
        "description": spec.description,
        "goal": spec.goal,
        "observed_periods": spec.observed_periods,
        "total_periods": spec.total_periods,
        "checkpoint": {
            "status": plan["status"],
            "regime": plan.get("regime"),
            "variance_policy": plan.get("variance_policy"),
            "shrunk_mean": plan.get("shrunk_mean"),
            "bounded_std": plan.get("bounded_std"),
            "required_pace": plan.get("required_pace"),
            "difficulty_z": plan.get("difficulty_z"),
            "recommended_next_target": plan.get("recommended_next_target"),
            "attainment_probability_pct": 100.0 * plan["probability"],
            "normal_approx_pct": 100.0 * plan["normal_approx_probability"] if "normal_approx_probability" in plan else None,
            "realized_goal_hit_in_this_run": bool(sum(series) >= spec.goal),
        },
        "calibration": {
            "replicates": n,
            "predicted_mean_pct": 100.0 * sum(preds) / n,
            "realized_rate_pct": 100.0 * base_rate,
            "brier": brier,
            "brier_skill_vs_base_rate": skill,
        },
    }
    return report, series


def build_report(quick: bool = False) -> dict:
    cfg = load_config()
    specs = {s.key: s for s in load_domain_specs(cfg)}
    ctrl = cfg["controller"]
    fc_cfg = cfg["forecast_player"]
    bet = cfg["betting"]
    replicates = 20 if quick else ctrl["calibration_replicates"]
    seasons = 4 if quick else bet["seasons"]

    report: dict = {"disclaimer": DISCLAIMER, "domains": {}, "forecast": None, "paper_trading": None}
    series_by_key: Dict[str, List[float]] = {}
    for idx, (key, spec) in enumerate(specs.items()):
        domain_report, series = run_domain(spec, ctrl, replicates, seed=ctrl["seed"] + 1000 * idx)
        report["domains"][key] = domain_report
        series_by_key[key] = series

    star = specs["sports_star"]
    history = series_by_key["sports_star"][: star.observed_periods]
    fc = forecast_next_period(
        history,
        prior_mean=star.prior_mean,
        prior_strength=star.prior_strength,
        stat_min=star.stat_min,
        stat_max=star.stat_max,
        planned_actions=fc_cfg["planned_actions"],
        reference_actions=fc_cfg["reference_actions"],
        action_elasticity=fc_cfg["action_elasticity"],
        conditions_shift=fc_cfg["conditions_shift"],
        recent_workload=fc_cfg["recent_workload"],
        baseline_workload=fc_cfg["baseline_workload"],
        fatigue_drag=fc_cfg["fatigue_drag"],
        milestone=star.milestone,
        trials=ctrl["trials"],
        rng=random.Random(ctrl["seed"]),
    )
    fc["simulated_next_game_for_reference_only"] = series_by_key["sports_star"][star.observed_periods]
    report["forecast"] = fc

    policy = BetPolicy(
        bankroll=bet["bankroll"],
        kelly_fraction=bet["kelly_fraction"],
        max_stake_fraction=bet["max_stake_fraction"],
        edge_threshold=bet["edge_threshold"],
        fee_rate=bet["fee_rate"],
    )
    # fair_market: price equals the true probability (no mispricing). Any loss here is the model's own error.
    # noisy_market: price = true probability + random noise. Its edge exists only by construction.
    report["paper_trading"] = {}
    for name, noise in (("fair_market", 0.0), ("noisy_market", bet["market_noise_sd"])):
        events = []
        for idx, key in enumerate(("sports_star", "sports_role_player")):
            events += synthetic_sports_events(
                specs[key],
                warmup=bet["warmup_games"],
                market_noise_sd=noise,
                seasons=seasons,
                seed=ctrl["seed"] + 5000 + idx,
            )
        result = paper_trade(events, policy)
        result["events_source"] = "synthetic"
        result["market_noise_sd"] = noise
        report["paper_trading"][name] = result
    return report


def _pct(x) -> str:
    return "n/a" if x is None else f"{100.0 * x:5.1f}%"


def _num(x, nd: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def print_report(report: dict) -> None:
    print(report["disclaimer"])
    print()
    print("GOAL ATTAINMENT")
    print("  P(goal) this run = controller's probability at the checkpoint, for one simulated season")
    print("  pred / realized  = average predicted vs. actual hit rate over many simulated seasons")
    print(f"{'domain':<23}{'regime':<27}{'P(goal) this run':>17}{'normal':>9}{'pred avg':>10}{'realized':>10}{'brier skill':>13}")
    for key, d in report["domains"].items():
        c = d["checkpoint"]
        cal = d["calibration"]
        regime = c["regime"] or c["status"]
        skill = _num(cal["brier_skill_vs_base_rate"], 3)
        approx = c["normal_approx_pct"]
        print(
            f"{key:<23}{regime:<27}"
            f"{c['attainment_probability_pct']:15.1f}%"
            f"{(f'{approx:7.1f}%' if approx is not None else 'n/a'):>9}"
            f"{cal['predicted_mean_pct']:9.1f}%"
            f"{cal['realized_rate_pct']:9.1f}%"
            f"{skill:>13}"
        )
    print()
    fc = report["forecast"]
    print("NEXT GAME FORECAST (sports_star, planned actions from config.json)")
    print(f"  expected points          {fc['expected']:.1f}")
    print(f"  likely range (p10-p90)   {fc['likely_range_p10']:.1f} to {fc['likely_range_p90']:.1f}")
    print(f"  P(>= {fc['milestone']:.0f} points)           {_pct(fc['milestone_probability'])}")
    print(f"  simulated game (reference only)  {fc['simulated_next_game_for_reference_only']:.1f}")
    print()
    print("PAPER TRADING (synthetic prices, virtual bankroll)")
    for name, pt in report["paper_trading"].items():
        print(f"  [{name}] market noise sd {pt['market_noise_sd']}")
        print(f"    events {pt['events']}, bets placed {pt['bets']}")
        if pt["win_rate"] is not None:
            lo, hi = pt["win_rate_ci95"]
            print(f"    win rate {_pct(pt['win_rate'])}  (95% CI {100*lo:.1f}% to {100*hi:.1f}%)")
            print(f"    mean price paid {_num(pt['mean_price_paid'])}")
        print(f"    ROI {_pct(pt['roi'])}   bankroll {pt['start_bankroll']:.0f} -> {pt['final_bankroll']:.2f}")
        print(f"    max drawdown {_pct(pt['max_drawdown'])}")
        print(f"    Brier model {_num(pt['brier_model'], 4)} vs market {_num(pt['brier_market'], 4)}, "
              f"skill {_num(pt['brier_skill_vs_market'], 3)}")
        print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the prediction-markets simulation demo.")
    ap.add_argument("--quick", action="store_true", help="smaller run for a smoke test; writes no file")
    ap.add_argument("--out", default=None, help="JSON output path (default: results/latest.json for full runs)")
    args = ap.parse_args(argv)

    report = build_report(quick=args.quick)
    print_report(report)

    out = args.out if args.out is not None else (None if args.quick else DEFAULT_OUT)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
