from __future__ import annotations

import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .path_utils import to_wsl_path


FAST_DOWNWARD_SCRIPT = (
    "/home/lyy/planning-tools/fast-downward/fast-downward.py"
)


@dataclass
class FastDownwardResult:
    solved: bool
    return_code: int
    runtime_seconds: float
    plan: list[str]
    plan_length: int | None
    plan_cost: int | None
    expanded_states: int | None
    evaluated_states: int | None
    generated_states: int | None
    planner_reported_time: float | None
    stdout: str
    stderr: str
    plan_file: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_plan_file(plan_file: Path) -> list[str]:
    """
    Read a Fast Downward plan file.

    Example line:
        (pick-up b4)

    Returned as:
        pick-up b4
    """
    if not plan_file.exists():
        return []

    actions: list[str] = []

    for raw_line in plan_file.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith(";"):
            continue

        if line.startswith("(") and line.endswith(")"):
            line = line[1:-1].strip()

        if line:
            actions.append(line)

    return actions


def extract_integer(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def run_fast_downward(
    domain_file: str | Path,
    problem_file: str | Path,
    plan_file: str | Path,
    alias: str = "lama-first",
    timeout_seconds: int = 120,
) -> FastDownwardResult:
    """
    Run Fast Downward inside Ubuntu WSL.

    The Python program itself may run on Windows.
    """
    domain_path = Path(domain_file).resolve()
    problem_path = Path(problem_file).resolve()
    output_plan = Path(plan_file).resolve()

    for required_file in (domain_path, problem_path):
        if not required_file.exists():
            raise FileNotFoundError(
                f"Required PDDL file not found: {required_file}"
            )

    output_plan.parent.mkdir(parents=True, exist_ok=True)

    # Prevent a failed run from accidentally reusing an old plan.
    if output_plan.exists():
        output_plan.unlink()

    domain_wsl = to_wsl_path(domain_path)
    problem_wsl = to_wsl_path(problem_path)
    plan_wsl = to_wsl_path(output_plan)

    command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        "python3",
        FAST_DOWNWARD_SCRIPT,
        "--alias",
        alias,
        "--plan-file",
        plan_wsl,
        domain_wsl,
        problem_wsl,
    ]

    start = time.perf_counter()

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start

        return FastDownwardResult(
            solved=False,
            return_code=-1,
            runtime_seconds=elapsed,
            plan=[],
            plan_length=None,
            plan_cost=None,
            expanded_states=None,
            evaluated_states=None,
            generated_states=None,
            planner_reported_time=None,
            stdout=exc.stdout or "",
            stderr=f"Fast Downward timed out after {timeout_seconds} seconds.",
            plan_file=str(output_plan),
        )

    elapsed = time.perf_counter() - start
    combined_output = f"{completed.stdout}\n{completed.stderr}"
    plan = parse_plan_file(output_plan)

    solved = (
        completed.returncode == 0
        and output_plan.exists()
        and bool(plan)
        and "solution found" in combined_output.lower()
    )

    return FastDownwardResult(
        solved=solved,
        return_code=completed.returncode,
        runtime_seconds=elapsed,
        plan=plan,
        plan_length=extract_integer(
            r"Plan length:\s*(\d+)",
            combined_output,
        ),
        plan_cost=extract_integer(
            r"Plan cost:\s*(\d+)",
            combined_output,
        ),
        expanded_states=extract_integer(
            r"Expanded\s+(\d+)\s+state",
            combined_output,
        ),
        evaluated_states=extract_integer(
            r"Evaluated\s+(\d+)\s+state",
            combined_output,
        ),
        generated_states=extract_integer(
            r"Generated\s+(\d+)\s+state",
            combined_output,
        ),
        planner_reported_time=extract_float(
            r"Planner time:\s*([0-9.]+)",
            combined_output,
        ),
        stdout=completed.stdout,
        stderr=completed.stderr,
        plan_file=str(output_plan),
    )