from __future__ import annotations

import tempfile
from pathlib import Path

from src.external_tools.fast_downward_runner import (
    run_fast_downward,
)
from src.external_tools.val_runner import run_val
from src.external_val_feedback_loop import (
    PROJECT_ROOT,
    initialise_runtime_context,
)


def main() -> None:
    print("=" * 72)
    print("EXTERNAL FAST DOWNWARD PLAN TEST")
    print("=" * 72)

    scene_ids = (
        "scene_01_blocksworld_basic",
        "scene_02_pyramid",
        "scene_03_large_pyramid",
    )

    # Fast Downward plans and VAL logs are created in a temporary
    # project-local directory so WSL can access them. The complete
    # directory is automatically deleted when the test finishes.
    with tempfile.TemporaryDirectory(
        prefix=".tmp_fast_downward_",
        dir=PROJECT_ROOT,
    ) as temporary_directory:
        temporary_root = Path(
            temporary_directory
        )

        for scene_id in scene_ids:
            context = initialise_runtime_context(
                scene_id
            )

            scene_test_directory = (
                temporary_root / scene_id
            )

            scene_test_directory.mkdir(
                parents=True,
                exist_ok=False,
            )

            planner_plan_file = (
                scene_test_directory
                / "fast_downward.plan"
            )

            val_log_file = (
                scene_test_directory
                / "val_validation.txt"
            )

            print()
            print("-" * 72)
            print(f"Scene ID       : {scene_id}")
            print("-" * 72)

            fd_result = run_fast_downward(
                domain_file=context.domain_file,
                problem_file=context.problem_file,
                plan_file=planner_plan_file,
                alias="lama-first",
                timeout_seconds=120,
            )

            if not fd_result.solved:
                combined_output = (
                    f"{fd_result.stdout}\n"
                    f"{fd_result.stderr}"
                ).strip()

                raise AssertionError(
                    f"Fast Downward failed to solve "
                    f"'{scene_id}'.\n"
                    f"Return code: "
                    f"{fd_result.return_code}\n"
                    f"Planner output:\n"
                    f"{combined_output}"
                )

            if not planner_plan_file.exists():
                raise AssertionError(
                    f"Fast Downward reported success but "
                    f"did not create a plan for "
                    f"'{scene_id}'."
                )

            if not fd_result.plan:
                raise AssertionError(
                    f"Fast Downward returned an empty plan "
                    f"for '{scene_id}'."
                )

            if (
                fd_result.plan_length is not None
                and fd_result.plan_length
                != len(fd_result.plan)
            ):
                raise AssertionError(
                    f"Fast Downward plan-length mismatch "
                    f"for '{scene_id}': reported "
                    f"{fd_result.plan_length}, parsed "
                    f"{len(fd_result.plan)}."
                )

            val_result = run_val(
                domain_file=context.domain_file,
                problem_file=context.problem_file,
                plan_file=planner_plan_file,
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
                    f"VAL rejected the Fast Downward plan "
                    f"for '{scene_id}'.\n"
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

            print(
                f"Problem file   : "
                f"{context.problem_file}"
            )
            print(
                f"Planner solved : "
                f"{fd_result.solved}"
            )
            print(
                f"Plan actions   : "
                f"{len(fd_result.plan)}"
            )
            print(
                f"Reported length: "
                f"{fd_result.plan_length}"
            )
            print(
                f"Plan cost      : "
                f"{fd_result.plan_cost}"
            )
            print(
                f"FD runtime     : "
                f"{fd_result.runtime_seconds:.3f} seconds"
            )
            print(
                f"VAL valid      : "
                f"{val_result.valid}"
            )
            print(
                f"VAL return code: "
                f"{val_result.return_code}"
            )
            print(
                f"VAL runtime    : "
                f"{val_result.runtime_seconds:.3f} seconds"
            )
            print("Pipeline result: SUCCESS")

            print("Planner actions:")

            for index, action in enumerate(
                fd_result.plan,
                start=1,
            ):
                print(
                    f"  {index}. {action}"
                )

    if any(
        PROJECT_ROOT.glob(
            ".tmp_fast_downward_*"
        )
    ):
        raise AssertionError(
            "Temporary Fast Downward test directory "
            "was not cleaned up."
        )

    print()
    print("Temporary planner and VAL files: CLEANED")
    print()
    print("=" * 72)
    print(
        "ALL EXTERNAL FAST DOWNWARD PLAN TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()