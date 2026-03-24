import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    history_path = RESULTS_DIR / "history.json"
    latest_path = RESULTS_DIR / "latest.json"

    history = load_json(history_path, [])
    latest = load_json(latest_path, {})

    print("Portable Memory MVP - Benchmark Summary")
    print("-" * 48)
    print(f"History entries: {len(history)}")

    if not latest:
        print("No latest benchmark snapshot found.")
        return

    print(f"Latest run id: {latest.get('latest_run_id')}")
    print(f"Updated at: {latest.get('updated_at')}")

    metrics = latest.get("last_metrics", {})
    print(f"Merge success rate: {metrics.get('merge_success_rate')}")

    for mode_name, label in [
        ("recall_mode", "Recall mode"),
        ("compression_mode", "Compression mode"),
        ("hybrid_mode", "Hybrid mode"),
        ("phrase_saver_per_byte_mode", "Phrase-saver-per-byte mode"),
        ("phrase_fragment_per_byte_mode", "Phrase-fragment-per-byte mode"),
        ("title_aware_fragment_bundle_mode", "Title-aware fragment bundle mode"),
        ("threshold_gated_adaptive_mode", "Threshold-gated adaptive mode"),
        ("learned_boundary_controller_mode", "Learned-boundary controller mode"),
    ]:
        mode = metrics.get(mode_name, {})
        if mode:
            print("")
            print(label)
            print(f"  Retrieval hit rate: {mode.get('retrieval_hit_rate')}")
            print(f"  Context reduction percent: {mode.get('context_reduction_percent')}")
            print(f"  Repeated explanation items removed: {mode.get('repeated_explanation_items_removed')}")
            if "controller_choices" in mode:
                print(f"  Controller choices: {mode.get('controller_choices')}")


if __name__ == "__main__":
    main()
