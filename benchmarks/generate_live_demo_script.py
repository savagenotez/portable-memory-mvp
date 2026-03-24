import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
POLICY_DIR = ROOT / "policy_report"
CUSTOMER_DIR = ROOT / "customer_deck"
OUT_DIR = ROOT / "demo_script"

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

def mode_map(scenario):
    return {m.get("mode"): m for m in scenario.get("modes", [])}

def choose_demo_scenario(run):
    candidates = []
    for s in run.get("scenario_results", []):
        modes = mode_map(s)
        robust = modes.get("robustness_aware_pruning_mode", {})
        compression = modes.get("compression_mode", {})
        hybrid = modes.get("hybrid_mode", {})

        robust_hit = robust.get("retrieval_hit_rate")
        robust_red = robust.get("context_reduction_percent")
        compression_hit = compression.get("retrieval_hit_rate")
        hybrid_hit = hybrid.get("retrieval_hit_rate")

        score = 0.0
        if robust_hit is not None:
            score += robust_hit * 100
        if robust_red is not None:
            score += max(0, robust_red)
        if compression_hit is not None and robust_hit is not None:
            score += max(0, (robust_hit - compression_hit) * 50)
        if hybrid_hit is not None and robust_red is not None:
            score += max(0, robust_red)

        candidates.append((score, s))

    if not candidates:
        raise RuntimeError("No benchmark scenarios found in latest run.")
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_file(RESULTS_DIR, "run-*.json")
    policy_path = latest_file(POLICY_DIR, "robustness-aware-policy-report-*.json")
    customer_path = latest_file(CUSTOMER_DIR, "customer-deck-summary-*.json")

    run = load_json(run_path, {})
    policy = load_json(policy_path, {})
    customer = load_json(customer_path, {})

    if not run or not policy or not customer:
        raise RuntimeError("Could not load one or more required source files.")

    scenario = choose_demo_scenario(run)
    modes = mode_map(scenario)

    robust = modes.get("robustness_aware_pruning_mode", {})
    compression = modes.get("compression_mode", {})
    hybrid = modes.get("hybrid_mode", {})

    report = {
        "demo_script_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_policy_report": policy_path.name,
        "source_customer_deck": customer_path.name,
        "run_id": run.get("run_id"),
        "selected_scenario": {
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "query": scenario.get("query"),
            "expected_phrases": scenario.get("expected_phrases", []),
        },
        "comparison": {
            "compression_mode": {
                "retrieval_hit_rate": compression.get("retrieval_hit_rate"),
                "soft_hit_rate": compression.get("soft_hit_rate"),
                "context_reduction_percent": compression.get("context_reduction_percent"),
                "preview": compression.get("preview"),
            },
            "hybrid_mode": {
                "retrieval_hit_rate": hybrid.get("retrieval_hit_rate"),
                "soft_hit_rate": hybrid.get("soft_hit_rate"),
                "context_reduction_percent": hybrid.get("context_reduction_percent"),
                "preview": hybrid.get("preview"),
            },
            "robustness_aware_pruning_mode": {
                "retrieval_hit_rate": robust.get("retrieval_hit_rate"),
                "soft_hit_rate": robust.get("soft_hit_rate"),
                "context_reduction_percent": robust.get("context_reduction_percent"),
                "preview": robust.get("preview"),
                "pruned_line_count": robust.get("pruned_line_count"),
                "controller_choice": robust.get("controller_choice"),
            },
        },
        "demo_talk_track": [
            "Start by stating the problem: memory systems either keep too much context or lose important meaning.",
            "Show the selected scenario and the user question.",
            "Show compression mode first and explain what it saves, but point out what it risks losing.",
            "Show hybrid mode next and explain that it rescues meaning, but grows context too much.",
            "Show robustness-aware pruning last and explain that it keeps the rescue value while cutting context safely.",
            "Call out the exact metrics on screen: retrieval hit rate, soft hit rate, and context reduction percent.",
            "Close with the message that this is minimum robust meaning for continuity, not naive summarization."
        ],
        "demo_flow": [
            {
                "step": 1,
                "title": "Frame the problem",
                "script": "We need memory that preserves continuity without dragging unnecessary context forward."
            },
            {
                "step": 2,
                "title": "Introduce the scenario",
                "script": f"Here is a real benchmark scenario: {scenario.get('title')}. The query is: {scenario.get('query')}"
            },
            {
                "step": 3,
                "title": "Show compression baseline",
                "script": f"Compression mode gets hit rate {compression.get('retrieval_hit_rate')} with context reduction {compression.get('context_reduction_percent')}. It compresses, but risks losing meaning.",
                "preview": compression.get("preview", "")[:900]
            },
            {
                "step": 4,
                "title": "Show hybrid rescue",
                "script": f"Hybrid mode rescues meaning with hit rate {hybrid.get('retrieval_hit_rate')}, but context reduction is {hybrid.get('context_reduction_percent')}, which means it is still bloated.",
                "preview": hybrid.get("preview", "")[:900]
            },
            {
                "step": 5,
                "title": "Show robustness-aware pruning",
                "script": f"Robustness-aware pruning keeps hit rate {robust.get('retrieval_hit_rate')} and soft hit rate {robust.get('soft_hit_rate')} while reaching context reduction {robust.get('context_reduction_percent')}.",
                "preview": robust.get("preview", "")[:900]
            },
            {
                "step": 6,
                "title": "Explain why it wins",
                "script": "It starts from rescued context, then prunes only when exact recall, soft recall, and overlap robustness remain intact."
            },
            {
                "step": 7,
                "title": "Close with business value",
                "script": "That means lower context cost, stronger continuity, and more trustworthy memory behavior for real AI products."
            }
        ]
    }

    run_id = report.get("run_id") or "unknown-run"
    json_path = OUT_DIR / f"live-demo-script-{run_id}.json"
    md_path = OUT_DIR / f"live-demo-script-{run_id}.md"

    save_json(json_path, report)

    lines = []
    lines.append("# Portable Memory MVP - Live Demo Script")
    lines.append("")
    lines.append(f"Run ID: `{run_id}`")
    lines.append(f"Scenario: `{report['selected_scenario']['title']}`")
    lines.append("")
    lines.append("## Selected Scenario")
    lines.append(f"- Scenario ID: `{report['selected_scenario']['scenario_id']}`")
    lines.append(f"- Query: {report['selected_scenario']['query']}")
    lines.append(f"- Expected phrases: `{report['selected_scenario']['expected_phrases']}`")
    lines.append("")
    lines.append("## Talk Track")
    for item in report["demo_talk_track"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Demo Flow")
    for step in report["demo_flow"]:
        lines.append(f"### Step {step['step']}: {step['title']}")
        lines.append(f"- Script: {step['script']}")
        if step.get("preview"):
            lines.append("- Preview:")
            lines.append("")
            lines.append("```text")
            lines.append(step["preview"])
            lines.append("```")
        lines.append("")
    lines.append("## Comparison Snapshot")
    for mode_name, vals in report["comparison"].items():
        lines.append(f"### {mode_name}")
        lines.append(f"- Retrieval hit rate: `{vals.get('retrieval_hit_rate')}`")
        lines.append(f"- Soft hit rate: `{vals.get('soft_hit_rate')}`")
        lines.append(f"- Context reduction percent: `{vals.get('context_reduction_percent')}`")
        if vals.get("pruned_line_count") is not None:
            lines.append(f"- Pruned line count: `{vals.get('pruned_line_count')}`")
        if vals.get("controller_choice") is not None:
            lines.append(f"- Controller choice: `{vals.get('controller_choice')}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Live demo script generated.")
    print(f"Source benchmark run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print("Demo scenario:")
    print(f"  {report['selected_scenario']['scenario_id']} :: {report['selected_scenario']['title']}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
