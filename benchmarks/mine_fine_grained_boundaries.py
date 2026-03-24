import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
ANALYSIS_DIR = ROOT / "analysis"
ATTR_DIR = ROOT / "attribution"
FRAG_DIR = ROOT / "fragments"
OUT_DIR = ROOT / "fine_grained_boundaries"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def contains_phrase(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(text)


def bytes_len(s: str) -> int:
    return len((s or "").encode("utf-8"))


def latest_run_file():
    files = sorted(RESULTS_DIR.glob("run-*.json"))
    if not files:
        raise RuntimeError("No benchmark run files found.")
    return files[-1]


def latest_analysis_file():
    files = sorted(ANALYSIS_DIR.glob("per-scenario-winners-*.json"))
    return files[-1] if files else None


def latest_attr_file():
    files = sorted(ATTR_DIR.glob("phrase-saver-attribution-*.json"))
    return files[-1] if files else None


def latest_frag_file():
    files = sorted(FRAG_DIR.glob("phrase-fragment-attribution-*.json"))
    return files[-1] if files else None


def mode_map(scenario):
    out = {}
    for mode in scenario.get("modes", []):
        out[mode.get("mode")] = mode
    return out


def build_attribution_maps(attr):
    by_scenario = {}
    for scenario in attr.get("scenario_reports", []):
        line_map = {}
        for item in scenario.get("added_lines_in_hybrid", []):
            line = item.get("line", "")
            norm = normalize_text(line)
            if norm:
                line_map[norm] = {
                    "line": line,
                    "kind": item.get("kind"),
                    "restored_phrases": item.get("restored_phrases", []),
                    "restored_phrase_count": item.get("restored_phrase_count", 0),
                    "length": item.get("length", len(line)),
                    "phrases_per_byte": item.get("phrases_per_byte", 0.0),
                }
        by_scenario[scenario.get("scenario_id")] = line_map
    return by_scenario


def build_fragment_maps(frag_attr):
    by_scenario = {}
    for scenario in frag_attr.get("scenario_reports", []):
        frags = []
        for line_report in scenario.get("line_reports", []):
            for frag in line_report.get("best_fragments", []):
                frags.append({
                    "source_line": line_report.get("line", ""),
                    "fragment_type": frag.get("fragment_type"),
                    "fragment": frag.get("fragment", ""),
                    "length": frag.get("length", len(frag.get("fragment", ""))),
                    "restored_phrases": frag.get("restored_phrases", []),
                    "restored_phrase_count": frag.get("restored_phrase_count", 0),
                    "phrases_per_char": frag.get("phrases_per_char", 0.0),
                })
        by_scenario[scenario.get("scenario_id")] = frags
    return by_scenario


def extract_features(scenario, modes, attr_map, frag_map):
    expected = scenario.get("expected_phrases", [])
    query = scenario.get("query", "")
    title = scenario.get("title", "")
    raw_text = scenario.get("retrieval_preview_raw", "")
    baseline = scenario.get("baseline_preview", "")

    threshold = modes.get("threshold_gated_adaptive_mode", {})
    hybrid = modes.get("hybrid_mode", {})
    saver = modes.get("phrase_saver_per_byte_mode", {})
    compression = modes.get("compression_mode", {})
    frag_mode = modes.get("phrase_fragment_per_byte_mode", {})
    learned = modes.get("learned_boundary_controller_mode", {})
    classifier = modes.get("scenario_classifier_mode", {})

    missing_under_compression = [
        p for p in expected
        if p not in compression.get("matched_phrases", [])
    ]
    missing_under_frag = [
        p for p in expected
        if p not in frag_mode.get("matched_phrases", [])
    ]

    attr_items = list(attr_map.values())
    frag_items = frag_map

    top_phrase_saver_ppb = max([x.get("phrases_per_byte", 0.0) for x in attr_items], default=0.0)
    top_phrase_saver_restored = max([x.get("restored_phrase_count", 0) for x in attr_items], default=0)
    top_fragment_ppc = max([x.get("phrases_per_char", 0.0) for x in frag_items], default=0.0)
    top_fragment_restored = max([x.get("restored_phrase_count", 0) for x in frag_items], default=0)

    return {
        "scenario_id": scenario.get("scenario_id"),
        "title": title,
        "query": query,
        "expected_phrase_count": len(expected),
        "avg_expected_phrase_words": round(
            sum(len(p.split()) for p in expected) / len(expected), 2
        ) if expected else 0.0,
        "long_expected_phrase_count": sum(1 for p in expected if len(p.split()) >= 4),
        "query_mentions_constraints": "constraint" in normalize_text(query),
        "query_mentions_proof": ("proof" in normalize_text(query) or "proven" in normalize_text(query)),
        "query_mentions_next_step": ("next" in normalize_text(query) or "should happen" in normalize_text(query)),
        "query_mentions_workflow": any(x in normalize_text(query) for x in ["workflow", "codex", "claude", "tool"]),
        "raw_retrieval_bytes": bytes_len(raw_text),
        "baseline_preview_bytes": bytes_len(baseline),
        "compression_hit_rate": compression.get("retrieval_hit_rate"),
        "frag_hit_rate": frag_mode.get("retrieval_hit_rate"),
        "hybrid_hit_rate": hybrid.get("retrieval_hit_rate"),
        "saver_hit_rate": saver.get("retrieval_hit_rate"),
        "threshold_hit_rate": threshold.get("retrieval_hit_rate"),
        "learned_hit_rate": learned.get("retrieval_hit_rate"),
        "classifier_hit_rate": classifier.get("retrieval_hit_rate"),
        "threshold_choice": threshold.get("controller_choice"),
        "learned_choice": learned.get("controller_choice"),
        "classifier_choice": classifier.get("controller_choice"),
        "classifier_label": classifier.get("classifier_label"),
        "missing_under_compression_count": len(missing_under_compression),
        "missing_under_frag_count": len(missing_under_frag),
        "top_phrase_saver_ppb": round(top_phrase_saver_ppb, 6),
        "top_phrase_saver_restored": top_phrase_saver_restored,
        "top_fragment_ppc": round(top_fragment_ppc, 6),
        "top_fragment_restored": top_fragment_restored,
        "threshold_beats_learned": (
            threshold.get("retrieval_hit_rate", -1) > learned.get("retrieval_hit_rate", -1)
            or (
                threshold.get("retrieval_hit_rate", -1) == learned.get("retrieval_hit_rate", -1)
                and threshold.get("context_reduction_percent", -999) > learned.get("context_reduction_percent", -999)
            )
        ),
        "hybrid_equals_threshold": (
            hybrid.get("retrieval_hit_rate") == threshold.get("retrieval_hit_rate")
            and hybrid.get("context_reduction_percent") == threshold.get("context_reduction_percent")
        ),
        "saver_equals_threshold": (
            saver.get("retrieval_hit_rate") == threshold.get("retrieval_hit_rate")
            and saver.get("context_reduction_percent") == threshold.get("context_reduction_percent")
        ),
    }


def rule(name, conditions, preferred_mode, evidence_count, notes):
    return {
        "rule_name": name,
        "conditions": conditions,
        "preferred_mode": preferred_mode,
        "evidence_count": evidence_count,
        "notes": notes,
    }


def mine_rules(feature_rows):
    rules = []

    saver_rows = [r for r in feature_rows if r["threshold_choice"] == "phrase_saver_escalation"]
    if saver_rows:
        rules.append(rule(
            "phrase_saver_when_compression_misses_and_saver_can_restore",
            [
                "missing_under_compression_count >= 1",
                "top_phrase_saver_restored >= 1",
            ],
            "phrase_saver_per_byte_mode",
            sum(1 for r in saver_rows if r["missing_under_compression_count"] >= 1 and r["top_phrase_saver_restored"] >= 1),
            "Use phrase-saver rescue when compression drops required phrases and local saver evidence exists."
        ))

    hybrid_rows = [r for r in feature_rows if r["threshold_choice"] == "hybrid_fallback"]
    if hybrid_rows:
        rules.append(rule(
            "hybrid_when_compression_misses_and_phrase_saver_signal_is_absent",
            [
                "missing_under_compression_count >= 1",
                "top_phrase_saver_restored == 0 OR phrase_saver insufficient",
            ],
            "hybrid_mode",
            sum(1 for r in hybrid_rows if r["missing_under_compression_count"] >= 1),
            "Use hybrid when compression misses required phrases and local middle-strength rescue is absent or insufficient."
        ))

    frag_rows = [r for r in feature_rows if r["threshold_choice"] == "fragment_escalation"]
    if frag_rows:
        rules.append(rule(
            "fragment_when_fragment_signal_is_real_and_small_gap_remains",
            [
                "missing_under_compression_count >= 1",
                "top_fragment_restored >= 1",
                "top_fragment_ppc > 0",
            ],
            "phrase_fragment_per_byte_mode",
            sum(1 for r in frag_rows if r["top_fragment_restored"] >= 1 and r["top_fragment_ppc"] > 0),
            "Use fragment rescue only when fragment evidence is real."
        ))

    compression_rows = [r for r in feature_rows if r["threshold_choice"] == "compression_seed"]
    if compression_rows:
        rules.append(rule(
            "compression_when_nothing_important_is_missing",
            [
                "missing_under_compression_count == 0",
            ],
            "compression_mode",
            sum(1 for r in compression_rows if r["missing_under_compression_count"] == 0),
            "Keep compression when it already preserves required signal."
        ))

    learned_fail_rows = [r for r in feature_rows if r["threshold_beats_learned"]]
    if learned_fail_rows:
        rules.append(rule(
            "do_not_force_compression_when_required_phrases_are_missing",
            [
                "learned_choice == compression_mode",
                "missing_under_compression_count >= 1",
            ],
            "threshold_gated_adaptive_mode",
            sum(1 for r in learned_fail_rows if r["learned_choice"] == "compression_mode" and r["missing_under_compression_count"] >= 1),
            "Coarse learned boundaries over-compress when missing phrases are not explicitly checked."
        ))

    saver_equal_rows = [r for r in feature_rows if r["saver_equals_threshold"]]
    if saver_equal_rows:
        rules.append(rule(
            "phrase_saver_is_primary_middle_state",
            [
                "saver_equals_threshold on many scenarios",
            ],
            "phrase_saver_per_byte_mode",
            len(saver_equal_rows),
            "Phrase-saver is the key middle-strength rescue mode."
        ))

    return rules


def main():
    print("[PY] Starting fine-grained boundary mining...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_run_file()
    print(f"[PY] Latest run file: {run_path}")
    run = load_json(run_path, {})
    if not run:
        raise RuntimeError("Could not load latest run.")

    analysis_path = latest_analysis_file()
    attr_path = latest_attr_file()
    frag_path = latest_frag_file()

    print(f"[PY] Latest analysis file: {analysis_path}")
    print(f"[PY] Latest attribution file: {attr_path}")
    print(f"[PY] Latest fragment file: {frag_path}")

    attr = load_json(attr_path, {"scenario_reports": []}) if attr_path else {"scenario_reports": []}
    frag = load_json(frag_path, {"scenario_reports": []}) if frag_path else {"scenario_reports": []}

    attr_maps = build_attribution_maps(attr)
    frag_maps = build_fragment_maps(frag)

    feature_rows = []
    scenario_notes = []

    for scenario in run.get("scenario_results", []):
        sid = scenario.get("scenario_id")
        modes = mode_map(scenario)
        row = extract_features(
            scenario,
            modes,
            attr_maps.get(sid, {}),
            frag_maps.get(sid, [])
        )
        feature_rows.append(row)

        scenario_notes.append({
            "scenario_id": sid,
            "title": scenario.get("title"),
            "threshold_choice": row["threshold_choice"],
            "learned_choice": row["learned_choice"],
            "classifier_choice": row["classifier_choice"],
            "missing_under_compression_count": row["missing_under_compression_count"],
            "top_phrase_saver_restored": row["top_phrase_saver_restored"],
            "top_fragment_restored": row["top_fragment_restored"],
            "top_phrase_saver_ppb": row["top_phrase_saver_ppb"],
            "top_fragment_ppc": row["top_fragment_ppc"],
            "threshold_beats_learned": row["threshold_beats_learned"],
        })

    print(f"[PY] Feature rows built: {len(feature_rows)}")
    rules = mine_rules(feature_rows)
    print(f"[PY] Rules mined: {len(rules)}")

    out = {
        "fine_grained_boundary_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_run_id": run.get("run_id"),
        "source_analysis_file": analysis_path.name if analysis_path else None,
        "source_attr_file": attr_path.name if attr_path else None,
        "source_frag_file": frag_path.name if frag_path else None,
        "timestamp": run.get("timestamp"),
        "scenario_count": len(feature_rows),
        "rules": rules,
        "feature_rows": feature_rows,
        "scenario_notes": scenario_notes,
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"fine-grained-boundaries-{run_id}.json"
    md_path = OUT_DIR / f"fine-grained-boundaries-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Fine-Grained Boundary Mining")
    lines.append("")
    lines.append(f"- Source run: `{run_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Scenario count: `{out['scenario_count']}`")
    lines.append("")
    lines.append("## Mined Rules")
    lines.append("")

    for r in rules:
        lines.append(f"### {r['rule_name']}")
        lines.append(f"- Preferred mode: `{r['preferred_mode']}`")
        lines.append(f"- Evidence count: `{r['evidence_count']}`")
        lines.append("- Conditions:")
        for cond in r["conditions"]:
            lines.append(f"  - {cond}")
        lines.append(f"- Notes: {r['notes']}")
        lines.append("")

    lines.append("## Scenario Notes")
    lines.append("")
    for s in scenario_notes:
        lines.append(f"### {s['title']}")
        lines.append(f"- Scenario ID: `{s['scenario_id']}`")
        lines.append(f"- Threshold choice: `{s['threshold_choice']}`")
        lines.append(f"- Learned choice: `{s['learned_choice']}`")
        lines.append(f"- Classifier choice: `{s['classifier_choice']}`")
        lines.append(f"- Missing under compression: `{s['missing_under_compression_count']}`")
        lines.append(f"- Top phrase-saver restored: `{s['top_phrase_saver_restored']}`")
        lines.append(f"- Top fragment restored: `{s['top_fragment_restored']}`")
        lines.append(f"- Top phrase-saver ppb: `{s['top_phrase_saver_ppb']}`")
        lines.append(f"- Top fragment ppc: `{s['top_fragment_ppc']}`")
        lines.append(f"- Threshold beats learned: `{s['threshold_beats_learned']}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Fine-grained boundary mining completed.")
    print(f"Source run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[PY][ERROR] {exc}", file=sys.stderr)
        raise
