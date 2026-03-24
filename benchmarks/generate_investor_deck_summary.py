import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FOUNDER_DIR = ROOT / "founder_onepager"
POLICY_DIR = ROOT / "policy_report"
ADV_DIR = ROOT / "adversarial_robustness"
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "investor_deck"


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


def short_mode(mode):
    return {
        "retrieval_hit_rate": mode.get("retrieval_hit_rate"),
        "soft_hit_rate": mode.get("soft_hit_rate"),
        "context_reduction_percent": mode.get("context_reduction_percent"),
        "repeated_explanation_items_removed": mode.get("repeated_explanation_items_removed"),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    founder_path = latest_file(FOUNDER_DIR, "founder-one-pager-*.json")
    policy_path = latest_file(POLICY_DIR, "robustness-aware-policy-report-*.json")
    adv_path = latest_file(ADV_DIR, "robustness-aware-pruning-validation-*.json")
    run_path = latest_file(RESULTS_DIR, "run-*.json")

    founder = load_json(founder_path, {})
    policy = load_json(policy_path, {})
    adv = load_json(adv_path, {})
    run = load_json(run_path, {})

    if not founder or not policy or not adv or not run:
        raise RuntimeError("Could not load one or more required source files.")

    exec_summary = policy.get("executive_summary", {})
    headline = exec_summary.get("headline_metrics", {})
    compare = policy.get("comparative_metrics", {})
    business = policy.get("business_value", {})
    overall = adv.get("overall", {})
    run_id = policy.get("source_run_id") or run.get("run_id") or "unknown-run"

    deck = {
        "deck_version": "0.1.0",
        "run_id": run_id,
        "source_files": {
            "founder_onepager": founder_path.name,
            "policy_report": policy_path.name,
            "adversarial_validation": adv_path.name,
            "benchmark_run": run_path.name,
        },
        "slides": [
            {
                "slide_number": 1,
                "title": "Portable Memory MVP",
                "subtitle": "Investor Deck Summary",
                "bullets": [
                    "Robustness-aware pruning preserves continuity while shrinking context.",
                    "Current recommended policy: robustness_aware_pruning_mode.",
                    "Validated against benchmark and adversarial scenario suite."
                ]
            },
            {
                "slide_number": 2,
                "title": "Problem",
                "bullets": [
                    "Memory systems often trade off badly: either preserve signal and bloat context, or compress and lose meaning.",
                    "Long-session continuity becomes expensive, brittle, or both.",
                    "Enterprise memory needs lower cost with stronger continuity guarantees."
                ]
            },
            {
                "slide_number": 3,
                "title": "Solution",
                "bullets": [
                    "Use a rescue-and-prune controller rather than static summarization.",
                    "Start from phrase-saver rescue context.",
                    "Prune only when exact recall, soft recall, and overlap robustness remain intact."
                ]
            },
            {
                "slide_number": 4,
                "title": "Core Metrics",
                "bullets": [
                    f"Retrieval hit rate: {headline.get('retrieval_hit_rate')}",
                    f"Soft hit rate: {headline.get('soft_hit_rate')}",
                    f"Context reduction percent: {headline.get('context_reduction_percent')}",
                    f"Total pruned lines: {headline.get('total_pruned_lines')}",
                    f"Unbeaten scenarios: {headline.get('unbeaten_scenarios')} / {headline.get('scenario_count')}",
                ]
            },
            {
                "slide_number": 5,
                "title": "Why We Win",
                "bullets": [
                    "Not just summarization: minimum robust meaning for continuity.",
                    "Interpretable policy with explicit protected properties.",
                    "Preserves high-signal continuity while reducing context cost."
                ]
            },
            {
                "slide_number": 6,
                "title": "Comparative Performance",
                "table_like": {
                    "robustness_aware_pruning_mode": short_mode(compare.get("robustness_aware_pruning_mode", {})),
                    "threshold_gated_adaptive_mode": short_mode(compare.get("threshold_gated_adaptive_mode", {})),
                    "hybrid_mode": short_mode(compare.get("hybrid_mode", {})),
                    "phrase_saver_per_byte_mode": short_mode(compare.get("phrase_saver_per_byte_mode", {})),
                    "compression_mode": short_mode(compare.get("compression_mode", {})),
                }
            },
            {
                "slide_number": 7,
                "title": "Defensibility",
                "bullets": [
                    f"Adversarial validation unbeaten scenarios: {overall.get('unbeaten_scenarios')} / {overall.get('scenario_count')}",
                    f"Loss counts by mode: {overall.get('loss_counts_by_mode', {})}",
                    "Protected against over-pruning, loss of token overlap, and paraphrase fragility."
                ]
            },
            {
                "slide_number": 8,
                "title": "Business Value",
                "bullets": (
                    business.get("cost_value", []) +
                    business.get("product_value", []) +
                    business.get("research_value", [])
                )
            },
            {
                "slide_number": 9,
                "title": "Go-To-Market Angle",
                "bullets": [
                    "Memory controller layer for AI assistants and enterprise copilots.",
                    "Value proposition: lower inference cost + stronger session continuity.",
                    "Can be sold as infra, middleware, or premium memory capability."
                ]
            },
            {
                "slide_number": 10,
                "title": "Next Steps",
                "bullets": [
                    "Expand adversarial suite and live usage trace testing.",
                    "Package controller as reusable module.",
                    "Build investor deck / demo narrative around benchmark wins and cost savings.",
                    "Prepare technical note and commercialization roadmap."
                ]
            }
        ]
    }

    json_path = OUT_DIR / f"investor-deck-summary-{run_id}.json"
    md_path = OUT_DIR / f"investor-deck-summary-{run_id}.md"

    save_json(json_path, deck)

    lines = []
    lines.append("# Portable Memory MVP - Investor Deck Summary")
    lines.append("")
    lines.append(f"Run ID: `{run_id}`")
    lines.append("")
    for slide in deck["slides"]:
        lines.append(f"## Slide {slide['slide_number']}: {slide['title']}")
        if slide.get("subtitle"):
            lines.append(f"**{slide['subtitle']}**")
        lines.append("")
        if "bullets" in slide:
            for bullet in slide["bullets"]:
                lines.append(f"- {bullet}")
        if "table_like" in slide:
            for mode_name, vals in slide["table_like"].items():
                lines.append(f"### {mode_name}")
                for k, v in vals.items():
                    lines.append(f"- {k}: `{v}`")
                lines.append("")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Investor deck summary generated.")
    print(f"Source founder one-pager: {founder_path}")
    print(f"Source policy report: {policy_path}")
    print(f"Source validation report: {adv_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Headline:")
    print(f"  recommended_policy = {exec_summary.get('recommended_policy')}")
    print(f"  retrieval_hit_rate = {headline.get('retrieval_hit_rate')}")
    print(f"  soft_hit_rate = {headline.get('soft_hit_rate')}")
    print(f"  context_reduction_percent = {headline.get('context_reduction_percent')}")
    print(f"  unbeaten_scenarios = {headline.get('unbeaten_scenarios')} / {headline.get('scenario_count')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
