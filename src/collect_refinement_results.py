from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFINEMENT_ROOT = (
    PROJECT_ROOT
    / "results"
    / "refinement"
)

RESULTS_ROOTS = (
    REFINEMENT_ROOT
    / "scene_02_pyramid",
    REFINEMENT_ROOT
    / "block_building",
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "results"
    / "tables"
)

RUN_OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "refinement_runs.csv"
)

MODEL_OUTPUT_FILE = (
    OUTPUT_DIRECTORY
    / "refinement_model_summary.csv"
)


# The known correct Scene 02 action sequence.
SCENE_02_VALID_PLAN = [
    ("pick-up", ("b4",)),
    ("stack-bridge", ("b4", "b1", "b2")),
    ("pick-up", ("b5",)),
    ("stack-bridge", ("b5", "b2", "b3")),
    ("pick-up", ("pyramid",)),
    ("stack-bridge", ("pyramid", "b4", "b5")),
]


def normalise_plan(
    plan: list[dict[str, Any]] | None,
) -> list[tuple[str, tuple[str, ...]]]:
    """
    Convert a JSON plan into a comparable lowercase form.
    """
    if not plan:
        return []

    normalised = []

    for step in plan:
        action = str(step.get("action", "")).strip().lower()
        args = tuple(
            str(argument).strip().lower()
            for argument in step.get("args", [])
        )

        normalised.append((action, args))

    return normalised


def extract_failure_details(
    attempt: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Extract the structured symbolic failure information
    from one attempt.
    """
    empty_result = {
        "failed_step": "",
        "failed_action": "",
        "error": "",
    }

    if not attempt:
        return empty_result

    feedback = attempt.get("feedback")

    if not isinstance(feedback, dict):
        return empty_result

    details = feedback.get("symbolic_failure_details")

    if not isinstance(details, dict):
        return empty_result

    return {
        "failed_step": details.get("failed_step", ""),
        "failed_action": details.get("failed_action", ""),
        "error": details.get("error", ""),
    }


def infer_root_cause(
    scene_id: str,
    first_attempt: dict[str, Any] | None,
) -> str:
    """
    Infer a high-level planning failure category.

    This is separate from VAL's direct error message.
    """
    if not first_attempt:
        return ""

    plan = normalise_plan(first_attempt.get("plan"))

    # Scene 02-specific pattern:
    # the first six actions already solve the task,
    # but unnecessary actions are appended afterwards.
    if (
        scene_id == "scene_02_pyramid"
        and len(plan)
        > len(SCENE_02_VALID_PLAN)
        and plan[
            : len(SCENE_02_VALID_PLAN)
        ]
        == SCENE_02_VALID_PLAN
    ):
        return "redundant_actions_after_goal_achievement"

    details = extract_failure_details(first_attempt)
    error = str(details["error"]).lower()

    if "handempty" in error:
        return "unsatisfied_precondition_handempty"

    if (
        "right-free" in error
        or "left-free" in error
    ):
        return "support_slot_conflict"

    if error:
        return "other_unsatisfied_precondition"

    return ""


def find_summary_files() -> list[Path]:
    """
    Find run-summary JSON files in both the legacy Scene 02
    result location and the new domain/scene result layout.

    Duplicate runs are removed later using run_directory.
    """

    existing_roots = [
        root
        for root in RESULTS_ROOTS
        if root.exists()
    ]

    if not existing_roots:
        searched_locations = "\n".join(
            f"- {root}"
            for root in RESULTS_ROOTS
        )

        raise FileNotFoundError(
            "No refinement result directories were found.\n"
            f"Searched:\n{searched_locations}"
        )

    candidates: list[Path] = []

    for results_root in existing_roots:
        for json_file in results_root.rglob(
            "*.json"
        ):
            filename = json_file.name.lower()

            if (
                filename == "run_summary.json"
                or filename.endswith(
                    "_summary.json"
                )
            ):
                candidates.append(
                    json_file
                )

    return sorted(
        set(candidates)
    )


def load_run_rows() -> list[dict[str, Any]]:
    summary_files = find_summary_files()

    rows = []
    seen_run_directories: set[str] = set()

    for summary_file in summary_files:
        try:
            data = json.loads(
                summary_file.read_text(
                    encoding="utf-8",
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"Skipping unreadable file: "
                f"{summary_file}\nReason: {exc}"
            )
            continue

        # Ignore JSON files that are not run summaries.
        required_keys = {
            "scene",
            "mode",
            "success",
            "iterations",
            "attempts",
        }

        if not required_keys.issubset(data.keys()):
            continue

        run_directory = str(
            data.get(
                "run_directory",
                summary_file.parent,
            )
        )

        # Avoid counting renamed copies twice.
        if run_directory in seen_run_directories:
            continue

        seen_run_directories.add(run_directory)

        attempts = data.get("attempts", [])

        if not isinstance(attempts, list):
            attempts = []

        first_attempt = attempts[0] if attempts else None
        final_attempt = attempts[-1] if attempts else None

        first_val = (
            first_attempt.get("val", {})
            if isinstance(first_attempt, dict)
            else {}
        )

        first_attempt_valid = bool(
            first_val.get("valid", False)
        )

        final_plan = data.get("final_plan")

        first_plan = (
            first_attempt.get("plan", [])
            if isinstance(first_attempt, dict)
            else []
        )

        first_failure = extract_failure_details(
            first_attempt
        )

        final_failure = (
            extract_failure_details(final_attempt)
            if not data.get("success", False)
            else {
                "failed_step": "",
                "failed_action": "",
                "error": "",
            }
        )

        val_runtimes = []

        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue

            val_data = attempt.get("val", {})

            if not isinstance(val_data, dict):
                continue

            runtime = val_data.get("runtime_seconds")

            if isinstance(runtime, (int, float)):
                val_runtimes.append(float(runtime))

        total_val_runtime = sum(val_runtimes)

        average_val_runtime = (
            total_val_runtime / len(val_runtimes)
            if val_runtimes
            else 0.0
        )

        run_id = Path(run_directory).name

        rows.append(
            {
                "run_id": run_id,
                "scene": data.get("scene", ""),
                "mode": data.get("mode", ""),
                "method": data.get("method", ""),
                "model": data.get("model", ""),
                "success": bool(
                    data.get("success", False)
                ),
                "first_attempt_valid": first_attempt_valid,
                "iterations": data.get("iterations", ""),
                "first_plan_length": len(first_plan),
                "final_plan_length": (
                    len(final_plan)
                    if isinstance(final_plan, list)
                    else ""
                ),
                "first_failed_step":
                    first_failure["failed_step"],
                "first_failed_action":
                    first_failure["failed_action"],
                "first_error":
                    first_failure["error"],
                "final_failed_step":
                    final_failure["failed_step"],
                "final_failed_action":
                    final_failure["failed_action"],
                "final_error":
                    final_failure["error"],
                "inferred_root_cause":
                    infer_root_cause(
                        scene_id=str(
                            data.get("scene", "")
                        ),
                        first_attempt=first_attempt,
                ),
                "total_val_runtime_seconds":
                    round(total_val_runtime, 6),
                "average_val_runtime_seconds":
                    round(average_val_runtime, 6),
                "failure_stage":
                    data.get("failure_stage", ""),
                "run_directory": run_directory,
                "summary_file": str(summary_file),
            }
        )

    return rows


def write_run_csv(
    rows: list[dict[str, Any]],
) -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "run_id",
        "scene",
        "mode",
        "method",
        "model",
        "success",
        "first_attempt_valid",
        "iterations",
        "first_plan_length",
        "final_plan_length",
        "first_failed_step",
        "first_failed_action",
        "first_error",
        "final_failed_step",
        "final_failed_action",
        "final_error",
        "inferred_root_cause",
        "total_val_runtime_seconds",
        "average_val_runtime_seconds",
        "failure_stage",
        "run_directory",
        "summary_file",
    ]

    with RUN_OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def write_model_summary_csv(
    rows: list[dict[str, Any]],
) -> None:
    grouped_rows: dict[
        tuple[str, str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        key = (
            str(row["scene"]),
            str(row["mode"]),
            str(row["method"]),
            str(row["model"]),
        )

        grouped_rows[key].append(row)

    summary_rows = []

    for (
        scene,
        mode,
        method,
        model,
    ), group in sorted(grouped_rows.items()):

        total_runs = len(group)

        first_successes = sum(
            1
            for row in group
            if row["first_attempt_valid"]
        )

        final_successes = sum(
            1
            for row in group
            if row["success"]
        )

        iteration_values = [
            int(row["iterations"])
            for row in group
            if str(row["iterations"]).isdigit()
        ]

        average_iterations = (
            sum(iteration_values)
            / len(iteration_values)
            if iteration_values
            else 0.0
        )

        runtime_values = [
            float(
                row["total_val_runtime_seconds"]
            )
            for row in group
        ]

        average_total_val_runtime = (
            sum(runtime_values)
            / len(runtime_values)
            if runtime_values
            else 0.0
        )

        summary_rows.append(
            {
                "scene": scene,
                "mode": mode,
                "method": method,
                "model": model,
                "total_runs": total_runs,
                "first_attempt_successes":
                    first_successes,
                "first_attempt_success_rate":
                    round(
                        first_successes / total_runs,
                        4,
                    ),
                "final_successes": final_successes,
                "final_success_rate":
                    round(
                        final_successes / total_runs,
                        4,
                    ),
                "average_iterations":
                    round(average_iterations, 4),
                "average_total_val_runtime_seconds":
                    round(
                        average_total_val_runtime,
                        6,
                    ),
            }
        )

    fieldnames = [
        "scene",
        "mode",
        "method",
        "model",
        "total_runs",
        "first_attempt_successes",
        "first_attempt_success_rate",
        "final_successes",
        "final_success_rate",
        "average_iterations",
        "average_total_val_runtime_seconds",
    ]

    with MODEL_OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(summary_rows)


def print_console_summary(
    rows: list[dict[str, Any]],
) -> None:
    print("=" * 78)
    print("REFINEMENT RESULT COLLECTION")
    print("=" * 78)

    print(f"Unique runs found: {len(rows)}")
    print(f"Run-level CSV: {RUN_OUTPUT_FILE}")
    print(f"Model summary CSV: {MODEL_OUTPUT_FILE}")

    print("\nCollected runs:")

    for row in rows:
        print(
            f"- {row['run_id']} | "
            f"{row['model']} | "
            f"success={row['success']} | "
            f"first_valid="
            f"{row['first_attempt_valid']} | "
            f"iterations={row['iterations']}"
        )


def main() -> None:
    rows = load_run_rows()

    if not rows:
        print(
            "No valid run summary files were found."
        )
        raise SystemExit(1)

    write_run_csv(rows)
    write_model_summary_csv(rows)
    print_console_summary(rows)


if __name__ == "__main__":
    main()