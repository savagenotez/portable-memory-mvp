import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY_DIR = ROOT / "policy_report"
ADV_DIR = ROOT / "adversarial_robustness"
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "customer_deck"

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

    policy_path = latest_file(POLICY_DIR, "robustness-aware-policy-report-*.json")
    adv_path = latest_file(ADV_DIR, "robustness-aware-pruning-validation-*.json")
    run_path = latest_file(RESULTS_DIR, "run-*.json")

    print(f"Using policy report: {policy_path}")
    print(f"Using adversarial validation: {adv_path}")
    print(f"Using benchmark run: {run_path}")

    policy = load_json(policy_path, {})
    adv = load_json(adv_path, {})
    run = load_json(run_path, {})

    if not policy or not adv or not run:
        raise RuntimeError("Could not load one or more required source files.")

    exec_summary = policy.get("executive_summary", {})
    headline = exec_summary.get("headline_metrics", {})
    compare = policy.get("comparative_metrics", {})
    overall = adv.get("overall", {})
    run_id = policy.get("source_run_id") or run.get("run_id") or "unknown-run"

    deck = {
        "deck_version": "0.1.0",
        "run_id": run_id,
        "source_files": {
            "policy_report": policy_path.name,
            "adversarial_validation": adv_path.name,
            "benchmark_run": run_path.name,
        },
        "slides": [
            {
                "slide_number": 1,
                "title": "Portable Memory MVP",
                "subtitle": "Customer Deck",
                "bullets": [
                    "Keep conversation continuity without dragging around bloated context.",
                    "Reduce context cost while preserving important meaning.",
                    "Designed for AI assistants, copilots, and enterprise memory workflows."
                ]
            },
            {
                "slide_number": 2,
                "title": "Customer Problem",
                "bullets": [
                    "AI sessions forget important context or become too expensive to maintain.",
                    "Summaries often drop the very details users need next.",
                    "Teams need continuity that is cheaper, safer, and easier to trust."
                ]
            },
            {
                "slide_number": 3,
                "title": "What We Do",
                "bullets": [
                    "We rescue the high-signal context that matters.",
                    "We prune only when meaning and robustness are preserved.",
                    "The result is continuity with less wasted context."
                ]
            },
            {
                "slide_number": 4,
                "title": "Customer Outcomes",
                "bullets": [
                    "Lower context usage per continued session.",
                    "Better retention of important project details.",
                    "Fewer dropped instructions, constraints, and identity details.",
                    "More predictable memory behavior across long interactions."
                ]
            },
            {
                "slide_number": 5,
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
                "slide_number": 6,
                "title": "Why Customers Benefit",
                "bullets": [
                    "You get lower cost without sacrificing continuity quality.",
                    "You keep robust meaning, not just compressed wording.",
                    "You reduce the risk of losing critical context under paraphrase or variation."
                ]
            },
            {
                "slide_number": 7,
                "title": "Compared to Simpler Approaches",
                "table_like": {
                    "robustness_aware_pruning_mode": short_mode(compare.get("robustness_aware_pruning_mode", {})),
                    "threshold_gated_adaptive_mode": short_mode(compare.get("threshold_gated_adaptive_mode", {})),
                    "hybrid_mode": short_mode(compare.get("hybrid_mode", {})),
                    "compression_mode": short_mode(compare.get("compression_mode", {})),
                }
            },
            {
                "slide_number": 8,
                "title": "Where It Fits",
                "bullets": [
                    "Enterprise copilots",
                    "Long-session assistants",
                    "Knowledge work orchestration",
                    "Support and success copilots",
                    "Memory middleware for AI applications"
                ]
            },
            {
                "slide_number": 9,
                "title": "Why It Is Trustworthy",
                "bullets": [
                    f"Adversarial validation unbeaten scenarios: {overall.get('unbeaten_scenarios')} / {overall.get('scenario_count')}",
                    f"Loss counts by mode: {overall.get('loss_counts_by_mode', {})}",
                    "Protected against over-pruning, token-overlap loss, and paraphrase fragility."
                ]
            },
            {
                "slide_number": 10,
                "title": "Next Customer Step",
                "bullets": [
                    "Run the controller on your own conversation traces.",
                    "Measure token and cost savings against your current method.",
                    "Compare continuity quality on real workflows.",
                    "Decide whether to deploy as memory middleware or premium capability."
                ]
            }
        ]
    }

    json_path = OUT_DIR / f"customer-deck-summary-{run_id}.json"
    md_path = OUT_DIR / f"customer-deck-summary-{run_id}.md"

    save_json(json_path, deck)

    lines = []
    lines.append("# Portable Memory MVP - Customer Deck Summary")
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

    print("Customer deck summary generated.")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
