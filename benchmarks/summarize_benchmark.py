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

    if latest:
        print(f"Latest run id: {latest.get('latest_run_id')}")
        print(f"Updated at: {latest.get('updated_at')}")
        scenario = latest.get("last_scenario", {})
        print(f"Latest scenario: {scenario.get('title')}")
        print(f"Latest status: {latest.get('status')}")
    else:
        print("No latest benchmark snapshot found.")


if __name__ == "__main__":
    main()

