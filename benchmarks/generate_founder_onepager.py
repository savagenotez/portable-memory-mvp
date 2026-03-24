import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
POLICY_DIR = ROOT / "policy_report"
ADV_DIR = ROOT / "adversarial_robustness"
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "founder_onepager"


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


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    policy_path = latest_file(POLICY_DIR, "robustness-aware-policy-report-*.json")
    adv_path = latest_file(ADV_DIR, "robustness-aware-pruning-validation-*.json")
    run_path = latest_file(RESULTS_DIR, "run-*.json")

    policy = load_json(policy_path, {})
    adv = load_json(adv_path, {})
    run = load_json(run_path, {})

    if not policy or not adv or not run:
        raise RuntimeError("Could not load one or more required source files.")

    exec_summary = policy.get("executive_summary", {})
    headline = exec_summary.get("headline_metrics", {})
    compare = policy.get("comparative_metrics", {})
    business = policy.get("business_value", {})
    overall = adv.get("overall", {})

    robust = compare.get("robustness_aware_pruning_mode", {})
    threshold = compare.get("threshold_gated_adaptive_mode", {})
    hybrid = compare.get("hybrid_mode", {})
    compression = compare.get("compression_mode", {})

    onepager = {
        "onepager_version": "0.1.0",
        "source_run_id": policy.get("source_run_id"),
        "source_policy_report": policy_path.name,
        "source_validation_report": adv_path.name,
        "headline": {
            "product_name": "Portable Memory MVP",
            "recommended_policy": exec_summary.get("recommended_policy"),
            "core_claim": "Robustness-aware pruning preserves continuity while shrinking context, and it remained unbeaten across the current adversarial benchmark suite.",
        },
        "key_metrics": {
            "retrieval_hit_rate": headline.get("retrieval_hit_rate"),
            "soft_hit_rate": headline.get("soft_hit_rate"),
            "context_reduction_percent": headline.get("context_reduction_percent"),
            "total_pruned_lines": headline.get("total_pruned_lines"),
            "unbeaten_scenarios": headline.get("unbeaten_scenarios"),
            "scenario_count": headline.get("scenario_count"),
        },
        "why_it_matters": [
            "Most memory systems either preserve signal but bloat context, or compress context but lose important meaning.",
            "This policy keeps the high-signal rescue behavior, then prunes only when robustness is preserved.",
            "The result is lower context cost without losing continuity quality on the tested scenarios.",
        ],
        "what_we_built": [
            "A rescue-and-prune memory policy for session continuity.",
            "A benchmark suite with exact, soft, and adversarial evaluation.",
            "An interpretable policy that protects exact recall, soft recall, and anchor-token overlap.",
        ],
        "competitive_positioning": {
            "robustness_aware_pruning_mode": robust,
            "threshold_gated_adaptive_mode": threshold,
            "hybrid_mode": hybrid,
            "compression_mode": compression,
        },
        "business_value": {
            "cost_savings": business.get("cost_value", []),
            "product_value": business.get("product_value", []),
            "research_value": business.get("research_value", []),
        },
        "founder_talking_points": [
            "We are not just summarizing context; we are preserving the minimum robust meaning needed for continuity.",
            "The system is benchmarked against multiple weaker policies and wins on the current suite.",
            "The policy is interpretable, measurable, and can be productized as a memory controller layer.",
            "This can support lower inference cost, longer usable sessions, and more trustworthy enterprise memory behavior.",
        ],
        "proof_points": {
            "unbeaten_scenarios": f"{overall.get('unbeaten_scenarios')} / {overall.get('scenario_count')}",
            "loss_counts_by_mode": overall.get("loss_counts_by_mode", {}),
            "recommended_policy": exec_summary.get("recommended_policy"),
        },
        "next_steps": [
            "Expand the adversarial suite and scenario coverage.",
            "Test the policy against live usage traces and token-cost accounting.",
            "Package the controller as a reusable module.",
            "Prepare a technical note and a business-facing pitch deck.",
        ],
    }

    run_id = onepager.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"founder-one-pager-{run_id}.json"
    md_path = OUT_DIR / f"founder-one-pager-{run_id}.md"

    save_json(json_path, onepager)

    lines = []
    lines.append("# Portable Memory MVP - Founder One-Pager")
    lines.append("")
    lines.append(f"Run ID: `{run_id}`")
    lines.append("")
    lines.append("## What it is")
    lines.append("")
    lines.append(onepager["headline"]["core_claim"])
    lines.append("")
    lines.append("## Key Metrics")
    lines.append("")
    lines.append(f"- Retrieval hit rate: `{onepager['key_metrics']['retrieval_hit_rate']}`")
    lines.append(f"- Soft hit rate: `{onepager['key_metrics']['soft_hit_rate']}`")
    lines.append(f"- Context reduction percent: `{onepager['key_metrics']['context_reduction_percent']}`")
    lines.append(f"- Total pruned lines: `{onepager['key_metrics']['total_pruned_lines']}`")
    lines.append(f"- Unbeaten scenarios: `{onepager['key_metrics']['unbeaten_scenarios']}` / `{onepager['key_metrics']['scenario_count']}`")
    lines.append("")
    lines.append("## Why it matters")
    lines.append("")
    for item in onepager["why_it_matters"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## What we built")
    lines.append("")
    for item in onepager["what_we_built"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Why this is better")
    lines.append("")
    for mode_name in [
        "robustness_aware_pruning_mode",
        "threshold_gated_adaptive_mode",
        "hybrid_mode",
        "compression_mode",
    ]:
        mode = onepager["competitive_positioning"].get(mode_name, {})
        lines.append(f"### {mode_name}")
        lines.append(f"- Retrieval hit rate: `{mode.get('retrieval_hit_rate')}`")
        lines.append(f"- Soft hit rate: `{mode.get('soft_hit_rate')}`")
        lines.append(f"- Context reduction percent: `{mode.get('context_reduction_percent')}`")
        lines.append("")
    lines.append("## Business value")
    lines.append("")
    lines.append("### Cost savings")
    for item in onepager["business_value"]["cost_savings"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Product value")
    for item in onepager["business_value"]["product_value"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Research value")
    for item in onepager["business_value"]["research_value"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Founder talking points")
    for item in onepager["founder_talking_points"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Proof points")
    lines.append(f"- Recommended policy: `{onepager['proof_points']['recommended_policy']}`")
    lines.append(f"- Unbeaten scenarios: `{onepager['proof_points']['unbeaten_scenarios']}`")
    lines.append(f"- Loss counts by mode: `{onepager['proof_points']['loss_counts_by_mode']}`")
    lines.append("")
    lines.append("## Next steps")
    for item in onepager["next_steps"]:
        lines.append(f"- {item}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Founder one-pager generated.")
    print(f"Source policy report: {policy_path}")
    print(f"Source validation report: {adv_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Headline:")
    print(f"  recommended_policy = {onepager['headline']['recommended_policy']}")
    print(f"  retrieval_hit_rate = {onepager['key_metrics']['retrieval_hit_rate']}")
    print(f"  soft_hit_rate = {onepager['key_metrics']['soft_hit_rate']}")
    print(f"  context_reduction_percent = {onepager['key_metrics']['context_reduction_percent']}")
    print(f"  unbeaten_scenarios = {onepager['key_metrics']['unbeaten_scenarios']} / {onepager['key_metrics']['scenario_count']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
