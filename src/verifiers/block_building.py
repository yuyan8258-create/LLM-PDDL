from __future__ import annotations

import copy
from typing import Any

from src.domain_config import DomainConfig
from src.plan_model import (
    PlanStep,
    validate_plan,
)
from src.scene_config import SceneConfig
from src.verifiers.base import (
    SymbolicVerifier,
    VerificationResult,
)


class BlockBuildingVerifier(SymbolicVerifier):
    """
    Symbolic state simulator for the block_building domain.

    This verifier supports ordinary BlocksWorld stacking and bridge
    construction. VAL remains the final authority for plan validity.
    """

    def __init__(
        self,
        domain: DomainConfig,
    ) -> None:
        if domain.domain_id != "block_building":
            raise ValueError(
                "BlockBuildingVerifier requires domain "
                "'block_building', but received "
                f"'{domain.domain_id}'."
            )

        self.domain = domain

    def verify(
        self,
        plan: list[PlanStep],
        scene: SceneConfig,
        verbose: bool = False,
    ) -> VerificationResult:
        """
        Structurally validate and simulate the complete plan.
        """

        validate_plan(
            plan=plan,
            scene=scene,
            domain=self.domain,
        )

        state = self._copy_state(
            scene.initial_state
        )

        if verbose:
            print(
                "\nSymbolic verifier checking "
                "block action preconditions/effects:"
            )

        for step_number, step in enumerate(
            plan,
            start=1,
        ):
            state_before = self._state_summary(
                state
            )

            success, error, next_state = (
                self._apply(
                    step=step,
                    state=state,
                )
            )

            if verbose:
                marker = "SUCCESS" if success else "FAILED"

                print(
                    f"  Step {step_number}: "
                    f"{step.to_function_text()} "
                    f"-> {marker}"
                )

                if error:
                    print(f"    {error}")

            if not success:
                return VerificationResult(
                    success=False,
                    message=error,
                    final_state=self._state_summary(
                        state
                    ),
                    failed_step=step_number,
                    failed_action=(
                        step.to_function_text()
                    ),
                    error=error,
                    state_before_failure=state_before,
                )

            state = next_state

        goal_success, goal_error = (
            self._check_goal(
                state=state,
                goal_state=scene.goal_state,
            )
        )

        if not goal_success:
            if verbose:
                print(
                    "  Goal check -> FAILED"
                )
                print(f"    {goal_error}")

            return VerificationResult(
                success=False,
                message=goal_error,
                final_state=self._state_summary(
                    state
                ),
                failed_step="goal_check",
                error=goal_error,
            )

        if verbose:
            print("  Goal check -> SUCCESS")

        return VerificationResult(
            success=True,
            message=(
                "Plan is symbolically valid and all "
                "goal conditions are satisfied."
            ),
            final_state=self._state_summary(
                state
            ),
        )

    def _apply(
        self,
        step: PlanStep,
        state: dict[str, Any],
    ) -> tuple[
        bool,
        str,
        dict[str, Any],
    ]:
        """
        Apply one block action to a copied state.
        """

        action = step.action
        args = step.args
        next_state = self._copy_state(state)

        if action == "pick-up":
            return self._apply_pick_up(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "put-down":
            return self._apply_put_down(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "stack":
            return self._apply_stack(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "unstack":
            return self._apply_unstack(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "stack-bridge":
            return self._apply_stack_bridge(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "unstack-bridge":
            return self._apply_unstack_bridge(
                args=args,
                state=state,
                next_state=next_state,
            )

        return (
            False,
            f"Unsupported block action: {action}",
            state,
        )

    def _apply_pick_up(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name = args[0]
        missing: list[str] = []

        if object_name not in state["ontable"]:
            missing.append(
                f"ontable({object_name})"
            )

        if object_name not in state["clear"]:
            missing.append(
                f"clear({object_name})"
            )

        if not state["handempty"]:
            missing.append("handempty")

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["ontable"].remove(
            object_name
        )
        next_state["clear"].remove(
            object_name
        )
        next_state["holding"].add(
            object_name
        )
        next_state["handempty"] = False

        return True, "ok", next_state

    def _apply_put_down(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name = args[0]

        if object_name not in state["holding"]:
            return (
                False,
                "Missing precondition: "
                f"holding({object_name})",
                state,
            )

        next_state["holding"].remove(
            object_name
        )
        next_state["ontable"].add(
            object_name
        )
        next_state["clear"].add(
            object_name
        )
        next_state["handempty"] = True

        return True, "ok", next_state

    def _apply_stack(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name, support = args
        missing: list[str] = []

        if object_name not in state["holding"]:
            missing.append(
                f"holding({object_name})"
            )

        if support not in state["clear"]:
            missing.append(
                f"clear({support})"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            object_name
        )
        next_state["on"].add(
            (object_name, support)
        )
        next_state["clear"].add(
            object_name
        )
        next_state["clear"].discard(
            support
        )
        next_state["handempty"] = True

        return True, "ok", next_state

    def _apply_unstack(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name, support = args
        relation = (
            object_name,
            support,
        )

        missing: list[str] = []

        if relation not in state["on"]:
            missing.append(
                f"on({object_name},{support})"
            )

        if object_name not in state["clear"]:
            missing.append(
                f"clear({object_name})"
            )

        if not state["handempty"]:
            missing.append("handempty")

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["on"].remove(relation)
        next_state["clear"].discard(
            object_name
        )
        next_state["clear"].add(
            support
        )
        next_state["holding"].add(
            object_name
        )
        next_state["handempty"] = False

        return True, "ok", next_state

    def _apply_stack_bridge(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name, left, right = args
        missing: list[str] = []

        if object_name not in state["holding"]:
            missing.append(
                f"holding({object_name})"
            )

        if left not in state["right_free"]:
            missing.append(
                f"right-free({left})"
            )

        if right not in state["left_free"]:
            missing.append(
                f"left-free({right})"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            object_name
        )
        next_state["on_bridge"].add(
            (object_name, left, right)
        )
        next_state["clear"].add(
            object_name
        )
        next_state["right_free"].remove(
            left
        )
        next_state["left_free"].remove(
            right
        )
        next_state["handempty"] = True

        return True, "ok", next_state

    def _apply_unstack_bridge(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        object_name, left, right = args
        relation = (
            object_name,
            left,
            right,
        )

        missing: list[str] = []

        if relation not in state["on_bridge"]:
            missing.append(
                "on-bridge"
                f"({object_name},{left},{right})"
            )

        if object_name not in state["clear"]:
            missing.append(
                f"clear({object_name})"
            )

        if not state["handempty"]:
            missing.append("handempty")

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["on_bridge"].remove(
            relation
        )
        next_state["clear"].discard(
            object_name
        )
        next_state["holding"].add(
            object_name
        )
        next_state["right_free"].add(left)
        next_state["left_free"].add(right)
        next_state["handempty"] = False

        return True, "ok", next_state

    def _check_goal(
        self,
        state: dict[str, Any],
        goal_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check every supported positive block goal predicate.

        Unlike the old Scene 02 verifier, this also checks ordinary
        on relations required by Scene 01.
        """

        missing: list[str] = []

        for raw_predicate, raw_value in (
            goal_state.items()
        ):
            predicate = raw_predicate.replace(
                "-",
                "_",
            )

            if predicate == "handempty":
                if bool(raw_value) and not state[
                    "handempty"
                ]:
                    missing.append("handempty")

                continue

            if predicate not in state:
                missing.append(
                    f"unsupported-goal({raw_predicate})"
                )
                continue

            if not isinstance(raw_value, list):
                missing.append(
                    f"invalid-goal({raw_predicate})"
                )
                continue

            if predicate in {
                "on",
                "on_bridge",
            }:
                for raw_relation in raw_value:
                    relation = tuple(
                        raw_relation
                    )

                    if relation not in state[
                        predicate
                    ]:
                        missing.append(
                            self._format_relation(
                                raw_predicate,
                                relation,
                            )
                        )

                continue

            for object_name in raw_value:
                if object_name not in state[
                    predicate
                ]:
                    missing.append(
                        f"{raw_predicate}"
                        f"({object_name})"
                    )

        if missing:
            return (
                False,
                "Missing goal conditions: "
                + ", ".join(missing),
            )

        return True, "All goal conditions met."

    def _copy_state(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert external JSON-style state data into mutable sets.
        """

        return {
            "ontable": set(
                state.get("ontable", [])
            ),
            "on": {
                tuple(relation)
                for relation in state.get(
                    "on",
                    [],
                )
            },
            "on_bridge": {
                tuple(relation)
                for relation in (
                    state.get(
                        "on_bridge",
                        state.get(
                            "on-bridge",
                            [],
                        ),
                    )
                )
            },
            "clear": set(
                state.get("clear", [])
            ),
            "holding": set(
                state.get("holding", [])
            ),
            "handempty": bool(
                state.get("handempty", True)
            ),
            "left_free": set(
                state.get(
                    "left_free",
                    state.get(
                        "left-free",
                        [],
                    ),
                )
            ),
            "right_free": set(
                state.get(
                    "right_free",
                    state.get(
                        "right-free",
                        [],
                    ),
                )
            ),
        }

    def _state_summary(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert internal set-based state into stable JSON data.
        """

        return {
            "ontable": sorted(
                state["ontable"]
            ),
            "on": [
                list(relation)
                for relation in sorted(
                    state["on"]
                )
            ],
            "on_bridge": [
                list(relation)
                for relation in sorted(
                    state["on_bridge"]
                )
            ],
            "clear": sorted(
                state["clear"]
            ),
            "holding": sorted(
                state["holding"]
            ),
            "handempty": state[
                "handempty"
            ],
            "left_free": sorted(
                state["left_free"]
            ),
            "right_free": sorted(
                state["right_free"]
            ),
        }

    def _format_relation(
        self,
        predicate: str,
        relation: tuple[str, ...],
    ) -> str:
        return (
            f"{predicate}("
            + ",".join(relation)
            + ")"
        )


Verifier = BlockBuildingVerifier