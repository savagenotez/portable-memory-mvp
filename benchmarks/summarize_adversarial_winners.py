import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ADV_DIR = ROOT / "adversarial"
OUT_DIR = ROOT / "adversarial_summary"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_adv_file():
    files = sorted(ADV_DIR.glob("adversarial-pruning-validation-*.json"))
    if not files:
        raise RuntimeError("No adversarial validation JSON files found.")
    return files[-1]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    adv_path = latest_adv_file()
    adv = load_json(adv_path, {})
    if not adv:
        raise RuntimeError("Could not load adversarial validation file.")

    scenario_reports = adv.get("scenario_reports", [])
    summary_by_mode = adv.get("summary_by_mode", {})

    winner_counts = {}
    winner_details = []

    for scenario in scenario_reports:
        winner = scenario.get("winner_by_adversarial_rate")
        title = scenario.get("title")
        scenario_id = scenario.get("scenario_id")
        mode_reports = scenario.get("mode_reports", [])

        if winner:
            winner_counts[winner] = winner_counts.get(winner, 0) + 1

        top_report = None
        for mr in mode_reports:
            if mr.get("mode") == winner:
                top_report = mr
                break

        winner_details.append({
            "scenario_id": scenario_id,
            "title": title,
            "winner_mode": winner,
            "winner_adversarial_variant_hit_rate": top_report.get("adversarial_variant_hit_rate") if top_report else None,
            "winner_soft_hit_rate": top_report.get("soft_hit_rate") if top_report else None,
            "winner_exact_hit_rate": top_report.get("exact_hit_rate") if top_report else None,
            "winner_context_reduction_percent": top_report.get("context_reduction_percent") if top_report else None,
        })

    ranked_winners = sorted(
        [{"mode": k, "win_count": v, **summary_by_mode.get(k, {})} for k, v in winner_counts.items()],
        key=lambda x: (-x["win_count"], -(x.get("avg_adversarial_variant_hit_rate") or -1), x["mode"])
    )

    out = {
        "adversarial_summary_version": "0.1.0",
        "source_adversarial_file": adv_path.name,
        "source_run_id": adv.get("source_run_id"),
        "timestamp": adv.get("timestamp"),
        "scenario_count": len(scenario_reports),
        "winner_counts_by_mode": winner_counts,
        "ranked_winners": ranked_winners,
        "winner_details": winner_details,
        "summary_by_mode": summary_by_mode,
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"adversarial-winner-summary-{run_id}.json"
    md_path = OUT_DIR / f"adversarial-winner-summary-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Adversarial Winner Summary")
    lines.append("")
    lines.append(f"- Source adversarial file: `{adv_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Scenario count: `{out['scenario_count']}`")
    lines.append("")
    lines.append("## Winners Ranked By Scenario Wins")
    lines.append("")
    for item in ranked_winners:
        lines.append(f"### {item['mode']}")
        lines.append(f"- Win count: `{item['win_count']}`")
        lines.append(f"- Avg adversarial variant hit rate: `{item.get('avg_adversarial_variant_hit_rate')}`")
        lines.append(f"- Avg soft hit rate: `{item.get('avg_soft_hit_rate')}`")
        lines.append(f"- Avg exact hit rate: `{item.get('avg_exact_hit_rate')}`")
        lines.append(f"- Avg context reduction percent: `{item.get('avg_context_reduction_percent')}`")
        lines.append("")

    lines.append("## Scenario-Level Winners")
    lines.append("")
    for item in winner_details:
        lines.append(f"### {item['title']}")
        lines.append(f"- Scenario ID: `{item['scenario_id']}`")
        lines.append(f"- Winner mode: `{item['winner_mode']}`")
        lines.append(f"- Winner adversarial variant hit rate: `{item['winner_adversarial_variant_hit_rate']}`")
        lines.append(f"- Winner soft hit rate: `{item['winner_soft_hit_rate']}`")
        lines.append(f"- Winner exact hit rate: `{item['winner_exact_hit_rate']}`")
        lines.append(f"- Winner context reduction percent: `{item['winner_context_reduction_percent']}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Adversarial winner summary completed.")
    print(f"Source adversarial file: {adv_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Winner counts by mode:")
    for item in ranked_winners:
        print(f"  {item['mode']}: {item['win_count']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
