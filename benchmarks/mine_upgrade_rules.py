import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIAG_DIR = ROOT / "diagnostics"
RULES_DIR = ROOT / "rules"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_diag_file():
    files = sorted(DIAG_DIR.glob("context-diagnostics-*.json"))
    if not files:
        raise RuntimeError("No diagnostics JSON files found in benchmarks/diagnostics.")
    return files[-1]


def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def mode_metric(mode_report, key):
    return safe_get(mode_report, "headline_metrics", key, default=None)


def line_key(line_obj):
    return line_obj.get("line", "").strip()


def add_counter_from_lines(counter, lines, weight=1):
    for item in lines:
        line = line_key(item)
        if line:
            counter[line] += weight


def mine_rules(diag):
    scenario_reports = diag.get("scenario_reports", [])

    keep_priority = Counter()
    keep_durable = Counter()
    keep_situational = Counter()
    drop_redundant = Counter()
    compress_candidates = Counter()
    phrase_savers = Counter()

    line_mode_presence = defaultdict(lambda: {"recall": 0, "compression": 0, "hybrid": 0})
    line_stats = {}

    for scenario in scenario_reports:
        mode_reports = scenario.get("mode_reports", [])
        by_mode = {m.get("mode"): m for m in mode_reports}

        recall = by_mode.get("recall_mode", {})
        compression = by_mode.get("compression_mode", {})
        hybrid = by_mode.get("hybrid_mode", {})

        recall_hit = mode_metric(recall, "retrieval_hit_rate")
        compression_hit = mode_metric(compression, "retrieval_hit_rate")
        hybrid_hit = mode_metric(hybrid, "retrieval_hit_rate")

        recall_red = mode_metric(recall, "context_reduction_percent")
        compression_red = mode_metric(compression, "context_reduction_percent")
        hybrid_red = mode_metric(hybrid, "context_reduction_percent")

        for mode_name, mode_obj, short_name in [
            ("recall_mode", recall, "recall"),
            ("compression_mode", compression, "compression"),
            ("hybrid_mode", hybrid, "hybrid"),
        ]:
            per_line = mode_obj.get("per_line", [])
            for item in per_line:
                line = line_key(item)
                if not line:
                    continue
                line_mode_presence[line][short_name] += 1
                if line not in line_stats:
                    line_stats[line] = {
                        "kind": item.get("kind"),
                        "durability_score": item.get("durability_score"),
                        "situational_score": item.get("situational_score"),
                        "centrality_score": item.get("centrality_score"),
                        "novelty_score": item.get("novelty_score"),
                        "redundancy_score": item.get("redundancy_score"),
                        "cost_bytes": item.get("cost_bytes"),
                    }

        # Durable lines in recall/hybrid are likely core keepers
        if recall_hit is not None and recall_hit >= 0.75:
            add_counter_from_lines(keep_durable, recall.get("likely_durable_lines", []), weight=2)
            add_counter_from_lines(phrase_savers, recall.get("likely_situational_lines", []), weight=1)

        if hybrid_hit is not None and hybrid_hit >= 0.75:
            add_counter_from_lines(keep_durable, hybrid.get("likely_durable_lines", []), weight=3)
            add_counter_from_lines(phrase_savers, hybrid.get("likely_situational_lines", []), weight=2)

        # Compression lines that still survive positive compression are valuable compact keepers
        if compression_red is not None and compression_red > 0:
            add_counter_from_lines(keep_priority, compression.get("likely_durable_lines", []), weight=3)
            add_counter_from_lines(keep_situational, compression.get("likely_situational_lines", []), weight=2)

        # Redundant lines in recall are likely drop or merge candidates
        add_counter_from_lines(drop_redundant, recall.get("likely_redundant_lines", []), weight=2)
        add_counter_from_lines(drop_redundant, hybrid.get("likely_redundant_lines", []), weight=1)

        # Costly lines in recall are compression targets unless they are phrase savers
        add_counter_from_lines(compress_candidates, recall.get("likely_costly_lines", []), weight=2)
        add_counter_from_lines(compress_candidates, hybrid.get("likely_costly_lines", []), weight=1)

    # Build ranked rules
    def top_items(counter, n=20):
        out = []
        for line, score in counter.most_common(n):
            out.append({
                "line": line,
                "score": score,
                **line_stats.get(line, {})
            })
        return out

    keep_priority_items = top_items(keep_priority, 20)
    keep_durable_items = top_items(keep_durable, 20)
    keep_situational_items = top_items(keep_situational, 20)
    drop_redundant_items = top_items(drop_redundant, 20)
    compress_candidate_items = top_items(compress_candidates, 20)
    phrase_saver_items = top_items(phrase_savers, 20)

    synthesized_rules = []

    if keep_durable_items:
        synthesized_rules.append({
            "rule_id": "R1",
            "title": "Always prefer high-durability core lines",
            "why": "These lines repeatedly survive in high-recall and hybrid modes.",
            "action": "Promote preference/fact/project lines with strong durability and centrality into the default retained set."
        })

    if phrase_saver_items:
        synthesized_rules.append({
            "rule_id": "R2",
            "title": "Protect phrase-saving situational lines",
            "why": "These lines help recover expected phrases even when compression is active.",
            "action": "Allow a small budget for query-relevant situational lines when they restore missed expected phrases."
        })

    if drop_redundant_items:
        synthesized_rules.append({
            "rule_id": "R3",
            "title": "Collapse redundant lines aggressively",
            "why": "These lines recur with high redundancy and mostly add bytes without new signal.",
            "action": "Drop or merge semantically overlapping lines once one representative line is retained."
        })

    if compress_candidate_items:
        synthesized_rules.append({
            "rule_id": "R4",
            "title": "Compress costly lines unless they save recall",
            "why": "These lines consume many bytes and often drive negative context reduction.",
            "action": "Only keep costly lines when they materially improve expected-phrase coverage or central project state."
        })

    # Derive per-line decision hints
    decision_hints = []
    all_lines = set(list(line_mode_presence.keys()))
    for line in sorted(all_lines):
        presence = line_mode_presence[line]
        stats = line_stats.get(line, {})
        keep_score = (
            keep_priority.get(line, 0) +
            keep_durable.get(line, 0) +
            keep_situational.get(line, 0) +
            phrase_savers.get(line, 0)
        )
        drop_score = drop_redundant.get(line, 0) + compress_candidates.get(line, 0)

        if keep_score > drop_score:
            decision = "keep_or_prefer"
        elif drop_score > keep_score:
            decision = "compress_or_drop"
        else:
            decision = "review"

        decision_hints.append({
            "line": line,
            "decision_hint": decision,
            "keep_score": keep_score,
            "drop_score": drop_score,
            "presence": presence,
            **stats
        })

    return {
        "rules_version": "0.1.0",
        "source_diagnostics_run": diag.get("run_id"),
        "source_timestamp": diag.get("timestamp"),
        "synthesized_rules": synthesized_rules,
        "ranked_lists": {
            "keep_priority": keep_priority_items,
            "keep_durable": keep_durable_items,
            "keep_situational": keep_situational_items,
            "drop_redundant": drop_redundant_items,
            "compress_candidates": compress_candidate_items,
            "phrase_savers": phrase_saver_items,
        },
        "decision_hints": decision_hints
    }


def markdown_report(rules):
    lines = []
    lines.append("# Upgrade Rules Report")
    lines.append("")
    lines.append(f"- Source diagnostics run: `{rules.get('source_diagnostics_run')}`")
    lines.append(f"- Source timestamp: `{rules.get('source_timestamp')}`")
    lines.append("")

    lines.append("## Synthesized Rules")
    lines.append("")
    for rule in rules.get("synthesized_rules", []):
        lines.append(f"### {rule['rule_id']} - {rule['title']}")
        lines.append(f"- Why: {rule['why']}")
        lines.append(f"- Action: {rule['action']}")
        lines.append("")

    def emit_ranked(title, key, limit=8):
        items = rules.get("ranked_lists", {}).get(key, [])
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for item in items[:limit]:
            lines.append(f"- score={item.get('score')} | kind={item.get('kind')} | cost={item.get('cost_bytes')} | {item.get('line')}")
        lines.append("")

    emit_ranked("Keep Priority Lines", "keep_priority")
    emit_ranked("Durable Core Lines", "keep_durable")
    emit_ranked("Situational Phrase Savers", "keep_situational")
    emit_ranked("Redundant Drop Candidates", "drop_redundant")
    emit_ranked("Costly Compression Candidates", "compress_candidates")
    emit_ranked("Phrase Saver Lines", "phrase_savers")

    lines.append("## Decision Hints")
    lines.append("")
    for item in rules.get("decision_hints", [])[:20]:
        lines.append(
            f"- {item.get('decision_hint')} | keep={item.get('keep_score')} drop={item.get('drop_score')} "
            f"| recall={item.get('presence', {}).get('recall')} comp={item.get('presence', {}).get('compression')} hybrid={item.get('presence', {}).get('hybrid')} "
            f"| {item.get('line')}"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    diag_path = latest_diag_file()
    diag = load_json(diag_path, {})
    if not diag:
        raise RuntimeError("Diagnostics file could not be loaded.")

    rules = mine_rules(diag)

    run_id = rules.get("source_diagnostics_run") or "unknown-run"
    json_path = RULES_DIR / f"upgrade-rules-{run_id}.json"
    md_path = RULES_DIR / f"upgrade-rules-{run_id}.md"

    save_json(json_path, rules)
    md_path.write_text(markdown_report(rules), encoding="utf-8")

    print("Upgrade rules mined successfully.")
    print(f"Source diagnostics: {diag_path}")
    print(f"Rules JSON: {json_path}")
    print(f"Rules Markdown: {md_path}")


if __name__ == "__main__":
    main()
