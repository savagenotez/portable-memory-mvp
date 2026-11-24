"""Pre-registered study of the branch ensemble under hard conditions.

PRE-REGISTERED CRITERIA, written before the final-seed run (seeds from study.final_seed_base):

  C1  clean calibration     pooled post-warm-up |mean(pred) - realized| <= 2 SE overall, and every calibration
                            slice with n >= 300 within 3 SE. (Revised before any final-seed run. The first draft
                            required 90% of 12 slices within 2 SE, which a perfectly calibrated model fails about
                            10% of the time. Three SE across all slices is passed about 97% of the time.)
  C2  clean skill           Brier skill vs the base rate is positive with a 95% interval above zero across leagues,
                            and the ensemble is not worse than one flat logistic model (paired mean Brier difference >= 0).
  C3  learning              capture of the achievable gain in the last two scored seasons >= capture in the first two.
  C4  spurious feature      after the feature stops working, capture >= 0.95 x the clean-run capture on the same games.
  C5  leakage trap          capture <= 1.05 x the clean-run capture (no fake skill), and the leaking branch is
                            quarantined in at least 90% of leagues.
  C6  duplicate branch      capture >= 0.95 x clean capture, and overall calibration still passes.
  C7  regime shift          capture in the 150 games after the shift >= 0.5 x capture in the 150 games before,
                            and capture in the following 150 games >= 0.8 x capture before the shift.
  C8  branch scores         in clean runs, the mean final decision score of the team branch is > 2 and of the
                            pure-noise branch is < 1.

"capture" = (brier_base - brier_model) / (brier_base - brier_oracle): the share of the achievable gain captured.
The oracle is the simulator's true probability. Real data has no oracle, so capture is a simulation-only measure.

The model hyperparameters were tuned on dev seeds only. The plausibility cap is set to
plausible_multiple x the oracle's log-loss gain over the base rate, measured on the dev leagues. In real data the
analogue would be a bound taken from a strong external benchmark, such as a market price.

    python3 -m prediction_markets.league.study --dev        # dev seeds, no claims, writes nothing
    python3 -m prediction_markets.league.study              # final seeds, writes results/league_study.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from dataclasses import asdict, replace
from typing import Dict, List, Optional, Sequence, Tuple

from . import evaluate as ev
from .features import build_rows, branches_for
from .model import ModelConfig
from .sim import SCENARIOS, LeagueConfig, config_from_dict, simulate_league

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
RESULTS_DIR = os.path.join(os.path.dirname(HERE), "results")
DEFAULT_OUT = os.path.join(RESULTS_DIR, "league_study.json")

TRIPWIRE_FLAGS = ["use_gates", "use_drift", "use_plausibility_cap", "use_early_shrink", "use_platt"]

CRITERIA = {
    "C1": "clean: pooled overall calibration within 2 SE, and every slice (n >= 300) within 3 SE",
    "C2": "clean: Brier skill vs base rate has 95% interval above 0, and ensemble not worse than flat logistic",
    "C3": "clean: capture in last two scored seasons >= capture in first two",
    "C4": "spurious_decoy: capture after the break >= 0.95 x clean capture",
    "C5": "leakage_trap: capture <= 1.05 x clean capture, and leak branch quarantined in >= 90% of leagues",
    "C6": "duplicate_branch: capture >= 0.95 x clean capture, and overall calibration passes",
    "C7": "regime_shift: capture after shift >= 0.5 x before (next 150 games >= 0.8 x before)",
    "C8": "clean: mean final decision score of team branch > 2, of decoy_noise branch < 1",
}


def load_config(path: Optional[str] = None) -> dict:
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def variants(base: ModelConfig) -> Dict[str, ModelConfig]:
    out = {"ens": base, "ens_off": replace(base, **{f: False for f in TRIPWIRE_FLAGS})}
    for f in TRIPWIRE_FLAGS:
        out["no_" + f[4:]] = replace(base, **{f: False})
    return out


def derive_plausible_cap(league_cfg: LeagueConfig, study: dict) -> Tuple[float, float]:
    """Oracle log-loss gain over the base rate on dev leagues, times plausible_multiple."""
    gains = []
    for s in range(study["dev_seed_base"], study["dev_seed_base"] + study["dev_leagues"]):
        ld = simulate_league(replace(league_cfg, scenario="clean"), random.Random(s))
        rows = build_rows(ld)
        seasons = [g.season for g in ld.games]
        start = ev.first_index_of_season(rows, seasons, study["warmup_seasons"])
        base = ev.run_base_rate(rows)
        orc = [r.p_true for r in rows]
        gains.append(ev.mean(ev.log_losses(base, rows)[start:]) - ev.mean(ev.log_losses(orc, rows)[start:]))
    gain = ev.mean(gains)
    return study["plausible_multiple"] * gain, gain


def _windows(ld, rows, seasons, study) -> Dict[str, Tuple[int, int]]:
    cfg = ld.config
    warm = study["warmup_seasons"]
    n = len(rows)
    idx = lambda s: ev.first_index_of_season(rows, seasons, s)
    w = {"post_warmup": (idx(warm), n)}
    for s in range(warm, cfg.seasons):
        w[f"season_{s}"] = (idx(s), idx(s + 1))
    w["early"] = (idx(warm), idx(warm + 2))
    w["late"] = (idx(cfg.seasons - 2), n)
    w["after_break"] = (idx(cfg.spurious_until_season), n)
    if ld.shift_game_index is not None:
        k, span = ld.shift_game_index, study["shift_window_games"]
        w["pre_shift"] = (max(0, k - span), k)
        w["post_shift_1"] = (k, min(n, k + span))
        w["post_shift_2"] = (min(n, k + span), min(n, k + 2 * span))
    return w


def run_league(seed: int, scenario: str, league_cfg: LeagueConfig, model_cfg: ModelConfig,
               cap: float, study: dict, want_samples: bool) -> dict:
    ld = simulate_league(replace(league_cfg, scenario=scenario), random.Random(seed))
    rows = build_rows(ld)
    seasons = [g.season for g in ld.games]
    windows = _windows(ld, rows, seasons, study)
    bf = branches_for(scenario)
    all_features = [f for cols in bf.values() for f in cols]

    preds: Dict[str, List[float]] = {"base": ev.run_base_rate(rows), "oracle": [r.p_true for r in rows]}
    preds["flat"] = ev.run_flat(rows, all_features, model_cfg)
    ens_model = None
    for name, cfg in variants(model_cfg).items():
        p, m = ev.run_ensemble(rows, bf, cfg, plausible_gain=cap)
        preds[name] = p
        if name == "ens":
            ens_model = m

    sq = {name: ev.sq_errors(p, rows) for name, p in preds.items()}
    win_briers = {w: {name: ev.mean(arr[a:b]) for name, arr in sq.items()} for w, (a, b) in windows.items() if b > a}

    out = {"seed": seed, "windows": win_briers, "report": ens_model.report(),
           "quarantined": {name: b.quarantined for name, b in ens_model.branches.items()}}
    if want_samples:
        a, b = windows["post_warmup"]
        out["samples"] = [(rows[i].context, preds["ens"][i], rows[i].y) for i in range(a, b)]
    return out


# ---- aggregation --------------------------------------------------------------------------

def window_summary(results: Sequence[dict], window: str) -> Optional[dict]:
    have = [r["windows"][window] for r in results if window in r["windows"]]
    if not have:
        return None
    models = have[0].keys()
    mean_b = {m: ev.mean([h[m] for h in have]) for m in models}
    base, orc = mean_b["base"], mean_b["oracle"]
    out = {"brier": mean_b, "n_leagues": len(have),
           "capture": {m: ev.capture(base, mean_b[m], orc) for m in models if m not in ("base", "oracle")},
           "skill": {m: 1.0 - mean_b[m] / base for m in models if m != "base"}}
    return out


def paired_diff(results: Sequence[dict], window: str, a: str, b: str) -> Tuple[float, float, float]:
    """Mean and 95% interval of brier[a] - brier[b] across leagues."""
    return ev.ci95([r["windows"][window][a] - r["windows"][window][b] for r in results if window in r["windows"]])


def skill_interval(results: Sequence[dict], window: str, model: str) -> Tuple[float, float, float]:
    vals = [1.0 - r["windows"][window][model] / r["windows"][window]["base"] for r in results if window in r["windows"]]
    return ev.ci95(vals)


def branch_table(results: Sequence[dict]) -> Dict[str, dict]:
    names = results[0]["report"].keys()
    out = {}
    for n in names:
        scores = [r["report"][n]["score"] for r in results if r["report"][n]["score"] is not None]
        out[n] = {
            "mean_score": ev.mean(scores) if scores else None,
            "mean_gate": ev.mean([r["report"][n]["gate"] for r in results]),
            "mean_weight": ev.mean([r["report"][n]["weight"] for r in results]),
            "mean_solo_gain": ev.mean([r["report"][n]["solo_gain"] for r in results]),
            "mean_marginal_gain": ev.mean([r["report"][n]["marginal_gain"] for r in results]),
            "quarantine_rate": ev.mean([1.0 if r["report"][n]["quarantined"] else 0.0 for r in results]),
            "mean_drift_alarms": ev.mean([r["report"][n]["drift_alarms"] for r in results]),
        }
    return out


def pooled_calibration(results: Sequence[dict], min_n: int) -> dict:
    samples = [s for r in results for s in r.get("samples", [])]
    table = ev.slice_table(samples, min_n)
    passed, total = ev.slice_pass_rate(table)
    return {"table": table, "slices_passed": passed, "slices_evaluated": total}


def run_scenario(scenario: str, seeds: Sequence[int], league_cfg: LeagueConfig, model_cfg: ModelConfig,
                 cap: float, study: dict, want_samples: bool) -> List[dict]:
    return [run_league(s, scenario, league_cfg, model_cfg, cap, study, want_samples) for s in seeds]


def judge(by_scenario: Dict[str, List[dict]], study: dict) -> Dict[str, dict]:
    verdict: Dict[str, dict] = {}
    clean = by_scenario["clean"]
    cs = window_summary(clean, "post_warmup")
    cal = pooled_calibration(clean, study["min_slice_n"])
    overall_ok = cal["table"]["overall"]["passes"]
    evaluated = {k: v for k, v in cal["table"].items() if k != "overall" and v.get("evaluated")}
    worst = max(evaluated.items(), key=lambda kv: abs(kv[1]["gap_in_se"])) if evaluated else None
    all_within_3 = bool(evaluated) and all(abs(v["gap_in_se"]) <= 3.0 for v in evaluated.values())
    verdict["C1"] = {"passed": bool(overall_ok and all_within_3),
                     "value": {"overall_gap_in_se": cal["table"]["overall"]["gap_in_se"],
                               "slices_within_2se": cal["slices_passed"], "slices_evaluated": cal["slices_evaluated"],
                               "worst_slice": worst[0] if worst else None,
                               "worst_slice_gap_in_se": worst[1]["gap_in_se"] if worst else None}}

    sk = skill_interval(clean, "post_warmup", "ens")
    d_flat = paired_diff(clean, "post_warmup", "flat", "ens")
    verdict["C2"] = {"passed": bool(sk[1] > 0 and d_flat[0] >= 0),
                     "value": {"skill_mean_and_95ci": sk, "flat_minus_ens_brier_mean_and_95ci": d_flat}}

    early, late = window_summary(clean, "early"), window_summary(clean, "late")
    verdict["C3"] = {"passed": bool(late["capture"]["ens"] >= early["capture"]["ens"]),
                     "value": {"early_capture": early["capture"]["ens"], "late_capture": late["capture"]["ens"]}}

    def cap_of(sc: str, window: str) -> float:
        return window_summary(by_scenario[sc], window)["capture"]["ens"]

    if "spurious_decoy" in by_scenario:
        a, b = cap_of("spurious_decoy", "after_break"), cap_of("clean", "after_break")
        verdict["C4"] = {"passed": bool(a >= 0.95 * b), "value": {"spurious": a, "clean": b}}
    if "leakage_trap" in by_scenario:
        a, b = cap_of("leakage_trap", "post_warmup"), cap_of("clean", "post_warmup")
        q = ev.mean([1.0 if r["quarantined"].get("leak") else 0.0 for r in by_scenario["leakage_trap"]])
        verdict["C5"] = {"passed": bool(a <= 1.05 * b and q >= 0.9),
                         "value": {"leak_capture": a, "clean_capture": b, "quarantine_rate": q}}
    if "duplicate_branch" in by_scenario:
        a, b = cap_of("duplicate_branch", "post_warmup"), cap_of("clean", "post_warmup")
        dcal = pooled_calibration(by_scenario["duplicate_branch"], study["min_slice_n"])
        verdict["C6"] = {"passed": bool(a >= 0.95 * b and dcal["table"]["overall"]["passes"]),
                         "value": {"dup_capture": a, "clean_capture": b,
                                   "overall_gap_in_se": dcal["table"]["overall"]["gap_in_se"]}}
    if "regime_shift" in by_scenario:
        pre = cap_of("regime_shift", "pre_shift")
        p1, p2 = cap_of("regime_shift", "post_shift_1"), cap_of("regime_shift", "post_shift_2")
        verdict["C7"] = {"passed": bool(p1 >= 0.5 * pre and p2 >= 0.8 * pre),
                         "value": {"pre": pre, "post_1": p1, "post_2": p2}}
    bt = branch_table(clean)
    team, noise = bt["team"]["mean_score"], bt["decoy_noise"]["mean_score"]
    verdict["C8"] = {"passed": bool(team is not None and noise is not None and team > 2 and noise < 1),
                     "value": {"team_score": team, "decoy_noise_score": noise}}
    return verdict


def run_study(dev: bool = False, quick: bool = False, scenarios: Sequence[str] = SCENARIOS) -> dict:
    cfg = load_config()
    league_cfg = config_from_dict(cfg["league"])
    model_cfg = ModelConfig(**cfg["model"])
    study = cfg["study"]
    base_seed = study["dev_seed_base"] if (dev or quick) else study["final_seed_base"]
    n_leagues = study["dev_leagues"] if dev else study["final_leagues"]
    if quick:
        n_leagues = 4
    seeds = list(range(base_seed, base_seed + n_leagues))
    cap, oracle_gain = derive_plausible_cap(league_cfg, study)

    by_scenario: Dict[str, List[dict]] = {}
    t0 = time.time()
    for sc in scenarios:
        by_scenario[sc] = run_scenario(sc, seeds, league_cfg, model_cfg, cap, study,
                                       want_samples=sc in ("clean", "duplicate_branch"))
    summary = {sc: {w: window_summary(res, w) for w in res[0]["windows"]} for sc, res in by_scenario.items()}
    out = {
        "mode": "dev" if (dev or quick) else "final",
        "seeds": [seeds[0], seeds[-1]],
        "leagues": n_leagues,
        "seasons": league_cfg.seasons,
        "scored_from_season": study["warmup_seasons"],
        "plausible_cap_nats": cap,
        "oracle_gain_nats_on_dev": oracle_gain,
        "criteria": CRITERIA,
        "model": asdict(model_cfg),
        "seconds": time.time() - t0,
        "summary": summary,
        "branches_clean": branch_table(by_scenario["clean"]),
        "calibration_clean": pooled_calibration(by_scenario["clean"], study["min_slice_n"]),
    }
    if all(s in by_scenario for s in SCENARIOS):
        out["verdict"] = judge(by_scenario, study)
    return out


def _print(out: dict) -> None:
    print(f"mode={out['mode']} leagues={out['leagues']} seeds {out['seeds'][0]}..{out['seeds'][1]} "
          f"seasons={out['seasons']} scored from season {out['scored_from_season']} ({out['seconds']:.0f}s)")
    print(f"plausibility cap {out['plausible_cap_nats']:.4f} nats/game (oracle gain on dev {out['oracle_gain_nats_on_dev']:.4f})\n")
    print("capture of achievable accuracy, post warm-up (1.0 = oracle; leaked 'skill' shows as > 1)")
    header = f"{'scenario':<18}{'ensemble':>10}{'tripwires off':>15}{'flat model':>12}"
    print(header)
    for sc, ws in out["summary"].items():
        c = ws["post_warmup"]["capture"]
        print(f"{sc:<18}{c['ens']:>10.3f}{c['ens_off']:>15.3f}{c['flat']:>12.3f}")
    print("\nbranch decision scores, clean runs (mean over leagues)")
    print(f"{'branch':<13}{'score':>8}{'gate':>7}{'weight':>8}{'solo gain':>11}{'marg gain':>11}")
    for n, b in out["branches_clean"].items():
        sc = "n/a" if b["mean_score"] is None else f"{b['mean_score']:+.2f}"
        print(f"{n:<13}{sc:>8}{b['mean_gate']:>7.2f}{b['mean_weight']:>8.2f}{b['mean_solo_gain']:>+11.4f}{b['mean_marginal_gain']:>+11.4f}")
    if "verdict" in out:
        print("\npre-registered criteria")
        for k, v in out["verdict"].items():
            print(f"  {k} {'PASS' if v['passed'] else 'FAIL'}  {out['criteria'][k]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pre-registered branch-ensemble study.")
    ap.add_argument("--dev", action="store_true", help="use dev seeds; writes nothing")
    ap.add_argument("--quick", action="store_true", help="4 leagues; writes nothing")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    out = run_study(dev=args.dev, quick=args.quick)
    _print(out)
    path = args.out if args.out is not None else (None if (args.dev or args.quick) else DEFAULT_OUT)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, default=str)
        print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
