import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8-sig")


def build_placeholder_run() -> dict:
    run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    timestamp = utc_now()

    return {
        "schema_version": "0.1.0",
        "run_id": run_id,
        "timestamp": timestamp,
        "status": "skeleton_run",
        "project": "portable-memory-mvp",
        "scenario": {
            "scenario_id": "skeleton-demo",
            "title": "Benchmark skeleton placeholder run",
            "mode": "scaffold_only",
            "description": "This is a placeholder benchmark run produced by the benchmark runner skeleton."
        },
        "metrics": {
            "merge_success_rate": None,
            "conflicts_created": None,
            "conflicts_resolved": None,
            "retrieval_hit_rate": None,
            "retrieval_relevance_score": None,
            "context_bytes_without_memory": None,
            "context_bytes_with_memory": None,
            "context_reduction_percent": None,
            "repeated_explanation_items_removed": None,
            "package_count_used": None,
            "session_count_used": None
        },
        "human_eval": {
            "continuity_rating_0_to_5": None,
            "reduced_reexplaining_yes_no": None,
            "retrieved_right_state_yes_no": None,
            "felt_like_same_project_yes_no": None,
            "evaluator_notes": "No human evaluation captured in skeleton run."
        },
        "notes": [
            "Benchmark runner skeleton executed successfully.",
            "Real benchmark logic has not been implemented yet."
        ]
    }


def update_history(history_path: Path, entry: dict) -> None:
    history = load_json(history_path, [])
    history.append({
        "timestamp": entry["timestamp"],
        "event": "benchmark_run_recorded",
        "run_id": entry["run_id"],
        "status": entry["status"],
        "scenario_id": entry["scenario"]["scenario_id"]
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
            "human_eval_fields_defined": True
        },
        "last_scenario": entry["scenario"],
        "last_metrics": entry["metrics"],
        "last_human_eval": entry["human_eval"],
        "note": "This file tracks the most recent benchmark run."
    }
    save_json(latest_path, latest)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    run = build_placeholder_run()
    run_path = RESULTS_DIR / f"{run['run_id']}.json"
    latest_path = RESULTS_DIR / "latest.json"
    history_path = RESULTS_DIR / "history.json"

    save_json(run_path, run)
    update_latest(latest_path, run)
    update_history(history_path, run)

    print("Benchmark skeleton run created.")
    print(f"Run file: {run_path}")
    print(f"Latest file: {latest_path}")
    print(f"History file: {history_path}")


if __name__ == "__main__":
    main()

