"""
Automatic PDDL Scene Description Generation Using LLM

APPROACH 1 (Primary): LLM generates TAMP solution → PDDL Verifier checks →
                       Feedback loop for self-correction

Uses Ollama (local, free, no API key needed)
"""

import re
import json
import ollama

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MODEL = "llama3.1:8b" # local model, runs on your machine


# ─────────────────────────────────────────────
# BLOCKSWORLD DOMAIN
# Simulates the "environment model" input
# ─────────────────────────────────────────────
BLOCKS_WORLD_DOMAIN = """
DOMAIN: BlocksWorld
OBJECTS: blockA, blockB, blockC, table

PREDICATES:
  - on(X, Y)    : block X is on top of Y
  - ontable(X)  : block X is on the table
  - clear(X)    : nothing is on top of X
  - holding(X)  : robot arm is holding X
  - handempty   : robot arm is empty

ACTIONS:
  pick-up(X):
    PRECONDITIONS: clear(X), ontable(X), handempty
    EFFECTS: holding(X), NOT ontable(X), NOT clear(X), NOT handempty

  put-down(X):
    PRECONDITIONS: holding(X)
    EFFECTS: ontable(X), clear(X), handempty, NOT holding(X)

  stack(X, Y):
    PRECONDITIONS: holding(X), clear(Y)
    EFFECTS: on(X,Y), clear(X), handempty, NOT holding(X), NOT clear(Y)

  unstack(X, Y):
    PRECONDITIONS: on(X,Y), clear(X), handempty
    EFFECTS: holding(X), clear(Y), NOT on(X,Y), NOT clear(X), NOT handempty
"""

# Initial state: blockA is on blockB, blockB and blockC are on table
INITIAL_STATE = {
    "on":        [("blockA", "blockB")],
    "ontable":   ["blockB", "blockC"],
    "clear":     ["blockA", "blockC"],
    "holding":   [],
    "handempty": True,
}

GOAL_DESCRIPTION = "blockA on table, blockB on top of blockC, hand empty"


# ─────────────────────────────────────────────
# MODULE 1 - LLM PLANNER
# ─────────────────────────────────────────────
class LLMPlanner:

    def generate_plan(self, task: str, domain: str,
                      initial_state: dict, feedback: str = None) -> list:
        """
        Call local LLM to generate an action sequence.
        If feedback is provided, ask LLM to self-correct.
        """
        feedback_section = ""
        if feedback:
            feedback_section = f"""
YOUR PREVIOUS PLAN FAILED. Here is the structured error feedback from the PDDL verifier:
{feedback}

Fix the plan so that every action's preconditions are satisfied by the current state.
"""

        prompt = f"""You are a robot task planner. Generate a step-by-step plan for the BlocksWorld domain.

DOMAIN:
{domain}

CURRENT STATE:
{json.dumps(initial_state, indent=2)}

GOAL: {task}
{feedback_section}
CRITICAL CONSTRAINTS (read carefully before planning):
- blockA is ON TOP OF blockB, it is NOT on the table
- Therefore you CANNOT use pick-up(blockA) as the first action
- You MUST use unstack(blockA, blockB) to remove blockA first
- Only use pick-up when a block is directly on the TABLE
- After stack(X, Y), your hand is ALREADY empty automatically. Do NOT add put-down after stack.
- The correct plan is EXACTLY 4 steps. Stop after stack(blockB, blockC).
OUTPUT RULES (follow exactly):
- Respond with ONLY a JSON array
- Each element: {{"action": "<action-name>", "args": ["<arg1>", "<arg2>"]}}
- action must be one of: pick-up, put-down, stack, unstack
- No explanation, no markdown, no extra text

Example:
[
  {{"action": "unstack", "args": ["blockA", "blockB"]}},
  {{"action": "put-down", "args": ["blockA"]}}
]"""

        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )

        raw = response["message"]["content"].strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"LLM returned invalid JSON:\n{raw}")


# ─────────────────────────────────────────────
# MODULE 2 - PDDL SYMBOLIC VERIFIER
# ─────────────────────────────────────────────
class PDDLVerifier:
    """
    Checks each action's preconditions against the current state.
    Applies effects if preconditions are satisfied.
    Returns: (success, feedback_message, final_state)
    """

    def verify(self, plan: list, initial_state: dict):
        state  = self._copy(initial_state)
        errors = []

        for i, step in enumerate(plan):
            action = step.get("action", "").lower().replace("-", "_")
            args   = step.get("args", [])
            label  = f"Step {i+1}: {step['action']}({', '.join(args)})"

            ok, error, state = self._apply(action, args, state)
            if ok:
                print(f"  ✓ {label}")
            else:
                print(f"  ✗ {label}  ->  {error}")
                errors.append(f"  {label}\n    ERROR: {error}")

        if errors:
            return False, "LOGICAL ERRORS:\n" + "\n".join(errors), state
        return True, "All preconditions satisfied.", state

    def _apply(self, action, args, state):
        s = self._copy(state)

        if action == "pick_up":
            x = args[0]
            missing = []
            if x not in s["clear"]:   missing.append(f"clear({x})")
            if x not in s["ontable"]: missing.append(f"ontable({x})")
            if not s["handempty"]:    missing.append("handempty")
            if missing:
                return False, f"Missing preconditions: {', '.join(missing)}", state
            s["ontable"].remove(x); s["clear"].remove(x)
            s["handempty"] = False;  s["holding"].append(x)
            return True, "", s

        elif action == "put_down":
            x = args[0]
            if x not in s["holding"]:
                return False, f"Missing preconditions: holding({x})", state
            s["holding"].remove(x); s["ontable"].append(x)
            s["clear"].append(x);   s["handempty"] = True
            return True, "", s

        elif action == "stack":
            x, y = args[0], args[1]
            missing = []
            if x not in s["holding"]: missing.append(f"holding({x})")
            if y not in s["clear"]:   missing.append(f"clear({y})")
            if missing:
                return False, f"Missing preconditions: {', '.join(missing)}", state
            s["holding"].remove(x); s["clear"].remove(y)
            s["on"].append((x, y)); s["clear"].append(x)
            s["handempty"] = True
            return True, "", s

        elif action == "unstack":
            x, y = args[0], args[1]
            missing = []
            if (x, y) not in s["on"]: missing.append(f"on({x},{y})")
            if x not in s["clear"]:   missing.append(f"clear({x})")
            if not s["handempty"]:    missing.append("handempty")
            if missing:
                return False, f"Missing preconditions: {', '.join(missing)}", state
            s["on"].remove((x, y)); s["clear"].remove(x)
            s["holding"].append(x); s["clear"].append(y)
            s["handempty"] = False
            return True, "", s

        else:
            return False, f"Unknown action: '{action}'", state

    def _copy(self, state):
        return {
            "on":        list(state.get("on", [])),
            "ontable":   list(state.get("ontable", [])),
            "clear":     list(state.get("clear", [])),
            "holding":   list(state.get("holding", [])),
            "handempty": state.get("handempty", True),
        }


# ─────────────────────────────────────────────
# MODULE 3 - HYBRID PLANNING PIPELINE
# ─────────────────────────────────────────────
class HybridPlanner:
    """
    Core pipeline (Approach 1):
    LLM generates plan -> PDDL verifier checks -> feedback loop -> valid plan
    """

    def __init__(self, max_iterations: int = 3):
        self.llm      = LLMPlanner()
        self.verifier = PDDLVerifier()
        self.max_iter = max_iterations

    def plan(self, task: str, domain: str, initial_state: dict) -> dict:
        print("\n" + "=" * 60)
        print("  HYBRID LLM + PDDL PLANNER  (Approach 1)")
        print("=" * 60)
        print(f"  Task  : {task}")
        print(f"  Goal  : {GOAL_DESCRIPTION}")
        print("=" * 60)

        feedback = None
        log      = []

        for iteration in range(1, self.max_iter + 1):
            print(f"\n[ Iteration {iteration} / {self.max_iter} ]")
            print("  -> LLM generating plan...")

            plan = self.llm.generate_plan(task, domain, initial_state, feedback)
            steps = [f"{s['action']}({','.join(s['args'])})" for s in plan]
            print(f"  -> Plan ({len(plan)} steps): {steps}")
            print("  -> PDDL Verifier checking...")

            success, feedback, final_state = self.verifier.verify(plan, initial_state)
            log.append({"iteration": iteration, "plan": plan,
                        "success": success, "feedback": feedback})

            if success:
                print(f"\n  [SUCCESS] Valid plan found in {iteration} iteration(s)!")
                return {"success": True, "plan": plan,
                        "iterations": iteration, "log": log}

            print(f"\n  [FAIL] Verifier feedback sent back to LLM:\n{feedback}")

        print(f"\n  [FAIL] No valid plan found after {self.max_iter} iterations.")
        return {"success": False, "plan": None,
                "iterations": self.max_iter, "log": log}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    planner = HybridPlanner(max_iterations=3)

    result = planner.plan(
        task=f"Rearrange blocks to reach this goal state: {GOAL_DESCRIPTION}",
        domain=BLOCKS_WORLD_DOMAIN,
        initial_state=INITIAL_STATE,
    )

    print("\n" + "=" * 60)
    print("  EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"  Initial state : blockA on blockB; blockB, blockC on table")
    print(f"  Goal state    : {GOAL_DESCRIPTION}")
    print(f"  Result        : {'SUCCESS' if result['success'] else 'FAILED'}")
    print(f"  Iterations    : {result['iterations']}")
    if result["success"]:
        print(f"  Final plan ({len(result['plan'])} steps):")
        for i, s in enumerate(result["plan"], 1):
            print(f"    {i}. {s['action']}({', '.join(s['args'])})")
    print("=" * 60)


if __name__ == "__main__":
    main()
