from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import src.run_batch_refinement as batch_module


def main() -> None:
    print("=" * 72)
    print("RUN BATCH SCENE SELECTION TEST")
    print("=" * 72)

    original_batch_results_root = (
        batch_module.BATCH_RESULTS_ROOT
    )
    original_run_refinement_loop = (
        batch_module.run_refinement_loop
    )
    original_refresh = (
        batch_module.refresh_existing_csv_summaries
    )

    calls: list[dict[str, Any]] = []

    def fake_run_refinement_loop(
        mode: str,
        model: str,
        max_iterations: int,
        scene_id: str,
        method: str | None = None,
    ) -> dict[str, Any]:
        calls.append(
            {
                "mode": mode,
                "model": model,
                "max_iterations": max_iterations,
                "scene_id": scene_id,
                "method": method,
            }
        )

        return {
            "scene": scene_id,
            "mode": mode,
            "method": method,
            "model": model,
            "success": True,
            "iterations": 1,
            "run_directory": (
                f"fake/{scene_id}/run_{len(calls):02d}"
            ),
        }

    try:
        with tempfile.TemporaryDirectory(
            prefix="batch_scene_test_"
        ) as temporary_directory:
            temporary_root = Path(
                temporary_directory
            )

            batch_module.BATCH_RESULTS_ROOT = (
                temporary_root / "batches"
            )

            batch_module.run_refinement_loop = (
                fake_run_refinement_loop
            )

            batch_module.refresh_existing_csv_summaries = (
                lambda: None
            )

            summary = batch_module.run_batch(
                scene_id="scene_03_large_pyramid",
                model="fake-test-model",
                number_of_runs=2,
                max_iterations=1,
            )

            if len(calls) != 2:
                raise AssertionError(
                    "Expected two independent loop calls."
                )

            for call in calls:
                if call["method"] != "pure_llm":
                    raise AssertionError(
                        "Batch did not pass the resolved "
                        "pure_llm method to the loop."
                    )

            for call in calls:
                if call["scene_id"] != (
                    "scene_03_large_pyramid"
                ):
                    raise AssertionError(
                        "Batch did not pass the requested "
                        "scene ID to run_refinement_loop()."
                    )

                if call["mode"] != "llm":
                    raise AssertionError(
                        "Batch did not use LLM mode."
                    )

            if summary.get("scene") != (
                "scene_03_large_pyramid"
            ):
                raise AssertionError(
                    "Batch summary did not preserve "
                    "the requested scene ID."
                )

            if summary.get(
                "successful_runs"
            ) != 2:
                raise AssertionError(
                    "Expected two successful fake runs."
                )

            batch_directory = Path(
                summary["batch_directory"]
            )

            config_file = (
                batch_directory
                / "batch_config.json"
            )

            summary_file = (
                batch_directory
                / "batch_summary.json"
            )

            if not config_file.is_file():
                raise AssertionError(
                    "batch_config.json was not created."
                )

            if not summary_file.is_file():
                raise AssertionError(
                    "batch_summary.json was not created."
                )

            config_data = json.loads(
                config_file.read_text(
                    encoding="utf-8"
                )
            )

            if config_data.get("scene") != (
                "scene_03_large_pyramid"
            ):
                raise AssertionError(
                    "batch_config.json contains "
                    "the wrong scene ID."
                )

            if (
                "scene_03_large_pyramid"
                not in batch_directory.name
            ):
                raise AssertionError(
                    "Batch directory name does not "
                    "contain the scene ID."
                )

            print()
            print(
                "Requested scene : "
                "scene_03_large_pyramid"
            )
            print(
                f"Loop calls      : {len(calls)}"
            )
            print(
                "Successful runs : "
                f"{summary['successful_runs']}"
            )
            print(
                "Config scene    : "
                f"{config_data['scene']}"
            )
            print("Batch result    : SUCCESS")

    finally:
        batch_module.BATCH_RESULTS_ROOT = (
            original_batch_results_root
        )
        batch_module.run_refinement_loop = (
            original_run_refinement_loop
        )
        batch_module.refresh_existing_csv_summaries = (
            original_refresh
        )

    print()
    print(
        "Temporary batch directory: CLEANED"
    )
    print()
    print("=" * 72)
    print(
        "ALL RUN BATCH SCENE SELECTION "
        "TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()