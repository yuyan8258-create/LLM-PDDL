"""
Revised MSc Demo: Image-Inspired Block Construction with LLM + PDDL Verification
================================================================================

Project: Automatic PDDL Scene Description Generation Using LLM
Student: Yuyan Liu
Supervisor: Kunpeng Yao

What this demo does:
1. Manually abstracts an image-like block structure into a symbolic scene description.
2. Exports a real PDDL domain file and PDDL problem file.
3. Uses an LLM to generate a candidate construction plan WITHOUT giving it the exact answer.
4. Verifies the LLM plan using a lightweight PDDL-style symbolic verifier.
5. If verification fails, sends structured failure feedback to the LLM for repair.
6. Provides a manual/reference mode so the symbolic model can be tested even without Ollama.

Important research note:
- This is a prototype for the LLM + symbolic verification loop.
- The current scene extraction is manually defined, not computer vision based.
- The verifier is lightweight and implemented in Python; it mirrors the PDDL action rules
  and exports matching .pddl files for later integration with an external PDDL planner.

Run examples:
    python pyramid_demo_revised.py --planner manual
    python pyramid_demo_revised.py --planner llm --model llama3.1:8b
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


# =============================================================================
# 1. SYMBOLIC SCENE DESCRIPTION
# =============================================================================
# This manually represents the image-like pyramid/block structure:
#
#              [pyramid]
#         [B4]           [B5]
#    [B1]      [B2]           [B3]
#    -------------------------------- table
#
# The key issue in this structure is that B2 supports both B4 and B5.
# A naive "clear(B2)" model would reject this.
# Therefore, this demo uses support slots:
# - right-free(B1), left-free(B2) are consumed by placing B4 across B1-B2
# - right-free(B2), left-free(B3) are consumed by placing B5 across B2-B3
#
# This is more suitable for bridge-like block structures than ordinary BlocksWorld.

OBJECTS = ["B1", "B2", "B3", "B4", "B5", "pyramid"]

SCENE_DESCRIPTION = {
    "scene_name": "image_pyramid_scene",
    "objects": OBJECTS,
    "initial_state": {
        "on": [],
        "on_bridge": [],
        "ontable": ["B1", "B2", "B3", "B4", "B5", "pyramid"],
        "clear": ["B1", "B2", "B3", "B4", "B5", "pyramid"],
        "holding": [],
        "handempty": True,
        "left_free": ["B1", "B2", "B3", "B4", "B5", "pyramid"],
        "right_free": ["B1", "B2", "B3", "B4", "B5", "pyramid"],
    },
    "goal_state": {
        "on_bridge": [
            ["B4", "B1", "B2"],
            ["B5", "B2", "B3"],
            ["pyramid", "B4", "B5"],
        ],
        "ontable": ["B1", "B2", "B3"],
        "handempty": True,
    },
}

TASK_DESCRIPTION = """
Build the image-inspired block pyramid structure.

Target structure:
- B1, B2, and B3 form the base and remain on the table.
- B4 bridges across B1 and B2.
- B5 bridges across B2 and B3.
- pyramid bridges across B4 and B5.
- The robot hand must be empty at the end.
""".strip()


# =============================================================================
# 2. PDDL DOMAIN AND PROBLEM EXPORT
# =============================================================================

PDDL_DOMAIN = """(define (domain image_block_building)
  (:requirements :strips)

  (:predicates
    (ontable ?x)
    (on ?x ?y)
    (on-bridge ?x ?left ?right)
    (clear ?x)
    (holding ?x)
    (handempty)
    (left-free ?x)
    (right-free ?x)
  )

  (:action pick-up
    :parameters (?x)
    :precondition (and
      (ontable ?x)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (not (ontable ?x))
      (not (clear ?x))
      (not (handempty))
    )
  )

  (:action put-down
    :parameters (?x)
    :precondition (and
      (holding ?x)
    )
    :effect (and
      (ontable ?x)
      (clear ?x)
      (handempty)
      (not (holding ?x))
    )
  )

  (:action stack
    :parameters (?x ?y)
    :precondition (and
      (holding ?x)
      (clear ?y)
    )
    :effect (and
      (on ?x ?y)
      (clear ?x)
      (handempty)
      (not (holding ?x))
      (not (clear ?y))
    )
  )

  (:action unstack
    :parameters (?x ?y)
    :precondition (and
      (on ?x ?y)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (clear ?y)
      (not (on ?x ?y))
      (not (clear ?x))
      (not (handempty))
    )
  )

  (:action stack-bridge
    :parameters (?x ?left ?right)
    :precondition (and
      (holding ?x)
      (right-free ?left)
      (left-free ?right)
    )
    :effect (and
      (on-bridge ?x ?left ?right)
      (clear ?x)
      (handempty)
      (not (holding ?x))
      (not (right-free ?left))
      (not (left-free ?right))
    )
  )

  (:action unstack-bridge
    :parameters (?x ?left ?right)
    :precondition (and
      (on-bridge ?x ?left ?right)
      (clear ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (right-free ?left)
      (left-free ?right)
      (not (on-bridge ?x ?left ?right))
      (not (clear ?x))
      (not (handempty))
    )
  )
)
"""


def pddl_atom(name: str, *args: str) -> str:
    if args:
        return f"({name} {' '.join(args)})"
    return f"({name})"


def scene_to_pddl_problem(scene: Dict[str, Any]) -> str:
    objects = scene["objects"]
    init = scene["initial_state"]
    goal = scene["goal_state"]

    init_atoms: List[str] = []
    for x in init["ontable"]:
        init_atoms.append(pddl_atom("ontable", x))
    for x in init["clear"]:
        init_atoms.append(pddl_atom("clear", x))
    for x in init["holding"]:
        init_atoms.append(pddl_atom("holding", x))
    for x in init["left_free"]:
        init_atoms.append(pddl_atom("left-free", x))
    for x in init["right_free"]:
        init_atoms.append(pddl_atom("right-free", x))
    for x, y in init["on"]:
        init_atoms.append(pddl_atom("on", x, y))
    for x, left, right in init["on_bridge"]:
        init_atoms.append(pddl_atom("on-bridge", x, left, right))
    if init["handempty"]:
        init_atoms.append(pddl_atom("handempty"))

    goal_atoms: List[str] = []
    for x in goal.get("ontable", []):
        goal_atoms.append(pddl_atom("ontable", x))
    for x, left, right in goal.get("on_bridge", []):
        goal_atoms.append(pddl_atom("on-bridge", x, left, right))
    if goal.get("handempty", False):
        goal_atoms.append(pddl_atom("handempty"))

    init_text = "\n".join(f"    {a}" for a in init_atoms)
    goal_text = "\n".join(f"      {a}" for a in goal_atoms)

    return f"""(define (problem {scene["scene_name"]})
  (:domain image_block_building)

  (:objects
    {' '.join(objects)}
  )

  (:init
{init_text}
  )

  (:goal
    (and
{goal_text}
    )
  )
)
"""


def export_pddl_files(output_dir: str = "generated_pddl") -> Tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    domain_path = out / "domain.pddl"
    problem_path = out / "problem_image_pyramid.pddl"

    domain_path.write_text(PDDL_DOMAIN, encoding="utf-8")
    problem_path.write_text(scene_to_pddl_problem(SCENE_DESCRIPTION), encoding="utf-8")

    return domain_path, problem_path


# =============================================================================
# 3. PLAN REPRESENTATION
# =============================================================================

@dataclass
class PlanStep:
    action: str
    args: List[str]

    def pretty(self) -> str:
        return f"{self.action}({', '.join(self.args)})"


REFERENCE_PLAN = [
    PlanStep("pick-up", ["B4"]),
    PlanStep("stack-bridge", ["B4", "B1", "B2"]),
    PlanStep("pick-up", ["B5"]),
    PlanStep("stack-bridge", ["B5", "B2", "B3"]),
    PlanStep("pick-up", ["pyramid"]),
    PlanStep("stack-bridge", ["pyramid", "B4", "B5"]),
]


def plan_steps_to_json(plan: List[PlanStep]) -> str:
    return json.dumps(
        [{"action": s.action, "args": s.args} for s in plan],
        indent=2,
        ensure_ascii=False,
    )


def _clean_llm_output(raw: str) -> str:
    """Remove common LLM wrappers such as markdown code fences."""
    raw = raw.strip()
    raw = re.sub(r"```(?:json|python|text)?", "", raw, flags=re.IGNORECASE).strip()
    raw = raw.replace("```", "").strip()
    return raw


def _try_parse_json_like_plan(raw: str) -> Optional[List[PlanStep]]:
    """
    Try to parse LLM output as JSON-like data.

    This accepts the ideal format:
      [{"action": "pick-up", "args": ["B4"]}, ...]

    It also repairs common LLM mistakes:
    - extra text before/after the JSON array
    - trailing commas before ] or }
    - Python-style single-quoted lists/dicts via ast.literal_eval
    """
    cleaned = _clean_llm_output(raw)

    match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)

    # Remove JavaScript-style comments and trailing commas.
    repaired = re.sub(r"//.*", "", cleaned)
    repaired = re.sub(r",\s*([\]}])", r"\1", repaired)

    data: Any
    try:
        data = json.loads(repaired)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(repaired)
        except Exception:
            return None

    if not isinstance(data, list):
        return None

    parsed: List[PlanStep] = []
    for item in data:
        if isinstance(item, dict):
            action = item.get("action")
            args = item.get("args")
            if isinstance(action, str) and isinstance(args, list):
                parsed.append(PlanStep(action=action.strip(), args=[str(a).strip() for a in args]))
            else:
                return None
        elif isinstance(item, str):
            # Accept JSON arrays of action strings, e.g. ["pick-up(B4)", ...]
            step = _parse_single_action_text(item)
            if step is None:
                return None
            parsed.append(step)
        else:
            return None

    return parsed if parsed else None


def _parse_single_action_text(text_line: str) -> Optional[PlanStep]:
    """Parse a single action line such as '1. pick-up(B4)' or '(pick-up B4)'."""
    line = text_line.strip()
    if not line:
        return None

    # Remove common list markers: "1.", "-", "*".
    line = re.sub(r"^\s*\d+\s*[\.)]\s*", "", line)
    line = re.sub(r"^\s*[-*]\s*", "", line)

    # JSON-ish escaped quotes are not useful here.
    line = line.strip().strip('"').strip("'")

    valid_actions = r"pick-up|put-down|stack-bridge|unstack-bridge|stack|unstack"

    # Form 1: pick-up(B4), stack-bridge(B4, B1, B2)
    m = re.search(rf"\b({valid_actions})\s*\(\s*([^)]*?)\s*\)", line, flags=re.IGNORECASE)
    if m:
        action = m.group(1).lower()
        args_text = m.group(2).strip()
        args = [a.strip() for a in re.split(r"\s*,\s*|\s+", args_text) if a.strip()]
        return PlanStep(action=action, args=args)

    # Form 2: (pick-up B4), (stack-bridge B4 B1 B2)
    m = re.search(rf"\(\s*({valid_actions})\s+([^)]*?)\s*\)", line, flags=re.IGNORECASE)
    if m:
        action = m.group(1).lower()
        args = [a.strip().strip(",") for a in m.group(2).split() if a.strip().strip(",")]
        return PlanStep(action=action, args=args)

    return None


def _parse_action_list_text(raw: str) -> Optional[List[PlanStep]]:
    """
    Fallback parser for non-JSON LLM outputs.

    Accepts outputs such as:
      1. pick-up(B4)
      2. stack-bridge(B4, B1, B2)

    or:
      (pick-up B4)
      (stack-bridge B4 B1 B2)
    """
    cleaned = _clean_llm_output(raw)
    parsed: List[PlanStep] = []

    for line in cleaned.splitlines():
        step = _parse_single_action_text(line)
        if step is not None:
            parsed.append(step)

    # If the model put all actions on one line, regex across the whole output.
    if not parsed:
        valid_actions = r"pick-up|put-down|stack-bridge|unstack-bridge|stack|unstack"
        for m in re.finditer(rf"\b({valid_actions})\s*\(\s*([^)]*?)\s*\)", cleaned, flags=re.IGNORECASE):
            action = m.group(1).lower()
            args_text = m.group(2).strip()
            args = [a.strip() for a in re.split(r"\s*,\s*|\s+", args_text) if a.strip()]
            parsed.append(PlanStep(action=action, args=args))

    return parsed if parsed else None


def normalize_llm_json_plan(raw: str) -> List[PlanStep]:
    """
    Robustly parse an LLM-generated plan.

    The earlier demo accepted only strict JSON. In practice, local LLMs often return
    almost-correct JSON, markdown wrappers, numbered action lists, or PDDL-like actions.
    This parser first tries JSON, then falls back to extracting action text.
    """
    plan = _try_parse_json_like_plan(raw)
    if plan is not None:
        return plan

    plan = _parse_action_list_text(raw)
    if plan is not None:
        return plan

    cleaned = _clean_llm_output(raw)
    raise ValueError(
        "Could not parse LLM output as JSON or action-list text.\n"
        "Raw LLM output was:\n"
        f"{cleaned}"
    )

# =============================================================================
# 4. LIGHTWEIGHT PDDL-STYLE SYMBOLIC VERIFIER
# =============================================================================

class SymbolicVerifier:
    """
    This verifier mirrors the PDDL domain rules in Python.
    It is used to produce detailed feedback for the LLM.
    """

    VALID_ARITY = {
        "pick-up": 1,
        "put-down": 1,
        "stack": 2,
        "unstack": 2,
        "stack-bridge": 3,
        "unstack-bridge": 3,
    }

    def verify(self, plan: List[PlanStep], initial_state: Dict[str, Any], goal_state: Dict[str, Any], verbose: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        state = self._copy_state(initial_state)

        if verbose:
            print("\n  Verifier checking action preconditions/effects:")

        for idx, step in enumerate(plan, start=1):
            ok, message, new_state = self._apply(step, state)
            if verbose:
                icon = "✓" if ok else "✗"
                print(f"    {icon} Step {idx}: {step.pretty()}")
                if not ok:
                    print(f"      ERROR: {message}")

            if not ok:
                feedback = {
                    "failed_step": idx,
                    "failed_action": step.pretty(),
                    "error": message,
                    "state_before_failure": self._state_summary(state),
                }
                return False, json.dumps(feedback, indent=2, ensure_ascii=False), state

            state = new_state

        goal_ok, goal_msg = self._check_goal(state, goal_state)
        if not goal_ok:
            feedback = {
                "failed_step": "goal_check",
                "error": goal_msg,
                "final_state": self._state_summary(state),
            }
            if verbose:
                print(f"    ✗ Goal check failed: {goal_msg}")
            return False, json.dumps(feedback, indent=2, ensure_ascii=False), state

        if verbose:
            print("    ✓ Goal check passed.")

        return True, "Plan is valid and all goal conditions are achieved.", state

    def _apply(self, step: PlanStep, state: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        action = step.action.lower().strip()
        args = step.args
        s = self._copy_state(state)

        if action not in self.VALID_ARITY:
            return False, f"Unknown action '{step.action}'.", state

        expected = self.VALID_ARITY[action]
        if len(args) != expected:
            return False, f"Action '{action}' requires {expected} argument(s), but got {len(args)}.", state

        if action == "pick-up":
            x = args[0]
            missing = []
            if x not in s["ontable"]:
                missing.append(f"ontable({x})")
            if x not in s["clear"]:
                missing.append(f"clear({x})")
            if not s["handempty"]:
                missing.append("handempty")
            if missing:
                return False, "Missing preconditions: " + ", ".join(missing), state

            s["ontable"].remove(x)
            s["clear"].remove(x)
            s["holding"].append(x)
            s["handempty"] = False
            return True, "ok", s

        if action == "put-down":
            x = args[0]
            if x not in s["holding"]:
                return False, f"Missing precondition: holding({x})", state

            s["holding"].remove(x)
            s["ontable"].append(x)
            if x not in s["clear"]:
                s["clear"].append(x)
            s["handempty"] = True
            return True, "ok", s

        if action == "stack":
            x, y = args
            missing = []
            if x not in s["holding"]:
                missing.append(f"holding({x})")
            if y not in s["clear"]:
                missing.append(f"clear({y})")
            if missing:
                return False, "Missing preconditions: " + ", ".join(missing), state

            s["holding"].remove(x)
            s["on"].append((x, y))
            if x not in s["clear"]:
                s["clear"].append(x)
            if y in s["clear"]:
                s["clear"].remove(y)
            s["handempty"] = True
            return True, "ok", s

        if action == "unstack":
            x, y = args
            missing = []
            if (x, y) not in s["on"]:
                missing.append(f"on({x},{y})")
            if x not in s["clear"]:
                missing.append(f"clear({x})")
            if not s["handempty"]:
                missing.append("handempty")
            if missing:
                return False, "Missing preconditions: " + ", ".join(missing), state

            s["on"].remove((x, y))
            if x in s["clear"]:
                s["clear"].remove(x)
            s["holding"].append(x)
            if y not in s["clear"]:
                s["clear"].append(y)
            s["handempty"] = False
            return True, "ok", s

        if action == "stack-bridge":
            x, left, right = args
            missing = []
            if x not in s["holding"]:
                missing.append(f"holding({x})")
            if left not in s["right_free"]:
                missing.append(f"right-free({left})")
            if right not in s["left_free"]:
                missing.append(f"left-free({right})")
            if missing:
                return False, "Missing preconditions: " + ", ".join(missing), state

            s["holding"].remove(x)
            s["on_bridge"].append((x, left, right))
            if x not in s["clear"]:
                s["clear"].append(x)
            s["right_free"].remove(left)
            s["left_free"].remove(right)
            s["handempty"] = True
            return True, "ok", s

        if action == "unstack-bridge":
            x, left, right = args
            missing = []
            if (x, left, right) not in s["on_bridge"]:
                missing.append(f"on-bridge({x},{left},{right})")
            if x not in s["clear"]:
                missing.append(f"clear({x})")
            if not s["handempty"]:
                missing.append("handempty")
            if missing:
                return False, "Missing preconditions: " + ", ".join(missing), state

            s["on_bridge"].remove((x, left, right))
            if x in s["clear"]:
                s["clear"].remove(x)
            s["holding"].append(x)
            if left not in s["right_free"]:
                s["right_free"].append(left)
            if right not in s["left_free"]:
                s["left_free"].append(right)
            s["handempty"] = False
            return True, "ok", s

        return False, f"Unhandled action '{action}'.", state

    def _check_goal(self, state: Dict[str, Any], goal_state: Dict[str, Any]) -> Tuple[bool, str]:
        missing = []

        for triple in goal_state.get("on_bridge", []):
            t = tuple(triple)
            if t not in state["on_bridge"]:
                missing.append(f"on-bridge({','.join(triple)})")

        for x in goal_state.get("ontable", []):
            if x not in state["ontable"]:
                missing.append(f"ontable({x})")

        if goal_state.get("handempty", False) and not state["handempty"]:
            missing.append("handempty")

        if missing:
            return False, "Missing goal conditions: " + ", ".join(missing)

        return True, "All goal conditions met."

    def _copy_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "on": [tuple(x) for x in state.get("on", [])],
            "on_bridge": [tuple(x) for x in state.get("on_bridge", [])],
            "ontable": list(state.get("ontable", [])),
            "clear": list(state.get("clear", [])),
            "holding": list(state.get("holding", [])),
            "handempty": bool(state.get("handempty", True)),
            "left_free": list(state.get("left_free", [])),
            "right_free": list(state.get("right_free", [])),
        }

    def _state_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "on": [list(x) for x in state["on"]],
            "on_bridge": [list(x) for x in state["on_bridge"]],
            "ontable": sorted(state["ontable"]),
            "clear": sorted(state["clear"]),
            "holding": sorted(state["holding"]),
            "handempty": state["handempty"],
            "left_free": sorted(state["left_free"]),
            "right_free": sorted(state["right_free"]),
        }


# =============================================================================
# 5. LLM PLANNER WITH STRUCTURED FEEDBACK
# =============================================================================

class LLMPlanner:
    def __init__(self, model: str):
        self.model = model
        self.last_raw_response = ""

    def generate(self, feedback: Optional[str] = None) -> List[PlanStep]:
        prompt = self._build_prompt(feedback)
        raw = self._call_ollama(prompt)
        self.last_raw_response = raw
        return normalize_llm_json_plan(raw)

    def _build_prompt(self, feedback: Optional[str]) -> str:
        feedback_section = ""
        if feedback:
            feedback_section = f"""
Your previous plan failed symbolic verification.
Use the feedback below to repair the FULL plan.

VERIFIER FEEDBACK:
{feedback}

Repair guidance:
- If the error says handempty is missing, it means the plan tried to pick up another block while already holding one.
- Fix this by placing the currently held block with stack-bridge before any later pick-up action.
- If the error says holding(X) is missing, it means the plan tried to stack-bridge X after it had already been put down or before it was picked up.
- For this task, remove put-down actions and use the alternating pattern: pick-up(X), then stack-bridge(X, LEFT, RIGHT).
"""

        return f"""
You are a robot task planner for an image-inspired block construction scene.

This is a symbolic planning task, not a language explanation task.

TASK:
{TASK_DESCRIPTION}

OBJECTS:
{", ".join(OBJECTS)}

SYMBOLIC DOMAIN:
Predicates:
- ontable(X): X is on the table
- clear(X): X can be picked up or used as an upper block
- holding(X): robot is holding X
- handempty: robot hand is empty
- on-bridge(X, LEFT, RIGHT): X bridges across LEFT and RIGHT
- left-free(X): the left support slot of X is available
- right-free(X): the right support slot of X is available

Available actions:
1. pick-up(X)
   Preconditions: ontable(X), clear(X), handempty
   Effects: holding(X), not ontable(X), not clear(X), not handempty

2. put-down(X)
   Preconditions: holding(X)
   Effects: ontable(X), clear(X), handempty, not holding(X)

3. stack-bridge(X, LEFT, RIGHT)
   Meaning: place X so it bridges across LEFT and RIGHT.
   Preconditions: holding(X), right-free(LEFT), left-free(RIGHT)
   Effects: on-bridge(X, LEFT, RIGHT), clear(X), handempty,
            not holding(X), not right-free(LEFT), not left-free(RIGHT)

Important rules:
- B1, B2, and B3 are base blocks. They must remain on the table. Do NOT pick them up.
- You may use B2 as a shared support: its left slot and right slot are different.
- For this construction task, do NOT use put-down. Every picked-up block must be placed into the structure.
- The robot has only one hand. Never pick-up a second block while another block is being held.
- Therefore, each pick-up(X) must be immediately followed by stack-bridge(X, LEFT, RIGHT) for the SAME X.
- Build from lower layer to upper layer: B4 and B5 must be placed before pyramid can be placed.
- Do not output explanations.
- Do not output markdown.
- Output ONLY a JSON array.
- Each item must have "action" and "args".
- Use action names exactly: "pick-up" and "stack-bridge".

Goal conditions:
- on-bridge(B4, B1, B2)
- on-bridge(B5, B2, B3)
- on-bridge(pyramid, B4, B5)
- ontable(B1)
- ontable(B2)
- ontable(B3)
- handempty
{feedback_section}
Output format example:
[
  {{"action": "pick-up", "args": ["some_block"]}},
  {{"action": "stack-bridge", "args": ["some_block", "left_support", "right_support"]}}
]
""".strip()

    def _call_ollama(self, prompt: str) -> str:
        try:
            import ollama  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The 'ollama' Python package is not installed. "
                "Install it with: pip install ollama\n"
                "Or run this demo with: --planner manual"
            ) from exc

        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
        return response["message"]["content"].strip()


# =============================================================================
# 6. HYBRID PIPELINE
# =============================================================================

class HybridPipeline:
    def __init__(self, model: str, max_iterations: int = 3):
        self.model = model
        self.max_iterations = max_iterations
        self.verifier = SymbolicVerifier()

    def run_with_manual_plan(self) -> Dict[str, Any]:
        print("\n[MODE] Manual/reference plan verification")
        print("This mode tests whether the symbolic model and verifier are internally consistent.")
        return self._verify_and_summarize(REFERENCE_PLAN, iteration=1)

    def run_with_llm(self) -> Dict[str, Any]:
        print("\n[MODE] LLM + symbolic verification loop")
        print("The prompt does NOT contain the exact correct answer, but includes stricter action-sequencing rules.")
        planner = LLMPlanner(model=self.model)
        feedback: Optional[str] = None
        logs: List[Dict[str, Any]] = []

        for iteration in range(1, self.max_iterations + 1):
            print("\n" + "-" * 72)
            print(f"Iteration {iteration}/{self.max_iterations}")
            print("-" * 72)

            try:
                plan = planner.generate(feedback=feedback)
            except Exception as exc:
                logs.append({
                    "iteration": iteration,
                    "parse_or_generation_error": str(exc),
                    "raw_llm_output": getattr(planner, "last_raw_response", ""),
                    "success": False,
                })
                return {
                    "success": False,
                    "error": str(exc),
                    "logs": logs,
                }

            print("\n  LLM generated plan:")
            for i, step in enumerate(plan, start=1):
                print(f"    {i}. {step.pretty()}")

            ok, verifier_msg, final_state = self.verifier.verify(
                plan,
                SCENE_DESCRIPTION["initial_state"],
                SCENE_DESCRIPTION["goal_state"],
                verbose=True,
            )

            logs.append({
                "iteration": iteration,
                "plan": [{"action": s.action, "args": s.args} for s in plan],
                "raw_llm_output": planner.last_raw_response,
                "verifier_message": verifier_msg,
                "success": ok,
            })

            if ok:
                return {
                    "success": True,
                    "iterations": iteration,
                    "plan": plan,
                    "final_state": final_state,
                    "logs": logs,
                }

            feedback = verifier_msg
            print("\n  Plan failed. Structured verifier feedback will be sent back to the LLM.")

        return {
            "success": False,
            "iterations": self.max_iterations,
            "plan": None,
            "logs": logs,
        }

    def _verify_and_summarize(self, plan: List[PlanStep], iteration: int) -> Dict[str, Any]:
        print("\n  Plan to verify:")
        for i, step in enumerate(plan, start=1):
            print(f"    {i}. {step.pretty()}")

        ok, msg, final_state = self.verifier.verify(
            plan,
            SCENE_DESCRIPTION["initial_state"],
            SCENE_DESCRIPTION["goal_state"],
            verbose=True,
        )

        return {
            "success": ok,
            "iterations": iteration,
            "plan": plan if ok else None,
            "verifier_message": msg,
            "final_state": final_state,
        }


# =============================================================================
# 7. OUTPUT / REPORTING
# =============================================================================

def print_header(domain_path: Path, problem_path: Path) -> None:
    print("=" * 78)
    print("IMAGE-INSPIRED BLOCK CONSTRUCTION DEMO")
    print("LLM plan generation + PDDL-style symbolic verification")
    print("=" * 78)
    print("\nResearch alignment:")
    print("  1. Image-like target structure is manually abstracted into symbolic scene relations.")
    print("  2. The symbolic scene is exported as real PDDL domain/problem files.")
    print("  3. The LLM generates candidate construction plans.")
    print("  4. The verifier checks preconditions, effects, and goal satisfaction.")
    print("  5. Structured errors are fed back to the LLM for refinement.")
    print("\nImportant limitation:")
    print("  - This prototype does not perform computer vision.")
    print("  - The Python verifier is lightweight; external PDDL solver integration is the next step.")
    print("\nTarget structure:")
    print("              [pyramid]")
    print("         [B4]           [B5]")
    print("    [B1]      [B2]           [B3]")
    print("    -------------------------------- table")
    print("\nExported PDDL files:")
    print(f"  Domain : {domain_path}")
    print(f"  Problem: {problem_path}")
    print("=" * 78)


def save_result(result: Dict[str, Any], output_path: str = "results/pyramid_demo_result.json") -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    serializable = copy.deepcopy(result)
    if serializable.get("plan"):
        serializable["plan"] = [
            {"action": step.action, "args": step.args}
            for step in serializable["plan"]
        ]

    out.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved experiment result to: {out}")


def print_summary(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 78)
    print("EXPERIMENT SUMMARY")
    print("=" * 78)
    print(f"Result: {'SUCCESS' if result.get('success') else 'FAILED'}")
    if "iterations" in result:
        print(f"Iterations: {result['iterations']}")

    if result.get("error"):
        print(f"Error: {result['error']}")

    if result.get("success") and result.get("plan"):
        print("\nFinal validated plan:")
        for i, step in enumerate(result["plan"], start=1):
            print(f"  {i}. {step.pretty()}")

    print("\nGoal conditions:")
    print("  on-bridge(B4, B1, B2)")
    print("  on-bridge(B5, B2, B3)")
    print("  on-bridge(pyramid, B4, B5)")
    print("  ontable(B1), ontable(B2), ontable(B3), handempty")
    print("=" * 78)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--planner",
        choices=["manual", "llm"],
        default="manual",
        help="manual verifies a reference plan; llm runs LLM generation + verification loop.",
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Ollama model name, used only with --planner llm.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum LLM refinement iterations.",
    )
    args = parser.parse_args()

    domain_path, problem_path = export_pddl_files()
    print_header(domain_path, problem_path)

    pipeline = HybridPipeline(model=args.model, max_iterations=args.max_iterations)

    if args.planner == "manual":
        result = pipeline.run_with_manual_plan()
    else:
        result = pipeline.run_with_llm()

    print_summary(result)
    save_result(result)


if __name__ == "__main__":
    main()
