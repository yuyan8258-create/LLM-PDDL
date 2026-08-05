from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import requests

from src.external_tools.val_runner import ValResult, run_val


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

DOMAIN_PATH = (
    PROJECT_ROOT
    / "generated_pddl"
    / "scene_02_pyramid"
    / "domain.pddl"
)

PROBLEM_PATH = (
    PROJECT_ROOT
    / "generated_pddl"
    / "scene_02_pyramid"
    / "problem.pddl"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "results"
    / "local_llm_test"
    / "llama3.1_8b"
)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"

INITIAL_TEMPERATURE = 0.0
REFINEMENT_TEMPERATURE = 0.4

MAX_REFINEMENTS = 3
OLLAMA_TIMEOUT_SECONDS = 1200
VAL_TIMEOUT_SECONDS = 60


# ============================================================
# File helpers
# ============================================================

def read_text_file(path: Path) -> str:
    """Read a UTF-8 text file and raise a clear error if it is missing."""

    if not path.exists():
        raise RuntimeError(f"File not found: {path}")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def write_text_file(path: Path, content: str) -> None:
    """Write UTF-8 text, creating parent folders when required."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ============================================================
# Ollama client
# ============================================================

def call_local_model(
    prompt: str,
    temperature: float,
) -> str:
    """Send one prompt to the local Ollama API and return model text."""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 2048,
        },
        "keep_alive": "10m",
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "The local model request timed out."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama request failed: {exc}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Ollama returned invalid JSON: {response.text}"
        ) from exc

    try:
        output = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Unexpected Ollama response structure: {data}"
        ) from exc

    if not output or not output.strip():
        raise RuntimeError("The model returned an empty response.")

    return output.strip()


# ============================================================
# Prompt construction
# ============================================================

def build_planning_prompt(
    domain_text: str,
    problem_text: str,
) -> str:
    """Build the initial PDDL planning prompt."""

    return f"""
You are a classical planning assistant.

Generate a valid sequential plan for the PDDL domain and problem below.

Before answering, reason silently about:
1. the goal predicates;
2. the action preconditions;
3. the action effects;
4. the state after every action.

Output requirements:
- Return only plan actions.
- Use exactly one action per line.
- Put every action inside parentheses.
- Do not include explanations.
- Do not include Markdown code fences.
- Do not include numbering.
- Use only actions and objects defined in the PDDL files.
- The plan must achieve every goal condition.
- Object and action names must be lowercase.

PDDL DOMAIN:
{domain_text}

PDDL PROBLEM:
{problem_text}

Return the complete plan now.
""".strip()


def extract_key_val_feedback(val_feedback: str) -> str:
    """Extract only the first useful VAL failure message."""

    lines = [
        line.strip()
        for line in val_feedback.splitlines()
        if line.strip()
    ]

    useful_lines: list[str] = []
    capture_next_action = False

    for line in lines:
        lowered = line.lower()

        if "plan failed because" in lowered:
            useful_lines.append(line)
            capture_next_action = True
            continue

        if capture_next_action:
            if re.fullmatch(r"\([^()\n]+\)", line):
                useful_lines.append(line)
                capture_next_action = False
                continue

        if "has an unsatisfied precondition" in lowered:
            useful_lines.append(line)
            continue

        if lowered.startswith("(set "):
            useful_lines.append(line)
            continue

        if lowered.startswith("and (set "):
            useful_lines.append(line)
            continue

        if "goal not satisfied" in lowered:
            useful_lines.append(line)
            continue

        if "goal not achieved" in lowered:
            useful_lines.append(line)
            continue

    if useful_lines:
        return "\n".join(useful_lines)

    return val_feedback[-1200:].strip()

def build_refinement_prompt(
    domain_text: str,
    problem_text: str,
    previous_plan: str,
    val_feedback: str,
    attempt_number: int,
) -> str:
    """Build a focused prompt for repairing an invalid plan."""

    return f"""
You are repairing an invalid classical PDDL plan.

This is refinement attempt {attempt_number}.

The previous plan failed formal validation in VAL. Produce a NEW,
complete replacement plan that fixes the reported failure and achieves
all goal predicates.

Reason silently before answering:
1. Read the exact goal predicates in the PDDL problem.
2. Identify the first failed action from the VAL feedback.
3. Identify its unsatisfied precondition.
4. Simulate the effects of every earlier action.
5. Discard unnecessary actions from the previous plan.
6. Construct a complete executable sequence from the initial state.
7. Check every action precondition and the final goal state.

Important rules:
- Do not copy the previous invalid plan unchanged.
- Do not repair the plan by adding random actions.
- Reconstruct the plan from the initial state and goal predicates.
- Preserve goal predicates that are already true unless changing them
  is strictly necessary.
- Do not move objects whose required final condition is already true.
- The hand can hold only one object at a time.
- After pick-up, another pick-up is impossible until the held object
  is placed by put-down, stack, or stack-bridge.
- Use the exact action signatures:
  (pick-up ?x)
  (put-down ?x)
  (stack ?x ?y)
  (unstack ?x ?y)
  (stack-bridge ?x ?left ?right)
  (unstack-bridge ?x ?left ?right)
- Never add extra parameters.
- put-down takes exactly one object argument.
- Return a complete replacement plan.
- Return only PDDL actions.
- Use exactly one action per line.
- Put every action inside parentheses.
- Do not include explanations.
- Do not include Markdown code fences.
- Do not include numbering.
- Use only actions and objects from the PDDL files.
- Use lowercase action and object names.

PDDL DOMAIN:
{domain_text}

PDDL PROBLEM:
{problem_text}

PREVIOUS INVALID PLAN:
{previous_plan}

KEY VAL FEEDBACK:
{val_feedback}

Return the corrected complete plan now.
""".strip()


# ============================================================
# Plan processing
# ============================================================

def extract_plan(raw_response: str) -> str:
    """Extract PDDL action lines from a model response."""

    cleaned = (
        raw_response
        .replace("```pddl", "")
        .replace("```PDDL", "")
        .replace("```", "")
    )

    action_lines: list[str] = []

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        # Remove common numbering, for example:
        # 1. (pick-up b4)
        # 2) (stack-bridge b4 b1 b2)
        line = re.sub(
            r"^\s*\d+\s*[\.\):\-]\s*",
            "",
            line,
        )

        matches = re.findall(
            r"\([^()\n]+\)",
            line,
        )

        for match in matches:
            action = match.strip().lower()

            if action.startswith("(define"):
                continue

            if action.startswith("(:"):
                continue

            action_lines.append(action)

    if not action_lines:
        raise RuntimeError(
            "No PDDL plan actions could be extracted "
            "from the model response."
        )

    return "\n".join(action_lines) + "\n"


def normalise_plan(plan: str) -> str:
    """Normalise whitespace so equivalent plans can be compared safely."""

    normalised_lines = [
        re.sub(r"\s+", " ", line.strip()).lower()
        for line in plan.splitlines()
        if line.strip()
    ]

    return "\n".join(normalised_lines)


def count_plan_actions(plan: str) -> int:
    """Count non-empty action lines."""

    return sum(
        1
        for line in plan.splitlines()
        if line.strip()
    )


# ============================================================
# Validation helpers
# ============================================================

def validate_plan(
    plan_path: Path,
    log_path: Path,
) -> ValResult:
    """Run VAL on one saved plan."""

    return run_val(
        domain_file=DOMAIN_PATH,
        problem_file=PROBLEM_PATH,
        plan_file=plan_path,
        log_file=log_path,
        verbose=True,
        timeout_seconds=VAL_TIMEOUT_SECONDS,
    )


def val_result_to_dict(result: ValResult) -> dict[str, Any]:
    """Convert the validation result into JSON-safe summary data."""

    return {
        "valid": result.valid,
        "return_code": result.return_code,
        "runtime_seconds": result.runtime_seconds,
        "final_value": result.final_value,
        "raw_log_file": result.raw_log_file,
    }


# ============================================================
# Main experiment
# ============================================================

def main() -> None:
    print(f"Domain:  {DOMAIN_PATH}")
    print(f"Problem: {PROBLEM_PATH}")
    print(f"Model:   {MODEL_NAME}")

    domain_text = read_text_file(DOMAIN_PATH)
    problem_text = read_text_file(PROBLEM_PATH)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary: dict[str, Any] = {
        "model": MODEL_NAME,
        "domain_file": str(DOMAIN_PATH),
        "problem_file": str(PROBLEM_PATH),
        "max_refinements": MAX_REFINEMENTS,
        "initial_temperature": INITIAL_TEMPERATURE,
        "refinement_temperature": REFINEMENT_TEMPERATURE,
        "attempts": [],
        "final_status": None,
        "final_valid": False,
        "refinements_used": 0,
    }

    # --------------------------------------------------------
    # Attempt 0: initial plan
    # --------------------------------------------------------

    initial_prompt = build_planning_prompt(
        domain_text=domain_text,
        problem_text=problem_text,
    )

    initial_prompt_path = OUTPUT_DIR / "planning_prompt.txt"
    initial_raw_path = OUTPUT_DIR / "raw_response.txt"
    initial_plan_path = OUTPUT_DIR / "extracted_plan.plan"
    initial_val_path = OUTPUT_DIR / "validation.txt"

    write_text_file(
        initial_prompt_path,
        initial_prompt,
    )

    print("\nCalling local model for the initial plan...")

    initial_raw_response = call_local_model(
        initial_prompt,
        temperature=INITIAL_TEMPERATURE,
    )

    write_text_file(
        initial_raw_path,
        initial_raw_response + "\n",
    )

    current_plan = extract_plan(
        initial_raw_response
    )

    write_text_file(
        initial_plan_path,
        current_plan,
    )

    print("\nValidating initial plan with VAL...")

    current_val_result = validate_plan(
        plan_path=initial_plan_path,
        log_path=initial_val_path,
    )

    summary["attempts"].append(
        {
            "attempt": 0,
            "type": "initial",
            "temperature": INITIAL_TEMPERATURE,
            "prompt_file": str(initial_prompt_path),
            "raw_response_file": str(initial_raw_path),
            "plan_file": str(initial_plan_path),
            "plan_length": count_plan_actions(current_plan),
            "validation": val_result_to_dict(current_val_result),
        }
    )

    print("\nInitial VAL result:")
    print(f"Valid: {current_val_result.valid}")
    print(f"Return code: {current_val_result.return_code}")
    print(
        f"Runtime: "
        f"{current_val_result.runtime_seconds:.3f} seconds"
    )
    print(f"Validation log: {current_val_result.raw_log_file}")

    if current_val_result.valid:
        summary["final_status"] = "valid_initially"
        summary["final_valid"] = True
        summary["refinements_used"] = 0

    # --------------------------------------------------------
    # Attempts 1..MAX_REFINEMENTS: feedback-guided repair
    # --------------------------------------------------------

    else:
        seen_plans = {
            normalise_plan(current_plan)
        }

        for attempt_number in range(
            1,
            MAX_REFINEMENTS + 1,
        ):
            print(
                f"\nRefinement attempt "
                f"{attempt_number}/{MAX_REFINEMENTS}..."
            )

            current_log_path = Path(
                current_val_result.raw_log_file
                or initial_val_path
            )

            full_val_feedback = read_text_file(
                current_log_path
            )

            key_val_feedback = extract_key_val_feedback(
                full_val_feedback
            )

            refinement_prompt = build_refinement_prompt(
                domain_text=domain_text,
                problem_text=problem_text,
                previous_plan=current_plan,
                val_feedback=key_val_feedback,
                attempt_number=attempt_number,
            )

            attempt_prefix = (
                f"refinement_{attempt_number:02d}"
            )

            refinement_prompt_path = (
                OUTPUT_DIR
                / f"{attempt_prefix}_prompt.txt"
            )

            refinement_raw_path = (
                OUTPUT_DIR
                / f"{attempt_prefix}_raw_response.txt"
            )

            refinement_plan_path = (
                OUTPUT_DIR
                / f"{attempt_prefix}_plan.plan"
            )

            refinement_val_path = (
                OUTPUT_DIR
                / f"{attempt_prefix}_validation.txt"
            )

            write_text_file(
                refinement_prompt_path,
                refinement_prompt,
            )

            refined_raw_response = call_local_model(
                refinement_prompt,
                temperature=REFINEMENT_TEMPERATURE,
            )

            write_text_file(
                refinement_raw_path,
                refined_raw_response + "\n",
            )

            refined_plan = extract_plan(
                refined_raw_response
            )

            refined_plan_normalised = normalise_plan(
                refined_plan
            )

            # Save the plan even when it is repeated so the model
            # behaviour remains auditable.
            write_text_file(
                refinement_plan_path,
                refined_plan,
            )

            if refined_plan_normalised in seen_plans:
                print(
                    "The model returned a previously seen "
                    "invalid plan. Refinement has stalled."
                )

                summary["attempts"].append(
                    {
                        "attempt": attempt_number,
                        "type": "refinement",
                        "temperature": REFINEMENT_TEMPERATURE,
                        "prompt_file": str(
                            refinement_prompt_path
                        ),
                        "raw_response_file": str(
                            refinement_raw_path
                        ),
                        "plan_file": str(
                            refinement_plan_path
                        ),
                        "plan_length": count_plan_actions(
                            refined_plan
                        ),
                        "validation": None,
                        "status": "repeated_plan",
                    }
                )

                summary["final_status"] = (
                    "stalled_repeated_plan"
                )
                summary["final_valid"] = False
                summary["refinements_used"] = attempt_number
                break

            seen_plans.add(
                refined_plan_normalised
            )

            print(
                f"Validating refinement attempt "
                f"{attempt_number} with VAL..."
            )

            refined_val_result = validate_plan(
                plan_path=refinement_plan_path,
                log_path=refinement_val_path,
            )

            summary["attempts"].append(
                {
                    "attempt": attempt_number,
                    "type": "refinement",
                    "temperature": REFINEMENT_TEMPERATURE,
                    "prompt_file": str(
                        refinement_prompt_path
                    ),
                    "raw_response_file": str(
                        refinement_raw_path
                    ),
                    "plan_file": str(
                        refinement_plan_path
                    ),
                    "plan_length": count_plan_actions(
                        refined_plan
                    ),
                    "validation": val_result_to_dict(
                        refined_val_result
                    ),
                }
            )

            print(
                f"Refinement {attempt_number} valid: "
                f"{refined_val_result.valid}"
            )

            current_plan = refined_plan
            current_val_result = refined_val_result

            if current_val_result.valid:
                summary["final_status"] = (
                    "valid_after_refinement"
                )
                summary["final_valid"] = True
                summary["refinements_used"] = attempt_number
                break

        else:
            summary["final_status"] = (
                "max_refinements_reached"
            )
            summary["final_valid"] = False
            summary["refinements_used"] = (
                MAX_REFINEMENTS
            )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    summary_path = OUTPUT_DIR / "experiment_summary.json"

    write_text_file(
        summary_path,
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    print("\nExperiment complete.")
    print(f"Final status: {summary['final_status']}")
    print(f"Final valid: {summary['final_valid']}")
    print(
        f"Refinements used: "
        f"{summary['refinements_used']}"
    )
    print(f"Summary file: {summary_path}")


if __name__ == "__main__":
    try:
        main()

    except (
        RuntimeError,
        FileNotFoundError,
    ) as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)