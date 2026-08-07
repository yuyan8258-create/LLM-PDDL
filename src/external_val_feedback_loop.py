from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
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
from src.domain_adapters import get_domain_adapter
from src.domain_adapters.base import DomainAdapter
from src.domain_config import DomainConfig, load_domain_config
from src.external_tools.val_runner import run_val
from src.pddl_problem_builder import write_pddl_problem
from src.plan_model import (
    PlanStep as DomainPlanStep,
    load_expected_plan,
)
from src.scene_config import SceneConfig, load_scene_config
from src.verifiers import get_symbolic_verifier
from src.verifiers.base import (
    SymbolicVerifier as DomainSymbolicVerifier,
)

# Legacy Scene 02 components are temporarily preserved so the currently
# working refinement loop continues to behave exactly as before.
from src.pyramid_demo_v3 import (
    LLMPlanner,
    PlanStep,
    REFERENCE_PLAN,
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
# Unified runtime context
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeContext:
    """
    Runtime objects and paths resolved from one scene ID.

    This is the first migration seam between the legacy Scene 02 loop
    and the new domain-independent project infrastructure.

    Creating this context does not run the LLM, VAL, feedback loop, or
    batch execution.
    """

    scene: SceneConfig
    domain: DomainConfig
    adapter: DomainAdapter
    prepared_scene: SceneConfig
    verifier: DomainSymbolicVerifier
    expected_plan: tuple[DomainPlanStep, ...]

    domain_file: Path
    problem_file: Path
    results_root: Path


def initialise_runtime_context(
    scene_id: str,
) -> RuntimeContext:
    """
    Load and prepare all common runtime dependencies for one scene.

    This function intentionally performs initialization only. It does
    not create a refinement run directory and does not execute the
    legacy LLM/VAL loop.
    """

    scene = load_scene_config(scene_id)

    domain = load_domain_config(
        scene.domain_id
    )

    adapter = get_domain_adapter(domain)

    prepared_scene = adapter.prepare_scene(
        scene
    )

    verifier = get_symbolic_verifier(
        domain
    )

    expected_plan = tuple(
        load_expected_plan(
            scene=prepared_scene,
            domain=domain,
        )
    )

    problem_file = write_pddl_problem(
        scene=prepared_scene,
        domain=domain,
    )

    domain_file = domain.domain_file
    results_root = prepared_scene.results_directory

    if not domain_file.exists():
        raise FileNotFoundError(
            f"Domain file does not exist: {domain_file}"
        )

    if not problem_file.exists():
        raise FileNotFoundError(
            f"Generated problem file does not exist: "
            f"{problem_file}"
        )

    return RuntimeContext(
        scene=scene,
        domain=domain,
        adapter=adapter,
        prepared_scene=prepared_scene,
        verifier=verifier,
        expected_plan=expected_plan,
        domain_file=domain_file,
        problem_file=problem_file,
        results_root=results_root,
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

def legacy_plan_to_domain_plan(
    plan: list[PlanStep],
) -> list[DomainPlanStep]:
    """
    Convert legacy Scene 02 PlanStep objects into the common PlanModel.

    This is a temporary migration boundary. The legacy LLM planner and
    mock generator still return pyramid_demo_v3.PlanStep objects, while
    the new domain verifier accepts domain-independent PlanStep objects.
    """

    return [
        DomainPlanStep(
            action=step.action,
            args=tuple(step.args),
        )
        for step in plan
    ]


def make_structured_feedback(
    context: RuntimeContext,
    plan: list[PlanStep],
    val_valid: bool,
    val_stdout: str,
    val_stderr: str,
) -> dict[str, Any]:
    """
    Generate structured repair feedback.

    VAL is the final authority for plan validity.

    The domain symbolic verifier is used to identify the failed action,
    missing preconditions, and state before failure.
    """

    domain_plan = legacy_plan_to_domain_plan(
        plan
    )

    symbolic_result = context.verifier.verify(
        domain_plan,
        context.prepared_scene,
    )

    symbolic_valid = symbolic_result.success

    symbolic_details: dict[str, Any] = {
        "message": symbolic_result.message,
    }

    if symbolic_result.failed_step is not None:
        symbolic_details["failed_step"] = (
            symbolic_result.failed_step
        )

    if symbolic_result.failed_action is not None:
        symbolic_details["failed_action"] = (
            symbolic_result.failed_action
        )

    if symbolic_result.error is not None:
        symbolic_details["error"] = (
            symbolic_result.error
        )

    if (
        symbolic_result.state_before_failure
        is not None
    ):
        symbolic_details["state_before_failure"] = (
            symbolic_result.state_before_failure
        )

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


def resolve_experiment_method(
    mode: str,
    max_iterations: int,
    requested_method: str | None = None,
) -> str:
    """
    Resolve and validate the experiment method.

    When requested_method is omitted, the legacy behaviour is
    preserved for backward compatibility.

    Explicit methods prevent accidental mixing of Pure LLM and
    feedback-based Hybrid experiments.
    """

    if max_iterations < 1:
        raise ValueError(
            "max_iterations must be at least 1."
        )

    if mode == "mock":
        if requested_method not in (
            None,
            "mock",
        ):
            raise ValueError(
                "Mock mode can only use method='mock'."
            )

        return "mock"

    if mode != "llm":
        raise ValueError(
            f"Unsupported refinement mode: '{mode}'."
        )

    if requested_method is None:
        if max_iterations == 1:
            return "pure_llm"

        return "hybrid_feedback"

    if requested_method == "pure_llm":
        if max_iterations != 1:
            raise ValueError(
                "Pure LLM requires "
                "max_iterations=1."
            )

        return "pure_llm"

    if requested_method == "hybrid_feedback":
        if max_iterations <= 1:
            raise ValueError(
                "Hybrid feedback requires "
                "max_iterations greater than 1."
            )

        return "hybrid_feedback"

    raise ValueError(
        "Unsupported experiment method: "
        f"'{requested_method}'."
    )


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
    results_root: Path,
    prefix: str,
) -> int:
    """
    Find the next available run number below one scene result root.

    Example:
        run_pure_llm_qwen2.5_latest_01
        run_pure_llm_qwen2.5_latest_02

    Returns:
        3
    """

    existing_numbers: list[int] = []

    if not results_root.exists():
        return 1

    for directory in results_root.glob(
        f"{prefix}_*"
    ):
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
    results_root: Path,
    mode: str,
    method: str,
    model: str,
) -> Path:
    """
    Create a clearly named result directory for each experiment run.
    """

    if mode == "llm":
        safe_model_name = sanitise_name(model)

        run_prefix = (
            f"run_{method}_{safe_model_name}"
        )
    else:
        run_prefix = "run_mock"

    run_number = get_next_run_number(
        results_root=results_root,
        prefix=run_prefix,
    )

    run_directory = (
        results_root
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
    scene_id: str = SCENE_NAME,
    method: str | None = None,
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

    context = initialise_runtime_context(
        scene_id
    )

    resolved_method = resolve_experiment_method(
        mode=mode,
        max_iterations=max_iterations,
        requested_method=method,
    )

    if (
        mode == "mock"
        and context.scene.scene_id != SCENE_NAME
    ):
        raise ValueError(
            "The legacy mock plans currently support only "
            "'scene_02_pyramid'. "
            f"Requested scene: '{context.scene.scene_id}'. "
            "Use LLM mode for other scenes, or add a "
            "scene-specific mock plan."
        )

    run_directory = create_run_directory(
        results_root=context.results_root,
        mode=mode,
        method=resolved_method,
        model=model,
    )

    # Save copies of the exact PDDL files used in this run.
    shutil.copy2(
        context.domain_file,
        run_directory / "domain.pddl",
    )

    shutil.copy2(
        context.problem_file,
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
    print(
         f"Scene          : "
         f"{context.scene.scene_id}"
    )
    print(f"Mode           : {mode}")
    print(f"Method         : {resolved_method}")
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

            planning_prompt = ""

            try:
                planning_prompt = (
                    context.adapter.build_plan_prompt(
                        scene=context.prepared_scene,
                        feedback=feedback_text,
                    )
                )

                plan = planner.generate_from_prompt(
                    planning_prompt
                )

                raw_llm_output = (
                    planner.last_raw_response
                )

            except Exception as exc:
                error_record = {
                    "iteration": iteration,
                    "stage": "llm_generation_or_parsing",
                    "error": str(exc),
                    "planning_prompt": planning_prompt,
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
                    "scene": context.scene.scene_id,
                    "mode": mode,
                    "method": resolved_method,
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

        if mode == "llm":
            (
                run_directory
                / f"attempt_{iteration:02d}_prompt.txt"
            ).write_text(
                planning_prompt,
                encoding="utf-8",
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
            domain_file=context.domain_file,
            problem_file=context.problem_file,
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
                "scene": context.scene.scene_id,
                "mode": mode,
                "method": resolved_method,
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
            context=context,
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
        "scene": context.scene.scene_id,
        "mode": mode,
        "method": resolved_method,
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
        "--scene",
        default=SCENE_NAME,
        help=(
            "Scene ID to run. "
            "LLM mode supports configured scenes; "
            "legacy mock mode currently supports only "
            "'scene_02_pyramid'."
        ),
    )

    parser.add_argument(
        "--method",
        choices=[
            "pure_llm",
            "hybrid_feedback",
        ],
        default=None,
        help=(
            "Explicit LLM experiment method. "
            "pure_llm requires --max-iterations 1; "
            "hybrid_feedback requires more than 1. "
            "When omitted, the legacy iteration-based "
            "method inference is preserved."
        ),
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
        scene_id=args.scene,
        method=args.method,
    )


if __name__ == "__main__":
    main()