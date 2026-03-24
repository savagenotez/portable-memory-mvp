import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
OUT_DIR = ROOT / "adversarial_robustness"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s:_-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def token_set(s: str):
    return set(t for t in normalize_text(s).split() if t)


def jaccard(a: str, b: str) -> float:
    sa = token_set(a)
    sb = token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def phrase_hit_exact(text: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(text)


def phrase_hit_soft(text: str, phrase: str, threshold: float = 0.60) -> bool:
    norm_text = normalize_text(text)
    norm_phrase = normalize_text(phrase)
    if not norm_phrase:
        return False
    if norm_phrase in norm_text:
        return True

    p_tokens = norm_phrase.split()
    t_tokens = norm_text.split()
    if not p_tokens or not t_tokens:
        return False

    win = max(len(p_tokens), 3)
    best = 0.0
    if len(t_tokens) < win:
        best = jaccard(norm_text, norm_phrase)
    else:
        for i in range(0, len(t_tokens) - win + 1):
            chunk = " ".join(t_tokens[i:i+win])
            score = jaccard(chunk, norm_phrase)
            if score > best:
                best = score
    return best >= threshold


def adversarial_phrase_variants(phrase: str):
    p = phrase.strip()
    variants = {p}

    swaps = {
        "portable": "movable",
        "persistent": "durable",
        "mergeable": "combinable",
        "memory": "context memory",
        "context": "working context",
        "working": "active",
        "constraints": "limits",
        "constraint": "limit",
        "project": "system",
        "goal": "objective",
        "goals": "objectives",
        "proven": "demonstrated",
        "proof": "evidence",
        "next": "following",
        "workflow": "process",
        "tooling": "tools",
        "shared": "common",
        "layer": "stack",
        "update": "revision",
        "retrieval": "recovery",
        "fastest": "quickest",
    }

    words = p.split()
    for i, w in enumerate(words):
        key = re.sub(r"[^A-Za-z0-9]", "", w).lower()
        if key in swaps:
            alt = list(words)
            alt[i] = swaps[key]
            variants.add(" ".join(alt))

    if len(words) >= 4:
        variants.add(" ".join(words[:-1]))
        variants.add(" ".join(words[1:]))

    if ":" in p:
        left, right = p.split(":", 1)
        variants.add(right.strip())
        variants.add(left.strip())

    return sorted(v for v in variants if v.strip())


def retrieval_score(text: str, expected_phrases, matcher):
    if not expected_phrases:
        return None, []
    hits = [phrase for phrase in expected_phrases if matcher(text, phrase)]
    return len(hits) / len(expected_phrases), hits


def latest_run_file():
    files = sorted(RESULTS_DIR.glob("run-*.json"))
    if not files:
        raise RuntimeError("No benchmark run files found.")
    return files[-1]


def mode_map(scenario):
    out = {}
    for mode in scenario.get("modes", []):
        out[mode.get("mode")] = mode
    return out


def summarize_mode(report):
    return {
        "exact_hit_rate": report.get("exact_hit_rate"),
        "soft_hit_rate": report.get("soft_hit_rate"),
        "adversarial_variant_hit_rate": report.get("adversarial_variant_hit_rate"),
        "context_reduction_percent": report.get("context_reduction_percent"),
        "preview_bytes": report.get("preview_bytes"),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_run_file()
    run = load_json(run_path, {})
    if not run:
        raise RuntimeError("Could not load latest run file.")

    scenario_reports = []
    aggregate = {}
    target_mode = "robustness_aware_pruning_mode"
    compare_modes = [
        "hybrid_mode",
        "phrase_saver_per_byte_mode",
        "phrase_saver_pruning_mode",
        "threshold_gated_adaptive_mode",
        "scenario_classifier_mode",
        "compression_mode",
    ]

    for scenario in run.get("scenario_results", []):
        sid = scenario.get("scenario_id")
        title = scenario.get("title")
        expected = scenario.get("expected_phrases", [])
        variants_by_phrase = {p: adversarial_phrase_variants(p) for p in expected}
        modes = mode_map(scenario)

        reports = {}
        for mode_name, mode in modes.items():
            text = mode.get("preview", "")

            exact_hit, exact_hits = retrieval_score(text, expected, phrase_hit_exact)
            soft_hit, soft_hits = retrieval_score(text, expected, lambda t, p: phrase_hit_soft(t, p, 0.60))

            adversarial_hits = []
            for phrase, variants in variants_by_phrase.items():
                matched = False
                best_variant = None
                best_score = -1.0
                for variant in variants:
                    score = jaccard(text, variant)
                    if phrase_hit_soft(text, variant, 0.45):
                        matched = True
                        best_variant = variant
                        break
                    if score > best_score:
                        best_score = score
                        best_variant = variant
                if matched:
                    adversarial_hits.append({
                        "expected_phrase": phrase,
                        "matched_variant": best_variant,
                    })

            reports[mode_name] = {
                "mode": mode_name,
                "exact_hit_rate": round(exact_hit, 4) if exact_hit is not None else None,
                "soft_hit_rate": round(soft_hit, 4) if soft_hit is not None else None,
                "adversarial_variant_hit_rate": round(len(adversarial_hits) / len(expected), 4) if expected else None,
                "context_reduction_percent": mode.get("context_reduction_percent"),
                "preview_bytes": len(text.encode("utf-8")),
                "matched_exact_phrases": exact_hits,
                "matched_soft_phrases": soft_hits,
                "matched_adversarial_variants": adversarial_hits,
            }

            agg = aggregate.setdefault(mode_name, {"exact": [], "soft": [], "adv": [], "reduction": []})
            if reports[mode_name]["exact_hit_rate"] is not None:
                agg["exact"].append(reports[mode_name]["exact_hit_rate"])
            if reports[mode_name]["soft_hit_rate"] is not None:
                agg["soft"].append(reports[mode_name]["soft_hit_rate"])
            if reports[mode_name]["adversarial_variant_hit_rate"] is not None:
                agg["adv"].append(reports[mode_name]["adversarial_variant_hit_rate"])
            if reports[mode_name]["context_reduction_percent"] is not None:
                agg["reduction"].append(reports[mode_name]["context_reduction_percent"])

        target = reports.get(target_mode)
        comparisons = []
        target_wins = []
        target_losses = []

        for cm in compare_modes:
            if cm not in reports:
                continue
            other = reports[cm]

            t_tuple = (
                target.get("adversarial_variant_hit_rate", -1),
                target.get("soft_hit_rate", -1),
                target.get("exact_hit_rate", -1),
                target.get("context_reduction_percent", -999),
            )
            o_tuple = (
                other.get("adversarial_variant_hit_rate", -1),
                other.get("soft_hit_rate", -1),
                other.get("exact_hit_rate", -1),
                other.get("context_reduction_percent", -999),
            )

            winner = target_mode if t_tuple >= o_tuple else cm
            if winner == target_mode:
                target_wins.append(cm)
            else:
                target_losses.append(cm)

            comparisons.append({
                "against_mode": cm,
                "winner": winner,
                "target": summarize_mode(target),
                "other": summarize_mode(other),
            })

        scenario_reports.append({
            "scenario_id": sid,
            "title": title,
            "expected_phrase_count": len(expected),
            "target_mode": target_mode,
            "target_summary": summarize_mode(target),
            "target_wins_against": target_wins,
            "target_loses_against": target_losses,
            "comparisons": comparisons,
        })

    summary_by_mode = {}
    for mode_name, vals in aggregate.items():
        summary_by_mode[mode_name] = {
            "avg_exact_hit_rate": round(sum(vals["exact"]) / len(vals["exact"]), 4) if vals["exact"] else None,
            "avg_soft_hit_rate": round(sum(vals["soft"]) / len(vals["soft"]), 4) if vals["soft"] else None,
            "avg_adversarial_variant_hit_rate": round(sum(vals["adv"]) / len(vals["adv"]), 4) if vals["adv"] else None,
            "avg_context_reduction_percent": round(sum(vals["reduction"]) / len(vals["reduction"]), 2) if vals["reduction"] else None,
        }

    overall = {
        "target_mode": target_mode,
        "scenario_count": len(scenario_reports),
        "unbeaten_scenarios": sum(1 for s in scenario_reports if not s["target_loses_against"]),
        "scenarios_with_any_loss": sum(1 for s in scenario_reports if s["target_loses_against"]),
        "loss_counts_by_mode": {},
    }

    for s in scenario_reports:
        for loser_to in s["target_loses_against"]:
            overall["loss_counts_by_mode"][loser_to] = overall["loss_counts_by_mode"].get(loser_to, 0) + 1

    out = {
        "adversarial_robustness_validation_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "overall": overall,
        "summary_by_mode": summary_by_mode,
        "scenario_reports": scenario_reports,
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = OUT_DIR / f"robustness-aware-pruning-validation-{run_id}.json"
    md_path = OUT_DIR / f"robustness-aware-pruning-validation-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Robustness-Aware Pruning Validation")
    lines.append("")
    lines.append(f"- Source run: `{run_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Target mode: `{target_mode}`")
    lines.append(f"- Scenario count: `{overall['scenario_count']}`")
    lines.append(f"- Unbeaten scenarios: `{overall['unbeaten_scenarios']}`")
    lines.append(f"- Scenarios with any loss: `{overall['scenarios_with_any_loss']}`")
    lines.append(f"- Loss counts by mode: `{overall['loss_counts_by_mode']}`")
    lines.append("")
    lines.append("## Mode Summary")
    lines.append("")
    for mode_name, stats in sorted(summary_by_mode.items()):
        lines.append(f"### {mode_name}")
        lines.append(f"- Avg exact hit rate: `{stats['avg_exact_hit_rate']}`")
        lines.append(f"- Avg soft hit rate: `{stats['avg_soft_hit_rate']}`")
        lines.append(f"- Avg adversarial variant hit rate: `{stats['avg_adversarial_variant_hit_rate']}`")
        lines.append(f"- Avg context reduction percent: `{stats['avg_context_reduction_percent']}`")
        lines.append("")
    lines.append("## Scenario Comparison")
    lines.append("")
    for s in scenario_reports:
        lines.append(f"### {s['title']}")
        lines.append(f"- Target summary: `{s['target_summary']}`")
        lines.append(f"- Wins against: `{s['target_wins_against']}`")
        lines.append(f"- Loses against: `{s['target_loses_against']}`")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Robustness-aware pruning adversarial validation completed.")
    print(f"Source run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    print("")
    print(f"Unbeaten scenarios: {overall['unbeaten_scenarios']} / {overall['scenario_count']}")
    print(f"Loss counts by mode: {overall['loss_counts_by_mode']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
