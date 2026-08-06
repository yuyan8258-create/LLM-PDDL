from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

from src.domain_adapters.base import DomainAdapter
from src.scene_config import SceneConfig


class BlockBuildingAdapter(DomainAdapter):
    """
    Adapter for ordinary BlocksWorld and bridge-style block building.

    Common pipeline code should use this adapter instead of containing
    block-specific scene preparation, prompt wording, or support-slot
    assumptions.
    """

    REQUIRED_PREDICATES = {
        "ontable",
        "on",
        "on-bridge",
        "clear",
        "holding",
        "handempty",
        "left-free",
        "right-free",
    }

    BLOCK_STATE_FIELDS = {
        "ontable",
        "on",
        "on_bridge",
        "on-bridge",
        "clear",
        "holding",
        "handempty",
        "left_free",
        "left-free",
        "right_free",
        "right-free",
    }

    def validate_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate one block-building scene before preparation or prompt
        construction.
        """

        self.validate_domain_link(scene)

        missing_predicates = sorted(
            self.REQUIRED_PREDICATES
            - set(self.domain.predicate_arities)
        )

        if missing_predicates:
            raise ValueError(
                f"Block domain '{self.domain.domain_id}' is missing "
                f"required predicate(s): "
                f"{', '.join(missing_predicates)}"
            )

        if not scene.objects:
            raise ValueError(
                f"Block scene '{scene.scene_id}' has no objects."
            )

        if len(scene.objects) != len(set(scene.objects)):
            raise ValueError(
                f"Block scene '{scene.scene_id}' contains duplicate "
                f"object names."
            )

        if not scene.goal_state:
            raise ValueError(
                f"Block scene '{scene.scene_id}' has no goal state."
            )

        self._validate_state_section(
            scene=scene,
            state=scene.initial_state,
            section_name="initial_state",
        )

        self._validate_state_section(
            scene=scene,
            state=scene.goal_state,
            section_name="goal_state",
        )

    def prepare_scene(
        self,
        scene: SceneConfig,
    ) -> SceneConfig:
        """
        Return a prepared copy of one block-building scene.

        The original SceneConfig and the original nested dictionaries
        are not modified.

        Bridge scenes receive left_free and right_free defaults only
        when those fields are absent from the JSON. Explicit values,
        including explicit empty lists, are preserved.
        """

        self.validate_scene(scene)

        initial_state = copy.deepcopy(
            scene.initial_state
        )

        goal_state = copy.deepcopy(
            scene.goal_state
        )

        # Supply stable containers used by the block domain and the
        # future block symbolic verifier.
        initial_state.setdefault("ontable", [])
        initial_state.setdefault("on", [])
        initial_state.setdefault("on_bridge", [])
        initial_state.setdefault("clear", [])
        initial_state.setdefault("holding", [])
        initial_state.setdefault("handempty", True)

        if self._uses_bridge_structure(scene):
            # This reproduces the support-slot assumption used by the
            # original bridge-construction prototype.
            initial_state.setdefault(
                "left_free",
                list(scene.objects),
            )

            initial_state.setdefault(
                "right_free",
                list(scene.objects),
            )

        prepared_scene = replace(
            scene,
            initial_state=initial_state,
            goal_state=goal_state,
            scene_data=copy.deepcopy(scene.scene_data),
        )

        self.validate_scene(prepared_scene)

        return prepared_scene

    def build_plan_prompt(
        self,
        scene: SceneConfig,
        feedback: str | None = None,
    ) -> str:
        """
        Build a scene-specific block-planning prompt.

        Object names, initial state, goal state, and planning guidance
        come from SceneConfig instead of being hard-coded for Scene 02.
        """

        prepared_scene = self.prepare_scene(scene)

        action_lines = [
            f"- {action_name}: "
            f"{arity} argument(s)"
            for action_name, arity
            in sorted(self.domain.action_arities.items())
        ]

        planning_guidance = (
            prepared_scene.planning_guidance.strip()
            if prepared_scene.planning_guidance
            else (
                "Construct a valid plan from the initial state to the "
                "goal state. Respect every action precondition and "
                "effect."
            )
        )

        feedback_section = ""

        if feedback and feedback.strip():
            feedback_section = f"""

PREVIOUS VERIFICATION FEEDBACK:
{feedback.strip()}

Return a repaired complete plan, not only the corrected action.
"""

        initial_state_text = json.dumps(
            prepared_scene.initial_state,
            indent=2,
            ensure_ascii=False,
        )

        goal_state_text = json.dumps(
            prepared_scene.goal_state,
            indent=2,
            ensure_ascii=False,
        )

        return f"""
You are a symbolic task planner for the block_building PDDL domain.

SCENE ID:
{prepared_scene.scene_id}

SCENE NAME:
{prepared_scene.scene_name}

DESCRIPTION:
{prepared_scene.description}

DIFFICULTY:
{prepared_scene.difficulty}

OBJECTS:
{", ".join(prepared_scene.objects)}

INITIAL STATE:
{initial_state_text}

GOAL STATE:
{goal_state_text}

AVAILABLE ACTIONS:
{chr(10).join(action_lines)}

BLOCK-DOMAIN RULES:
- pick-up removes one clear object from the table and makes the robot hold it.
- put-down places the held object on the table.
- stack places one held object on one clear supporting object.
- unstack removes one clear object from another object.
- stack-bridge places one held object across a left support and a right support.
- stack-bridge requires right-free on the left support and left-free on the right support.
- unstack-bridge removes a clear bridge object and restores its support slots.
- The robot can hold at most one object.
- Every action must satisfy its PDDL preconditions.
- The final state must satisfy every listed goal condition.

PLANNING GUIDANCE:
{planning_guidance}
{feedback_section}
OUTPUT REQUIREMENTS:
- Output only one JSON array.
- Do not output markdown.
- Do not output explanations.
- Each array item must contain exactly:
  "action": an available action name
  "args": a list of object names
- Use only the objects listed in this scene.
- Return the complete plan from the initial state to the goal state.

OUTPUT EXAMPLE:
[
  {{"action": "pick-up", "args": ["object_name"]}},
  {{"action": "stack", "args": ["object_name", "support_name"]}}
]
""".strip()

    def build_feedback(
        self,
        scene: SceneConfig,
        verifier_feedback: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Add block-domain repair guidance while preserving the original
        verifier message.
        """

        base_feedback = super().build_feedback(
            scene=scene,
            verifier_feedback=verifier_feedback,
            context=context,
        )

        lower_feedback = base_feedback.lower()
        guidance: list[str] = []

        if "handempty" in lower_feedback:
            guidance.append(
                "The robot may already be holding an object. Place or "
                "stack the held object before using another pick-up or "
                "unstack action."
            )

        if "holding" in lower_feedback:
            guidance.append(
                "An object can be stacked or put down only while that "
                "same object is being held."
            )

        if (
            "left-free" in lower_feedback
            or "right-free" in lower_feedback
        ):
            guidance.append(
                "A bridge placement consumes one support slot on each "
                "support. Check the build order and avoid reusing an "
                "already occupied support slot."
            )

        if "clear" in lower_feedback:
            guidance.append(
                "An object must be clear before it can be picked up or "
                "removed from another support."
            )

        if not guidance:
            guidance.append(
                "Recheck the failed action against the block-domain "
                "preconditions and return a complete repaired plan."
            )

        return (
            f"{base_feedback}\n\n"
            "BLOCK-DOMAIN REPAIR GUIDANCE:\n"
            + "\n".join(
                f"- {item}"
                for item in guidance
            )
        )

    def _uses_bridge_structure(
        self,
        scene: SceneConfig,
    ) -> bool:
        """
        Return True when the initial state or goal state contains at
        least one non-empty on-bridge relation.
        """

        for state in (
            scene.initial_state,
            scene.goal_state,
        ):
            for key in (
                "on_bridge",
                "on-bridge",
            ):
                relations = state.get(key)

                if relations:
                    return True

        return False

    def _validate_state_section(
        self,
        scene: SceneConfig,
        state: dict[str, Any],
        section_name: str,
    ) -> None:
        """
        Validate block-state field names, arities, booleans, object
        references, and duplicate relations.
        """

        if not isinstance(state, dict):
            raise ValueError(
                f"Block scene '{scene.scene_id}' "
                f"{section_name} must be a dictionary."
            )

        declared_objects = set(scene.objects)

        for raw_field_name, raw_value in state.items():
            field_name = raw_field_name.strip()
            predicate_name = field_name.replace(
                "_",
                "-",
            )

            if predicate_name not in (
                self.domain.predicate_arities
            ):
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name} contains unknown predicate "
                    f"'{raw_field_name}'."
                )

            arity = self.domain.predicate_arities[
                predicate_name
            ]

            if arity == 0:
                if not isinstance(raw_value, bool):
                    raise ValueError(
                        f"Block scene '{scene.scene_id}' "
                        f"{section_name}.{raw_field_name} must be "
                        f"true or false."
                    )

                continue

            if not isinstance(raw_value, list):
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{raw_field_name} must be a list."
                )

            if arity == 1:
                self._validate_unary_values(
                    scene=scene,
                    field_name=raw_field_name,
                    values=raw_value,
                    declared_objects=declared_objects,
                    section_name=section_name,
                )

                continue

            self._validate_relations(
                scene=scene,
                field_name=raw_field_name,
                relations=raw_value,
                expected_arity=arity,
                declared_objects=declared_objects,
                section_name=section_name,
            )

    def _validate_unary_values(
        self,
        scene: SceneConfig,
        field_name: str,
        values: list[Any],
        declared_objects: set[str],
        section_name: str,
    ) -> None:
        """
        Validate unary predicate values such as clear and ontable.
        """

        normalised_values: list[str] = []

        for raw_object in values:
            if not isinstance(raw_object, str):
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{field_name} contains a "
                    f"non-string object: {raw_object!r}"
                )

            object_name = raw_object.strip()

            if object_name not in declared_objects:
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{field_name} references "
                    f"undeclared object '{object_name}'."
                )

            normalised_values.append(object_name)

        if len(normalised_values) != len(
            set(normalised_values)
        ):
            raise ValueError(
                f"Block scene '{scene.scene_id}' "
                f"{section_name}.{field_name} contains duplicate "
                f"objects."
            )

    def _validate_relations(
        self,
        scene: SceneConfig,
        field_name: str,
        relations: list[Any],
        expected_arity: int,
        declared_objects: set[str],
        section_name: str,
    ) -> None:
        """
        Validate binary and higher-arity block relations.
        """

        normalised_relations: list[
            tuple[str, ...]
        ] = []

        for raw_relation in relations:
            if not isinstance(
                raw_relation,
                (list, tuple),
            ):
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{field_name} contains an "
                    f"invalid relation: {raw_relation!r}"
                )

            if len(raw_relation) != expected_arity:
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{field_name} requires "
                    f"{expected_arity} arguments, but received "
                    f"{len(raw_relation)}: {raw_relation!r}"
                )

            relation: list[str] = []

            for raw_object in raw_relation:
                if not isinstance(raw_object, str):
                    raise ValueError(
                        f"Block scene '{scene.scene_id}' "
                        f"{section_name}.{field_name} contains a "
                        f"non-string object: {raw_object!r}"
                    )

                object_name = raw_object.strip()

                if object_name not in declared_objects:
                    raise ValueError(
                        f"Block scene '{scene.scene_id}' "
                        f"{section_name}.{field_name} references "
                        f"undeclared object '{object_name}'."
                    )

                relation.append(object_name)

            if len(set(relation)) != len(relation):
                raise ValueError(
                    f"Block scene '{scene.scene_id}' "
                    f"{section_name}.{field_name} contains a "
                    f"self-referential relation: {raw_relation!r}"
                )

            normalised_relations.append(
                tuple(relation)
            )

        if len(normalised_relations) != len(
            set(normalised_relations)
        ):
            raise ValueError(
                f"Block scene '{scene.scene_id}' "
                f"{section_name}.{field_name} contains duplicate "
                f"relations."
            )


# The dynamic adapter loader looks for this common exported name.
Adapter = BlockBuildingAdapter