from __future__ import annotations

import json
import sys
from pathlib import Path


# Allow direct execution:
# python src/external_tools/test_external_pipeline.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.external_tools.fast_downward_runner import run_fast_downward
from src.external_tools.val_runner import run_val


def main() -> None:
    domain_file = (
        PROJECT_ROOT
        / "generated_pddl"
        / "scene_02_pyramid"
        / "domain.pddl"
    )

    problem_file = (
        PROJECT_ROOT
        / "generated_pddl"
        / "scene_02_pyramid"
        / "problem.pddl"
    )

    plan_file = (
        PROJECT_ROOT
        / "results"
        / "fast_downward"
        / "scene02_python.plan"
    )

    fast_downward_log = (
        PROJECT_ROOT
        / "results"
        / "fast_downward"
        / "scene02_python_stdout.txt"
    )

    val_log = (
        PROJECT_ROOT
        / "results"
        / "val"
        / "scene02_python_validation.txt"
    )

    json_result_file = (
        PROJECT_ROOT
        / "results"
        / "external_pipeline"
        / "scene02_result.json"
    )

    print("Running Fast Downward...")

    fd_result = run_fast_downward(
        domain_file=domain_file,
        problem_file=problem_file,
        plan_file=plan_file,
    )

    fast_downward_log.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fast_downward_log.write_text(
        f"{fd_result.stdout}\n{fd_result.stderr}",
        encoding="utf-8-sig",
        newline="\r\n",
    )

    print(f"Solved: {fd_result.solved}")
    print(f"Plan length: {fd_result.plan_length}")
    print(f"Plan cost: {fd_result.plan_cost}")
    print(f"Runtime: {fd_result.runtime_seconds:.3f} seconds")

    for index, action in enumerate(fd_result.plan, start=1):
        print(f"{index}. {action}")

    if not fd_result.solved:
        print("\nFast Downward failed.")
        print(fd_result.stdout)
        print(fd_result.stderr)
        raise SystemExit(1)

    print("\nRunning VAL...")

    val_result = run_val(
        domain_file=domain_file,
        problem_file=problem_file,
        plan_file=plan_file,
        log_file=val_log,
        verbose=True,
    )

    print(f"VAL valid: {val_result.valid}")
    print(f"VAL final value: {val_result.final_value}")
    print(f"VAL runtime: {val_result.runtime_seconds:.3f} seconds")

    combined_result = {
        "scene": "scene_02_pyramid",
        "domain_file": str(domain_file),
        "problem_file": str(problem_file),
        "fast_downward": fd_result.to_dict(),
        "val": val_result.to_dict(),
    }

    json_result_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_result_file.write_text(
        json.dumps(
            combined_result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nPipeline completed.")
    print(f"Plan: {plan_file}")
    print(f"Fast Downward log: {fast_downward_log}")
    print(f"VAL log: {val_log}")
    print(f"JSON result: {json_result_file}")


if __name__ == "__main__":
    main()