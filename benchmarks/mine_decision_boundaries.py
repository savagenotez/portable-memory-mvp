import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT / "analysis"
BOUNDARY_DIR = ROOT / "boundaries"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_analysis_file():
    files = sorted(ANALYSIS_DIR.glob("per-scenario-winners-*.json"))
    if not files:
        raise RuntimeError("No per-scenario winner analysis JSON files found.")
    return files[-1]


def classify_title(title: str):
    t = (title or "").lower()
    flags = {
        "low_recall": "low-recall" in t,
        "mixed_recall": "mixed-recall" in t,
        "project_identity": "project" in t or "identity" in t,
        "constraints": "constraint" in t,
        "proof": "proof" in t or "proven" in t,
        "workflow": "workflow" in t or "tooling" in t or "codex" in t or "claude" in t,
        "next_step": "next step" in t or "should happen next" in t,
        "goal": "goal" in t,
    }
    return flags


def winner_count(reports, field):
    counts = {}
    for report in reports:
        winner = report.get(field)
        if winner:
            counts[winner] = counts.get(winner, 0) + 1
    return counts


def mine_rules(reports):
    rules = []

    low_reports = [r for r in reports if r["features"]["low_recall"]]
    mixed_reports = [r for r in reports if r["features"]["mixed_recall"]]
    proof_reports = [r for r in reports if r["features"]["proof"]]
    constraint_reports = [r for r in reports if r["features"]["constraints"]]
    workflow_reports = [r for r in reports if r["features"]["workflow"]]
    goal_reports = [r for r in reports if r["features"]["goal"]]

    def add_rule(name, if_all=None, if_any=None, preferred=None, evidence=None, notes=None):
        rules.append({
            "rule_name": name,
            "if_all": if_all or [],
            "if_any": if_any or [],
            "preferred_mode": preferred,
            "evidence_count": evidence or 0,
            "notes": notes or ""
        })

    low_best = winner_count(low_reports, "best_overall")
    mixed_best = winner_count(mixed_reports, "best_overall")
    proof_best = winner_count(proof_reports, "best_overall")
    constraint_best = winner_count(constraint_reports, "best_overall")
    workflow_best = winner_count(workflow_reports, "best_overall")
    goal_best = winner_count(goal_reports, "best_overall")

    def top_winner(counts):
        if not counts:
            return None, 0
        items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return items[0]

    winner, count = top_winner(low_best)
    if winner:
        add_rule(
            "low_recall_default",
            if_all=["low_recall"],
            preferred=winner,
            evidence=count,
            notes="Derived from scenarios marked low-recall."
        )

    winner, count = top_winner(mixed_best)
    if winner:
        add_rule(
            "mixed_recall_default",
            if_all=["mixed_recall"],
            preferred=winner,
            evidence=count,
            notes="Derived from scenarios marked mixed-recall."
        )

    winner, count = top_winner(proof_best)
    if winner:
        add_rule(
            "proof_queries",
            if_any=["proof"],
            preferred=winner,
            evidence=count,
            notes="Proof/proven style queries often need stronger preservation."
        )

    winner, count = top_winner(constraint_best)
    if winner:
        add_rule(
            "constraint_queries",
            if_any=["constraints"],
            preferred=winner,
            evidence=count,
            notes="Constraint-heavy queries often benefit from stronger semantic retention."
        )

    winner, count = top_winner(workflow_best)
    if winner:
        add_rule(
            "workflow_queries",
            if_any=["workflow"],
            preferred=winner,
            evidence=count,
            notes="Workflow/tooling language may need structured preservation."
        )

    winner, count = top_winner(goal_best)
    if winner:
        add_rule(
            "goal_queries",
            if_any=["goal"],
            preferred=winner,
            evidence=count,
            notes="Goal-only questions may be more compressible."
        )

    # fallback meta rule
    overall_best = winner_count(reports, "best_overall")
    overall_winner, overall_count = top_winner(overall_best)
    if overall_winner:
        add_rule(
            "global_fallback",
            preferred=overall_winner,
            evidence=overall_count,
            notes="Fallback winner across all analyzed scenarios."
        )

    return rules


def main():
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)

    analysis_path = latest_analysis_file()
    analysis = load_json(analysis_path, {})
    if not analysis:
        raise RuntimeError("Could not load latest per-scenario analysis JSON.")

    enriched_reports = []
    for report in analysis.get("scenario_reports", []):
        features = classify_title(report.get("title", ""))
        enriched_reports.append({
            **report,
            "features": features
        })

    rules = mine_rules(enriched_reports)

    out = {
        "boundary_version": "0.1.0",
        "source_analysis_file": analysis_path.name,
        "source_run_id": analysis.get("source_run_id"),
        "timestamp": analysis.get("timestamp"),
        "scenario_count": len(enriched_reports),
        "rules": rules,
        "feature_breakdown": {
            "low_recall": sum(1 for r in enriched_reports if r["features"]["low_recall"]),
            "mixed_recall": sum(1 for r in enriched_reports if r["features"]["mixed_recall"]),
            "project_identity": sum(1 for r in enriched_reports if r["features"]["project_identity"]),
            "constraints": sum(1 for r in enriched_reports if r["features"]["constraints"]),
            "proof": sum(1 for r in enriched_reports if r["features"]["proof"]),
            "workflow": sum(1 for r in enriched_reports if r["features"]["workflow"]),
            "next_step": sum(1 for r in enriched_reports if r["features"]["next_step"]),
            "goal": sum(1 for r in enriched_reports if r["features"]["goal"]),
        }
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = BOUNDARY_DIR / f"decision-boundaries-{run_id}.json"
    md_path = BOUNDARY_DIR / f"decision-boundaries-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Decision Boundary Mining")
    lines.append("")
    lines.append(f"- Source analysis file: `{analysis_path.name}`")
    lines.append(f"- Source run ID: `{run_id}`")
    lines.append(f"- Scenario count: `{out['scenario_count']}`")
    lines.append("")
    lines.append("## Feature Breakdown")
    lines.append("")
    for k, v in out["feature_breakdown"].items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## Mined Rules")
    lines.append("")
    for rule in rules:
        lines.append(f"### {rule['rule_name']}")
        lines.append(f"- Preferred mode: `{rule['preferred_mode']}`")
        lines.append(f"- Evidence count: `{rule['evidence_count']}`")
        if rule["if_all"]:
            lines.append(f"- If all: `{', '.join(rule['if_all'])}`")
        if rule["if_any"]:
            lines.append(f"- If any: `{', '.join(rule['if_any'])}`")
        lines.append(f"- Notes: {rule['notes']}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Decision boundary mining completed.")
    print(f"Source analysis: {analysis_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
