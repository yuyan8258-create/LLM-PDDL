from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Reuse your existing modules instead of rewriting them.
from src.external_tools.val_runner import run_val
from src.pyramid_demo_v3 import (
    LLMPlanner,
    PlanStep,
    REFERENCE_PLAN,
    SCENE_DESCRIPTION,
    SymbolicVerifier,
)


# ---------------------------------------------------------------------------
# Scene configuration
# ---------------------------------------------------------------------------

SCENE_NAME = "scene_02_pyramid"

DOMAIN_FILE = (
    PROJECT_ROOT
    / "generated_pddl"
    / SCENE_NAME
    / "domain.pddl"
)

PROBLEM_FILE = (
    PROJECT_ROOT
    / "generated_pddl"
    / SCENE_NAME
    / "problem.pddl"
)

RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "refinement"
    / SCENE_NAME
)


# ---------------------------------------------------------------------------
# Plan conversion
# ---------------------------------------------------------------------------

def plan_to_pddl_text(plan: list[PlanStep]) -> str:
    """
    Convert a list of PlanStep objects into a VAL-compatible plan.

    Example:
        PlanStep("pick-up", ["B4"])

    becomes:
        (pick-up b4)
    """

    lines: list[str] = []

    for step in plan:
        action = step.action.strip().lower()

        arguments = [
            str(argument).strip().lower()
            for argument in step.args
        ]

        if arguments:
            line = f"({action} {' '.join(arguments)})"
        else:
            line = f"({action})"

        lines.append(line)

    return "\n".join(lines) + "\n"


def save_plan_file(
    plan: list[PlanStep],
    output_path: Path,
) -> None:
    """
    Save a candidate plan in the exact text format expected by VAL.
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        plan_to_pddl_text(plan),
        encoding="utf-8",
        newline="\n",
    )


def plan_to_dict(plan: list[PlanStep]) -> list[dict[str, Any]]:
    """
    Convert PlanStep objects into JSON-serializable dictionaries.
    """

    return [
        {
            "action": step.action,
            "args": step.args,
        }
        for step in plan
    ]


# ---------------------------------------------------------------------------
# Feedback generation
# ---------------------------------------------------------------------------

def make_structured_feedback(
    plan: list[PlanStep],
    val_valid: bool,
    val_stdout: str,
    val_stderr: str,
) -> dict[str, Any]:
    """
    Generate structured repair feedback.

    VAL is the final authority for plan validity.

    The existing Python SymbolicVerifier is used to identify the failed
    action, missing preconditions, and state before failure.
    """

    symbolic_verifier = SymbolicVerifier()

    symbolic_valid, symbolic_message, _ = symbolic_verifier.verify(
        plan=plan,
        initial_state=SCENE_DESCRIPTION["initial_state"],
        goal_state=SCENE_DESCRIPTION["goal_state"],
        verbose=False,
    )

    try:
        symbolic_details: Any = json.loads(symbolic_message)
    except json.JSONDecodeError:
        symbolic_details = {
            "message": symbolic_message,
        }

    val_combined_output = (
        f"{val_stdout}\n{val_stderr}"
    ).strip()

    # Keep only the final section of VAL output in the LLM feedback.
    # The full output is still saved separately in the VAL log file.
    val_output_lines = val_combined_output.splitlines()
    val_output_tail = "\n".join(val_output_lines[-40:])

    feedback = {
        "validation_authority": "VAL",
        "val_valid": val_valid,
        "symbolic_verifier_valid": symbolic_valid,
        "previous_plan": plan_to_dict(plan),
        "symbolic_failure_details": symbolic_details,
        "val_output_tail": val_output_tail,
        "repair_instruction": (
            "Generate a complete corrected plan. "
            "Fix the failed action and any earlier actions that caused "
            "the failed precondition. Do not return only a partial plan."
        ),
    }

    # This case means the lightweight verifier and VAL disagree.
    if symbolic_valid and not val_valid:
        feedback["warning"] = (
            "The lightweight symbolic verifier accepted the plan, "
            "but VAL rejected it. Treat VAL as authoritative and inspect "
            "the VAL output when repairing the plan."
        )

    return feedback


# ---------------------------------------------------------------------------
# Mock plans for pipeline testing
# ---------------------------------------------------------------------------

def build_mock_invalid_plan() -> list[PlanStep]:
    """
    Deliberately invalid plan.

    After picking up B4, the robot hand is not empty.
    The next pick-up(B5) therefore violates the handempty precondition.
    """

    return [
        PlanStep(
            action="pick-up",
            args=["B4"],
        ),
        PlanStep(
            action="pick-up",
            args=["B5"],
        ),
        PlanStep(
            action="stack-bridge",
            args=["B4", "B1", "B2"],
        ),
        PlanStep(
            action="stack-bridge",
            args=["B5", "B2", "B3"],
        ),
        PlanStep(
            action="pick-up",
            args=["pyramid"],
        ),
        PlanStep(
            action="stack-bridge",
            args=["pyramid", "B4", "B5"],
        ),
    ]


def get_mock_plan(iteration: int) -> list[PlanStep]:
    """
    Mock iteration 1 is invalid.
    Mock iteration 2 uses the known valid reference plan.
    """

    if iteration == 1:
        return build_mock_invalid_plan()

    return [
        PlanStep(
            action=step.action,
            args=list(step.args),
        )
        for step in REFERENCE_PLAN
    ]


# ---------------------------------------------------------------------------
# Run directory and result saving
# ---------------------------------------------------------------------------

def sanitise_name(value: str) -> str:
    """
    Convert text into a safe Windows directory name.
    """
    return (
        value.strip()
        .replace(":", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def get_next_run_number(
    prefix: str,
) -> int:
    """
    Find the next available run number for a given prefix.

    Example:
        run_pure_llm_qwen2.5_latest_01
        run_pure_llm_qwen2.5_latest_02

    Returns:
        3
    """
    existing_numbers: list[int] = []

    for directory in RESULTS_ROOT.glob(f"{prefix}_*"):
        if not directory.is_dir():
            continue

        final_part = directory.name.rsplit(
            "_",
            maxsplit=1,
        )[-1]

        if final_part.isdigit():
            existing_numbers.append(
                int(final_part)
            )

    if existing_numbers:
        return max(existing_numbers) + 1

    return 1


def create_run_directory(
    mode: str,
    model: str,
    max_iterations: int,
) -> Path:
    """
    Create a clearly named result directory for each experiment run.
    """

    method = (
        "pure_llm"
        if mode == "llm" and max_iterations == 1
        else (
            "hybrid_feedback"
            if mode == "llm"
            else "mock"
        )
    )

    if mode == "llm":
        safe_model_name = sanitise_name(model)

        run_prefix = (
            f"run_{method}_{safe_model_name}"
        )
    else:
        run_prefix = "run_mock"

    run_number = get_next_run_number(
        prefix=run_prefix,
    )

    run_directory = (
        RESULTS_ROOT
        / f"{run_prefix}_{run_number:02d}"
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    return run_directory


def save_json(
    data: Any,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main refinement loop
# ---------------------------------------------------------------------------

def run_refinement_loop(
    mode: str,
    model: str,
    max_iterations: int,
) -> dict[str, Any]:
    """
    Run:

        plan generation
            -> plan file
            -> VAL
            -> structured feedback
            -> repair
            -> VAL again
    """

    if not DOMAIN_FILE.exists():
        raise FileNotFoundError(
            f"Domain file does not exist: {DOMAIN_FILE}"
        )

    if not PROBLEM_FILE.exists():
        raise FileNotFoundError(
            f"Problem file does not exist: {PROBLEM_FILE}"
        )

    run_directory = create_run_directory(
        mode=mode,
        model=model,
        max_iterations=max_iterations,
    )

    # Save copies of the exact PDDL files used in this run.
    shutil.copy2(
        DOMAIN_FILE,
        run_directory / "domain.pddl",
    )

    shutil.copy2(
        PROBLEM_FILE,
        run_directory / "problem.pddl",
    )

    planner: LLMPlanner | None = None

    if mode == "llm":
        planner = LLMPlanner(model=model)

    feedback_text: str | None = None
    iteration_logs: list[dict[str, Any]] = []

    print("=" * 78)
    print("EXTERNAL VAL FEEDBACK LOOP")
    print("=" * 78)
    print(f"Scene          : {SCENE_NAME}")
    print(f"Mode           : {mode}")
    print(f"Model          : {model if mode == 'llm' else 'not used'}")
    print(f"Max iterations : {max_iterations}")
    print(f"Run directory  : {run_directory}")
    print("=" * 78)

    for iteration in range(1, max_iterations + 1):
        print()
        print("-" * 78)
        print(f"ITERATION {iteration}/{max_iterations}")
        print("-" * 78)

        # ---------------------------------------------------------------
        # 1. Generate candidate plan
        # ---------------------------------------------------------------

        if mode == "mock":
            plan = get_mock_plan(iteration)
            raw_llm_output = None

        else:
            assert planner is not None

            try:
                plan = planner.generate(
                    feedback=feedback_text,
                )

                raw_llm_output = planner.last_raw_response

            except Exception as exc:
                error_record = {
                    "iteration": iteration,
                    "stage": "llm_generation_or_parsing",
                    "error": str(exc),
                    "raw_llm_output": getattr(
                        planner,
                        "last_raw_response",
                        "",
                    ),
                }

                iteration_logs.append(error_record)

                save_json(
                    error_record,
                    run_directory
                    / f"attempt_{iteration:02d}_generation_error.json",
                )

                summary = {
                    "scene": SCENE_NAME,
                    "mode": mode,
                    "model": model,
                    "success": False,
                    "iterations": iteration,
                    "failure_stage": "llm_generation_or_parsing",
                    "run_directory": str(run_directory),
                    "attempts": iteration_logs,
                }

                save_json(
                    summary,
                    run_directory / "run_summary.json",
                )

                print(f"LLM generation failed: {exc}")
                return summary

        print("Candidate plan:")

        for step_number, step in enumerate(plan, start=1):
            print(
                f"  {step_number}. "
                f"{step.action}({', '.join(step.args)})"
            )

        if raw_llm_output is not None:
            (
                run_directory
                / f"attempt_{iteration:02d}_raw_llm.txt"
            ).write_text(
                raw_llm_output,
                encoding="utf-8",
            )

        save_json(
            plan_to_dict(plan),
            run_directory
            / f"attempt_{iteration:02d}_plan.json",
        )

        # ---------------------------------------------------------------
        # 2. Save candidate as a VAL-compatible .plan file
        # ---------------------------------------------------------------

        plan_file = (
            run_directory
            / f"attempt_{iteration:02d}.plan"
        )

        save_plan_file(
            plan=plan,
            output_path=plan_file,
        )

        print(f"\nSaved plan file: {plan_file}")

        # ---------------------------------------------------------------
        # 3. Run real external VAL
        # ---------------------------------------------------------------

        val_log_file = (
            run_directory
            / f"attempt_{iteration:02d}_val.txt"
        )

        print("Running VAL...")

        val_result = run_val(
            domain_file=DOMAIN_FILE,
            problem_file=PROBLEM_FILE,
            plan_file=plan_file,
            log_file=val_log_file,
            verbose=True,
            timeout_seconds=60,
        )

        print(f"VAL valid   : {val_result.valid}")
        print(f"Return code : {val_result.return_code}")
        print(
            "Runtime     : "
            f"{val_result.runtime_seconds:.3f} seconds"
        )

        attempt_record: dict[str, Any] = {
            "iteration": iteration,
            "plan": plan_to_dict(plan),
            "plan_file": str(plan_file),
            "val": val_result.to_dict(),
        }

        # ---------------------------------------------------------------
        # 4. Stop when VAL accepts the plan
        # ---------------------------------------------------------------

        if val_result.valid:
            final_plan_file = (
                run_directory / "final_validated.plan"
            )

            shutil.copy2(
                plan_file,
                final_plan_file,
            )

            attempt_record["success"] = True
            iteration_logs.append(attempt_record)

            summary = {
                "scene": SCENE_NAME,
                "mode": mode,
                "method": (
                    "pure_llm"
                    if mode == "llm" and max_iterations == 1
                    else (
                        "hybrid_feedback"
                        if mode == "llm"
                        else "mock"
                    )
                ),
                "model": (
                    model
                    if mode == "llm"
                    else None
                ),
                "success": True,
                "iterations": iteration,
                "final_plan": plan_to_dict(plan),
                "final_plan_file": str(final_plan_file),
                "run_directory": str(run_directory),
                "attempts": iteration_logs,
            }

            save_json(
                summary,
                run_directory / "run_summary.json",
            )

            print()
            print("=" * 78)
            print("SUCCESS")
            print("=" * 78)
            print(
                "VAL accepted the plan after "
                f"{iteration} iteration(s)."
            )
            print(f"Final plan: {final_plan_file}")
            print(
                "Summary   : "
                f"{run_directory / 'run_summary.json'}"
            )

            return summary

        # ---------------------------------------------------------------
        # 5. Create structured feedback when VAL rejects the plan
        # ---------------------------------------------------------------

        feedback = make_structured_feedback(
            plan=plan,
            val_valid=val_result.valid,
            val_stdout=val_result.stdout,
            val_stderr=val_result.stderr,
        )

        feedback_file = (
            run_directory
            / f"attempt_{iteration:02d}_feedback.json"
        )

        save_json(
            feedback,
            feedback_file,
        )

        feedback_text = json.dumps(
            feedback,
            indent=2,
            ensure_ascii=False,
        )

        attempt_record["success"] = False
        attempt_record["feedback"] = feedback
        attempt_record["feedback_file"] = str(
            feedback_file
        )

        iteration_logs.append(attempt_record)

        print("\nPlan rejected by VAL.")
        print("Structured feedback:")

        failure_details = feedback.get(
            "symbolic_failure_details",
            {},
        )

        print(
            json.dumps(
                failure_details,
                indent=2,
                ensure_ascii=False,
            )
        )

        if iteration < max_iterations:
            print(
                "\nThe feedback will be used "
                "to generate the next complete plan."
            )

    # -------------------------------------------------------------------
    # Maximum iterations reached
    # -------------------------------------------------------------------

    summary = {
        "scene": SCENE_NAME,
        "mode": mode,
        "method": (
            "pure_llm"
            if mode == "llm" and max_iterations == 1
            else (
               "hybrid_feedback"
               if mode == "llm"
               else "mock"
            )
        ),
        "model": (
            model
            if mode == "llm"
            else None
        ),
        "success": False,
        "iterations": max_iterations,
        "failure_stage": "maximum_iterations_reached",
        "run_directory": str(run_directory),
        "attempts": iteration_logs,
    }

    save_json(
        summary,
        run_directory / "run_summary.json",
    )

    print()
    print("=" * 78)
    print("FAILED")
    print("=" * 78)
    print(
        "No VAL-valid plan was found after "
        f"{max_iterations} iteration(s)."
    )
    print(
        "Summary: "
        f"{run_directory / 'run_summary.json'}"
    )

    return summary


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "LLM plan generation, external VAL verification, "
            "structured feedback, and iterative repair."
        )
    )

    parser.add_argument(
        "--mode",
        choices=["mock", "llm"],
        default="mock",
        help=(
            "mock tests the pipeline with one invalid and one valid plan; "
            "llm uses Ollama to generate and repair plans."
        ),
    )

    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Ollama model name used in llm mode.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum number of generation/repair iterations.",
    )

    args = parser.parse_args()

    run_refinement_loop(
        mode=args.mode,
        model=args.model,
        max_iterations=args.max_iterations,
    )


if __name__ == "__main__":
    main()