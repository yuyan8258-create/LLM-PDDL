from __future__ import annotations

import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .path_utils import to_wsl_path


VAL_EXECUTABLE = "/home/lyy/planning-tools/VAL/build/bin/Validate"


@dataclass
class ValResult:
    valid: bool
    return_code: int
    runtime_seconds: float
    final_value: int | None
    stdout: str
    stderr: str
    raw_log_file: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def clean_terminal_output(text: str) -> str:
    """Convert VAL terminal output into readable plain text."""

    # Convert CRLF and CR into normal LF line endings.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove ANSI terminal control and colour sequences.
    text = re.sub(
        r"\x1b\[[0-?]*[ -/]*[@-~]",
        "",
        text,
    )

    cleaned_characters: list[str] = []

    for character in text:
        if character in ("\n", "\t"):
            cleaned_characters.append(character)
        elif ord(character) >= 32:
            cleaned_characters.append(character)

    cleaned_lines = [
        line.rstrip()
        for line in "".join(cleaned_characters).splitlines()
    ]

    return "\n".join(cleaned_lines).strip() + "\n"


def run_val(
    domain_file: str | Path,
    problem_file: str | Path,
    plan_file: str | Path,
    log_file: str | Path | None = None,
    verbose: bool = True,
    timeout_seconds: int = 60,
) -> ValResult:
    """Validate a plan using VAL inside Ubuntu WSL."""

    domain_path = Path(domain_file).resolve()
    problem_path = Path(problem_file).resolve()
    plan_path = Path(plan_file).resolve()

    for required_file in (
        domain_path,
        problem_path,
        plan_path,
    ):
        if not required_file.exists():
            raise FileNotFoundError(
                f"Required validation file not found: {required_file}"
            )

    domain_wsl = to_wsl_path(domain_path)
    problem_wsl = to_wsl_path(problem_path)
    plan_wsl = to_wsl_path(plan_path)

    command = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "--",
        VAL_EXECUTABLE,
    ]

    if verbose:
        command.append("-v")

    command.extend(
        [
            domain_wsl,
            problem_wsl,
            plan_wsl,
        ]
    )

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

        return ValResult(
            valid=False,
            return_code=-1,
            runtime_seconds=elapsed,
            final_value=None,
            stdout=exc.stdout or "",
            stderr=(
                f"VAL timed out after "
                f"{timeout_seconds} seconds."
            ),
            raw_log_file=str(log_file) if log_file else None,
        )

    elapsed = time.perf_counter() - start

    raw_output = (
        f"{completed.stdout}\n"
        f"{completed.stderr}"
    )

    combined_output = clean_terminal_output(raw_output)
    lowered = combined_output.lower()

    valid = (
        "plan valid" in lowered
        and "plan failed" not in lowered
        and "plan invalid" not in lowered
    )

    final_value_match = re.search(
        r"Final value:\s*(\d+)",
        combined_output,
        re.IGNORECASE,
    )

    final_value = (
        int(final_value_match.group(1))
        if final_value_match
        else None
    )

    saved_log_file: str | None = None

    if log_file is not None:
        log_path = Path(log_file).resolve()
        log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Write a clean Windows-compatible UTF-8 text file.
        with log_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as log_handle:
            log_handle.write(
                combined_output.replace("\n", "\r\n")
            )

        saved_log_file = str(log_path)

    return ValResult(
        valid=valid,
        return_code=completed.returncode,
        runtime_seconds=elapsed,
        final_value=final_value,
        stdout=completed.stdout,
        stderr=completed.stderr,
        raw_log_file=saved_log_file,
    )