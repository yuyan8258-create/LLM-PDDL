from __future__ import annotations

import re
import sys
from pathlib import Path

import requests

from src.external_tools.val_runner import run_val


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
)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:latest"


def read_text_file(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"File not found: {path}")

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")


def call_local_model(prompt: str) -> str:
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
            "temperature": 0.0,
            "num_predict": 2048,
        },
        "keep_alive": "10m",
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=1200,
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
            f"Unexpected Ollama response: {data}"
        ) from exc

    if not output or not output.strip():
        raise RuntimeError("The model returned an empty response.")

    return output.strip()


def build_planning_prompt(
    domain_text: str,
    problem_text: str,
) -> str:
    return f"""
You are a classical planning assistant.

Generate a valid sequential plan for the PDDL domain and problem below.

Output requirements:
- Return only plan actions.
- Use exactly one action per line.
- Put every action inside parentheses.
- Do not include explanations.
- Do not include Markdown code fences.
- Do not include numbering.
- Use only actions and objects defined in the PDDL files.
- The plan must achieve every goal condition.
- Object and action names should be written in lowercase.

PDDL DOMAIN:
{domain_text}

PDDL PROBLEM:
{problem_text}

Return the complete plan now.
""".strip()


def build_refinement_prompt(
    domain_text: str,
    problem_text: str,
    previous_plan: str,
    val_feedback: str,
) -> str:
    """Ask the model to repair an invalid PDDL plan."""

    return f"""
You are repairing an invalid classical PDDL plan.

The previous plan failed VAL validation.

You must produce a NEW complete plan that is different from the
previous invalid plan and fixes the first reported VAL error.

Follow this reasoning silently before answering:
1. Identify the first invalid action from the VAL feedback.
2. Check which precondition is unsatisfied.
3. Check the effects of all earlier actions.
4. Remove or replace actions that make the precondition false.
5. Verify every action in sequence.
6. Verify that the final state satisfies every goal.

Important:
- Do not copy the previous invalid plan unchanged.
- The robot hand can hold only one object at a time.
- After a pick-up action, another pick-up is impossible until the
  held object is placed using stack, stack-bridge, or put-down.
- Return a complete replacement plan.
- Return only PDDL actions.
- Use one action per line.
- Put every action inside parentheses.
- Do not include explanations.
- Do not include Markdown code fences.
- Do not include numbering.
- Use only actions and objects from the domain and problem.
- Use lowercase names.

PDDL DOMAIN:
{domain_text}

PDDL PROBLEM:
{problem_text}

PREVIOUS INVALID PLAN:
{previous_plan}

VAL FEEDBACK:
{val_feedback}

Return the corrected complete plan now.
""".strip()


def extract_plan(raw_response: str) -> str:
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


def main() -> None:
    print(f"Domain:  {DOMAIN_PATH}")
    print(f"Problem: {PROBLEM_PATH}")
    print(f"Model:   {MODEL_NAME}")

    domain_text = read_text_file(DOMAIN_PATH)
    problem_text = read_text_file(PROBLEM_PATH)

    prompt = build_planning_prompt(
        domain_text=domain_text,
        problem_text=problem_text,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    prompt_path = OUTPUT_DIR / "planning_prompt.txt"
    raw_response_path = OUTPUT_DIR / "raw_response.txt"
    plan_path = OUTPUT_DIR / "extracted_plan.plan"
    val_log_path = OUTPUT_DIR / "validation.txt"
    refinement_prompt_path = OUTPUT_DIR / "refinement_prompt.txt"
    refined_raw_response_path = OUTPUT_DIR / "refined_raw_response.txt"
    refined_plan_path = OUTPUT_DIR / "refined_plan.plan"
    refined_val_log_path = OUTPUT_DIR / "refined_validation.txt"

    prompt_path.write_text(
        prompt,
        encoding="utf-8",
    )

    print("\nCalling local model...")
    raw_response = call_local_model(prompt)

    raw_response_path.write_text(
        raw_response + "\n",
        encoding="utf-8",
    )

    plan = extract_plan(raw_response)

    plan_path.write_text(
        plan,
        encoding="utf-8",
    )
    print("\nValidating extracted plan with VAL...")

    val_result = run_val(
        domain_file=DOMAIN_PATH,
        problem_file=PROBLEM_PATH,
        plan_file=plan_path,
        log_file=val_log_path,
        verbose=True,
        timeout_seconds=60,
    )

    refined_plan: str | None = None
    refined_val_result = None

    if not val_result.valid:
        print("\nInitial plan is invalid.")
        print("Sending VAL feedback back to the local model...")

        val_feedback = val_log_path.read_text(
            encoding="utf-8-sig",
        )

        refinement_prompt = build_refinement_prompt(
            domain_text=domain_text,
            problem_text=problem_text,
            previous_plan=plan,
            val_feedback=val_feedback,
        )

        refinement_prompt_path.write_text(
            refinement_prompt,
            encoding="utf-8",
        )

        refined_raw_response = call_local_model(
            refinement_prompt
        )

        refined_raw_response_path.write_text(
            refined_raw_response + "\n",
            encoding="utf-8",
        )

        refined_plan = extract_plan(
            refined_raw_response
        )

        if refined_plan.strip() == plan.strip():
           raise RuntimeError(
              "The model returned exactly the same invalid plan "
              "during refinement."
           )

        refined_plan_path.write_text(
            refined_plan,
            encoding="utf-8",
        )

        print("\nValidating refined plan with VAL...")

        refined_val_result = run_val(
            domain_file=DOMAIN_PATH,
            problem_file=PROBLEM_PATH,
            plan_file=refined_plan_path,
            log_file=refined_val_log_path,
            verbose=True,
            timeout_seconds=60,
        )

    print("\nRaw response saved to:")
    print(raw_response_path)

    print("\nExtracted plan saved to:")
    print(plan_path)

    print("\nExtracted plan:")
    print(plan)

    print("\nVAL result:")
    print(f"Valid: {val_result.valid}")
    print(f"Return code: {val_result.return_code}")
    print(f"Runtime: {val_result.runtime_seconds:.3f} seconds")
    print(f"Validation log: {val_result.raw_log_file}")

    
    if refined_val_result is not None:
        print("\nRefinement result:")
        print(f"Valid: {refined_val_result.valid}")
        print(
            f"Return code: "
            f"{refined_val_result.return_code}"
        )
        print(
            f"Runtime: "
            f"{refined_val_result.runtime_seconds:.3f} seconds"
        )
        print(
            f"Validation log: "
            f"{refined_val_result.raw_log_file}"
        )

        print("\nRefined plan:")
        print(refined_plan)
    else:
        print(
            "\nInitial plan was already valid, "
            "so refinement was not required."
        )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(
            f"\nERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)