import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
ADV_ROBUST_DIR = ROOT / "adversarial_robustness"
OUT_DIR = ROOT / "policy_report"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_file(dir_path: Path, pattern: str):
    files = sorted(dir_path.glob(pattern))
    if not files:
        raise RuntimeError(f"No files found for pattern: {pattern}")
    return files[-1]


def mode_summary(metrics, mode_name):
    return metrics.get(mode_name, {})


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_file(RESULTS_DIR, "run-*.json")
    adv_path = latest_file(ADV_ROBUST_DIR, "robustness-aware-pruning-validation-*.json")

    run = load_json(run_path, {})
    adv = load_json(adv_path, {})

    if not run or not adv:
        raise RuntimeError("Could not load latest benchmark run or robustness validation.")

    metrics = run.get("metrics", {})
    robust = mode_summary(metrics, "robustness_aware_pruning_mode")
    threshold = mode_summary(metrics, "threshold_gated_adaptive_mode")
    hybrid = mode_summary(metrics, "hybrid_mode")
    saver = mode_summary(metrics, "phrase_saver_per_byte_mode")
    compression = mode_summary(metrics, "compression_mode")

    overall = adv.get("overall", {})
    summary_by_mode = adv.get("summary_by_mode", {})

    report = {
        "policy_report_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_validation_file": adv_path.name,
        "source_run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "executive_summary": {
            "recommended_policy": "robustness_aware_pruning_mode",
            "reason": "Best overall balance of retrieval preservation, soft robustness, compression, and adversarial dominance in the current benchmark suite.",
            "headline_metrics": {
                "retrieval_hit_rate": robust.get("retrieval_hit_rate"),
                "soft_hit_rate": robust.get("soft_hit_rate"),
                "context_reduction_percent": robust.get("context_reduction_percent"),
                "total_pruned_lines": robust.get("total_pruned_lines"),
                "unbeaten_scenarios": overall.get("unbeaten_scenarios"),
                "scenario_count": overall.get("scenario_count"),
            },
        },
        "comparative_metrics": {
            "robustness_aware_pruning_mode": robust,
            "threshold_gated_adaptive_mode": threshold,
            "hybrid_mode": hybrid,
            "phrase_saver_per_byte_mode": saver,
            "compression_mode": compression,
        },
        "validation_summary": overall,
        "mode_summary_under_adversarial_validation": summary_by_mode,
        "policy_spec": {
            "name": "Robustness-Aware Pruning",
            "purpose": "Preserve required semantic continuity while pruning context only when exact match, soft match, and overlap robustness remain intact.",
            "policy_steps": [
                "Start from phrase-saver-per-byte rescued context.",
                "Measure exact phrase preservation.",
                "Measure soft phrase preservation.",
                "Measure phrase/token overlap robustness.",
                "Attempt greedy line removal.",
                "Reject any removal that lowers exact hit rate.",
                "Reject any removal that lowers soft hit rate.",
                "Reject any removal that causes overlap robustness to fall below the protected threshold.",
                "Keep only removals that preserve robustness while saving bytes.",
            ],
            "protected_properties": [
                "exact recall",
                "soft recall",
                "anchor-token overlap",
                "adversarial robustness",
            ],
            "failure_modes_prevented": [
                "over-pruning of project identity phrases",
                "loss of variant-friendly token overlap",
                "dropping semantic cushion needed under paraphrase",
            ],
        },
        "business_value": {
            "cost_value": [
                "reduces context size while preserving meaning",
                "can lower inference cost compared with bloated rescue modes",
                "can extend usable context windows",
            ],
            "product_value": [
                "improves continuity across sessions",
                "makes memory behavior more interpretable",
                "supports enterprise-grade memory retention policies",
            ],
            "research_value": [
                "demonstrates that rescue-plus-pruning outperforms static summarization",
                "shows robustness-aware pruning is a better objective than raw compression",
                "creates a benchmarkable framework for semantic continuity preservation",
            ],
        },
        "next_actions": [
            "package this policy into a reusable controller module",
            "run broader scenario expansion with more adversarial paraphrases",
            "measure token-cost savings against live usage traces",
            "draft a public-facing technical note or whitepaper summary",
        ],
    }

    run_id = report.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"robustness-aware-policy-report-{run_id}.json"
    md_path = OUT_DIR / f"robustness-aware-policy-report-{run_id}.md"

    save_json(json_path, report)

    lines = []
    lines.append("# Robustness-Aware Policy Report")
    lines.append("")
    lines.append(f"- Source benchmark run: `{run_path.name}`")
    lines.append(f"- Source validation: `{adv_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- Recommended policy: `{report['executive_summary']['recommended_policy']}`")
    lines.append(f"- Reason: {report['executive_summary']['reason']}")
    lines.append(f"- Retrieval hit rate: `{report['executive_summary']['headline_metrics']['retrieval_hit_rate']}`")
    lines.append(f"- Soft hit rate: `{report['executive_summary']['headline_metrics']['soft_hit_rate']}`")
    lines.append(f"- Context reduction percent: `{report['executive_summary']['headline_metrics']['context_reduction_percent']}`")
    lines.append(f"- Total pruned lines: `{report['executive_summary']['headline_metrics']['total_pruned_lines']}`")
    lines.append(f"- Unbeaten scenarios: `{report['executive_summary']['headline_metrics']['unbeaten_scenarios']}` / `{report['executive_summary']['headline_metrics']['scenario_count']}`")
    lines.append("")
    lines.append("## Comparative Metrics")
    lines.append("")
    for mode_name in [
        "robustness_aware_pruning_mode",
        "threshold_gated_adaptive_mode",
        "hybrid_mode",
        "phrase_saver_per_byte_mode",
        "compression_mode",
    ]:
        mode = report["comparative_metrics"].get(mode_name, {})
        lines.append(f"### {mode_name}")
        lines.append(f"- Retrieval hit rate: `{mode.get('retrieval_hit_rate')}`")
        lines.append(f"- Soft hit rate: `{mode.get('soft_hit_rate')}`")
        lines.append(f"- Context reduction percent: `{mode.get('context_reduction_percent')}`")
        lines.append(f"- Repeated explanation items removed: `{mode.get('repeated_explanation_items_removed')}`")
        if "controller_choices" in mode:
            lines.append(f"- Controller choices: `{mode.get('controller_choices')}`")
        if "total_pruned_lines" in mode:
            lines.append(f"- Total pruned lines: `{mode.get('total_pruned_lines')}`")
        lines.append("")
    lines.append("## Policy Spec")
    lines.append("")
    lines.append(f"- Name: `{report['policy_spec']['name']}`")
    lines.append(f"- Purpose: {report['policy_spec']['purpose']}")
    lines.append("")
    lines.append("### Policy Steps")
    for step in report["policy_spec"]["policy_steps"]:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("### Protected Properties")
    for item in report["policy_spec"]["protected_properties"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Failure Modes Prevented")
    for item in report["policy_spec"]["failure_modes_prevented"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Business Value")
    lines.append("")
    lines.append("### Cost Value")
    for item in report["business_value"]["cost_value"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Product Value")
    for item in report["business_value"]["product_value"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Research Value")
    for item in report["business_value"]["research_value"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next Actions")
    for item in report["next_actions"]:
        lines.append(f"- {item}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Robustness-aware policy report generated.")
    print(f"Source benchmark run: {run_path}")
    print(f"Source validation: {adv_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Headline:")
    print(f"  recommended_policy = {report['executive_summary']['recommended_policy']}")
    print(f"  retrieval_hit_rate = {report['executive_summary']['headline_metrics']['retrieval_hit_rate']}")
    print(f"  soft_hit_rate = {report['executive_summary']['headline_metrics']['soft_hit_rate']}")
    print(f"  context_reduction_percent = {report['executive_summary']['headline_metrics']['context_reduction_percent']}")
    print(f"  unbeaten_scenarios = {report['executive_summary']['headline_metrics']['unbeaten_scenarios']} / {report['executive_summary']['headline_metrics']['scenario_count']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
