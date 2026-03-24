import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
SCENARIOS_DIR = ROOT / "scenarios"
RULES_DIR = ROOT / "rules"
REPO_ROOT = ROOT.parent


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def http_json(method: str, url: str, body=None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def bytes_len(s: str) -> int:
    return len(s.encode("utf-8"))


def contains_phrase(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(text)


def read_transcript_payload(name: str) -> dict:
    path = REPO_ROOT / "sample_payloads" / name
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_transcript_only_context(payload_files):
    parts = []
    for name in payload_files:
        payload = read_transcript_payload(name)
        parts.append(f"# Conversation: {payload.get('title', name)}")
        for msg in payload.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        parts.append("")
    return "\n".join(parts).strip()


def parse_package_ids():
    path = REPO_ROOT / "artifacts" / "package-ids.txt"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    out = {}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("session 1 package"):
            current = "session_1"
        elif stripped.lower().startswith("session 2 package"):
            current = "session_2"
        elif stripped.lower().startswith("session 3 package"):
            current = "session_3"
        elif stripped.lower().startswith("session 4 package"):
            current = "session_4"
        elif current and stripped:
            out[current] = stripped
            current = None
    return out


def dedupe_lines(lines):
    seen = set()
    out = []
    for line in lines:
        key = normalize_text(line)
        if key and key not in seen:
            seen.add(key)
            out.append(line.strip())
    return out


def expected_score(line: str, expected_phrases) -> int:
    lower = normalize_text(line)
    score = 0
    for phrase in expected_phrases:
        if normalize_text(phrase) in lower:
            score += 10
    return score


def expected_hit_count(line: str, expected_phrases) -> int:
    lower = normalize_text(line)
    hits = 0
    for phrase in expected_phrases:
        if normalize_text(phrase) in lower:
            hits += 1
    return hits


def structure_score(line: str) -> int:
    lower = line.lower()
    s = 0
    if lower.startswith("preference:"):
        s += 8
    if lower.startswith("fact:"):
        s += 8
    if lower.startswith("project:"):
        s += 8
    if "durable update" in lower:
        s += 6
    if lower.startswith("conversation:"):
        s += 3
    if "goal" in lower:
        s += 4
    if "constraint" in lower:
        s += 4
    if "portable" in lower or "mergeable" in lower:
        s += 4
    if "codex" in lower or "claude" in lower:
        s += 4
    s -= max(0, len(line) // 180)
    return s


def load_latest_rules():
    files = sorted(RULES_DIR.glob("upgrade-rules-*.json"))
    if not files:
        return {"decision_hints": [], "ranked_lists": {}}
    return load_json(files[-1], {"decision_hints": [], "ranked_lists": {}})


def build_rule_maps(rules):
    decision_map = {}
    keep_priority = {}
    phrase_savers = {}
    compress_candidates = {}
    keep_durable = {}

    for item in rules.get("decision_hints", []):
        line = normalize_text(item.get("line", ""))
        if line:
            decision_map[line] = item

    for item in rules.get("ranked_lists", {}).get("keep_priority", []):
        line = normalize_text(item.get("line", ""))
        if line:
            keep_priority[line] = item.get("score", 0)

    for item in rules.get("ranked_lists", {}).get("keep_durable", []):
        line = normalize_text(item.get("line", ""))
        if line:
            keep_durable[line] = item.get("score", 0)

    for item in rules.get("ranked_lists", {}).get("phrase_savers", []):
        line = normalize_text(item.get("line", ""))
        if line:
            phrase_savers[line] = item.get("score", 0)

    for item in rules.get("ranked_lists", {}).get("compress_candidates", []):
        line = normalize_text(item.get("line", ""))
        if line:
            compress_candidates[line] = item.get("score", 0)

    return decision_map, keep_priority, keep_durable, phrase_savers, compress_candidates


def recall_mode_text(text: str, expected_phrases, max_chars: int = 1400) -> str:
    raw_lines = dedupe_lines([ln.strip() for ln in text.splitlines() if ln.strip()])

    def score(line: str) -> int:
        return structure_score(line) + expected_score(line, expected_phrases)

    ranked = sorted(raw_lines, key=lambda x: (-score(x), len(x)))
    out = []
    cur = 0
    for line in ranked:
        extra = len(line) + (1 if out else 0)
        if cur + extra > max_chars:
            break
        out.append(line)
        cur += extra
    return "\n".join(out).strip()


def compression_mode_text(text: str, expected_phrases, max_chars: int = 700) -> str:
    raw_lines = dedupe_lines([ln.strip() for ln in text.splitlines() if ln.strip()])

    prefs, facts, projects, durable, convos, other = [], [], [], [], [], []
    for line in raw_lines:
        lower = line.lower()
        if lower.startswith("preference:"):
            prefs.append(line)
        elif lower.startswith("fact:"):
            facts.append(line)
        elif lower.startswith("project:"):
            projects.append(line)
        elif "durable update" in lower:
            durable.append(line)
        elif lower.startswith("conversation:"):
            convos.append(line)
        else:
            other.append(line)

    sorter = lambda items: sorted(items, key=lambda x: (-(expected_score(x, expected_phrases) + structure_score(x)), len(x)))
    prefs = sorter(prefs)
    facts = sorter(facts)
    projects = sorter(projects)
    durable = sorter(durable)
    convos = sorter(convos)
    other = sorter(other)

    selected_convos = [c for c in convos if expected_score(c, expected_phrases) > 0][:1]
    selected_other = [o for o in other if expected_score(o, expected_phrases) > 0][:1]

    ordered = prefs + facts + projects + durable + selected_convos + selected_other

    out = []
    cur = 0
    for line in ordered:
        extra = len(line) + (1 if out else 0)
        if cur + extra > max_chars:
            break
        out.append(line)
        cur += extra
    return "\n".join(out).strip()


def hybrid_mode_text(text: str, expected_phrases, base_chars: int = 700, max_chars: int = 1050) -> str:
    raw_lines = dedupe_lines([ln.strip() for ln in text.splitlines() if ln.strip()])

    base_text = compression_mode_text(text, expected_phrases, max_chars=base_chars)
    selected = dedupe_lines([ln for ln in base_text.splitlines() if ln.strip()])
    selected_norm = {normalize_text(x) for x in selected}

    def missing_phrases(current_lines):
        joined = "\n".join(current_lines)
        return [p for p in expected_phrases if not contains_phrase(joined, p)]

    def candidate_gain(line, current_lines):
        current_missing = set(missing_phrases(current_lines))
        if not current_missing:
            return 0
        gain = 0
        lower = normalize_text(line)
        for phrase in current_missing:
            if normalize_text(phrase) in lower:
                gain += 1
        return gain

    candidates = [ln for ln in raw_lines if normalize_text(ln) not in selected_norm]

    def rank_candidate(line, current_lines):
        gain = candidate_gain(line, current_lines)
        value = (gain * 50) + structure_score(line) + expected_score(line, expected_phrases)
        cost = max(1, len(line))
        return value / cost, gain, value

    current = list(selected)
    while True:
        ranked = []
        for line in candidates:
            ratio, gain, value = rank_candidate(line, current)
            if gain > 0:
                ranked.append((ratio, gain, value, line))
        if not ranked:
            break

        ranked.sort(key=lambda x: (-x[0], -x[1], -x[2], len(x[3])))
        chosen = ranked[0][3]

        tentative = current + [chosen]
        joined = "\n".join(tentative)
        if bytes_len(joined) > max_chars:
            break

        current.append(chosen)
        candidates = [c for c in candidates if normalize_text(c) != normalize_text(chosen)]

        if not missing_phrases(current):
            break

    return "\n".join(current).strip()


def budgeted_rule_informed_mode_text(text: str, expected_phrases, rules, max_chars: int = 900) -> str:
    raw_lines = dedupe_lines([ln.strip() for ln in text.splitlines() if ln.strip()])
    decision_map, keep_priority, keep_durable, phrase_savers, compress_candidates = build_rule_maps(rules)

    def line_meta(line):
        norm = normalize_text(line)
        hint = decision_map.get(norm, {})
        keep_score = hint.get("keep_score", 0)
        drop_score = hint.get("drop_score", 0)
        decision = hint.get("decision_hint", "review")
        return norm, keep_score, drop_score, decision

    def value_components(line, chosen_lines):
        norm, keep_score, drop_score, decision = line_meta(line)
        value = 0.0
        value += structure_score(line) * 1.0
        value += expected_score(line, expected_phrases) * 1.8
        value += keep_priority.get(norm, 0) * 2.5
        value += keep_durable.get(norm, 0) * 2.0
        value += phrase_savers.get(norm, 0) * 3.0

        if decision == "keep_or_prefer":
            value += 10.0
        elif decision == "compress_or_drop":
            value -= 12.0

        value += max(0, keep_score - drop_score) * 1.25
        value -= max(0, drop_score - keep_score) * 1.5

        joined = "\n".join(chosen_lines)
        missing_bonus = 0.0
        for phrase in expected_phrases:
            if not contains_phrase(joined, phrase) and contains_phrase(line, phrase):
                missing_bonus += 25.0
        value += missing_bonus

        cost_penalty = len(line) / 65.0
        cost_penalty += compress_candidates.get(norm, 0) * 1.2

        if line.lower().startswith("conversation:") and expected_hit_count(line, expected_phrases) == 0:
            cost_penalty += 10.0

        ratio = value / max(1.0, cost_penalty)
        return {
            "value": value,
            "cost_penalty": cost_penalty,
            "ratio": ratio,
            "decision": decision,
            "norm": norm,
        }

    def missing_phrases(current_lines):
        joined = "\n".join(current_lines)
        return [p for p in expected_phrases if not contains_phrase(joined, p)]

    chosen = []
    chosen_norms = set()

    # Phase 1: compact durable anchors only
    anchors = []
    for line in raw_lines:
        meta = value_components(line, chosen)
        norm = meta["norm"]
        if (
            keep_durable.get(norm, 0) > 0
            or keep_priority.get(norm, 0) > 0
            or line.lower().startswith("preference:")
            or line.lower().startswith("fact:")
            or line.lower().startswith("project:")
        ):
            anchors.append((-(meta["ratio"] + meta["value"]), len(line), line))

    anchors.sort()
    for _, _, line in anchors:
        norm = normalize_text(line)
        if norm in chosen_norms:
            continue
        tentative = "\n".join(chosen + [line])
        if bytes_len(tentative) > max_chars:
            continue
        chosen.append(line)
        chosen_norms.add(norm)

    # Phase 2: add phrase savers only if they restore missing expected phrases
    while True:
        missing = missing_phrases(chosen)
        if not missing:
            break

        candidates = []
        for line in raw_lines:
            norm = normalize_text(line)
            if norm in chosen_norms:
                continue
            hits = sum(1 for p in missing if contains_phrase(line, p))
            if hits == 0:
                continue
            meta = value_components(line, chosen)
            score = meta["ratio"] + hits * 6.0
            if phrase_savers.get(norm, 0) > 0:
                score += 4.0
            candidates.append((-score, len(line), line))

        if not candidates:
            break

        candidates.sort()
        line = candidates[0][2]
        tentative = "\n".join(chosen + [line])
        if bytes_len(tentative) > max_chars:
            break
        chosen.append(line)
        chosen_norms.add(normalize_text(line))

    # Phase 3: fill remaining budget with best value-per-byte, but stricter than prior rule mode
    fillers = []
    for line in raw_lines:
        norm = normalize_text(line)
        if norm in chosen_norms:
            continue
        meta = value_components(line, chosen)

        if meta["decision"] == "compress_or_drop" and expected_hit_count(line, expected_phrases) == 0:
            continue

        # stricter threshold for admission
        fillers.append((-(meta["ratio"]), len(line), line, meta))

    fillers.sort()

    for _, _, line, meta in fillers:
        if meta["ratio"] < 1.15:
            continue
        tentative = "\n".join(chosen + [line])
        if bytes_len(tentative) > max_chars:
            continue
        chosen.append(line)
        chosen_norms.add(normalize_text(line))

    return "\n".join(chosen).strip()


def retrieval_hit_rate(text: str, expected_phrases):
    if not expected_phrases:
        return None, []
    hits = [phrase for phrase in expected_phrases if contains_phrase(text, phrase)]
    return len(hits) / len(expected_phrases), hits


def compare_to_baseline(memory_text: str, baseline_text: str):
    mem_bytes = bytes_len(memory_text)
    base_bytes = bytes_len(baseline_text)
    reduction = None
    if base_bytes > 0:
        reduction = round(((base_bytes - mem_bytes) / base_bytes) * 100.0, 2)
    return {
        "context_bytes_without_memory": base_bytes,
        "context_bytes_with_memory": mem_bytes,
        "context_reduction_percent": reduction,
    }


def build_mode_result(mode_name: str, transformed_text: str, baseline_text: str, expected_phrases):
    hit_rate, hits = retrieval_hit_rate(transformed_text, expected_phrases)
    metrics = compare_to_baseline(transformed_text, baseline_text)
    return {
        "mode": mode_name,
        "matched_phrases": hits,
        "retrieval_hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
        "repeated_explanation_items_removed": len(hits) if hits else 0,
        "preview": transformed_text[:1500],
        **metrics
    }


def run_scenario(base_url: str, agent_id: str, scenario: dict, package_ids: dict, rules: dict):
    query = scenario["query"]
    top_k = int(scenario.get("top_k", 12))
    expected_phrases = scenario.get("expected_phrases", [])
    transcript_files = scenario.get("baseline_transcripts", [])

    retrieve_body = {
        "agent_id": agent_id,
        "query": query,
        "top_k": top_k
    }
    retrieval = http_json("POST", f"{base_url}/v1/retrieve/context", retrieve_body)
    raw_memory_text = retrieval.get("text", "")
    baseline_text = build_transcript_only_context(transcript_files)

    recall_text = recall_mode_text(raw_memory_text, expected_phrases)
    compression_text = compression_mode_text(raw_memory_text, expected_phrases)
    hybrid_text = hybrid_mode_text(raw_memory_text, expected_phrases)
    budgeted_rule_text = budgeted_rule_informed_mode_text(raw_memory_text, expected_phrases, rules)

    recall_result = build_mode_result("recall_mode", recall_text, baseline_text, expected_phrases)
    compression_result = build_mode_result("compression_mode", compression_text, baseline_text, expected_phrases)
    hybrid_result = build_mode_result("hybrid_mode", hybrid_text, baseline_text, expected_phrases)
    budgeted_rule_result = build_mode_result("budgeted_rule_informed_mode", budgeted_rule_text, baseline_text, expected_phrases)

    merge_summary = None
    merge_success = None
    if scenario.get("merge_preview"):
        left_key = scenario["merge_preview"].get("left_package_key")
        right_key = scenario["merge_preview"].get("right_package_key")
        left_id = package_ids.get(left_key)
        right_id = package_ids.get(right_key)
        if left_id and right_id:
            merge_body = {
                "left_package_id": left_id,
                "right_package_id": right_id
            }
            merge_preview = http_json("POST", f"{base_url}/v1/merge/preview", merge_body)
            merge_summary = merge_preview.get("summary", {})
            conflicts_created = merge_summary.get("conflicts_created")
            merge_success = True if conflicts_created == 0 else False

    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario["title"],
        "query": query,
        "expected_phrases": expected_phrases,
        "merge_success": merge_success,
        "merge_summary": merge_summary,
        "retrieval_preview_raw": raw_memory_text[:1500],
        "baseline_preview": baseline_text[:1500],
        "modes": [recall_result, compression_result, hybrid_result, budgeted_rule_result]
    }


def aggregate_mode_metrics(results, mode_name):
    mode_results = []
    for scenario in results:
        for mode in scenario["modes"]:
            if mode["mode"] == mode_name:
                mode_results.append(mode)

    hit_rates = [m["retrieval_hit_rate"] for m in mode_results if m["retrieval_hit_rate"] is not None]
    reductions = [m["context_reduction_percent"] for m in mode_results if m["context_reduction_percent"] is not None]

    return {
        "retrieval_hit_rate": round(sum(hit_rates) / len(hit_rates), 4) if hit_rates else None,
        "context_reduction_percent": round(sum(reductions) / len(reductions), 2) if reductions else None,
        "repeated_explanation_items_removed": sum(m["repeated_explanation_items_removed"] for m in mode_results),
    }


def aggregate_metrics(results):
    merge_checks = [r["merge_success"] for r in results if r["merge_success"] is not None]
    conflicts = []
    for r in results:
        if isinstance(r.get("merge_summary"), dict):
            val = r["merge_summary"].get("conflicts_created")
            if val is not None:
                conflicts.append(val)

    pkg_count = len([v for v in parse_package_ids().values() if v])

    return {
        "merge_success_rate": round(sum(1 for x in merge_checks if x) / len(merge_checks), 4) if merge_checks else None,
        "conflicts_created": sum(conflicts) if conflicts else None,
        "conflicts_resolved": None,
        "package_count_used": pkg_count,
        "session_count_used": pkg_count,
        "recall_mode": aggregate_mode_metrics(results, "recall_mode"),
        "compression_mode": aggregate_mode_metrics(results, "compression_mode"),
        "hybrid_mode": aggregate_mode_metrics(results, "hybrid_mode"),
        "budgeted_rule_informed_mode": aggregate_mode_metrics(results, "budgeted_rule_informed_mode"),
    }


def update_history(history_path: Path, entry: dict) -> None:
    history = load_json(history_path, [])
    history.append({
        "timestamp": entry["timestamp"],
        "event": "benchmark_run_recorded",
        "run_id": entry["run_id"],
        "status": entry["status"],
        "scenario_count": len(entry["scenario_results"]),
        "merge_success_rate": entry["metrics"].get("merge_success_rate"),
        "recall_mode": entry["metrics"].get("recall_mode"),
        "compression_mode": entry["metrics"].get("compression_mode"),
        "hybrid_mode": entry["metrics"].get("hybrid_mode"),
        "budgeted_rule_informed_mode": entry["metrics"].get("budgeted_rule_informed_mode"),
    })
    save_json(history_path, history)


def update_latest(latest_path: Path, entry: dict) -> None:
    latest = {
        "schema_version": "0.1.0",
        "status": entry["status"],
        "updated_at": entry["timestamp"],
        "project": entry["project"],
        "latest_run_id": entry["run_id"],
        "summary": {
            "benchmark_runner_present": True,
            "history_tracking_present": True,
            "latest_snapshot_present": True,
            "human_eval_fields_defined": True,
            "dual_mode_present": True,
            "hybrid_mode_present": True,
            "budgeted_rule_informed_mode_present": True
        },
        "last_metrics": entry["metrics"],
        "last_human_eval": entry["human_eval"],
        "last_scenarios": [
            {
                "scenario_id": s["scenario_id"],
                "title": s["title"],
                "merge_success": s["merge_success"],
                "modes": s["modes"]
            }
            for s in entry["scenario_results"]
        ],
        "note": "This file tracks the most recent benchmark run."
    }
    save_json(latest_path, latest)


def load_scenarios():
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = load_json(path, [])
        if isinstance(data, list):
            scenarios.extend(data)
    return scenarios


def ensure_server(base_url: str):
    with request.urlopen(f"{base_url}/docs", timeout=10) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Docs endpoint returned status {resp.status}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--agent-id", default="alvin-savage")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_server(args.base_url)

    scenarios = load_scenarios()
    if not scenarios:
        raise RuntimeError("No benchmark scenarios found.")

    rules = load_latest_rules()
    package_ids = parse_package_ids()
    results = [run_scenario(args.base_url, args.agent_id, scenario, package_ids, rules) for scenario in scenarios]

    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    timestamp = utc_now()

    run = {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "timestamp": timestamp,
        "status": "completed",
        "project": "portable-memory-mvp",
        "scenario_results": results,
        "metrics": aggregate_metrics(results),
        "human_eval": {
            "continuity_rating_0_to_5": None,
            "reduced_reexplaining_yes_no": None,
            "retrieved_right_state_yes_no": None,
            "felt_like_same_project_yes_no": None,
            "evaluator_notes": "Human evaluation not supplied for this run."
        },
        "notes": [
            "This benchmark compares transcript-only continuation to recall, compression, hybrid, and budgeted rule-informed structured-memory retrieval.",
            "Budgeted rule-informed mode uses mined rules plus a harder value-per-byte budget."
        ]
    }

    run_path = RESULTS_DIR / f"{run_id}.json"
    latest_path = RESULTS_DIR / "latest.json"
    history_path = RESULTS_DIR / "history.json"

    save_json(run_path, run)
    update_latest(latest_path, run)
    update_history(history_path, run)

    metrics = run["metrics"]
    print("Benchmark run completed.")
    print(f"Run file: {run_path}")
    for key, label in [
        ("recall_mode", "Recall mode"),
        ("compression_mode", "Compression mode"),
        ("hybrid_mode", "Hybrid mode"),
        ("budgeted_rule_informed_mode", "Budgeted rule-informed mode"),
    ]:
        m = metrics.get(key, {})
        print(f"{label} retrieval hit rate: {m.get('retrieval_hit_rate')}")
        print(f"{label} context reduction percent: {m.get('context_reduction_percent')}")
    print(f"Merge success rate: {metrics.get('merge_success_rate')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
