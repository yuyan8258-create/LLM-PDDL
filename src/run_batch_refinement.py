from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.external_val_feedback_loop import (
    SCENE_NAME,
    resolve_experiment_method,
    run_refinement_loop,
)
from src.collect_refinement_results import (
    load_run_rows,
    print_console_summary,
    write_model_summary_csv,
    write_run_csv,
)

BATCH_RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "refinement"
    / "batches"
)


def sanitise_name(value: str) -> str:
    return (
        value.strip()
        .replace(":", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def save_json(data: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def refresh_existing_csv_summaries() -> None:
    rows = load_run_rows()

    if not rows:
        print(
            "Warning: no valid run summaries were found, "
            "so the CSV files were not updated."
        )
        return

    write_run_csv(rows)
    write_model_summary_csv(rows)
    print_console_summary(rows)


def run_batch(
    scene_id: str,
    model: str,
    number_of_runs: int,
    max_iterations: int,
) -> dict[str, Any]:
    if number_of_runs < 1:
        raise ValueError("--runs must be at least 1.")

    if max_iterations < 1:
        raise ValueError("--max-iterations must be at least 1.")

    method = resolve_experiment_method(
        mode="llm",
        max_iterations=max_iterations,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_scene_id = sanitise_name(
        scene_id
    )
    safe_model_name = sanitise_name(
        model
    )

    batch_id = (
        f"batch_{method}_{safe_scene_id}_"
        f"{safe_model_name}_{timestamp}"
    )
    batch_directory = BATCH_RESULTS_ROOT / batch_id
    batch_directory.mkdir(parents=True, exist_ok=False)

    batch_started_at = datetime.now()

    batch_config = {
        "batch_id": batch_id,
        "scene": scene_id,
        "model": model,
        "method": method,
        "number_of_runs": number_of_runs,
        "max_iterations": max_iterations,
        "started_at": batch_started_at.isoformat(timespec="seconds"),
        "batch_directory": str(batch_directory),
    }

    save_json(
        batch_config,
        batch_directory / "batch_config.json",
    )

    run_records: list[dict[str, Any]] = []

    print("=" * 78)
    print("BATCH REFINEMENT EXPERIMENT")
    print("=" * 78)
    print(f"Batch ID        : {batch_id}")
    print(f"Scene           : {scene_id}")
    print(f"Model           : {model}")
    print(f"Method          : {method}")
    print(f"Independent runs: {number_of_runs}")
    print(f"Max iterations  : {max_iterations}")
    print(f"Batch directory : {batch_directory}")
    print("=" * 78)

    for batch_run_index in range(1, number_of_runs + 1):
        print()
        print("#" * 78)
        print(
            f"INDEPENDENT RUN "
            f"{batch_run_index}/{number_of_runs}"
        )
        print("#" * 78)

        run_started_at = datetime.now()

        try:
            summary = run_refinement_loop(
                mode="llm",
                model=model,
                max_iterations=max_iterations,
                scene_id=scene_id,
            )

            run_finished_at = datetime.now()

            run_record = {
                "batch_run_index": batch_run_index,
                "completed": True,
                "success": bool(summary.get("success", False)),
                "scene": summary.get("scene", ""),
                "mode": summary.get("mode", "llm"),
                "method": summary.get("method", method),
                "model": summary.get("model", model),
                "iterations": summary.get("iterations", ""),
                "failure_stage": summary.get("failure_stage", ""),
                "run_directory": summary.get("run_directory", ""),
                "started_at": run_started_at.isoformat(timespec="seconds"),
                "finished_at": run_finished_at.isoformat(timespec="seconds"),
                "duration_seconds": round(
                    (run_finished_at - run_started_at).total_seconds(),
                    3,
                ),
            }

        except Exception as exc:
            run_finished_at = datetime.now()

            run_record = {
                "batch_run_index": batch_run_index,
                "completed": False,
                "success": False,
                "scene": scene_id,
                "mode": "llm",
                "method": method,
                "model": model,
                "iterations": "",
                "failure_stage": "unhandled_batch_exception",
                "error": str(exc),
                "run_directory": "",
                "started_at": run_started_at.isoformat(timespec="seconds"),
                "finished_at": run_finished_at.isoformat(timespec="seconds"),
                "duration_seconds": round(
                    (run_finished_at - run_started_at).total_seconds(),
                    3,
                ),
            }

            print()
            print(
                "This independent run raised an exception, "
                "but the batch will continue."
            )
            print(f"Error: {exc}")

        run_records.append(run_record)

        save_json(
            run_records,
            batch_directory / "batch_runs_partial.json",
        )

    batch_finished_at = datetime.now()

    completed_runs = sum(
        1 for record in run_records if record["completed"]
    )
    successful_runs = sum(
        1 for record in run_records if record["success"]
    )
    failed_runs = number_of_runs - successful_runs

    collection_success = True
    collection_error = ""

    try:
        refresh_existing_csv_summaries()
    except Exception as exc:
        collection_success = False
        collection_error = str(exc)
        print()
        print(
            "The batch runs finished, but updating "
            "the CSV summaries failed."
        )
        print(f"Collection error: {exc}")

    batch_summary = {
        **batch_config,
        "finished_at": batch_finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round(
            (batch_finished_at - batch_started_at).total_seconds(),
            3,
        ),
        "completed_runs": completed_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "completion_rate": round(completed_runs / number_of_runs, 4),
        "success_rate": round(successful_runs / number_of_runs, 4),
        "result_collection_success": collection_success,
        "result_collection_error": collection_error,
        "runs": run_records,
    }

    save_json(
        batch_summary,
        batch_directory / "batch_summary.json",
    )

    print()
    print("=" * 78)
    print("BATCH COMPLETE")
    print("=" * 78)
    print(f"Completed runs : {completed_runs}")
    print(f"Successful runs: {successful_runs}")
    print(f"Failed runs    : {failed_runs}")
    print(
        "CSV collection : "
        f"{'SUCCESS' if collection_success else 'FAILED'}"
    )
    print(
        "Batch summary  : "
        f"{batch_directory / 'batch_summary.json'}"
    )
    print(
        "Run-level CSV  : "
        f"{PROJECT_ROOT / 'results' / 'tables' / 'refinement_runs.csv'}"
    )
    print(
        "Model summary  : "
        f"{PROJECT_ROOT / 'results' / 'tables' / 'refinement_model_summary.csv'}"
    )

    return batch_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run multiple independent LLM-to-VAL "
            "refinement experiments."
        )
    )

    parser.add_argument(
        "--scene",
        default=SCENE_NAME,
        help=(
            "Scene ID used for every independent "
            "run in this batch."
        ),
    )

    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Ollama model name.",
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="Number of independent experiment runs.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help=(
            "Maximum attempts inside each independent run. "
            "Use 1 for pure LLM and more than 1 for hybrid feedback."
        ),
    )

    args = parser.parse_args()

    run_batch(
        scene_id=args.scene,
        model=args.model,
        number_of_runs=args.runs,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()
