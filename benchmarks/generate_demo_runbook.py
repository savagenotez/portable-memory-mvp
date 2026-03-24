import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO_DIR = ROOT / "demo_script"
CUSTOMER_DIR = ROOT / "customer_deck"
CUSTOMER_PPT_DIR = ROOT / "customer_ppt"
INVESTOR_PPT_DIR = ROOT / "investor_ppt"
OUT_DIR = ROOT / "demo_runbook"

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

    demo_path = latest_file(DEMO_DIR, "live-demo-script-*.json")
    customer_path = latest_file(CUSTOMER_DIR, "customer-deck-summary-*.json")
    customer_ppt = latest_file(CUSTOMER_PPT_DIR, "portable-memory-customer-deck-*.pptx")
    investor_ppt = latest_file(INVESTOR_PPT_DIR, "portable-memory-investor-deck-*.pptx")

    demo = load_json(demo_path, {})
    customer = load_json(customer_path, {})

    if not demo or not customer:
        raise RuntimeError("Could not load demo script or customer deck summary.")

    run_id = demo.get("run_id") or "unknown-run"
    scenario = demo.get("selected_scenario", {})
    comparison = demo.get("comparison", {})
    flow = demo.get("demo_flow", [])

    robust = comparison.get("robustness_aware_pruning_mode", {})
    compression = comparison.get("compression_mode", {})
    hybrid = comparison.get("hybrid_mode", {})

    runbook = {
        "demo_runbook_version": "0.1.0",
        "run_id": run_id,
        "source_demo_script": demo_path.name,
        "source_customer_deck": customer_path.name,
        "customer_ppt": customer_ppt.name,
        "investor_ppt": investor_ppt.name,
        "opening_goal": "Show that robustness-aware pruning preserves continuity while reducing context more safely than simpler approaches.",
        "scenario": scenario,
        "presenter_setup": [
            f"Open customer deck: {customer_ppt.name}",
            f"Keep investor deck available for follow-up: {investor_ppt.name}",
            "Keep the demo script markdown open in a side pane or second monitor.",
            "Be ready to zoom in on the comparison previews for compression, hybrid, and robustness-aware pruning."
        ],
        "demo_sequence": [
            {
                "order": 1,
                "screen_action": "Show customer deck slide 1",
                "say": "We help AI systems keep continuity without dragging around bloated context.",
                "goal": "Set the audience frame fast."
            },
            {
                "order": 2,
                "screen_action": "Show customer deck slides 2 and 3",
                "say": "The core problem is that most systems either keep too much context or lose important meaning. Our approach rescues the needed context, then prunes only when meaning remains robust.",
                "goal": "Explain the problem and solution in plain language."
            },
            {
                "order": 3,
                "screen_action": "Show the selected benchmark scenario title and query",
                "say": f"We will use this benchmark scenario: {scenario.get('title')}. The question is: {scenario.get('query')}",
                "goal": "Ground the demo in one concrete case."
            },
            {
                "order": 4,
                "screen_action": "Show compression preview",
                "say": f"Compression mode gets retrieval hit rate {compression.get('retrieval_hit_rate')} and context reduction {compression.get('context_reduction_percent')}. It compresses, but it risks losing critical context structure.",
                "goal": "Establish the low-cost baseline."
            },
            {
                "order": 5,
                "screen_action": "Show hybrid preview",
                "say": f"Hybrid mode rescues important meaning, but context reduction is {hybrid.get('context_reduction_percent')}, which means it still carries too much baggage.",
                "goal": "Show rescue without disciplined pruning."
            },
            {
                "order": 6,
                "screen_action": "Show robustness-aware pruning preview",
                "say": f"Robustness-aware pruning keeps retrieval hit rate {robust.get('retrieval_hit_rate')} and soft hit rate {robust.get('soft_hit_rate')} while improving context reduction to {robust.get('context_reduction_percent')}.",
                "goal": "Show the main win clearly."
            },
            {
                "order": 7,
                "screen_action": "Show customer deck core metrics slide",
                "say": "This is the important point: we are not just compressing. We are preserving the minimum robust meaning needed for continuity.",
                "goal": "Turn the example into the product claim."
            },
            {
                "order": 8,
                "screen_action": "Show customer deck deployment-fit slide",
                "say": "This fits enterprise copilots, long-session assistants, support workflows, and memory middleware for AI products.",
                "goal": "Connect the demo to buyer use cases."
            },
            {
                "order": 9,
                "screen_action": "Show trustworthiness / validation slide",
                "say": "This policy also held up under adversarial validation, which matters because real users paraphrase and vary wording.",
                "goal": "Reinforce confidence."
            },
            {
                "order": 10,
                "screen_action": "Close on next-customer-step slide",
                "say": "The next step with a customer is simple: run this against their own traces and measure cost savings and continuity quality.",
                "goal": "Create a direct call to action."
            }
        ],
        "comparison_snapshot": {
            "compression_mode": {
                "retrieval_hit_rate": compression.get("retrieval_hit_rate"),
                "soft_hit_rate": compression.get("soft_hit_rate"),
                "context_reduction_percent": compression.get("context_reduction_percent"),
                "preview": compression.get("preview")
            },
            "hybrid_mode": {
                "retrieval_hit_rate": hybrid.get("retrieval_hit_rate"),
                "soft_hit_rate": hybrid.get("soft_hit_rate"),
                "context_reduction_percent": hybrid.get("context_reduction_percent"),
                "preview": hybrid.get("preview")
            },
            "robustness_aware_pruning_mode": {
                "retrieval_hit_rate": robust.get("retrieval_hit_rate"),
                "soft_hit_rate": robust.get("soft_hit_rate"),
                "context_reduction_percent": robust.get("context_reduction_percent"),
                "pruned_line_count": robust.get("pruned_line_count"),
                "controller_choice": robust.get("controller_choice"),
                "preview": robust.get("preview")
            }
        },
        "objection_handling": [
            {
                "objection": "Why not just summarize harder?",
                "response": "Because harder summarization often loses the exact constraints and identity details that matter next. This policy is designed to preserve robust meaning, not just shorten text."
            },
            {
                "objection": "Why is this better than retrieval alone?",
                "response": "Retrieval can bring back too much or the wrong thing. This controller rescues useful context and then prunes safely under robustness constraints."
            },
            {
                "objection": "How do you know it is reliable?",
                "response": "It was benchmarked across exact, soft, and adversarial checks, and robustness-aware pruning was unbeaten across the current scenario set."
            },
            {
                "objection": "What is the business value?",
                "response": "Lower context cost, stronger continuity, fewer dropped details, and a more trustworthy memory layer for assistants and copilots."
            }
        ],
        "presenter_notes": {
            "tone": [
                "Keep the explanation concrete and operational.",
                "Do not over-explain algorithms before the win is visible.",
                "Emphasize lower cost plus better continuity together."
            ],
            "timing": [
                "30 seconds for the problem.",
                "60 seconds for the scenario walkthrough.",
                "30 seconds for the metrics.",
                "30 seconds for use cases and call to action."
            ],
            "must_say_lines": [
                "This is minimum robust meaning for continuity.",
                "We are not just summarizing; we are preserving what matters under variation.",
                "The result is lower context cost without sacrificing continuity quality."
            ]
        }
    }

    json_path = OUT_DIR / f"demo-runbook-{run_id}.json"
    md_path = OUT_DIR / f"demo-runbook-{run_id}.md"

    save_json(json_path, runbook)

    lines = []
    lines.append("# Portable Memory MVP - Demo Runbook")
    lines.append("")
    lines.append(f"Run ID: `{run_id}`")
    lines.append(f"Customer deck: `{customer_ppt.name}`")
    lines.append(f"Investor deck: `{investor_ppt.name}`")
    lines.append("")
    lines.append("## Opening Goal")
    lines.append(runbook["opening_goal"])
    lines.append("")
    lines.append("## Scenario")
    lines.append(f"- Scenario ID: `{scenario.get('scenario_id')}`")
    lines.append(f"- Title: `{scenario.get('title')}`")
    lines.append(f"- Query: {scenario.get('query')}")
    lines.append(f"- Expected phrases: `{scenario.get('expected_phrases')}`")
    lines.append("")
    lines.append("## Presenter Setup")
    for item in runbook["presenter_setup"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Demo Sequence")
    for step in runbook["demo_sequence"]:
        lines.append(f"### Step {step['order']}")
        lines.append(f"- Screen action: {step['screen_action']}")
        lines.append(f"- Say: {step['say']}")
        lines.append(f"- Goal: {step['goal']}")
        lines.append("")
    lines.append("## Comparison Snapshot")
    for mode_name, vals in runbook["comparison_snapshot"].items():
        lines.append(f"### {mode_name}")
        lines.append(f"- Retrieval hit rate: `{vals.get('retrieval_hit_rate')}`")
        lines.append(f"- Soft hit rate: `{vals.get('soft_hit_rate')}`")
        lines.append(f"- Context reduction percent: `{vals.get('context_reduction_percent')}`")
        if vals.get("pruned_line_count") is not None:
            lines.append(f"- Pruned line count: `{vals.get('pruned_line_count')}`")
        if vals.get("controller_choice") is not None:
            lines.append(f"- Controller choice: `{vals.get('controller_choice')}`")
        lines.append("- Preview:")
        lines.append("")
        lines.append("```text")
        lines.append((vals.get("preview") or "")[:900])
        lines.append("```")
        lines.append("")
    lines.append("## Objection Handling")
    for item in runbook["objection_handling"]:
        lines.append(f"- Objection: {item['objection']}")
        lines.append(f"  - Response: {item['response']}")
    lines.append("")
    lines.append("## Presenter Notes")
    lines.append("### Tone")
    for item in runbook["presenter_notes"]["tone"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Timing")
    for item in runbook["presenter_notes"]["timing"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Must-Say Lines")
    for item in runbook["presenter_notes"]["must_say_lines"]:
        lines.append(f"- {item}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Demo runbook generated.")
    print(f"Source demo script: {demo_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Runbook scenario:")
    print(f"  {scenario.get('scenario_id')} :: {scenario.get('title')}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
