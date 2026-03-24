import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
ATTR_DIR = ROOT / "attribution"


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


def split_lines(text: str):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def latest_run_file():
    runs = sorted(RESULTS_DIR.glob("run-*.json"))
    if not runs:
        raise RuntimeError("No benchmark run files found.")
    return runs[-1]


def mode_map(scenario):
    out = {}
    for mode in scenario.get("modes", []):
        out[mode.get("mode")] = mode
    return out


def classify_line(line: str):
    lower = line.lower()
    if lower.startswith("preference:"):
        return "preference"
    if lower.startswith("fact:"):
        return "fact"
    if lower.startswith("project:"):
        return "project"
    if "durable update" in lower:
        return "durable_update"
    if lower.startswith("conversation:"):
        return "conversation"
    return "other"


def main():
    ATTR_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_run_file()
    run = load_json(run_path, {})
    if not run:
        raise RuntimeError("Could not load latest run file.")

    scenario_reports = []

    for scenario in run.get("scenario_results", []):
        modes = mode_map(scenario)
        compression = modes.get("compression_mode", {})
        hybrid = modes.get("hybrid_mode", {})
        if not compression or not hybrid:
            continue

        compression_preview = compression.get("preview", "")
        hybrid_preview = hybrid.get("preview", "")
        expected_phrases = scenario.get("expected_phrases", [])

        compression_lines = split_lines(compression_preview)
        hybrid_lines = split_lines(hybrid_preview)

        compression_norms = {normalize_text(x) for x in compression_lines}
        added_lines = [ln for ln in hybrid_lines if normalize_text(ln) not in compression_norms]

        phrase_status = []
        for phrase in expected_phrases:
            in_compression = contains_phrase(compression_preview, phrase)
            in_hybrid = contains_phrase(hybrid_preview, phrase)
            restored_by_hybrid = (not in_compression) and in_hybrid

            saver_lines = []
            if restored_by_hybrid:
                for line in added_lines:
                    if contains_phrase(line, phrase):
                        saver_lines.append({
                            "line": line,
                            "kind": classify_line(line),
                            "length": len(line)
                        })

            phrase_status.append({
                "phrase": phrase,
                "in_compression": in_compression,
                "in_hybrid": in_hybrid,
                "restored_by_hybrid": restored_by_hybrid,
                "saver_lines": saver_lines
            })

        attribution_lines = []
        for line in added_lines:
            restored = []
            for item in phrase_status:
                if item["restored_by_hybrid"] and contains_phrase(line, item["phrase"]):
                    restored.append(item["phrase"])

            attribution_lines.append({
                "line": line,
                "kind": classify_line(line),
                "length": len(line),
                "restored_phrases": restored,
                "restored_phrase_count": len(restored)
            })

        scenario_reports.append({
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "compression_hit_rate": compression.get("retrieval_hit_rate"),
            "hybrid_hit_rate": hybrid.get("retrieval_hit_rate"),
            "compression_context_reduction_percent": compression.get("context_reduction_percent"),
            "hybrid_context_reduction_percent": hybrid.get("context_reduction_percent"),
            "compression_preview": compression_preview,
            "hybrid_preview": hybrid_preview,
            "added_lines_in_hybrid": attribution_lines,
            "phrase_status": phrase_status
        })

    report = {
        "attribution_version": "0.1.0",
        "source_run_file": run_path.name,
        "run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "scenario_reports": scenario_reports
    }

    json_path = ATTR_DIR / f"phrase-saver-attribution-{run.get('run_id')}.json"
    md_path = ATTR_DIR / f"phrase-saver-attribution-{run.get('run_id')}.md"

    save_json(json_path, report)

    md_lines = []
    md_lines.append("# Phrase-Saver Attribution Report")
    md_lines.append("")
    md_lines.append(f"- Run ID: `{run.get('run_id')}`")
    md_lines.append(f"- Source run: `{run_path.name}`")
    md_lines.append("")

    for scenario in scenario_reports:
        md_lines.append(f"## {scenario['title']}")
        md_lines.append("")
        md_lines.append(f"- Compression hit rate: `{scenario['compression_hit_rate']}`")
        md_lines.append(f"- Hybrid hit rate: `{scenario['hybrid_hit_rate']}`")
        md_lines.append(f"- Compression context reduction: `{scenario['compression_context_reduction_percent']}`")
        md_lines.append(f"- Hybrid context reduction: `{scenario['hybrid_context_reduction_percent']}`")
        md_lines.append("")

        md_lines.append("### Restored phrases")
        md_lines.append("")
        for item in scenario["phrase_status"]:
            if item["restored_by_hybrid"]:
                md_lines.append(f"- `{item['phrase']}`")
                for saver in item["saver_lines"]:
                    md_lines.append(f"  - saver line ({saver['kind']}): {saver['line']}")
        md_lines.append("")

        md_lines.append("### Hybrid-added lines")
        md_lines.append("")
        for line in scenario["added_lines_in_hybrid"]:
            md_lines.append(
                f"- ({line['kind']}, {line['length']} chars, restores {line['restored_phrase_count']} phrases) {line['line']}"
            )
        md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print("Phrase-saver attribution completed.")
    print(f"Source run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
