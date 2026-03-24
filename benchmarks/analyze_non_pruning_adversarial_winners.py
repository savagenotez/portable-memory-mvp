import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ADV_SUMMARY_DIR = ROOT / "adversarial_summary"
ADV_DIR = ROOT / "adversarial"
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "adversarial_explanations"


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


def bytes_len(s: str) -> int:
    return len((s or "").encode("utf-8"))


def latest_file(dir_path: Path, pattern: str):
    files = sorted(dir_path.glob(pattern))
    if not files:
        raise RuntimeError(f"No files found for pattern: {pattern}")
    return files[-1]


def mode_map(scenario):
    out = {}
    for mode in scenario.get("modes", []):
        out[mode.get("mode")] = mode
    return out


def adv_mode_map(scenario):
    out = {}
    for mode in scenario.get("mode_reports", []):
        out[mode.get("mode")] = mode
    return out


def token_set(s: str):
    return set(t for t in re.sub(r"[^a-z0-9\s]", " ", normalize_text(s)).split() if t)


def overlap_score(a: str, b: str) -> float:
    sa = token_set(a)
    sb = token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sb))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    adv_summary_path = latest_file(ADV_SUMMARY_DIR, "adversarial-winner-summary-*.json")
    adv_path = latest_file(ADV_DIR, "adversarial-pruning-validation-*.json")
    run_path = latest_file(RESULTS_DIR, "run-*.json")

    adv_summary = load_json(adv_summary_path, {})
    adv = load_json(adv_path, {})
    run = load_json(run_path, {})

    if not adv_summary or not adv or not run:
        raise RuntimeError("Could not load one or more required input files.")

    run_scenarios = {s.get("scenario_id"): s for s in run.get("scenario_results", [])}
    adv_scenarios = {s.get("scenario_id"): s for s in adv.get("scenario_reports", [])}

    non_pruning = [
        x for x in adv_summary.get("winner_details", [])
        if x.get("winner_mode") and x.get("winner_mode") != "phrase_saver_pruning_mode"
    ]

    reports = []

    for item in non_pruning:
        sid = item.get("scenario_id")
        run_s = run_scenarios.get(sid, {})
        adv_s = adv_scenarios.get(sid, {})

        run_modes = mode_map(run_s)
        adv_modes = adv_mode_map(adv_s)

        pruning_run = run_modes.get("phrase_saver_pruning_mode", {})
        winner_run = run_modes.get(item.get("winner_mode"), {})
        pruning_adv = adv_modes.get("phrase_saver_pruning_mode", {})
        winner_adv = adv_modes.get(item.get("winner_mode"), {})

        expected_phrases = run_s.get("expected_phrases", [])
        pruning_preview = pruning_run.get("preview", "")
        winner_preview = winner_run.get("preview", "")

        pruning_missing = [p for p in expected_phrases if p not in pruning_run.get("matched_phrases", [])]
        winner_missing = [p for p in expected_phrases if p not in winner_run.get("matched_phrases", [])]

        phrase_diffs = []
        for phrase in expected_phrases:
            p_overlap = overlap_score(pruning_preview, phrase)
            w_overlap = overlap_score(winner_preview, phrase)
            phrase_diffs.append({
                "phrase": phrase,
                "pruning_exact": phrase in pruning_run.get("matched_phrases", []),
                "winner_exact": phrase in winner_run.get("matched_phrases", []),
                "pruning_overlap": round(p_overlap, 4),
                "winner_overlap": round(w_overlap, 4),
                "winner_adv_variant_match": any(
                    m.get("expected_phrase") == phrase for m in winner_adv.get("matched_adversarial_variants", [])
                ),
                "pruning_adv_variant_match": any(
                    m.get("expected_phrase") == phrase for m in pruning_adv.get("matched_adversarial_variants", [])
                ),
            })

        likely_reasons = []

        if (winner_adv.get("adversarial_variant_hit_rate") or 0) > (pruning_adv.get("adversarial_variant_hit_rate") or 0):
            likely_reasons.append("winner_has_higher_adversarial_variant_hit_rate")

        if bytes_len(winner_preview) > bytes_len(pruning_preview):
            likely_reasons.append("winner_kept_more_context_than_pruning")

        if len(winner_missing) < len(pruning_missing):
            likely_reasons.append("winner_missed_fewer_expected_phrases_under_exact_check")

        overlap_advantage_phrases = [
            x["phrase"] for x in phrase_diffs
            if x["winner_overlap"] > x["pruning_overlap"]
        ]
        if overlap_advantage_phrases:
            likely_reasons.append("winner_preserved_better_token_overlap_for_some_phrases")

        reports.append({
            "scenario_id": sid,
            "title": item.get("title"),
            "winner_mode": item.get("winner_mode"),
            "winner_adversarial_variant_hit_rate": item.get("winner_adversarial_variant_hit_rate"),
            "pruning_adversarial_variant_hit_rate": pruning_adv.get("adversarial_variant_hit_rate"),
            "winner_soft_hit_rate": item.get("winner_soft_hit_rate"),
            "pruning_soft_hit_rate": pruning_adv.get("soft_hit_rate"),
            "winner_exact_hit_rate": item.get("winner_exact_hit_rate"),
            "pruning_exact_hit_rate": pruning_adv.get("exact_hit_rate"),
            "winner_context_reduction_percent": item.get("winner_context_reduction_percent"),
            "pruning_context_reduction_percent": pruning_run.get("context_reduction_percent"),
            "winner_preview_bytes": bytes_len(winner_preview),
            "pruning_preview_bytes": bytes_len(pruning_preview),
            "winner_missing_exact_phrases": winner_missing,
            "pruning_missing_exact_phrases": pruning_missing,
            "phrase_diffs": phrase_diffs,
            "likely_reasons": likely_reasons,
            "winner_preview": winner_preview[:1500],
            "pruning_preview": pruning_preview[:1500],
        })

    out = {
        "non_pruning_analysis_version": "0.1.0",
        "source_adversarial_summary_file": adv_summary_path.name,
        "source_adversarial_file": adv_path.name,
        "source_run_file": run_path.name,
        "source_run_id": adv_summary.get("source_run_id"),
        "scenario_count": len(reports),
        "reports": reports,
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"non-pruning-winner-analysis-{run_id}.json"
    md_path = OUT_DIR / f"non-pruning-winner-analysis-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Non-Pruning Adversarial Winner Analysis")
    lines.append("")
    lines.append(f"- Source adversarial summary: `{adv_summary_path.name}`")
    lines.append(f"- Source adversarial validation: `{adv_path.name}`")
    lines.append(f"- Source benchmark run: `{run_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Non-pruning winner scenarios: `{len(reports)}`")
    lines.append("")

    for report in reports:
        lines.append(f"## {report['title']}")
        lines.append("")
        lines.append(f"- Winner mode: `{report['winner_mode']}`")
        lines.append(f"- Winner adversarial hit rate: `{report['winner_adversarial_variant_hit_rate']}`")
        lines.append(f"- Pruning adversarial hit rate: `{report['pruning_adversarial_variant_hit_rate']}`")
        lines.append(f"- Winner soft hit rate: `{report['winner_soft_hit_rate']}`")
        lines.append(f"- Pruning soft hit rate: `{report['pruning_soft_hit_rate']}`")
        lines.append(f"- Winner exact hit rate: `{report['winner_exact_hit_rate']}`")
        lines.append(f"- Pruning exact hit rate: `{report['pruning_exact_hit_rate']}`")
        lines.append(f"- Winner context reduction percent: `{report['winner_context_reduction_percent']}`")
        lines.append(f"- Pruning context reduction percent: `{report['pruning_context_reduction_percent']}`")
        lines.append(f"- Winner bytes: `{report['winner_preview_bytes']}`")
        lines.append(f"- Pruning bytes: `{report['pruning_preview_bytes']}`")
        lines.append("")
        lines.append("### Likely reasons")
        for reason in report["likely_reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("### Exact-missing phrases")
        lines.append(f"- Winner missing: {report['winner_missing_exact_phrases']}")
        lines.append(f"- Pruning missing: {report['pruning_missing_exact_phrases']}")
        lines.append("")
        lines.append("### Phrase-level differences")
        for diff in report["phrase_diffs"]:
            lines.append(
                f"- `{diff['phrase']}` | winner_exact={diff['winner_exact']} pruning_exact={diff['pruning_exact']} "
                f"| winner_overlap={diff['winner_overlap']} pruning_overlap={diff['pruning_overlap']} "
                f"| winner_adv={diff['winner_adv_variant_match']} pruning_adv={diff['pruning_adv_variant_match']}"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Non-pruning winner analysis completed.")
    print(f"Source adversarial summary: {adv_summary_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print(f"Non-pruning winner scenarios found: {len(reports)}")
    for report in reports:
        print(f"  {report['scenario_id']} :: {report['title']} :: winner={report['winner_mode']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
