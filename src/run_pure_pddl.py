from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from src.external_tools.fast_downward_runner import (
    FastDownwardResult,
    run_fast_downward,
)
from src.external_tools.val_runner import (
    ValResult,
    run_val,
)
from src.external_val_feedback_loop import (
    PROJECT_ROOT,
    initialise_runtime_context,
)
from src.plan_model import (
    PlanStep,
    parse_external_plan_actions,
)

def save_json(
    data: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Save a dictionary as a readable UTF-8 JSON file.
    """
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

def run_pure_pddl(
    scene_id: str,
    alias: str = "lama-first",
    timeout_seconds: int = 120,
    results_base: Path | None = None,
) -> dict[str, Any]:
    """
    Run one Pure PDDL experiment for a configured scene.

    The planning decision is made only by Fast Downward.
    Python symbolic verification and VAL are used only to
    validate and record the generated plan.
    """
    context = initialise_runtime_context(scene_id)

    run_started_at = datetime.now()

    if results_base is None:
        effective_results_base = (
            PROJECT_ROOT / "results"
        )
    else:
        effective_results_base = Path(results_base)

        if not effective_results_base.is_absolute():
            effective_results_base = (
                PROJECT_ROOT / effective_results_base
            )

    run_directory = (
        effective_results_base
        / "pure_pddl"
        / context.domain.domain_id
        / context.scene.scene_id
        / run_started_at.strftime("run_%Y%m%d_%H%M%S_%f")
    )
    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    planner_plan_file = run_directory / "fast_downward.plan"

    fd_result = run_fast_downward(
        domain_file=context.domain_file,
        problem_file=context.problem_file,
        plan_file=planner_plan_file,
        alias=alias,
        timeout_seconds=timeout_seconds,
    )

    if not fd_result.solved:
        summary = {
            "scene": context.scene.scene_id,
            "domain": context.domain.domain_id,
            "method": "pure_pddl",
            "planner": "fast_downward",
            "planner_alias": alias,
            "success": False,
            "failure_stage": "fast_downward",
            "planner_return_code": fd_result.return_code,
            "planner_runtime_seconds": fd_result.runtime_seconds,
            "run_directory": str(run_directory),
        }

        save_json(
            summary,
            run_directory / "run_summary.json",
        )
        return summary

    domain_plan = parse_external_plan_actions(
        actions=fd_result.plan,
        scene=context.prepared_scene,
        domain=context.domain,
    )

    symbolic_result = context.verifier.verify(
        domain_plan,
        context.prepared_scene,
    )

    val_plan_file = run_directory / "candidate.plan"

    val_plan_file.write_text(
        "\n".join(
            step.to_pddl_text()
            for step in domain_plan
        )
        + "\n",
        encoding="utf-8",
    )

    val_result = run_val(
        domain_file=context.domain_file,
        problem_file=context.problem_file,
        plan_file=val_plan_file,
    )

    run_finished_at = datetime.now()

    success = (
        fd_result.solved
        and symbolic_result.success
        and val_result.valid
    )

    summary = {
        "scene": context.scene.scene_id,
        "domain": context.domain.domain_id,
        "method": "pure_pddl",
        "planner": "fast_downward",
        "planner_alias": alias,
        "success": success,
        "plan_steps": len(domain_plan),
        "planner_return_code": fd_result.return_code,
        "planner_runtime_seconds": fd_result.runtime_seconds,
        "symbolic_valid": symbolic_result.success,
        "val_valid": val_result.valid,
        "val_return_code": val_result.return_code,
        "val_runtime_seconds": val_result.runtime_seconds,
        "started_at": run_started_at.isoformat(
            timespec="seconds"
        ),
        "finished_at": run_finished_at.isoformat(
            timespec="seconds"
        ),
        "duration_seconds": round(
            (
                run_finished_at
                - run_started_at
            ).total_seconds(),
            3,
        ),
        "run_directory": str(run_directory),
    }

    save_json(
        summary,
        run_directory / "run_summary.json",
    )

    return summary

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Pure PDDL experiment using Fast Downward "
            "with Python symbolic verification and external VAL validation."
        )
    )

    parser.add_argument(
        "--scene",
        required=True,
        help="Configured scene ID to run.",
    )

    parser.add_argument(
        "--alias",
        default="lama-first",
        help="Fast Downward search alias.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Fast Downward timeout in seconds.",
    )

    parser.add_argument(
        "--results-base",
        type=Path,
        default=None,
        help=(
            "Optional experiment results base directory. "
            "When omitted, the existing Pure PDDL results "
            "location is preserved."
        ),
    )

    args = parser.parse_args()

    summary = run_pure_pddl(
        scene_id=args.scene,
        alias=args.alias,
        timeout_seconds=args.timeout,
        results_base=args.results_base,
    )

    print("=" * 72)
    print("PURE PDDL EXPERIMENT")
    print("=" * 72)
    print(f"Scene            : {summary['scene']}")
    print(f"Domain           : {summary['domain']}")
    print(f"Method           : {summary['method']}")
    print(f"Planner          : {summary['planner']}")
    print(f"Success          : {summary['success']}")
    print(f"Run directory    : {summary['run_directory']}")

    if "plan_steps" in summary:
        print(f"Plan steps       : {summary['plan_steps']}")
        print(
            f"Symbolic valid   : "
            f"{summary['symbolic_valid']}"
        )
        print(
            f"VAL valid        : "
            f"{summary['val_valid']}"
        )

    print("=" * 72)


if __name__ == "__main__":
    main()