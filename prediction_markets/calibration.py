"""Calibration study for goal-attainment probabilities.

PRE-REGISTERED CRITERION (fixed before any variant was run):

  A variant PASSES if, for every domain, the average predicted probability over R
  held-out simulated seasons is within two standard errors of the realized hit rate:

      |mean(pred) - mean(outcome)| <= 2 * SE,   SE = sqrt(p (1 - p) / R),  p = realized rate

  Secondary, reported but not part of the pass rule: mean Brier skill against the base rate.

The variants are structural choices, not tuned parameters. config.json is not changed to
make any variant pass. Evaluation uses a seed block (HELD_OUT_SEED_BASE) that no earlier
run in this package used.

    python3 -m prediction_markets.calibration               # full study, writes results/calibration.json
    python3 -m prediction_markets.calibration --quick       # smoke test, writes nothing
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
from typing import Dict, List

from .simulate import DomainSpec, load_config, load_domain_specs, simulate_series
from .vbgpc import GoalAttainmentController, SubjectProfile

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT_OUT = os.path.join(RESULTS_DIR, "calibration.json")

HELD_OUT_SEED_BASE = 912_000_000
DOMAIN_SEED_STRIDE = 10_000_000

VARIANTS: Dict[str, dict] = {
    "spec_plug_in": {"dependence": "iid", "mu_uncertainty": False},
    "mu_uncertainty": {"dependence": "iid", "mu_uncertainty": True},
    "ar1_momentum": {"dependence": "ar1", "mu_uncertainty": False},
    "ar1_momentum_and_mu_uncertainty": {"dependence": "ar1", "mu_uncertainty": True},
    # Added after the first study, motivated by a diagnostic (see README). It was run on a fresh
    # seed block; the first four variants were not re-tuned.
    "drift_adjusted": {"dependence": "iid", "mu_uncertainty": False, "drift_adjusted": True},
}


def _controller(spec: DomainSpec, ctrl_cfg: dict, variant: dict, seed: int, trials: int) -> GoalAttainmentController:
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
        trials=trials,
        seed=seed,
        dependence=variant["dependence"],
        mu_uncertainty=variant["mu_uncertainty"],
        drift=spec.known_drift if variant.get("drift_adjusted") else None,
    )


def evaluate(
    spec: DomainSpec,
    ctrl_cfg: dict,
    variant: dict,
    *,
    domain_index: int,
    replicates: int,
    trials: int,
    seed_base: int = HELD_OUT_SEED_BASE,
) -> dict:
    """Predicted vs realized over `replicates` fresh simulated seasons."""
    base = seed_base + domain_index * DOMAIN_SEED_STRIDE
    preds: List[float] = []
    outs: List[float] = []
    for r in range(replicates):
        rep = simulate_series(spec, random.Random(base + r))
        ctrl = _controller(spec, ctrl_cfg, variant, seed=base + 500_000 + r, trials=trials)
        for y in rep[: spec.observed_periods]:
            ctrl.record_observation(y)
        preds.append(ctrl.attainment_probability())
        outs.append(1.0 if sum(rep) >= spec.goal else 0.0)

    n = len(outs)
    realized = sum(outs) / n
    mean_pred = sum(preds) / n
    se = math.sqrt(realized * (1.0 - realized) / n)
    gap = mean_pred - realized
    brier = sum((p - o) ** 2 for p, o in zip(preds, outs)) / n
    clim = realized * (1.0 - realized)
    skill = 1.0 - brier / clim if clim > 0 else None
    return {
        "replicates": n,
        "predicted_mean": mean_pred,
        "realized_rate": realized,
        "gap": gap,
        "standard_error": se,
        "gap_in_se": gap / se if se > 0 else None,
        "passes": (abs(gap) <= 2.0 * se) if se > 0 else (abs(gap) < 1e-9),
        "brier": brier,
        "brier_skill_vs_base_rate": skill,
    }


def run_study(replicates: int, trials: int, seed_base: int = HELD_OUT_SEED_BASE) -> dict:
    cfg = load_config()
    specs = load_domain_specs(cfg)
    ctrl_cfg = cfg["controller"]
    study: dict = {
        "criterion": "pre-registered: |mean(pred) - realized| <= 2 * SE per domain",
        "seed_base": seed_base,
        "replicates": replicates,
        "mc_trials_per_prediction": trials,
        "variants": {},
    }
    for vname, variant in VARIANTS.items():
        per_domain = {}
        for idx, spec in enumerate(specs):
            per_domain[spec.key] = evaluate(
                spec, ctrl_cfg, variant,
                domain_index=idx, replicates=replicates, trials=trials, seed_base=seed_base,
            )
        all_pass = all(d["passes"] for d in per_domain.values())
        skills = [d["brier_skill_vs_base_rate"] for d in per_domain.values() if d["brier_skill_vs_base_rate"] is not None]
        study["variants"][vname] = {
            "settings": variant,
            "passes_all_domains": all_pass,
            "domains_passing": sum(1 for d in per_domain.values() if d["passes"]),
            "mean_brier_skill": sum(skills) / len(skills) if skills else None,
            "domains": per_domain,
        }
    return study


def _print(study: dict) -> None:
    print(study["criterion"])
    print(f"held-out seeds from {study['seed_base']}, {study['replicates']} replicates, "
          f"{study['mc_trials_per_prediction']} MC trials per prediction\n")
    names = list(next(iter(study["variants"].values()))["domains"].keys())
    header = f"{'variant':<34}" + "".join(f"{n[:14]:>16}" for n in names) + f"{'all pass':>10}{'skill':>9}"
    print(header)
    for vname, v in study["variants"].items():
        cells = []
        for n in names:
            d = v["domains"][n]
            mark = "ok" if d["passes"] else "FAIL"
            cells.append(f"{100*d['predicted_mean']:5.1f}/{100*d['realized_rate']:4.1f} {mark:>4}")
        skill = "n/a" if v["mean_brier_skill"] is None else f"{v['mean_brier_skill']:+.3f}"
        print(f"{vname:<34}" + "".join(f"{c:>16}" for c in cells)
              + f"{('YES' if v['passes_all_domains'] else 'no'):>10}{skill:>9}")
    print("\ncells: predicted% / realized%")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Calibration study for goal-attainment probabilities.")
    ap.add_argument("--quick", action="store_true", help="30 replicates, no file written")
    ap.add_argument("--seed-base", type=int, default=HELD_OUT_SEED_BASE,
                    help="seed block for the held-out replicates (use a fresh block for each new study)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    replicates = 30 if args.quick else 500
    trials = 200
    study = run_study(replicates=replicates, trials=trials, seed_base=args.seed_base)
    _print(study)
    out = args.out if args.out is not None else (None if args.quick else DEFAULT_OUT)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(study, fh, indent=2)
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
