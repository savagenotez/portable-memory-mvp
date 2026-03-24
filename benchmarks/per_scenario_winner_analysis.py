import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
ANALYSIS_DIR = ROOT / "analysis"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_run_file():
    files = sorted(RESULTS_DIR.glob("run-*.json"))
    if not files:
        raise RuntimeError("No benchmark run files found.")
    return files[-1]


def mode_map(scenario):
    out = {}
    for mode in scenario.get("modes", []):
        out[mode.get("mode")] = mode
    return out


def dominance_score(mode):
    hit = mode.get("retrieval_hit_rate")
    red = mode.get("context_reduction_percent")
    if hit is None:
        hit = -999.0
    if red is None:
        red = -999.0
    return (hit, red)


def best_by_recall_then_compactness(modes):
    vals = []
    for name, mode in modes.items():
        hit = mode.get("retrieval_hit_rate")
        red = mode.get("context_reduction_percent")
        vals.append((-(hit if hit is not None else -999.0), -(red if red is not None else -999.0), name))
    vals.sort()
    return vals[0][2]


def best_compact_above_threshold(modes, threshold=0.90):
    candidates = []
    for name, mode in modes.items():
        hit = mode.get("retrieval_hit_rate")
        red = mode.get("context_reduction_percent")
        if hit is None or red is None:
            continue
        if hit >= threshold:
            candidates.append((-red, name))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def safest_mode(modes):
    candidates = []
    for name, mode in modes.items():
        hit = mode.get("retrieval_hit_rate")
        removed = mode.get("repeated_explanation_items_removed")
        red = mode.get("context_reduction_percent")
        candidates.append((
            -(hit if hit is not None else -999.0),
            -(removed if removed is not None else -999.0),
            -(red if red is not None else -999.0),
            name
        ))
    candidates.sort()
    return candidates[0][3]


def cheapest_mode(modes):
    candidates = []
    for name, mode in modes.items():
        red = mode.get("context_reduction_percent")
        hit = mode.get("retrieval_hit_rate")
        candidates.append((
            -(red if red is not None else -999.0),
            -(hit if hit is not None else -999.0),
            name
        ))
    candidates.sort()
    return candidates[0][2]


def compare_pair(m1, m2):
    a = m1.get("retrieval_hit_rate")
    b = m2.get("retrieval_hit_rate")
    ar = m1.get("context_reduction_percent")
    br = m2.get("context_reduction_percent")
    return {
        "hit_rate_delta": None if a is None or b is None else round(a - b, 4),
        "context_reduction_delta": None if ar is None or br is None else round(ar - br, 2),
    }


def main():
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_run_file()
    run = load_json(run_path, {})
    if not run:
        raise RuntimeError("Could not load latest run JSON.")

    scenario_reports = []
    win_counts = {
        "best_overall": {},
        "best_above_threshold": {},
        "safest": {},
        "cheapest": {},
    }

    for scenario in run.get("scenario_results", []):
        modes = mode_map(scenario)

        best_overall = best_by_recall_then_compactness(modes)
        best_threshold = best_compact_above_threshold(modes, threshold=0.90)
        safest = safest_mode(modes)
        cheapest = cheapest_mode(modes)

        for bucket, winner in [
            ("best_overall", best_overall),
            ("best_above_threshold", best_threshold),
            ("safest", safest),
            ("cheapest", cheapest),
        ]:
            if winner:
                win_counts[bucket][winner] = win_counts[bucket].get(winner, 0) + 1

        key_modes = {}
        for name in [
            "compression_mode",
            "hybrid_mode",
            "phrase_saver_per_byte_mode",
            "threshold_gated_adaptive_mode",
            "scenario_classifier_mode",
        ]:
            if name in modes:
                key_modes[name] = {
                    "retrieval_hit_rate": modes[name].get("retrieval_hit_rate"),
                    "context_reduction_percent": modes[name].get("context_reduction_percent"),
                    "repeated_explanation_items_removed": modes[name].get("repeated_explanation_items_removed"),
                    "controller_choice": modes[name].get("controller_choice"),
                    "classifier_label": modes[name].get("classifier_label"),
                }

        scenario_reports.append({
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "best_overall": best_overall,
            "best_above_threshold": best_threshold,
            "safest": safest,
            "cheapest": cheapest,
            "key_modes": key_modes,
            "comparisons": {
                "threshold_vs_hybrid": compare_pair(
                    modes.get("threshold_gated_adaptive_mode", {}),
                    modes.get("hybrid_mode", {})
                ),
                "classifier_vs_threshold": compare_pair(
                    modes.get("scenario_classifier_mode", {}),
                    modes.get("threshold_gated_adaptive_mode", {})
                ),
                "compression_vs_threshold": compare_pair(
                    modes.get("compression_mode", {}),
                    modes.get("threshold_gated_adaptive_mode", {})
                ),
            }
        })

    out = {
        "analysis_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "win_counts": win_counts,
        "scenario_reports": scenario_reports
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = ANALYSIS_DIR / f"per-scenario-winners-{run_id}.json"
    md_path = ANALYSIS_DIR / f"per-scenario-winners-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Per-Scenario Winner Analysis")
    lines.append("")
    lines.append(f"- Source run: `{run_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append("")

    lines.append("## Win Counts")
    lines.append("")
    for bucket, winners in win_counts.items():
        lines.append(f"### {bucket}")
        if winners:
            for name, count in sorted(winners.items(), key=lambda x: (-x[1], x[0])):
                lines.append(f"- `{name}`: {count}")
        else:
            lines.append("- none")
        lines.append("")

    for report in scenario_reports:
        lines.append(f"## {report['title']}")
        lines.append("")
        lines.append(f"- Scenario ID: `{report['scenario_id']}`")
        lines.append(f"- Best overall: `{report['best_overall']}`")
        lines.append(f"- Best above threshold: `{report['best_above_threshold']}`")
        lines.append(f"- Safest: `{report['safest']}`")
        lines.append(f"- Cheapest: `{report['cheapest']}`")
        lines.append("")
        lines.append("### Key modes")
        for mode_name, mode in report["key_modes"].items():
            lines.append(
                f"- `{mode_name}` | hit={mode.get('retrieval_hit_rate')} | reduction={mode.get('context_reduction_percent')} | removed={mode.get('repeated_explanation_items_removed')} | choice={mode.get('controller_choice')} | label={mode.get('classifier_label')}"
            )
        lines.append("")
        lines.append("### Comparisons")
        for comp_name, comp in report["comparisons"].items():
            lines.append(
                f"- `{comp_name}` | hit_delta={comp.get('hit_rate_delta')} | reduction_delta={comp.get('context_reduction_delta')}"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Per-scenario winner analysis completed.")
    print(f"Source run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
