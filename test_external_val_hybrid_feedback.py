from __future__ import annotations

import shutil
from pathlib import Path

from src.external_val_feedback_loop import (
    initialise_runtime_context,
    run_refinement_loop,
)
from src.pyramid_demo_v3 import LLMPlanner
from src.plan_model import PlanStep


SCENE_ID = "scene_01_blocksworld_basic"


def main() -> None:
    print("=" * 72)
    print("EXTERNAL VAL HYBRID FEEDBACK TEST")
    print("=" * 72)

    context = initialise_runtime_context(SCENE_ID)

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
                "fake invalid first plan"
            )

            # Deliberately invalid:
            # blockB cannot be picked up while blockA is still on it.
            return [
                PlanStep(
                    action="pick-up",
                    args=("blockB",),
                ),
            ]

        self.last_raw_response = (
            "fake repaired second plan"
        )

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

    run_directory: Path | None = None

    try:
        LLMPlanner.generate_from_prompt = (
            fake_generate_from_prompt
        )

        summary = run_refinement_loop(
            mode="llm",
            model="fake-hybrid-feedback-model",
            max_iterations=3,
            scene_id=SCENE_ID,
            method="hybrid_feedback",
            provider="ollama",
        )

        run_directory = Path(
            summary["run_directory"]
        )

        if not summary.get("success", False):
            raise AssertionError(
                "Hybrid feedback test did not finish "
                "with a valid plan."
            )

        if summary.get("iterations") != 2:
            raise AssertionError(
                "Expected success on iteration 2, "
                f"but got iteration "
                f"{summary.get('iterations')}."
            )

        if call_count != 2:
            raise AssertionError(
                "Expected exactly two planner calls, "
                f"but got {call_count}."
            )

        if len(prompts_seen) != 2:
            raise AssertionError(
                "Expected exactly two captured prompts."
            )

        first_prompt = prompts_seen[0]
        second_prompt = prompts_seen[1]

        if "PREVIOUS VERIFICATION FEEDBACK" in (
            first_prompt
        ):
            raise AssertionError(
                "Initial prompt unexpectedly contained "
                "verification feedback."
            )

        if "PREVIOUS VERIFICATION FEEDBACK" not in (
            second_prompt
        ):
            raise AssertionError(
                "Repair prompt did not contain the "
                "feedback section."
            )

        if "Return a repaired complete plan" not in (
            second_prompt
        ):
            raise AssertionError(
                "Repair prompt did not contain the "
                "complete-plan repair instruction."
            )

        attempts = summary.get("attempts", [])

        if len(attempts) != 2:
            raise AssertionError(
                "Expected two recorded attempts, "
                f"but got {len(attempts)}."
            )

        if attempts[0].get("success") is not False:
            raise AssertionError(
                "First attempt should be recorded "
                "as unsuccessful."
            )

        if attempts[1].get("success") is not True:
            raise AssertionError(
                "Second attempt should be recorded "
                "as successful."
            )

        feedback_file = (
            run_directory
            / "attempt_01_feedback.json"
        )

        if not feedback_file.exists():
            raise AssertionError(
                "Structured feedback file was not created."
            )

        print()
        print(f"Scene                 : {SCENE_ID}")
        print(f"Planner calls         : {call_count}")
        print(
            "First attempt rejected: SUCCESS"
        )
        print(
            "Structured feedback    : SUCCESS"
        )
        print(
            "Feedback reached prompt: SUCCESS"
        )
        print(
            "Second attempt repaired: SUCCESS"
        )
        print(
            "VAL final acceptance   : SUCCESS"
        )

        print()
        print("=" * 72)
        print(
            "ALL EXTERNAL VAL HYBRID "
            "FEEDBACK TESTS PASSED"
        )
        print("=" * 72)

    finally:
        LLMPlanner.generate_from_prompt = (
            original_generate_from_prompt
        )

        if (
            run_directory is not None
            and run_directory.exists()
        ):
            shutil.rmtree(run_directory)

            print()
            print(
                "Temporary hybrid feedback "
                "run directory: CLEANED"
            )


if __name__ == "__main__":
    main()