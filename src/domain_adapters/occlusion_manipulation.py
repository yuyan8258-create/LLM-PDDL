from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

from src.domain_adapters.base import DomainAdapter
from src.pddl_problem_builder import (
    resolve_predicate_name,
    state_section_to_pddl_atoms,
)
from src.scene_config import SceneConfig


class OcclusionManipulationAdapter(DomainAdapter):
    """
    Adapter for the Lego-like structural occlusion benchmark.

    Version 1 responsibilities:
    - static scene/domain validation
    - immutable scene preparation
    - Occlusion-specific planning prompt construction

    DomainConfig remains the only source of truth for:
    - predicate names
    - predicate arities
    - action names
    - action arities

    This adapter does not implement:
    - dynamic state transition verification
    - accessibility inference
    - occlusion inference
    - action legality checking
    """

    TARGET_TYPE = "target-brick"
    OCCLUDER_TYPE = "occluder-brick"

    TARGET_STRUCTURAL_LOCATION_TYPE = (
        "target-structural-location"
    )

    OCCLUDER_STRUCTURAL_LOCATION_TYPE = (
        "occluder-structural-location"
    )

    TEMPORARY_LOCATION_TYPE = (
        "temporary-location"
    )

    GOAL_LOCATION_TYPE = (
        "goal-location"
    )

    def validate_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate static Occlusion semantic roles.

        Generic schema validation is delegated to existing helpers.
        """

        self.validate_domain_link(scene)

        if not scene.goal_state:
            raise ValueError(
                f"Occlusion scene '{scene.scene_id}' "
                "has no goal state."
            )

        self._validate_object_roles(scene)

        # DomainConfig remains the source of truth for
        # predicate names and arities.
        state_section_to_pddl_atoms(
            state_section=scene.initial_state,
            scene=scene,
            domain=self.domain,
            section_name="initial_state",
        )

        state_section_to_pddl_atoms(
            state_section=scene.goal_state,
            scene=scene,
            domain=self.domain,
            section_name="goal_state",
        )

        self._validate_state_roles(
            scene,
            scene.initial_state,
            "initial_state",
        )

        self._validate_state_roles(
            scene,
            scene.goal_state,
            "goal_state",
        )

    def prepare_scene(
        self,
        scene: SceneConfig,
    ) -> SceneConfig:
        """
        Return an immutable prepared copy.

        No symbolic state is inferred.
        """

        self.validate_scene(scene)

        prepared_scene = replace(
            scene,
            initial_state=copy.deepcopy(
                scene.initial_state
            ),
            goal_state=copy.deepcopy(
                scene.goal_state
            ),
            object_types=copy.deepcopy(
                scene.object_types
            ),
            scene_data=copy.deepcopy(
                scene.scene_data
            ),
        )

        self.validate_scene(prepared_scene)

        return prepared_scene

    def build_plan_prompt(
        self,
        scene: SceneConfig,
        feedback: str | None = None,
    ) -> str:
        """
        Build Occlusion planning prompt.

        AVAILABLE ACTIONS:
            generated from DomainConfig

        ACTION ARGUMENT GUIDANCE:
            prompt-only explanation of argument ordering

        It is not an action legality schema.
        """

        prepared_scene = self.prepare_scene(scene)

        action_lines = [
            f"- {name}: {arity} argument(s)"
            for name, arity
            in sorted(
                self.domain.action_arities.items()
            )
        ]

        argument_guidance_lines = (
            self._build_action_argument_guidance()
        )

        object_lines = [
            f"- {obj_type}: "
            f"{', '.join(objects)}"
            for obj_type, objects
            in prepared_scene.object_types.items()
        ]

        feedback_section = ""

        if feedback and feedback.strip():
            feedback_section = f"""

PREVIOUS VERIFICATION FEEDBACK:
{feedback.strip()}

Return a repaired complete plan, not only the corrected action.
"""

        return f"""
You are a symbolic task planner for the
occlusion_manipulation PDDL domain.

SCENE ID:
{prepared_scene.scene_id}

SCENE NAME:
{prepared_scene.scene_name}

DESCRIPTION:
{prepared_scene.description}

DIFFICULTY:
{prepared_scene.difficulty}

TYPED OBJECTS:
{chr(10).join(object_lines)}

INITIAL STATE:
{json.dumps(
    prepared_scene.initial_state,
    indent=2,
    ensure_ascii=False,
)}

GOAL STATE:
{json.dumps(
    prepared_scene.goal_state,
    indent=2,
    ensure_ascii=False,
)}

AVAILABLE ACTIONS:
{chr(10).join(action_lines)}

ACTION ARGUMENT GUIDANCE:
{chr(10).join(argument_guidance_lines)}

The AVAILABLE ACTIONS section is authoritative for legal action
names and argument counts.

ACTION ARGUMENT GUIDANCE only explains the intended argument order
for frozen Occlusion-v1 actions. It is not an action legality schema.

OCCLUSION-BENCHMARK RULES:
- The task models a Lego-like structure containing one target brick
  and removable occluder bricks.
- occludes(A,B) represents an immediate active occlusion relation,
  not transitive occlusion.
- For stacked occluders, on(A,B) together with occlusion relations
  represent benchmark dependency abstractions rather than full
  physical simulation.
- Stacked occluder layers must be cleared in dependency order.
- The front/ground occluder reveals the target.
- Removed occluders use temporary locations during clearing.
- Target relocation must happen before structural restoration.
- Ground restoration does not recreate the old target occlusion.
- Do not invent generic pick-up or put-down actions.

{feedback_section}

OUTPUT REQUIREMENTS:
- Output only one JSON array.
- Do not output markdown.
- Do not output explanations.
- Each item must contain:
  "action"
  "args"
- Respect action count and argument guidance.
- Use only declared objects.
- Return the complete plan.
""".strip()

    def _build_action_argument_guidance(
        self,
    ) -> list[str]:
        """
        Prompt-only argument ordering guidance.

        This is NOT a legality schema.
        """

        action_argument_guidance = {
            "remove-stacked-occluder": (
                "(occluder, support_occluder)"
            ),

            "remove-ground-occluder": (
                "(occluder, "
                "occluder_structural_location, target)"
            ),

            "put-down-occluder": (
                "(occluder, temporary_location)"
            ),

            "pick-up-temp-occluder": (
                "(occluder, temporary_location)"
            ),

            "pick-up-target": (
                "(target, target_structural_location)"
            ),

            "put-down-target": (
                "(target, goal_location)"
            ),

            "restore-ground-occluder": (
                "(occluder, "
                "occluder_structural_location)"
            ),

            "stack-occluder": (
                "(occluder, support_occluder)"
            ),
        }

        lines = []

        for action_name in sorted(
            self.domain.action_arities
        ):
            guidance = (
                action_argument_guidance.get(
                    action_name,
                    "(argument order not documented)",
                )
            )

            lines.append(
                f"- {action_name}: {guidance}"
            )

        return lines

    def _validate_object_roles(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate Occlusion-specific typed object roles.

        SceneConfig is responsible for generic object structure.
        This method only checks domain semantic requirements.
        """

        targets = self._objects_of_type(
            scene,
            self.TARGET_TYPE,
        )

        if len(targets) != 1:
            raise ValueError(
                f"Occlusion scene '{scene.scene_id}' "
                "must contain exactly one target-brick."
            )

        occluders = self._objects_of_type(
            scene,
            self.OCCLUDER_TYPE,
        )

        if not occluders:
            raise ValueError(
                f"Occlusion scene '{scene.scene_id}' "
                "must contain at least one occluder-brick."
            )

        required_location_types = [
            self.TARGET_STRUCTURAL_LOCATION_TYPE,
            self.OCCLUDER_STRUCTURAL_LOCATION_TYPE,
            self.TEMPORARY_LOCATION_TYPE,
            self.GOAL_LOCATION_TYPE,
        ]

        for location_type in required_location_types:
            if not self._objects_of_type(
                scene,
                location_type,
            ):
                raise ValueError(
                    f"Occlusion scene '{scene.scene_id}' "
                    f"requires location type "
                    f"'{location_type}'."
                )


    def _validate_state_roles(
        self,
        scene: SceneConfig,
        state: dict[str, Any],
        section_name: str,
    ) -> None:
        """
        Validate static Occlusion predicate argument roles.

        This does NOT verify:
        - reachability
        - action effects
        - state transition correctness
        """

        targets = set(
            self._objects_of_type(
                scene,
                self.TARGET_TYPE,
            )
        )

        occluders = set(
            self._objects_of_type(
                scene,
                self.OCCLUDER_TYPE,
            )
        )

        bricks = targets | occluders

        target_locations = set(
            self._objects_of_type(
                scene,
                self.TARGET_STRUCTURAL_LOCATION_TYPE,
            )
        )

        occluder_locations = set(
            self._objects_of_type(
                scene,
                self.OCCLUDER_STRUCTURAL_LOCATION_TYPE,
            )
        )

        temporary_locations = set(
            self._objects_of_type(
                scene,
                self.TEMPORARY_LOCATION_TYPE,
            )
        )

        goal_locations = set(
            self._objects_of_type(
                scene,
                self.GOAL_LOCATION_TYPE,
            )
        )

        locations = (
            target_locations
            | occluder_locations
            | temporary_locations
            | goal_locations
        )


        for raw_name, raw_value in state.items():

            predicate = resolve_predicate_name(
                state_key=raw_name,
                domain=self.domain,
            )


            if predicate == "at":

                for relation in raw_value:

                    brick, location = relation

                    if brick not in bricks:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "first argument must be brick",
                        )

                    if location not in locations:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "second argument must be location",
                        )


                    if (
                        brick in targets
                        and location not in (
                            target_locations
                            | goal_locations
                        )
                    ):
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "target can only be in target "
                            "structural location or goal location",
                        )


                    if (
                        brick in occluders
                        and location not in (
                            occluder_locations
                            | temporary_locations
                        )
                    ):
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "occluder can only be in "
                            "structural or temporary location",
                        )


            elif predicate == "on":

                for relation in raw_value:

                    upper, lower = relation

                    if (
                        upper not in occluders
                        or lower not in occluders
                    ):
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "both arguments must be "
                            "occluder-brick",
                        )


            elif predicate == "occludes":

                for relation in raw_value:

                    occ, blocked = relation

                    if occ not in occluders:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "first argument must be "
                            "occluder-brick",
                        )

                    if blocked not in bricks:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            relation,
                            "second argument must be brick",
                        )


            elif predicate in {
                "clear",
                "accessible",
                "holding",
            }:

                for obj in raw_value:

                    if obj not in bricks:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            [obj],
                            "argument must be brick",
                        )


            elif predicate == "free":

                for location in raw_value:

                    if location not in locations:
                        self._raise_role_error(
                            scene,
                            section_name,
                            predicate,
                            [location],
                            "argument must be location",
                        )

            # handempty and target-relocated are zero-arity
            # predicates. Their schema validation is already handled
            # by state_section_to_pddl_atoms().


    def _objects_of_type(
        self,
        scene: SceneConfig,
        object_type: str,
    ) -> list[str]:
        """
        Return typed objects without modifying the scene.
        """

        return list(
            scene.object_types.get(
                object_type,
                [],
            )
        )


    def _raise_role_error(
        self,
        scene: SceneConfig,
        section_name: str,
        predicate: str,
        relation: Any,
        requirement: str,
    ) -> None:

        raise ValueError(
            f"Occlusion scene '{scene.scene_id}' "
            f"{section_name}.{predicate} invalid role "
            f"for {relation}: {requirement}"
        )


# Dynamic adapter loader entry point.
Adapter = OcclusionManipulationAdapter