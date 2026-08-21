from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from src.external_val_feedback_loop import (
    initialise_runtime_context,
    run_refinement_loop,
)
from src.pyramid_demo_v3 import LLMPlanner
from src.plan_model import PlanStep


SCENE_ID = "scene_01_blocksworld_basic"


def build_valid_repair_plan() -> list[PlanStep]:
    return [
        PlanStep(
            action="unstack",
            args=("blockA", "blockB"),
        ),
        PlanStep(
            action="put-down",
            args=("blockA",),
        ),
        PlanStep(
            action="pick-up",
            args=("blockB",),
        ),
        PlanStep(
            action="stack",
            args=("blockB", "blockC"),
        ),
    ]


def run_malformed_case(
    case_name: str,
    malformed_plan_factory: Callable[[], list[PlanStep]],
    expected_error_text: str,
) -> None:
    original_generate_from_prompt = (
        LLMPlanner.generate_from_prompt
    )

    prompts_seen: list[str] = []
    call_count = 0

    def fake_generate_from_prompt(
        self: LLMPlanner,
        prompt: str,
    ) -> list[PlanStep]:
        nonlocal call_count

        call_count += 1
        prompts_seen.append(prompt)

        if call_count == 1:
            self.last_raw_response = (
                f"fake malformed plan: {case_name}"
            )
            return malformed_plan_factory()

        self.last_raw_response = (
            f"fake repaired plan: {case_name}"
        )
        return build_valid_repair_plan()

    run_directory: Path | None = None
    temporary_results: tempfile.TemporaryDirectory[str] | None = None

    try:
        temporary_results = tempfile.TemporaryDirectory(
            prefix=f"formal_malformed_{case_name}_"
        )

        formal_results_base = (
            Path(temporary_results.name)
            / "formal"
        )

        LLMPlanner.generate_from_prompt = (
            fake_generate_from_prompt
        )

        summary = run_refinement_loop(
            mode="llm",
            model=f"fake-{case_name}-model",
            max_iterations=3,
            scene_id=SCENE_ID,
            method="hybrid_feedback",
            provider="ollama",
            results_base=formal_results_base,
        )

        run_directory = Path(
            summary["run_directory"]
        )

        if not summary.get("success", False):
            raise AssertionError(
                f"{case_name}: repaired plan did not succeed."
            )

        if summary.get("iterations") != 2:
            raise AssertionError(
                f"{case_name}: expected success on iteration 2, "
                f"got {summary.get('iterations')}."
            )

        if call_count != 2:
            raise AssertionError(
                f"{case_name}: expected two planner calls, "
                f"got {call_count}."
            )

        if len(prompts_seen) != 2:
            raise AssertionError(
                f"{case_name}: expected two captured prompts."
            )

        second_prompt = prompts_seen[1]

        if "PREVIOUS VERIFICATION FEEDBACK" not in second_prompt:
            raise AssertionError(
                f"{case_name}: repair prompt did not contain "
                "verification feedback."
            )

        if expected_error_text not in second_prompt:
            raise AssertionError(
                f"{case_name}: malformed-plan error was not "
                "passed back to the repair prompt."
            )

        feedback_file = (
            run_directory
            / "attempt_01_feedback.json"
        )

        if not feedback_file.exists():
            raise AssertionError(
                f"{case_name}: feedback file was not created."
            )

        feedback = json.loads(
            feedback_file.read_text(
                encoding="utf-8"
            )
        )

        symbolic_details = feedback.get(
            "symbolic_failure_details",
            {},
        )

        if expected_error_text not in (
            symbolic_details.get("error", "")
        ):
            raise AssertionError(
                f"{case_name}: fallback feedback did not "
                "preserve the verifier error."
            )

        if "malformed" not in (
            symbolic_details.get("message", "")
        ).lower():
            raise AssertionError(
                f"{case_name}: fallback feedback did not "
                "identify the candidate as malformed."
            )

        attempts = summary.get("attempts", [])

        if len(attempts) != 2:
            raise AssertionError(
                f"{case_name}: expected two recorded attempts, "
                f"got {len(attempts)}."
            )

        first_val_summary = attempts[0].get(
            "val",
            {},
        )

        if "stdout" in first_val_summary:
            raise AssertionError(
                "Run summary unexpectedly contains raw "
                "VAL stdout."
            )

        if "stderr" in first_val_summary:
            raise AssertionError(
                "Run summary unexpectedly contains raw "
                "VAL stderr."
            )

        for required_key in (
            "valid",
            "return_code",
            "runtime_seconds",
            "log_file",
            "stdout_chars",
            "stderr_chars",
        ):
            if required_key not in first_val_summary:
                raise AssertionError(
                    "Compact VAL summary is missing "
                    f"'{required_key}'."
                )

        if attempts[0].get("success") is not False:
            raise AssertionError(
                f"{case_name}: first attempt should fail."
            )

        if attempts[1].get("success") is not True:
            raise AssertionError(
                f"{case_name}: second attempt should succeed."
            )

        if not (
            run_directory / "run_summary.json"
        ).exists():
            raise AssertionError(
                f"{case_name}: run_summary.json was not created."
            )

        print()
        print(f"Case                     : {case_name}")
        print("Malformed plan rejected  : SUCCESS")
        print("Fallback feedback created: SUCCESS")
        print("Verifier error preserved : SUCCESS")
        print("Feedback reached prompt  : SUCCESS")
        print("Second attempt repaired  : SUCCESS")
        print("VAL final acceptance     : SUCCESS")
        print("Compact VAL summary      : SUCCESS")
        print("Run summary created      : SUCCESS")

    finally:
        LLMPlanner.generate_from_prompt = (
            original_generate_from_prompt
        )

        if (
            run_directory is not None
            and run_directory.exists()
        ):
            shutil.rmtree(run_directory)

        if temporary_results is not None:
            temporary_results.cleanup()


def main() -> None:
    print("=" * 72)
    print("EXTERNAL VAL MALFORMED HYBRID FEEDBACK TEST")
    print("=" * 72)

    initialise_runtime_context(SCENE_ID)

    run_malformed_case(
        case_name="unknown_action",
        malformed_plan_factory=lambda: [
            PlanStep(
                action="clear",
                args=("blockA",),
            ),
        ],
        expected_error_text="unknown action 'clear'",
    )

    run_malformed_case(
        case_name="wrong_arity",
        malformed_plan_factory=lambda: [
            PlanStep(
                action="stack",
                args=(
                    "blockA",
                    "blockB",
                    "blockC",
                ),
            ),
        ],
        expected_error_text="requires 2 argument(s)",
    )

    print()
    print("=" * 72)
    print(
        "ALL EXTERNAL VAL MALFORMED "
        "HYBRID FEEDBACK TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()