from __future__ import annotations

import tempfile
from pathlib import Path

from src.external_tools.val_runner import run_val
from src.external_val_feedback_loop import (
    PROJECT_ROOT,
    initialise_runtime_context,
)
from src.plan_model import plan_to_pddl_text


def main() -> None:
    print("=" * 72)
    print("EXTERNAL VAL REFERENCE PLAN TEST")
    print("=" * 72)

    expected_lengths = {
        "scene_01_blocksworld_basic": 4,
        "scene_02_pyramid": 6,
        "scene_03_large_pyramid": 12,
    }

    # Plan files and VAL logs are written into one temporary directory
    # inside the project and removed automatically when the test ends.
    with tempfile.TemporaryDirectory(
        prefix=".tmp_val_reference_",
        dir=PROJECT_ROOT,
    ) as temporary_directory:
        temporary_root = Path(
            temporary_directory
        )

        for scene_id, expected_length in (
            expected_lengths.items()
        ):
            context = initialise_runtime_context(
                scene_id
            )

            if len(context.expected_plan) != (
                expected_length
            ):
                raise AssertionError(
                    f"'{scene_id}' expected "
                    f"{expected_length} plan steps, "
                    f"but received "
                    f"{len(context.expected_plan)}."
                )

            scene_test_directory = (
                temporary_root / scene_id
            )

            scene_test_directory.mkdir(
                parents=True,
                exist_ok=False,
            )

            plan_file = (
                scene_test_directory
                / "reference.plan"
            )

            val_log_file = (
                scene_test_directory
                / "val_output.txt"
            )

            plan_file.write_text(
                plan_to_pddl_text(
                    list(context.expected_plan)
                ),
                encoding="utf-8",
                newline="\n",
            )

            val_result = run_val(
                domain_file=context.domain_file,
                problem_file=context.problem_file,
                plan_file=plan_file,
                log_file=val_log_file,
                verbose=False,
                timeout_seconds=60,
            )

            if not val_result.valid:
                combined_output = (
                    f"{val_result.stdout}\n"
                    f"{val_result.stderr}"
                ).strip()

                raise AssertionError(
                    f"VAL rejected reference plan for "
                    f"'{scene_id}'.\n"
                    f"Return code: "
                    f"{val_result.return_code}\n"
                    f"VAL output:\n"
                    f"{combined_output}"
                )

            if not val_log_file.exists():
                raise AssertionError(
                    f"VAL log was not created for "
                    f"'{scene_id}'."
                )

            if val_result.raw_log_file is None:
                raise AssertionError(
                    f"ValResult did not record the log path "
                    f"for '{scene_id}'."
                )

            print()
            print(f"Scene ID       : {scene_id}")
            print(
                f"Plan steps     : "
                f"{len(context.expected_plan)}"
            )
            print(f"Domain file    : {context.domain_file}")
            print(f"Problem file   : {context.problem_file}")
            print(f"VAL valid      : {val_result.valid}")
            print(
                f"Return code    : "
                f"{val_result.return_code}"
            )
            print(
                f"Runtime        : "
                f"{val_result.runtime_seconds:.3f} seconds"
            )
            print("Reference plan : SUCCESS")

    if any(
        PROJECT_ROOT.glob(
            ".tmp_val_reference_*"
        )
    ):
        raise AssertionError(
            "Temporary VAL reference-plan directory "
            "was not cleaned up."
        )

    print()
    print("Temporary plan and VAL log files: CLEANED")
    print()
    print("=" * 72)
    print("ALL EXTERNAL VAL REFERENCE PLAN TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()