import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
ADV_DIR = ROOT / "adversarial"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def bytes_len(s: str) -> int:
    return len((s or "").encode("utf-8"))


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


def retrieval_score(text: str, expected_phrases, matcher):
    if not expected_phrases:
        return None, []
    hits = [p for p in expected_phrases if matcher(text, p)]
    return len(hits) / len(expected_phrases), hits


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


def main():
    ADV_DIR.mkdir(parents=True, exist_ok=True)

    run_path = latest_run_file()
    run = load_json(run_path, {})
    if not run:
        raise RuntimeError("Could not load latest run file.")

    scenario_reports = []
    mode_aggregate = {}

    for scenario in run.get("scenario_results", []):
        sid = scenario.get("scenario_id")
        title = scenario.get("title")
        expected = scenario.get("expected_phrases", [])
        variants_by_phrase = {p: adversarial_phrase_variants(p) for p in expected}

        scenario_mode_reports = []
        modes = mode_map(scenario)

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
                    soft_ok = phrase_hit_soft(text, variant, 0.45)
                    if soft_ok:
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

            adversarial_rate = round(len(adversarial_hits) / len(expected), 4) if expected else None

            report = {
                "mode": mode_name,
                "exact_hit_rate": round(exact_hit, 4) if exact_hit is not None else None,
                "soft_hit_rate": round(soft_hit, 4) if soft_hit is not None else None,
                "adversarial_variant_hit_rate": adversarial_rate,
                "context_reduction_percent": mode.get("context_reduction_percent"),
                "matched_exact_phrases": exact_hits,
                "matched_soft_phrases": soft_hits,
                "matched_adversarial_variants": adversarial_hits,
                "preview_bytes": bytes_len(text),
            }
            scenario_mode_reports.append(report)

            agg = mode_aggregate.setdefault(mode_name, {
                "exact": [],
                "soft": [],
                "adv": [],
                "reduction": [],
            })
            if report["exact_hit_rate"] is not None:
                agg["exact"].append(report["exact_hit_rate"])
            if report["soft_hit_rate"] is not None:
                agg["soft"].append(report["soft_hit_rate"])
            if report["adversarial_variant_hit_rate"] is not None:
                agg["adv"].append(report["adversarial_variant_hit_rate"])
            if report["context_reduction_percent"] is not None:
                agg["reduction"].append(report["context_reduction_percent"])

        scenario_mode_reports.sort(key=lambda x: (
            -(x["adversarial_variant_hit_rate"] if x["adversarial_variant_hit_rate"] is not None else -1),
            -(x["soft_hit_rate"] if x["soft_hit_rate"] is not None else -1),
            -(x["exact_hit_rate"] if x["exact_hit_rate"] is not None else -1),
            -(x["context_reduction_percent"] if x["context_reduction_percent"] is not None else -999),
        ))

        scenario_reports.append({
            "scenario_id": sid,
            "title": title,
            "expected_phrase_count": len(expected),
            "mode_reports": scenario_mode_reports,
            "winner_by_adversarial_rate": scenario_mode_reports[0]["mode"] if scenario_mode_reports else None,
        })

    summary = {}
    for mode_name, agg in mode_aggregate.items():
        summary[mode_name] = {
            "avg_exact_hit_rate": round(sum(agg["exact"]) / len(agg["exact"]), 4) if agg["exact"] else None,
            "avg_soft_hit_rate": round(sum(agg["soft"]) / len(agg["soft"]), 4) if agg["soft"] else None,
            "avg_adversarial_variant_hit_rate": round(sum(agg["adv"]) / len(agg["adv"]), 4) if agg["adv"] else None,
            "avg_context_reduction_percent": round(sum(agg["reduction"]) / len(agg["reduction"]), 2) if agg["reduction"] else None,
        }

    out = {
        "adversarial_validation_version": "0.1.0",
        "source_run_file": run_path.name,
        "source_run_id": run.get("run_id"),
        "timestamp": run.get("timestamp"),
        "scenario_count": len(scenario_reports),
        "summary_by_mode": summary,
        "scenario_reports": scenario_reports,
    }

    run_id = out.get("source_run_id") or "unknown-run"
    json_path = ADV_DIR / f"adversarial-pruning-validation-{run_id}.json"
    md_path = ADV_DIR / f"adversarial-pruning-validation-{run_id}.md"

    save_json(json_path, out)

    lines = []
    lines.append("# Adversarial Pruning Validation")
    lines.append("")
    lines.append(f"- Source run: `{run_path.name}`")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Scenario count: `{out['scenario_count']}`")
    lines.append("")
    lines.append("## Summary by Mode")
    lines.append("")

    for mode_name, stats in sorted(summary.items()):
        lines.append(f"### {mode_name}")
        lines.append(f"- Avg exact hit rate: `{stats['avg_exact_hit_rate']}`")
        lines.append(f"- Avg soft hit rate: `{stats['avg_soft_hit_rate']}`")
        lines.append(f"- Avg adversarial variant hit rate: `{stats['avg_adversarial_variant_hit_rate']}`")
        lines.append(f"- Avg context reduction percent: `{stats['avg_context_reduction_percent']}`")
        lines.append("")

    lines.append("## Scenario Winners")
    lines.append("")
    for scenario in scenario_reports:
        lines.append(f"### {scenario['title']}")
        lines.append(f"- Winner by adversarial rate: `{scenario['winner_by_adversarial_rate']}`")
        top = scenario["mode_reports"][:4]
        for m in top:
            lines.append(
                f"- `{m['mode']}` | adv={m['adversarial_variant_hit_rate']} | soft={m['soft_hit_rate']} | exact={m['exact_hit_rate']} | reduction={m['context_reduction_percent']}"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("Adversarial pruning validation completed.")
    print(f"Source run: {run_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
