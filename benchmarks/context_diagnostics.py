import json
import math
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
DIAG_DIR = ROOT / "diagnostics"


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


def tokenize(text: str):
    return re.findall(r"[a-z0-9_]+", normalize_text(text))


def bytes_len(s: str) -> int:
    return len(s.encode("utf-8"))


def vectorize(text: str):
    return Counter(tokenize(text))


def cosine_similarity(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def shannon_entropy_from_tokens(tokens):
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    total = sum(counts.values())
    ent = 0.0
    for count in counts.values():
        p = count / total
        ent -= p * math.log2(p)
    return ent


def split_lines(text: str):
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


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


def line_expected_score(line: str, expected_phrases):
    lower = normalize_text(line)
    score = 0
    matched = []
    for phrase in expected_phrases:
        p = normalize_text(phrase)
        if p in lower:
            score += 1
            matched.append(phrase)
    return score, matched


def line_cost_score(line: str):
    return bytes_len(line)


def redundancy_score(line, other_lines):
    vec = vectorize(line)
    if not other_lines:
        return 0.0
    sims = [cosine_similarity(vec, vectorize(x)) for x in other_lines if x.strip()]
    if not sims:
        return 0.0
    return max(sims)


def novelty_score(line, selected_lines):
    return 1.0 - redundancy_score(line, selected_lines)


def durability_heuristic(line):
    lower = line.lower()
    score = 0.0
    if lower.startswith("preference:"):
        score += 1.0
    if lower.startswith("fact:"):
        score += 1.0
    if lower.startswith("project:"):
        score += 1.0
    if "goal" in lower:
        score += 0.7
    if "constraint" in lower:
        score += 0.7
    if "portable" in lower or "mergeable" in lower:
        score += 0.5
    if "codex" in lower or "claude" in lower:
        score += 0.5
    if lower.startswith("conversation:"):
        score -= 0.5
    return round(score, 3)


def situational_heuristic(line, query):
    return round(cosine_similarity(vectorize(line), vectorize(query)), 4)


def centrality_heuristic(line, project_anchor):
    return round(cosine_similarity(vectorize(line), vectorize(project_anchor)), 4)


def context_entropy_report(text):
    toks = tokenize(text)
    return {
        "token_count": len(toks),
        "unique_token_count": len(set(toks)),
        "entropy_bits": round(shannon_entropy_from_tokens(toks), 4),
        "bytes": bytes_len(text),
        "lines": len(split_lines(text)),
    }


def build_project_anchor(raw_text):
    preferred = []
    for line in split_lines(raw_text):
        kind = classify_line(line)
        if kind in ("preference", "fact", "project", "durable_update"):
            preferred.append(line)
    if not preferred:
        preferred = split_lines(raw_text)[:8]
    return "\n".join(preferred)


def analyze_mode(mode, raw_text, query, expected_phrases, project_anchor):
    preview = mode.get("preview", "")
    lines = split_lines(preview)

    per_line = []
    selected_so_far = []
    for idx, line in enumerate(lines, start=1):
        exp_score, matched = line_expected_score(line, expected_phrases)
        item = {
            "line_number": idx,
            "line": line,
            "kind": classify_line(line),
            "expected_phrase_hits": exp_score,
            "matched_expected_phrases": matched,
            "cost_bytes": line_cost_score(line),
            "durability_score": durability_heuristic(line),
            "situational_score": situational_heuristic(line, query),
            "centrality_score": centrality_heuristic(line, project_anchor),
            "novelty_score": round(novelty_score(line, selected_so_far), 4),
            "redundancy_score": round(redundancy_score(line, selected_so_far), 4),
        }
        selected_so_far.append(line)
        per_line.append(item)

    total_expected_hits = sum(x["expected_phrase_hits"] for x in per_line)
    likely_durable = [x for x in per_line if x["durability_score"] >= 1.0]
    likely_situational = [x for x in per_line if x["situational_score"] >= 0.12 and x["durability_score"] < 1.0]
    likely_redundant = [x for x in per_line if x["redundancy_score"] >= 0.8]
    likely_costly = sorted(per_line, key=lambda x: (-x["cost_bytes"], x["expected_phrase_hits"]))[:5]

    return {
        "mode": mode.get("mode"),
        "headline_metrics": {
            "retrieval_hit_rate": mode.get("retrieval_hit_rate"),
            "context_reduction_percent": mode.get("context_reduction_percent"),
            "repeated_explanation_items_removed": mode.get("repeated_explanation_items_removed"),
        },
        "preview_entropy": context_entropy_report(preview),
        "expected_phrase_hit_total": total_expected_hits,
        "likely_durable_lines": [
            {
                "line_number": x["line_number"],
                "line": x["line"],
                "durability_score": x["durability_score"],
                "centrality_score": x["centrality_score"],
            }
            for x in likely_durable[:8]
        ],
        "likely_situational_lines": [
            {
                "line_number": x["line_number"],
                "line": x["line"],
                "situational_score": x["situational_score"],
                "matched_expected_phrases": x["matched_expected_phrases"],
            }
            for x in likely_situational[:8]
        ],
        "likely_redundant_lines": [
            {
                "line_number": x["line_number"],
                "line": x["line"],
                "redundancy_score": x["redundancy_score"],
            }
            for x in likely_redundant[:8]
        ],
        "likely_costly_lines": [
            {
                "line_number": x["line_number"],
                "line": x["line"],
                "cost_bytes": x["cost_bytes"],
                "expected_phrase_hits": x["expected_phrase_hits"],
            }
            for x in likely_costly
        ],
        "per_line": per_line,
    }


def pick_latest_run_file():
    runs = sorted(RESULTS_DIR.glob("run-*.json"))
    if not runs:
        raise RuntimeError("No benchmark run files found in benchmarks/results.")
    return runs[-1]


def make_markdown_report(run, scenario_reports):
    lines = []
    lines.append("# Context Diagnostics Report")
    lines.append("")
    lines.append(f"- Run ID: `{run.get('run_id')}`")
    lines.append(f"- Timestamp: `{run.get('timestamp')}`")
    lines.append(f"- Merge success rate: `{run.get('metrics', {}).get('merge_success_rate')}`")
    lines.append("")

    for scenario in scenario_reports:
        lines.append(f"## Scenario: {scenario['title']}")
        lines.append("")
        lines.append(f"- Query: `{scenario['query']}`")
        lines.append(f"- Expected phrases: {len(scenario['expected_phrases'])}")
        lines.append("")

        for mode in scenario["mode_reports"]:
            hm = mode["headline_metrics"]
            pe = mode["preview_entropy"]
            lines.append(f"### {mode['mode']}")
            lines.append("")
            lines.append(f"- Retrieval hit rate: `{hm['retrieval_hit_rate']}`")
            lines.append(f"- Context reduction percent: `{hm['context_reduction_percent']}`")
            lines.append(f"- Repeated explanation items removed: `{hm['repeated_explanation_items_removed']}`")
            lines.append(f"- Preview bytes: `{pe['bytes']}`")
            lines.append(f"- Preview entropy bits: `{pe['entropy_bits']}`")
            lines.append(f"- Preview lines: `{pe['lines']}`")
            lines.append("")

            if mode["likely_durable_lines"]:
                lines.append("#### Likely durable lines")
                for item in mode["likely_durable_lines"][:5]:
                    lines.append(f"- L{item['line_number']}: {item['line']}")
                lines.append("")

            if mode["likely_situational_lines"]:
                lines.append("#### Likely situational lines")
                for item in mode["likely_situational_lines"][:5]:
                    lines.append(f"- L{item['line_number']}: {item['line']}")
                lines.append("")

            if mode["likely_redundant_lines"]:
                lines.append("#### Likely redundant lines")
                for item in mode["likely_redundant_lines"][:5]:
                    lines.append(f"- L{item['line_number']}: {item['line']}")
                lines.append("")

            if mode["likely_costly_lines"]:
                lines.append("#### Likely costly lines")
                for item in mode["likely_costly_lines"][:5]:
                    lines.append(f"- L{item['line_number']} ({item['cost_bytes']} bytes): {item['line']}")
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def main():
    DIAG_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = pick_latest_run_file()
    run = load_json(latest_path, {})
    if not run:
        raise RuntimeError("Latest benchmark run could not be loaded.")

    scenario_reports = []
    for scenario in run.get("scenario_results", []):
        raw_text = scenario.get("retrieval_preview_raw", "")
        query = scenario.get("query", "")
        expected_phrases = scenario.get("expected_phrases", [])
        project_anchor = build_project_anchor(raw_text)

        mode_reports = []
        for mode in scenario.get("modes", []):
            mode_reports.append(analyze_mode(mode, raw_text, query, expected_phrases, project_anchor))

        scenario_reports.append({
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "query": query,
            "expected_phrases": expected_phrases,
            "mode_reports": mode_reports,
        })

    out_json = {
        "diagnostic_version": "0.1.0",
        "source_run_file": str(latest_path.name),
        "run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "scenario_reports": scenario_reports,
    }

    json_path = DIAG_DIR / f"context-diagnostics-{run.get('run_id')}.json"
    md_path = DIAG_DIR / f"context-diagnostics-{run.get('run_id')}.md"

    save_json(json_path, out_json)
    md_path.write_text(make_markdown_report(run, scenario_reports), encoding="utf-8")

    print("Context diagnostics completed.")
    print(f"Source run: {latest_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
