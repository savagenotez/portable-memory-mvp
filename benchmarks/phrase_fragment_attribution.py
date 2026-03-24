import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ATTR_DIR = ROOT / "attribution"
FRAG_DIR = ROOT / "fragments"


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


def latest_attr_file():
    files = sorted(ATTR_DIR.glob("phrase-saver-attribution-*.json"))
    if not files:
        raise RuntimeError("No phrase-saver attribution JSON files found.")
    return files[-1]


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


def fragment_candidates(line: str):
    raw = line.strip()
    candidates = []

    # whole line
    candidates.append(("full_line", raw))

    # title/body split on first colon
    if ":" in raw:
        left, right = raw.split(":", 1)
        left = left.strip()
        right = right.strip()
        if left:
            candidates.append(("title_only", left))
        if right:
            candidates.append(("body_only", right))
        if left and right:
            candidates.append(("title_plus_short_body", f"{left}: {right[:120].strip()}"))

    # split on punctuation / separators
    parts = re.split(r"[;|,]", raw)
    for idx, part in enumerate(parts, start=1):
        part = part.strip()
        if len(part) >= 8:
            candidates.append((f"part_{idx}", part))

    # sliding word windows
    words = raw.split()
    for size in (4, 6, 8, 10):
        if len(words) >= size:
            for i in range(0, len(words) - size + 1):
                frag = " ".join(words[i:i+size]).strip()
                if len(frag) >= 12:
                    candidates.append((f"window_{size}_{i+1}", frag))

    # dedupe by normalized text
    seen = set()
    deduped = []
    for label, frag in candidates:
        key = normalize_text(frag)
        if key and key not in seen:
            seen.add(key)
            deduped.append((label, frag))
    return deduped


def main():
    FRAG_DIR.mkdir(parents=True, exist_ok=True)

    attr_path = latest_attr_file()
    attr = load_json(attr_path, {})
    if not attr:
        raise RuntimeError("Could not load latest phrase-saver attribution file.")

    scenario_reports = []

    for scenario in attr.get("scenario_reports", []):
        restored_items = [x for x in scenario.get("phrase_status", []) if x.get("restored_by_hybrid")]
        added_lines = scenario.get("added_lines_in_hybrid", [])

        line_reports = []
        for item in added_lines:
            line = item.get("line", "")
            restored_phrases = item.get("restored_phrases", [])
            if not line or not restored_phrases:
                continue

            fragments = []
            for label, frag in fragment_candidates(line):
                matched = [p for p in restored_phrases if contains_phrase(frag, p)]
                if matched:
                    fragments.append({
                        "fragment_type": label,
                        "fragment": frag,
                        "length": len(frag),
                        "restored_phrases": matched,
                        "restored_phrase_count": len(matched),
                        "phrases_per_char": round(len(matched) / max(1, len(frag)), 6),
                    })

            fragments.sort(
                key=lambda x: (-x["restored_phrase_count"], -x["phrases_per_char"], x["length"])
            )

            line_reports.append({
                "line": line,
                "line_kind": classify_line(line),
                "line_length": len(line),
                "restored_phrases": restored_phrases,
                "best_fragments": fragments[:12]
            })

        scenario_reports.append({
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "restored_phrase_count": len(restored_items),
            "line_reports": line_reports
        })

    out = {
        "fragment_attribution_version": "0.1.0",
        "source_attribution_file": attr_path.name,
        "run_id": attr.get("run_id"),
        "timestamp": attr.get("timestamp"),
        "scenario_reports": scenario_reports
    }

    run_id = out.get("run_id") or "unknown-run"
    json_path = FRAG_DIR / f"phrase-fragment-attribution-{run_id}.json"
    md_path = FRAG_DIR / f"phrase-fragment-attribution-{run_id}.md"

    save_json(json_path, out)

    md = []
    md.append("# Phrase-Fragment Attribution Report")
    md.append("")
    md.append(f"- Source attribution file: `{attr_path.name}`")
    md.append(f"- Run ID: `{run_id}`")
    md.append("")

    for scenario in scenario_reports:
        md.append(f"## {scenario['title']}")
        md.append("")
        md.append(f"- Restored phrase count: `{scenario['restored_phrase_count']}`")
        md.append("")

        for line_report in scenario["line_reports"]:
            md.append(f"### Source line")
            md.append(f"- Kind: `{line_report['line_kind']}`")
            md.append(f"- Length: `{line_report['line_length']}`")
            md.append(f"- Line: {line_report['line']}")
            md.append("")
            md.append("#### Best fragments")
            for frag in line_report["best_fragments"][:8]:
                md.append(
                    f"- `{frag['fragment_type']}` | len={frag['length']} | restores={frag['restored_phrase_count']} | ppc={frag['phrases_per_char']} | {frag['fragment']}"
                )
            md.append("")

    md_path.write_text("\n".join(md), encoding="utf-8")

    print("Phrase-fragment attribution completed.")
    print(f"Source attribution: {attr_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
