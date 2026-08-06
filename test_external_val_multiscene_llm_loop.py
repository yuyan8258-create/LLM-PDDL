from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.external_val_feedback_loop import (
    initialise_runtime_context,
    run_refinement_loop,
)
from src.pyramid_demo_v3 import LLMPlanner


SCENE_IDS = (
    "scene_01_blocksworld_basic",
    "scene_02_pyramid",
    "scene_03_large_pyramid",
)


def expected_plan_json(
    scene_id: str,
) -> str:
    context = initialise_runtime_context(
        scene_id
    )

    plan_data = [
        {
            "action": step.action,
            "args": list(step.args),
        }
        for step in context.expected_plan
    ]

    return json.dumps(
        plan_data,
        ensure_ascii=False,
    )


def main() -> None:
    print("=" * 72)
    print("EXTERNAL VAL MULTI-SCENE FAKE LLM LOOP TEST")
    print("=" * 72)

    original_call_ollama = (
        LLMPlanner._call_ollama
    )

    created_run_directories: list[Path] = []

    current_scene_id = ""

    def fake_call_ollama(
        self: LLMPlanner,
        prompt: str,
    ) -> str:
        if current_scene_id not in prompt:
            raise AssertionError(
                f"Prompt does not contain scene ID "
                f"'{current_scene_id}'."
            )

        return expected_plan_json(
            current_scene_id
        )

    try:
        LLMPlanner._call_ollama = (
            fake_call_ollama
        )

        for scene_id in SCENE_IDS:
            current_scene_id = scene_id

            summary: dict[str, Any] = (
                run_refinement_loop(
                    mode="llm",
                    model="fake-test-model",
                    max_iterations=1,
                    scene_id=scene_id,
                )
            )

            run_directory = Path(
                summary["run_directory"]
            )

            created_run_directories.append(
                run_directory
            )

            if not summary.get("success"):
                raise AssertionError(
                    f"Fake LLM loop failed for "
                    f"'{scene_id}'."
                )

            if summary.get("scene") != scene_id:
                raise AssertionError(
                    f"Expected scene '{scene_id}', "
                    f"but summary recorded "
                    f"'{summary.get('scene')}'."
                )

            if summary.get("method") != (
                "pure_llm"
            ):
                raise AssertionError(
                    f"'{scene_id}' was not recorded "
                    f"as pure_llm."
                )

            if summary.get("iterations") != 1:
                raise AssertionError(
                    f"'{scene_id}' should succeed "
                    f"in one iteration."
                )

            required_files = (
                "attempt_01_prompt.txt",
                "attempt_01_raw_llm.txt",
                "attempt_01_plan.json",
                "attempt_01.plan",
                "attempt_01_val.txt",
                "final_validated.plan",
                "run_summary.json",
                "domain.pddl",
                "problem.pddl",
            )

            for file_name in required_files:
                file_path = (
                    run_directory / file_name
                )

                if not file_path.is_file():
                    raise AssertionError(
                        f"Missing '{file_name}' for "
                        f"'{scene_id}'."
                    )

            prompt_text = (
                run_directory
                / "attempt_01_prompt.txt"
            ).read_text(
                encoding="utf-8"
            )

            if scene_id not in prompt_text:
                raise AssertionError(
                    f"Saved prompt does not contain "
                    f"'{scene_id}'."
                )

            print()
            print(f"Scene ID      : {scene_id}")
            print(
                f"Plan steps    : "
                f"{len(summary['final_plan'])}"
            )
            print(
                f"VAL success   : "
                f"{summary['success']}"
            )
            print(
                f"Run directory : "
                f"{run_directory}"
            )
            print("Loop result   : SUCCESS")

    finally:
        LLMPlanner._call_ollama = (
            original_call_ollama
        )

        for run_directory in (
            created_run_directories
        ):
            if run_directory.exists():
                shutil.rmtree(
                    run_directory
                )

    print()
    print(
        "Temporary refinement run directories: "
        "CLEANED"
    )
    print()
    print("=" * 72)
    print(
        "ALL EXTERNAL VAL MULTI-SCENE "
        "FAKE LLM LOOP TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()