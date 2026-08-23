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


class GearboxVerifier(SymbolicVerifier):
    """
    Symbolic verifier for the Gearbox v1 domain.

    Semantic source of truth:
    - assembled
    - aid-present
    - precedes
    - requires-aid

    Encoding-only metadata such as has-predecessor and
    withdraw-group-* is deliberately not used as semantic authority.

    VAL remains the final formal validation authority.
    """

    PERMANENT_TYPE = "permanent-component"
    TEMPORARY_AID_TYPE = "temporary-aid"

    def __init__(
        self,
        domain: DomainConfig,
    ) -> None:
        if domain.domain_id != "gearbox":
            raise ValueError(
                "GearboxVerifier requires domain 'gearbox', "
                f"but received '{domain.domain_id}'."
            )

        self.domain = domain

    def verify(
        self,
        plan: list[PlanStep],
        scene: SceneConfig,
        verbose: bool = False,
    ) -> VerificationResult:
        """
        Structurally validate and simulate one complete Gearbox plan.
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
                "Gearbox action preconditions/effects:"
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
                scene=scene,
            )
        )

        if not goal_success:
            return VerificationResult(
                success=False,
                message=goal_error,
                final_state=self._state_summary(
                    state
                ),
                failed_step="goal_check",
                error=goal_error,
            )

        return VerificationResult(
            success=True,
            message=(
                "Plan is symbolically valid and all "
                "Gearbox goal conditions are satisfied."
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
        Apply one grounded Gearbox action.
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

        next_state = self._copy_state(
            state
        )

        if step.action == "assemble-basic":
            return self._apply_assemble_basic(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        if step.action == "assemble-after":
            return self._apply_assemble_after(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        if step.action == "assemble-with-aid":
            return self._apply_assemble_with_aid(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        if step.action == "assemble-after-with-aid":
            return self._apply_assemble_after_with_aid(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        if step.action == "insert-aid":
            return self._apply_insert_aid(
                args=step.args,
                state=state,
                next_state=next_state,
            )

        if step.action == "withdraw-aid-after-one":
            return self._apply_withdraw_after_one(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        if step.action == "withdraw-aid-after-two":
            return self._apply_withdraw_after_two(
                args=step.args,
                state=state,
                next_state=next_state,
                scene=scene,
            )

        return (
            False,
            f"Unsupported Gearbox action: {step.action}",
            state,
        )

    def _apply_assemble_basic(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        component = args[0]

        predecessors = self._predecessors_of(
            scene,
            component,
        )

        aids = self._required_aids_of(
            scene,
            component,
        )

        missing: list[str] = []

        if component in state["assembled"]:
            missing.append(
                f"not assembled({component})"
            )

        if predecessors:
            missing.append(
                "component has predecessor(s): "
                + ", ".join(
                    sorted(predecessors)
                )
            )

        if aids:
            missing.append(
                "component requires aid(s): "
                + ", ".join(
                    sorted(aids)
                )
            )

        if missing:
            return (
                False,
                "Invalid assemble-basic: "
                + "; ".join(missing),
                state,
            )

        next_state["assembled"].add(
            component
        )

        return True, "ok", next_state

    def _apply_assemble_after(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        component, predecessor = args

        predecessors = self._predecessors_of(
            scene,
            component,
        )

        aids = self._required_aids_of(
            scene,
            component,
        )

        missing: list[str] = []

        if component in state["assembled"]:
            missing.append(
                f"not assembled({component})"
            )

        if predecessors != {predecessor}:
            missing.append(
                "declared predecessor set is "
                f"{sorted(predecessors)}, not "
                f"['{predecessor}']"
            )

        if aids:
            missing.append(
                "component has an aid requirement"
            )

        if predecessor not in state["assembled"]:
            missing.append(
                f"assembled({predecessor})"
            )

        if missing:
            return (
                False,
                "Invalid assemble-after: "
                + "; ".join(missing),
                state,
            )

        next_state["assembled"].add(
            component
        )

        return True, "ok", next_state

    def _apply_assemble_with_aid(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        component, aid = args

        predecessors = self._predecessors_of(
            scene,
            component,
        )

        aids = self._required_aids_of(
            scene,
            component,
        )

        missing: list[str] = []

        if component in state["assembled"]:
            missing.append(
                f"not assembled({component})"
            )

        if predecessors:
            missing.append(
                "component has a predecessor requirement"
            )

        if aids != {aid}:
            missing.append(
                "declared aid set is "
                f"{sorted(aids)}, not ['{aid}']"
            )

        if aid not in state["aid_present"]:
            missing.append(
                f"aid-present({aid})"
            )

        if missing:
            return (
                False,
                "Invalid assemble-with-aid: "
                + "; ".join(missing),
                state,
            )

        next_state["assembled"].add(
            component
        )

        return True, "ok", next_state

    def _apply_assemble_after_with_aid(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        component, predecessor, aid = args

        predecessors = self._predecessors_of(
            scene,
            component,
        )

        aids = self._required_aids_of(
            scene,
            component,
        )

        missing: list[str] = []

        if component in state["assembled"]:
            missing.append(
                f"not assembled({component})"
            )

        if predecessors != {predecessor}:
            missing.append(
                "declared predecessor set is "
                f"{sorted(predecessors)}, not "
                f"['{predecessor}']"
            )

        if aids != {aid}:
            missing.append(
                "declared aid set is "
                f"{sorted(aids)}, not ['{aid}']"
            )

        if predecessor not in state["assembled"]:
            missing.append(
                f"assembled({predecessor})"
            )

        if aid not in state["aid_present"]:
            missing.append(
                f"aid-present({aid})"
            )

        if missing:
            return (
                False,
                "Invalid assemble-after-with-aid: "
                + "; ".join(missing),
                state,
            )

        next_state["assembled"].add(
            component
        )

        return True, "ok", next_state

    def _apply_insert_aid(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        aid = args[0]

        if aid in state["aid_present"]:
            return (
                False,
                f"Missing precondition: not aid-present({aid})",
                state,
            )

        next_state["aid_present"].add(
            aid
        )

        return True, "ok", next_state

    def _apply_withdraw_after_one(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        aid, component = args

        dependents = self._dependents_of_aid(
            scene,
            aid,
        )

        missing: list[str] = []

        if aid not in state["aid_present"]:
            missing.append(
                f"aid-present({aid})"
            )

        if dependents != {component}:
            missing.append(
                "declared dependent set is "
                f"{sorted(dependents)}, not "
                f"['{component}']"
            )

        if component not in state["assembled"]:
            missing.append(
                f"assembled({component})"
            )

        if missing:
            return (
                False,
                "Invalid withdraw-aid-after-one: "
                + "; ".join(missing),
                state,
            )

        next_state["aid_present"].remove(
            aid
        )

        return True, "ok", next_state

    def _apply_withdraw_after_two(
        self,
        args: tuple[str, ...],
        state: dict[str, Any],
        next_state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str, dict[str, Any]]:
        aid, component_1, component_2 = (
            args
        )

        provided_dependents = {
            component_1,
            component_2,
        }

        dependents = self._dependents_of_aid(
            scene,
            aid,
        )

        missing: list[str] = []

        if aid not in state["aid_present"]:
            missing.append(
                f"aid-present({aid})"
            )

        if (
            len(provided_dependents) != 2
            or dependents != provided_dependents
        ):
            missing.append(
                "declared dependent set is "
                f"{sorted(dependents)}, not "
                f"{sorted(provided_dependents)}"
            )

        for component in sorted(
            provided_dependents
        ):
            if component not in state[
                "assembled"
            ]:
                missing.append(
                    f"assembled({component})"
                )

        if missing:
            return (
                False,
                "Invalid withdraw-aid-after-two: "
                + "; ".join(missing),
                state,
            )

        next_state["aid_present"].remove(
            aid
        )

        return True, "ok", next_state

    def _validate_action_roles(
        self,
        step: PlanStep,
        scene: SceneConfig,
    ) -> str | None:
        permanents = set(
            scene.object_types.get(
                self.PERMANENT_TYPE,
                [],
            )
        )

        aids = set(
            scene.object_types.get(
                self.TEMPORARY_AID_TYPE,
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
            "assemble-basic": (
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
            ),
            "assemble-after": (
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
            ),
            "assemble-with-aid": (
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
                (
                    self.TEMPORARY_AID_TYPE,
                    aids,
                ),
            ),
            "assemble-after-with-aid": (
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
                (
                    self.TEMPORARY_AID_TYPE,
                    aids,
                ),
            ),
            "insert-aid": (
                (
                    self.TEMPORARY_AID_TYPE,
                    aids,
                ),
            ),
            "withdraw-aid-after-one": (
                (
                    self.TEMPORARY_AID_TYPE,
                    aids,
                ),
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
            ),
            "withdraw-aid-after-two": (
                (
                    self.TEMPORARY_AID_TYPE,
                    aids,
                ),
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
                (
                    self.PERMANENT_TYPE,
                    permanents,
                ),
            ),
        }

        role_spec = expected_roles.get(
            step.action
        )

        if role_spec is None:
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

    def _check_goal(
        self,
        state: dict[str, Any],
        scene: SceneConfig,
    ) -> tuple[bool, str]:
        missing: list[str] = []

        required_assembled = set(
            scene.goal_state.get(
                "assembled",
                [],
            )
        )

        for component in sorted(
            required_assembled
        ):
            if component not in state[
                "assembled"
            ]:
                missing.append(
                    f"assembled({component})"
                )

        forbidden_aids = set(
            scene.negative_goal_state.get(
                "aid_present",
                scene.negative_goal_state.get(
                    "aid-present",
                    [],
                ),
            )
        )

        for aid in sorted(
            forbidden_aids
        ):
            if aid in state["aid_present"]:
                missing.append(
                    f"not aid-present({aid})"
                )

        if missing:
            return (
                False,
                "Missing goal conditions: "
                + ", ".join(missing),
            )

        return (
            True,
            "All Gearbox goal conditions met.",
        )

    def _predecessors_of(
        self,
        scene: SceneConfig,
        component: str,
    ) -> set[str]:
        return {
            predecessor
            for predecessor, target
            in self._precedes_relations(
                scene
            )
            if target == component
        }

    def _required_aids_of(
        self,
        scene: SceneConfig,
        component: str,
    ) -> set[str]:
        return {
            aid
            for target, aid
            in self._requires_aid_relations(
                scene
            )
            if target == component
        }

    def _dependents_of_aid(
        self,
        scene: SceneConfig,
        aid: str,
    ) -> set[str]:
        return {
            component
            for component, required_aid
            in self._requires_aid_relations(
                scene
            )
            if required_aid == aid
        }

    def _precedes_relations(
        self,
        scene: SceneConfig,
    ) -> set[tuple[str, str]]:
        return {
            tuple(relation)
            for relation in scene.initial_state.get(
                "precedes",
                [],
            )
        }

    def _requires_aid_relations(
        self,
        scene: SceneConfig,
    ) -> set[tuple[str, str]]:
        raw_relations = (
            scene.initial_state.get(
                "requires_aid",
                scene.initial_state.get(
                    "requires-aid",
                    [],
                ),
            )
        )

        return {
            tuple(relation)
            for relation in raw_relations
        }

    def _copy_state(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "assembled": set(
                state.get(
                    "assembled",
                    [],
                )
            ),
            "aid_present": set(
                state.get(
                    "aid_present",
                    state.get(
                        "aid-present",
                        [],
                    ),
                )
            ),
        }

    def _state_summary(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "assembled": sorted(
                state["assembled"]
            ),
            "aid_present": sorted(
                state["aid_present"]
            ),
        }


Verifier = GearboxVerifier