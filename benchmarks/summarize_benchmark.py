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
    merge_success_rate = metrics.get("merge_success_rate")
    print(f"Merge success rate: {merge_success_rate}")

    recall = metrics.get("recall_mode", {})
    compression = metrics.get("compression_mode", {})

    if recall:
        print("")
        print("Recall mode")
        print(f"  Retrieval hit rate: {recall.get('retrieval_hit_rate')}")
        print(f"  Context reduction percent: {recall.get('context_reduction_percent')}")
        print(f"  Repeated explanation items removed: {recall.get('repeated_explanation_items_removed')}")

    if compression:
        print("")
        print("Compression mode")
        print(f"  Retrieval hit rate: {compression.get('retrieval_hit_rate')}")
        print(f"  Context reduction percent: {compression.get('context_reduction_percent')}")
        print(f"  Repeated explanation items removed: {compression.get('repeated_explanation_items_removed')}")

    if not recall and not compression:
        print(f"Average retrieval hit rate: {metrics.get('retrieval_hit_rate')}")
        print(f"Average context reduction percent: {metrics.get('context_reduction_percent')}")


if __name__ == "__main__":
    main()
