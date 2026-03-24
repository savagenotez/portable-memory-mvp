import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOUNDER_DIR = ROOT / "founder_onepager"
INVESTOR_DIR = ROOT / "investor_deck"
CUSTOMER_DIR = ROOT / "customer_deck"
RUNBOOK_DIR = ROOT / "demo_runbook"
OUT_DIR = ROOT / "outreach_assets"

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

    founder_path = latest_file(FOUNDER_DIR, "founder-one-pager-*.json")
    investor_path = latest_file(INVESTOR_DIR, "investor-deck-summary-*.json")
    customer_path = latest_file(CUSTOMER_DIR, "customer-deck-summary-*.json")
    runbook_path = latest_file(RUNBOOK_DIR, "demo-runbook-*.json")

    founder = load_json(founder_path, {})
    investor = load_json(investor_path, {})
    customer = load_json(customer_path, {})
    runbook = load_json(runbook_path, {})

    if not founder or not investor or not customer or not runbook:
        raise RuntimeError("Could not load one or more required source files.")

    run_id = founder.get("source_run_id") or investor.get("run_id") or "unknown-run"
    key_metrics = founder.get("key_metrics", {})
    proof_points = founder.get("proof_points", {})
    scenario = runbook.get("scenario", {})

    outreach = {
        "outreach_assets_version": "0.1.0",
        "run_id": run_id,
        "source_files": {
            "founder_onepager": founder_path.name,
            "investor_deck": investor_path.name,
            "customer_deck": customer_path.name,
            "demo_runbook": runbook_path.name,
        },
        "investor_cold_email": {
            "subject": "Portable Memory MVP: continuity with lower context cost",
            "body": (
                "Hi <Name>,\n\n"
                "I’m building Portable Memory MVP, a memory controller for AI systems that preserves continuity while reducing context cost.\n\n"
                f"Our current best policy, robustness-aware pruning, achieved retrieval hit rate {key_metrics.get('retrieval_hit_rate')}, "
                f"soft hit rate {key_metrics.get('soft_hit_rate')}, and context reduction {key_metrics.get('context_reduction_percent')}%, "
                f"while remaining unbeaten across {proof_points.get('unbeaten_scenarios')} in the current adversarial benchmark suite.\n\n"
                "The core idea is simple: rescue the minimum robust meaning needed for continuity, then prune only when exact recall, soft recall, "
                "and overlap robustness remain intact.\n\n"
                "I now have the benchmark evidence, investor deck, customer deck, and a live demo runbook ready. "
                "If this is relevant to your AI infra / copilot / memory thesis, I’d love to send the deck or walk through the demo.\n\n"
                "Best,\nAlvin"
            )
        },
        "customer_intro_email": {
            "subject": "Reduce AI context cost without sacrificing continuity",
            "body": (
                "Hi <Name>,\n\n"
                "I’m reaching out because we’ve built a memory controller that helps AI systems keep continuity without dragging around bloated context.\n\n"
                f"In our current benchmark suite, the best policy achieved retrieval hit rate {key_metrics.get('retrieval_hit_rate')}, "
                f"soft hit rate {key_metrics.get('soft_hit_rate')}, and context reduction {key_metrics.get('context_reduction_percent')}%.\n\n"
                "The benefit for teams is straightforward: lower context cost, fewer dropped details, and more trustworthy memory behavior "
                "for long-session assistants, copilots, and knowledge workflows.\n\n"
                "I can share a short deck or run a live demo using a benchmark scenario that shows the before/after clearly.\n\n"
                "Best,\nAlvin"
            )
        },
        "linkedin_dm": (
            "Built a memory controller for AI systems that preserves continuity while reducing context cost. "
            f"Current best policy hit {key_metrics.get('retrieval_hit_rate')} retrieval, {key_metrics.get('soft_hit_rate')} soft hit, "
            f"and {key_metrics.get('context_reduction_percent')}% context reduction, unbeaten on the current adversarial suite. "
            "Happy to share the deck or demo if relevant."
        ),
        "landing_page_copy": {
            "headline": "Preserve AI continuity without bloating context",
            "subheadline": "Portable Memory MVP keeps the minimum robust meaning needed for continuity, so assistants remember what matters at lower context cost.",
            "problem": [
                "AI systems either keep too much context or lose important meaning.",
                "Summaries often drop constraints, identity details, and next-step information.",
                "Long-session continuity becomes expensive, brittle, or both."
            ],
            "solution": [
                "Rescue high-signal context.",
                "Prune only when exact recall, soft recall, and overlap robustness remain intact.",
                "Deliver lower context cost with stronger continuity behavior."
            ],
            "proof": [
                f"Retrieval hit rate: {key_metrics.get('retrieval_hit_rate')}",
                f"Soft hit rate: {key_metrics.get('soft_hit_rate')}",
                f"Context reduction: {key_metrics.get('context_reduction_percent')}%",
                f"Adversarial result: {proof_points.get('unbeaten_scenarios')} unbeaten"
            ],
            "cta": "Request the deck or book a live demo"
        },
        "demo_booking_blurb": (
            "Live demo: see a real benchmark scenario where robustness-aware pruning keeps the same continuity signal "
            "while sharply reducing carried context. Includes before/after previews, metrics, and deployment discussion."
        ),
        "call_script": [
            "Open by stating the problem in one sentence: AI memory either bloats context or drops important meaning.",
            "Use the benchmark proof: strong hit rates plus positive context reduction.",
            f"Use the selected scenario from the runbook: {scenario.get('title')}.",
            "Offer either the customer deck, investor deck, or the live demo depending on audience."
        ]
    }

    json_path = OUT_DIR / f"outreach-assets-{run_id}.json"
    md_path = OUT_DIR / f"outreach-assets-{run_id}.md"

    save_json(json_path, outreach)

    lines = []
    lines.append("# Portable Memory MVP - Outreach Assets")
    lines.append("")
    lines.append(f"Run ID: `{run_id}`")
    lines.append("")
    lines.append("## Investor Cold Email")
    lines.append("")
    lines.append(f"**Subject:** {outreach['investor_cold_email']['subject']}")
    lines.append("")
    lines.append(outreach["investor_cold_email"]["body"])
    lines.append("")
    lines.append("## Customer Intro Email")
    lines.append("")
    lines.append(f"**Subject:** {outreach['customer_intro_email']['subject']}")
    lines.append("")
    lines.append(outreach["customer_intro_email"]["body"])
    lines.append("")
    lines.append("## LinkedIn DM")
    lines.append("")
    lines.append(outreach["linkedin_dm"])
    lines.append("")
    lines.append("## Landing Page Copy")
    lines.append("")
    lines.append(f"**Headline:** {outreach['landing_page_copy']['headline']}")
    lines.append("")
    lines.append(f"**Subheadline:** {outreach['landing_page_copy']['subheadline']}")
    lines.append("")
    lines.append("### Problem")
    for item in outreach["landing_page_copy"]["problem"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Solution")
    for item in outreach["landing_page_copy"]["solution"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Proof")
    for item in outreach["landing_page_copy"]["proof"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"**CTA:** {outreach['landing_page_copy']['cta']}")
    lines.append("")
    lines.append("## Demo Booking Blurb")
    lines.append("")
    lines.append(outreach["demo_booking_blurb"])
    lines.append("")
    lines.append("## Call Script")
    for item in outreach["call_script"]:
        lines.append(f"- {item}")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Outreach assets generated.")
    print(f"Source founder one-pager: {founder_path}")
    print(f"Source investor deck: {investor_path}")
    print(f"Source customer deck: {customer_path}")
    print(f"Source demo runbook: {runbook_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
