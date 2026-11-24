"""Attribution diagnostics for the calibration failures. NOT evaluations.

Each check changes one property of the simulated domain, then reruns the spec plug-in
controller on the same seed block used by the calibration study. Use these to identify a
cause, not to certify a fix. Any fix must still be checked on a fresh seed block.

    python3 -m prediction_markets.diagnostics.attribution
"""

from __future__ import annotations

import dataclasses
import json
import os

from ..calibration import VARIANTS, evaluate
from ..simulate import load_config, load_domain_specs

SEED_BLOCK = 913_000_000
REPLICATES = 500
TRIALS = 200
PLUG_IN = VARIANTS["spec_plug_in"]


def main() -> int:
    cfg = load_config()
    specs = load_domain_specs(cfg)
    index = {s.key: (i, s) for i, s in enumerate(specs)}
    ctrl = cfg["controller"]
    results = {}

    i, sys_spec = index["systems_throughput"]
    no_shock = dataclasses.replace(sys_spec, shock_prob=0.0)
    results["systems_throughput_without_outage_shocks"] = evaluate(
        no_shock, ctrl, PLUG_IN, domain_index=i, replicates=REPLICATES, trials=TRIALS, seed_base=SEED_BLOCK)
    results["systems_throughput_as_configured"] = evaluate(
        sys_spec, ctrl, PLUG_IN, domain_index=i, replicates=REPLICATES, trials=TRIALS, seed_base=SEED_BLOCK)

    j, role_spec = index["sports_role_player"]
    true_prior = dataclasses.replace(role_spec, prior_mean=role_spec.true_mu)
    results["sports_role_player_prior_at_true_mean"] = evaluate(
        true_prior, ctrl, PLUG_IN, domain_index=j, replicates=REPLICATES, trials=TRIALS, seed_base=SEED_BLOCK)
    results["sports_role_player_as_configured"] = evaluate(
        role_spec, ctrl, PLUG_IN, domain_index=j, replicates=REPLICATES, trials=TRIALS, seed_base=SEED_BLOCK)

    for name, d in results.items():
        mark = "ok" if d["passes"] else "FAIL"
        print(f"{name:<46} predicted {100*d['predicted_mean']:5.1f}%  realized {100*d['realized_rate']:5.1f}%  "
              f"gap {100*d['gap']:+5.1f} pts  {mark}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attribution_results.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"seed_block": SEED_BLOCK, "replicates": REPLICATES, "results": results}, fh, indent=2)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
