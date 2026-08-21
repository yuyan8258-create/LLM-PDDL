from __future__ import annotations

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


class OcclusionManipulationVerifier(SymbolicVerifier):
    """
    Symbolic state simulator for the Occlusion Manipulation v1 domain.

    VAL remains the final formal validation authority.

    This verifier:
    - mirrors the frozen PDDL action preconditions/effects;
    - mirrors PDDL parameter types using SceneConfig.object_types;
    - diagnoses failed symbolic transitions for Hybrid feedback;
    - does not infer additional physical or visual relationships.
    """

    TARGET_TYPE = "target-brick"
    OCCLUDER_TYPE = "occluder-brick"
    TARGET_STRUCTURAL_LOCATION_TYPE = (
        "target-structural-location"
    )
    OCCLUDER_STRUCTURAL_LOCATION_TYPE = (
        "occluder-structural-location"
    )
    TEMPORARY_LOCATION_TYPE = "temporary-location"
    GOAL_LOCATION_TYPE = "goal-location"

    def __init__(
        self,
        domain: DomainConfig,
    ) -> None:
        if domain.domain_id != "occlusion_manipulation":
            raise ValueError(
                "OcclusionManipulationVerifier requires domain "
                "'occlusion_manipulation', but received "
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
        Structurally validate and simulate one complete plan.
        """

        # Generic validation:
        # - action name
        # - arity
        # - declared objects
        #
        # Typed PDDL argument roles are checked separately below.
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
                "Occlusion action preconditions/effects:"
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
                    scene=scene,
                )
            )

            if verbose:
                marker = (
                    "SUCCESS"
                    if success
                    else "FAILED"
                )

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
                print("  Goal check -> FAILED")
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
        scene: SceneConfig,
    ) -> tuple[
        bool,
        str,
        dict[str, Any],
    ]:
        """
        Apply one Occlusion action to a copied state.

        PDDL parameter-role validation happens before dynamic
        precondition checking.
        """

        role_error = self._validate_action_roles(
            step=step,
            scene=scene,
        )

        if role_error:
            return (
                False,
                role_error,
                state,
            )

        action = step.action
        args = step.args

        next_state = self._copy_state(state)

        if action == "remove-stacked-occluder":
            return self._apply_remove_stacked_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "remove-ground-occluder":
            return self._apply_remove_ground_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "put-down-occluder":
            return self._apply_put_down_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "pick-up-temp-occluder":
            return self._apply_pick_up_temp_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "pick-up-target":
            return self._apply_pick_up_target(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "put-down-target":
            return self._apply_put_down_target(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "restore-ground-occluder":
            return self._apply_restore_ground_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        if action == "stack-occluder":
            return self._apply_stack_occluder(
                args=args,
                state=state,
                next_state=next_state,
            )

        return (
            False,
            f"Unsupported occlusion action: {action}",
            state,
        )

    def _validate_action_roles(
        self,
        step: PlanStep,
        scene: SceneConfig,
    ) -> str | None:
        """
        Mirror the typed parameters in Occlusion v1 domain.pddl.

        This does not define which actions are legal; action existence
        and arity remain controlled by DomainConfig/validate_plan().

        It only enforces the PDDL parameter types for an already
        structurally valid grounded action.
        """

        targets = set(
            scene.object_types.get(
                self.TARGET_TYPE,
                [],
            )
        )

        occluders = set(
            scene.object_types.get(
                self.OCCLUDER_TYPE,
                [],
            )
        )

        target_locations = set(
            scene.object_types.get(
                self.TARGET_STRUCTURAL_LOCATION_TYPE,
                [],
            )
        )

        occluder_locations = set(
            scene.object_types.get(
                self.OCCLUDER_STRUCTURAL_LOCATION_TYPE,
                [],
            )
        )

        temporary_locations = set(
            scene.object_types.get(
                self.TEMPORARY_LOCATION_TYPE,
                [],
            )
        )

        goal_locations = set(
            scene.object_types.get(
                self.GOAL_LOCATION_TYPE,
                [],
            )
        )

        expected_roles: dict[
            str,
            tuple[
                tuple[str, set[str]],
                ...
            ],
        ] = {
            "remove-stacked-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
            ),
            "remove-ground-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.OCCLUDER_STRUCTURAL_LOCATION_TYPE,
                    occluder_locations,
                ),
                (
                    self.TARGET_TYPE,
                    targets,
                ),
            ),
            "put-down-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.TEMPORARY_LOCATION_TYPE,
                    temporary_locations,
                ),
            ),
            "pick-up-temp-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.TEMPORARY_LOCATION_TYPE,
                    temporary_locations,
                ),
            ),
            "pick-up-target": (
                (
                    self.TARGET_TYPE,
                    targets,
                ),
                (
                    self.TARGET_STRUCTURAL_LOCATION_TYPE,
                    target_locations,
                ),
            ),
            "put-down-target": (
                (
                    self.TARGET_TYPE,
                    targets,
                ),
                (
                    self.GOAL_LOCATION_TYPE,
                    goal_locations,
                ),
            ),
            "restore-ground-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.OCCLUDER_STRUCTURAL_LOCATION_TYPE,
                    occluder_locations,
                ),
            ),
            "stack-occluder": (
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
                (
                    self.OCCLUDER_TYPE,
                    occluders,
                ),
            ),
        }

        role_spec = expected_roles.get(
            step.action
        )

        if role_spec is None:
            # Unknown actions should already have been rejected by
            # validate_plan(). Keep this defensive only.
            return None

        for index, (
            expected_type,
            allowed_objects,
        ) in enumerate(
            role_spec,
            start=1,
        ):
            argument = step.args[index - 1]

            if argument not in allowed_objects:
                return (
                    "Invalid argument role: "
                    f"action '{step.action}' argument "
                    f"{index} '{argument}' must be "
                    f"'{expected_type}'."
                )

        return None

    def _apply_remove_stacked_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, support = args

        relation = (
            occ,
            support,
        )

        missing: list[str] = []

        if relation not in state["on"]:
            missing.append(
                f"on({occ},{support})"
            )

        if relation not in state["occludes"]:
            missing.append(
                f"occludes({occ},{support})"
            )

        if occ not in state["clear"]:
            missing.append(
                f"clear({occ})"
            )

        if occ not in state["accessible"]:
            missing.append(
                f"accessible({occ})"
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

        next_state["on"].remove(
            relation
        )
        next_state["occludes"].remove(
            relation
        )
        next_state["clear"].discard(
            occ
        )
        next_state["accessible"].discard(
            occ
        )
        next_state["handempty"] = False

        next_state["holding"].add(
            occ
        )
        next_state["clear"].add(
            support
        )
        next_state["accessible"].add(
            support
        )

        return True, "ok", next_state

    def _apply_remove_ground_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, location, target = args

        at_relation = (
            occ,
            location,
        )

        occlusion_relation = (
            occ,
            target,
        )

        missing: list[str] = []

        if at_relation not in state["at"]:
            missing.append(
                f"at({occ},{location})"
            )

        if (
            occlusion_relation
            not in state["occludes"]
        ):
            missing.append(
                f"occludes({occ},{target})"
            )

        if occ not in state["clear"]:
            missing.append(
                f"clear({occ})"
            )

        if occ not in state["accessible"]:
            missing.append(
                f"accessible({occ})"
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

        next_state["at"].remove(
            at_relation
        )
        next_state["occludes"].remove(
            occlusion_relation
        )
        next_state["clear"].discard(
            occ
        )
        next_state["accessible"].discard(
            occ
        )
        next_state["handempty"] = False

        next_state["holding"].add(
            occ
        )
        next_state["free"].add(
            location
        )
        next_state["accessible"].add(
            target
        )

        return True, "ok", next_state

    def _apply_put_down_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, location = args

        missing: list[str] = []

        if occ not in state["holding"]:
            missing.append(
                f"holding({occ})"
            )

        if location not in state["free"]:
            missing.append(
                f"free({location})"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            occ
        )
        next_state["free"].remove(
            location
        )

        next_state["at"].add(
            (occ, location)
        )
        next_state["clear"].add(
            occ
        )
        next_state["accessible"].add(
            occ
        )
        next_state["handempty"] = True

        return True, "ok", next_state

    def _apply_pick_up_temp_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, location = args

        relation = (
            occ,
            location,
        )

        missing: list[str] = []

        if relation not in state["at"]:
            missing.append(
                f"at({occ},{location})"
            )

        if occ not in state["clear"]:
            missing.append(
                f"clear({occ})"
            )

        if occ not in state["accessible"]:
            missing.append(
                f"accessible({occ})"
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

        next_state["at"].remove(
            relation
        )
        next_state["clear"].discard(
            occ
        )
        next_state["accessible"].discard(
            occ
        )
        next_state["handempty"] = False

        next_state["holding"].add(
            occ
        )
        next_state["free"].add(
            location
        )

        return True, "ok", next_state

    def _apply_pick_up_target(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        target, location = args

        relation = (
            target,
            location,
        )

        missing: list[str] = []

        if relation not in state["at"]:
            missing.append(
                f"at({target},{location})"
            )

        if target not in state["clear"]:
            missing.append(
                f"clear({target})"
            )

        if target not in state["accessible"]:
            missing.append(
                f"accessible({target})"
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

        next_state["at"].remove(
            relation
        )
        next_state["clear"].discard(
            target
        )
        next_state["accessible"].discard(
            target
        )
        next_state["handempty"] = False

        next_state["holding"].add(
            target
        )
        next_state["free"].add(
            location
        )

        return True, "ok", next_state

    def _apply_put_down_target(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        target, location = args

        missing: list[str] = []

        if target not in state["holding"]:
            missing.append(
                f"holding({target})"
            )

        if location not in state["free"]:
            missing.append(
                f"free({location})"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            target
        )
        next_state["free"].remove(
            location
        )

        next_state["at"].add(
            (target, location)
        )
        next_state["clear"].add(
            target
        )
        next_state["accessible"].add(
            target
        )
        next_state["handempty"] = True
        next_state["target_relocated"] = True

        return True, "ok", next_state

    def _apply_restore_ground_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, location = args

        missing: list[str] = []

        if occ not in state["holding"]:
            missing.append(
                f"holding({occ})"
            )

        if location not in state["free"]:
            missing.append(
                f"free({location})"
            )

        if not state["target_relocated"]:
            missing.append(
                "target-relocated"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            occ
        )
        next_state["free"].remove(
            location
        )

        next_state["at"].add(
            (occ, location)
        )
        next_state["clear"].add(
            occ
        )
        next_state["accessible"].add(
            occ
        )
        next_state["handempty"] = True

        # Deliberately does NOT recreate
        # occludes(O1, T1).

        return True, "ok", next_state

    def _apply_stack_occluder(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        occ, support = args

        missing: list[str] = []

        if occ not in state["holding"]:
            missing.append(
                f"holding({occ})"
            )

        if support not in state["clear"]:
            missing.append(
                f"clear({support})"
            )

        if support not in state["accessible"]:
            missing.append(
                f"accessible({support})"
            )

        if not state["target_relocated"]:
            missing.append(
                "target-relocated"
            )

        if missing:
            return (
                False,
                "Missing preconditions: "
                + ", ".join(missing),
                state,
            )

        next_state["holding"].remove(
            occ
        )
        next_state["clear"].discard(
            support
        )
        next_state["accessible"].discard(
            support
        )

        next_state["on"].add(
            (occ, support)
        )
        next_state["occludes"].add(
            (occ, support)
        )
        next_state["clear"].add(
            occ
        )
        next_state["accessible"].add(
            occ
        )
        next_state["handempty"] = True

        return True, "ok", next_state

    def _check_goal(
        self,
        state: dict[str, Any],
        goal_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check positive goal conditions supported by the current
        SceneConfig/PDDL problem representation.

        False zero-arity values are ignored, matching the generic
        PDDL builder. Negative goals are not introduced here.
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
                if (
                    bool(raw_value)
                    and not state["handempty"]
                ):
                    missing.append(
                        "handempty"
                    )

                continue

            if predicate == "target_relocated":
                if (
                    bool(raw_value)
                    and not state[
                        "target_relocated"
                    ]
                ):
                    missing.append(
                        "target-relocated"
                    )

                continue

            if predicate not in state:
                missing.append(
                    f"unsupported-goal({raw_predicate})"
                )
                continue

            if not isinstance(
                raw_value,
                list,
            ):
                missing.append(
                    f"invalid-goal({raw_predicate})"
                )
                continue

            if predicate in {
                "at",
                "on",
                "occludes",
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

            if predicate in {
                "clear",
                "accessible",
                "holding",
                "free",
            }:
                for object_name in raw_value:
                    if object_name not in state[
                        predicate
                    ]:
                        missing.append(
                            f"{raw_predicate}"
                            f"({object_name})"
                        )

                continue

            missing.append(
                f"unsupported-goal({raw_predicate})"
            )

        if missing:
            return (
                False,
                "Missing goal conditions: "
                + ", ".join(missing),
            )

        return (
            True,
            "All goal conditions met.",
        )

    def _copy_state(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert external JSON-style state into mutable set-based state.
        """

        return {
            "at": {
                tuple(relation)
                for relation in state.get(
                    "at",
                    [],
                )
            },
            "on": {
                tuple(relation)
                for relation in state.get(
                    "on",
                    [],
                )
            },
            "clear": set(
                state.get(
                    "clear",
                    [],
                )
            ),
            "occludes": {
                tuple(relation)
                for relation in state.get(
                    "occludes",
                    [],
                )
            },
            "accessible": set(
                state.get(
                    "accessible",
                    [],
                )
            ),
            "holding": set(
                state.get(
                    "holding",
                    [],
                )
            ),
            "handempty": bool(
                state.get(
                    "handempty",
                    False,
                )
            ),
            "free": set(
                state.get(
                    "free",
                    [],
                )
            ),
            "target_relocated": bool(
                state.get(
                    "target_relocated",
                    state.get(
                        "target-relocated",
                        False,
                    ),
                )
            ),
        }

    def _state_summary(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return stable JSON-serializable state data.

        Internal sets are never exposed through VerificationResult.
        """

        return {
            "at": [
                list(relation)
                for relation in sorted(
                    state["at"]
                )
            ],
            "on": [
                list(relation)
                for relation in sorted(
                    state["on"]
                )
            ],
            "clear": sorted(
                state["clear"]
            ),
            "occludes": [
                list(relation)
                for relation in sorted(
                    state["occludes"]
                )
            ],
            "accessible": sorted(
                state["accessible"]
            ),
            "holding": sorted(
                state["holding"]
            ),
            "handempty": state[
                "handempty"
            ],
            "free": sorted(
                state["free"]
            ),
            "target_relocated": state[
                "target_relocated"
            ],
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


Verifier = OcclusionManipulationVerifier