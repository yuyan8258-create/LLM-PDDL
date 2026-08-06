from __future__ import annotations

import json
import tempfile
from pathlib import Path

import src.collect_refinement_results as collector


def write_summary(
    path: Path,
    scene_id: str,
    run_id: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = {
        "scene": scene_id,
        "mode": "llm",
        "method": "pure_llm",
        "model": "fake-test-model",
        "success": True,
        "iterations": 1,
        "attempts": [
            {
                "plan": [
                    {
                        "action": "pick-up",
                        "args": ["test-object"],
                    }
                ],
                "val": {
                    "valid": True,
                    "runtime_seconds": 0.1,
                },
                "feedback": None,
            }
        ],
        "final_plan": [
            {
                "action": "pick-up",
                "args": ["test-object"],
            }
        ],
        "run_directory": str(
            path.parent / run_id
        ),
    }

    path.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    print("=" * 72)
    print("COLLECT REFINEMENT MULTI-SCENE TEST")
    print("=" * 72)

    original_results_roots = (
        collector.RESULTS_ROOTS
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix="collector_multiscene_"
        ) as temporary_directory:
            root = Path(
                temporary_directory
            )

            legacy_root = (
                root
                / "results"
                / "refinement"
                / "scene_02_pyramid"
            )

            domain_root = (
                root
                / "results"
                / "refinement"
                / "block_building"
            )

            write_summary(
                legacy_root
                / "run_legacy"
                / "run_summary.json",
                scene_id="scene_02_pyramid",
                run_id="run_legacy",
            )

            write_summary(
                domain_root
                / "scene_01_blocksworld_basic"
                / "run_scene_01"
                / "run_summary.json",
                scene_id=(
                    "scene_01_blocksworld_basic"
                ),
                run_id="run_scene_01",
            )

            write_summary(
                domain_root
                / "scene_03_large_pyramid"
                / "run_scene_03"
                / "run_summary.json",
                scene_id=(
                    "scene_03_large_pyramid"
                ),
                run_id="run_scene_03",
            )

            collector.RESULTS_ROOTS = (
                legacy_root,
                domain_root,
            )

            summary_files = (
                collector.find_summary_files()
            )

            if len(summary_files) != 3:
                raise AssertionError(
                    "Expected three summary files, "
                    f"found {len(summary_files)}."
                )

            rows = collector.load_run_rows()

            if len(rows) != 3:
                raise AssertionError(
                    "Expected three collected runs, "
                    f"found {len(rows)}."
                )

            collected_scenes = {
                str(row["scene"])
                for row in rows
            }

            expected_scenes = {
                "scene_01_blocksworld_basic",
                "scene_02_pyramid",
                "scene_03_large_pyramid",
            }

            if collected_scenes != (
                expected_scenes
            ):
                raise AssertionError(
                    "Collector returned incorrect "
                    f"scenes: {collected_scenes}"
                )

            scene_01_cause = next(
                row["inferred_root_cause"]
                for row in rows
                if row["scene"]
                == "scene_01_blocksworld_basic"
            )

            if scene_01_cause:
                raise AssertionError(
                    "Scene 01 incorrectly received "
                    "a Scene 02-specific root cause."
                )

            print()
            print(
                f"Summary files : "
                f"{len(summary_files)}"
            )
            print(
                f"Collected runs: {len(rows)}"
            )
            print(
                "Scenes        : "
                + ", ".join(
                    sorted(collected_scenes)
                )
            )
            print(
                "Scene isolation: SUCCESS"
            )

    finally:
        collector.RESULTS_ROOTS = (
            original_results_roots
        )

    print()
    print(
        "Temporary collector data: CLEANED"
    )
    print()
    print("=" * 72)
    print(
        "ALL COLLECT REFINEMENT "
        "MULTI-SCENE TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()