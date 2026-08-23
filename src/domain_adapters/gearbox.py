from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

from src.domain_adapters.base import DomainAdapter
from src.pddl_problem_builder import (
    state_section_to_pddl_atoms,
)
from src.scene_config import SceneConfig


class GearboxAdapter(DomainAdapter):
    """
    Adapter for the Gearbox v1 symbolic assembly benchmark.

    Responsibilities:
    - validate Gearbox-specific object types and semantic relations;
    - preserve the original scene as the semantic source of truth;
    - derive quantifier-free encoding metadata in a prepared copy;
    - build the Gearbox-specific LLM planning prompt.

    Dynamic plan verification belongs to src.verifiers.gearbox.
    """

    PERMANENT_TYPE = "permanent-component"
    TEMPORARY_AID_TYPE = "temporary-aid"

    REQUIRED_PREDICATES = {
        "assembled",
        "aid-present",
        "precedes",
        "requires-aid",
        "has-predecessor",
        "has-aid-requirement",
        "withdraw-group-1",
        "withdraw-group-2",
    }

    def validate_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate static Gearbox-v1 scene semantics.
        """

        self.validate_domain_link(scene)

        missing_predicates = sorted(
            self.REQUIRED_PREDICATES
            - set(self.domain.predicate_arities)
        )

        if missing_predicates:
            raise ValueError(
                f"Gearbox domain '{self.domain.domain_id}' is missing "
                f"required predicate(s): "
                f"{', '.join(missing_predicates)}"
            )

        permanents = self._objects_of_type(
            scene,
            self.PERMANENT_TYPE,
        )

        aids = self._objects_of_type(
            scene,
            self.TEMPORARY_AID_TYPE,
        )

        if not permanents:
            raise ValueError(
                f"Gearbox scene '{scene.scene_id}' must contain "
                "at least one permanent-component."
            )

        # Generic predicate-name, arity, and object-reference checks.
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

        state_section_to_pddl_atoms(
            state_section=scene.negative_goal_state,
            scene=scene,
            domain=self.domain,
            section_name="negative_goal_state",
        )

        self._validate_semantic_relations(
            scene=scene,
            permanents=set(permanents),
            aids=set(aids),
        )

    def prepare_scene(
        self,
        scene: SceneConfig,
    ) -> SceneConfig:
        """
        Return an immutable prepared scene with encoding-only metadata.

        The original SceneConfig is not modified.
        """

        self.validate_scene(scene)

        initial_state = copy.deepcopy(
            scene.initial_state
        )

        goal_state = copy.deepcopy(
            scene.goal_state
        )

        negative_goal_state = copy.deepcopy(
            scene.negative_goal_state
        )

        precedes = self._read_relations(
            initial_state,
            "precedes",
        )

        requires_aid = self._read_relations(
            initial_state,
            "requires_aid",
            fallback_key="requires-aid",
        )

        predecessor_targets = sorted({
            component
            for _, component in precedes
        })

        aid_required_components = sorted({
            component
            for component, _ in requires_aid
        })

        initial_state[
            "has_predecessor"
        ] = predecessor_targets

        initial_state[
            "has_aid_requirement"
        ] = aid_required_components

        dependents_by_aid: dict[
            str,
            list[str],
        ] = {}

        for component, aid in requires_aid:
            dependents_by_aid.setdefault(
                aid,
                [],
            ).append(component)

        withdraw_group_1: list[
            list[str]
        ] = []

        withdraw_group_2: list[
            list[str]
        ] = []

        for aid, dependents in sorted(
            dependents_by_aid.items()
        ):
            canonical_dependents = sorted(
                set(dependents)
            )

            if len(canonical_dependents) == 1:
                withdraw_group_1.append([
                    aid,
                    canonical_dependents[0],
                ])

            elif len(canonical_dependents) == 2:
                withdraw_group_2.append([
                    aid,
                    canonical_dependents[0],
                    canonical_dependents[1],
                ])

            else:
                raise ValueError(
                    f"Unsupported Gearbox-v1 structure in scene "
                    f"'{scene.scene_id}': temporary aid '{aid}' "
                    f"has {len(canonical_dependents)} dependent "
                    "components; the validated quantifier-free "
                    "encoding supports at most 2."
                )

        initial_state[
            "withdraw_group_1"
        ] = withdraw_group_1

        initial_state[
            "withdraw_group_2"
        ] = withdraw_group_2

        prepared_scene = replace(
            scene,
            initial_state=initial_state,
            goal_state=goal_state,
            negative_goal_state=(
                negative_goal_state
            ),
            object_types=copy.deepcopy(
                scene.object_types
            ),
            scene_data=copy.deepcopy(
                scene.scene_data
            ),
        )

        # Validate the completed planner-facing representation.
        self._validate_prepared_scene(
            prepared_scene
        )

        return prepared_scene

    def build_plan_prompt(
        self,
        scene: SceneConfig,
        feedback: str | None = None,
    ) -> str:
        """
        Build the Gearbox-specific LLM planning prompt.
        """

        prepared_scene = self.prepare_scene(
            scene
        )

        action_lines = [
            f"- {name}: {arity} argument(s)"
            for name, arity
            in sorted(
                self.domain.action_arities.items()
            )
        ]

        argument_guidance = [
            "- assemble-basic: (component)",
            "- assemble-after: (component, predecessor)",
            "- assemble-with-aid: (component, aid)",
            (
                "- assemble-after-with-aid: "
                "(component, predecessor, aid)"
            ),
            "- insert-aid: (aid)",
            (
                "- withdraw-aid-after-one: "
                "(aid, component)"
            ),
            (
                "- withdraw-aid-after-two: "
                "(aid, component_1, component_2)"
            ),
        ]

        semantic_initial_state = {
            key: copy.deepcopy(value)
            for key, value in scene.initial_state.items()
            if key.replace("_", "-") in {
                "assembled",
                "aid-present",
                "precedes",
                "requires-aid",
            }
        }

        feedback_section = ""

        if feedback and feedback.strip():
            feedback_section = f"""

PREVIOUS VERIFICATION FEEDBACK:
{feedback.strip()}

Return a repaired complete plan, not only the corrected action.
"""

        return f"""
You are a symbolic task planner for the gearbox PDDL domain.

SCENE ID:
{scene.scene_id}

SCENE NAME:
{scene.scene_name}

DESCRIPTION:
{scene.description}

DIFFICULTY:
{scene.difficulty}

TYPED OBJECTS:
{json.dumps(
    scene.object_types,
    indent=2,
    ensure_ascii=False,
)}

SEMANTIC INITIAL STATE:
{json.dumps(
    semantic_initial_state,
    indent=2,
    ensure_ascii=False,
)}

GOAL STATE:
{json.dumps(
    scene.goal_state,
    indent=2,
    ensure_ascii=False,
)}

NEGATIVE GOAL STATE:
{json.dumps(
    scene.negative_goal_state,
    indent=2,
    ensure_ascii=False,
)}

AVAILABLE ACTIONS:
{chr(10).join(action_lines)}

ACTION ARGUMENT GUIDANCE:
{chr(10).join(argument_guidance)}

GEARBOX-BENCHMARK RULES:
- Permanent components may have explicit assembly-order constraints.
- precedes(A,B) means A must be assembled before B.
- requires-aid(P,T) means temporary aid T must be present while P is assembled.
- A temporary aid may be inserted when it is absent.
- A temporary aid may be withdrawn only after every permanent component
  requiring that aid has been assembled.
- The final configuration must satisfy all positive goals and all
  negative goals.
- The four assemble-* actions represent the same conceptual assembly
  operation under different dependency structures.
- Do not invent additional actions, stages, resources, locations, or
  physical simulation rules.

The AVAILABLE ACTIONS section is authoritative for legal action names
and argument counts.

ACTION ARGUMENT GUIDANCE explains parameter order only. It does not
replace the benchmark preconditions.

{feedback_section}

OUTPUT REQUIREMENTS:
- Output only one JSON array.
- Do not output markdown.
- Do not output explanations.
- Each item must contain exactly:
  "action"
  "args"
- Use only declared objects.
- Return the complete plan from the initial state to the final goal.
""".strip()

    def _validate_semantic_relations(
        self,
        scene: SceneConfig,
        permanents: set[str],
        aids: set[str],
    ) -> None:
        """
        Validate semantic source-of-truth relations and Gearbox-v1
        structural bounds.
        """

        precedes = self._read_relations(
            scene.initial_state,
            "precedes",
        )

        requires_aid = self._read_relations(
            scene.initial_state,
            "requires_aid",
            fallback_key="requires-aid",
        )

        predecessor_count: dict[str, int] = {}

        for predecessor, component in precedes:
            if predecessor not in permanents:
                raise ValueError(
                    f"Gearbox scene '{scene.scene_id}' precedes "
                    f"first argument '{predecessor}' must be a "
                    "permanent-component."
                )

            if component not in permanents:
                raise ValueError(
                    f"Gearbox scene '{scene.scene_id}' precedes "
                    f"second argument '{component}' must be a "
                    "permanent-component."
                )

            if predecessor == component:
                raise ValueError(
                    f"Gearbox scene '{scene.scene_id}' contains "
                    f"self precedence for '{component}'."
                )

            predecessor_count[component] = (
                predecessor_count.get(
                    component,
                    0,
                )
                + 1
            )

        for component, count in (
            predecessor_count.items()
        ):
            if count > 1:
                raise ValueError(
                    f"Unsupported Gearbox-v1 structure in scene "
                    f"'{scene.scene_id}': permanent component "
                    f"'{component}' has {count} direct predecessors; "
                    "the validated quantifier-free encoding supports "
                    "at most 1."
                )

        aid_count: dict[str, int] = {}
        dependents_by_aid: dict[
            str,
            set[str],
        ] = {}

        for component, aid in requires_aid:
            if component not in permanents:
                raise ValueError(
                    f"Gearbox scene '{scene.scene_id}' "
                    f"requires-aid first argument '{component}' "
                    "must be a permanent-component."
                )

            if aid not in aids:
                raise ValueError(
                    f"Gearbox scene '{scene.scene_id}' "
                    f"requires-aid second argument '{aid}' "
                    "must be a temporary-aid."
                )

            aid_count[component] = (
                aid_count.get(
                    component,
                    0,
                )
                + 1
            )

            dependents_by_aid.setdefault(
                aid,
                set(),
            ).add(component)

        for component, count in aid_count.items():
            if count > 1:
                raise ValueError(
                    f"Unsupported Gearbox-v1 structure in scene "
                    f"'{scene.scene_id}': permanent component "
                    f"'{component}' requires {count} temporary aids; "
                    "the validated quantifier-free encoding supports "
                    "at most 1."
                )

        for aid, dependents in (
            dependents_by_aid.items()
        ):
            if len(dependents) > 2:
                raise ValueError(
                    f"Unsupported Gearbox-v1 structure in scene "
                    f"'{scene.scene_id}': temporary aid '{aid}' "
                    f"has {len(dependents)} dependent components; "
                    "the validated quantifier-free encoding supports "
                    "at most 2."
                )

    def _validate_prepared_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        """
        Validate the compiled planner-facing state using the generic
        predicate/arity checker.
        """

        state_section_to_pddl_atoms(
            state_section=scene.initial_state,
            scene=scene,
            domain=self.domain,
            section_name="prepared_initial_state",
        )

        state_section_to_pddl_atoms(
            state_section=scene.goal_state,
            scene=scene,
            domain=self.domain,
            section_name="goal_state",
        )

        state_section_to_pddl_atoms(
            state_section=scene.negative_goal_state,
            scene=scene,
            domain=self.domain,
            section_name="negative_goal_state",
        )

    def _objects_of_type(
        self,
        scene: SceneConfig,
        object_type: str,
    ) -> list[str]:
        return list(
            scene.object_types.get(
                object_type,
                [],
            )
        )

    def _read_relations(
        self,
        state: dict[str, Any],
        key: str,
        fallback_key: str | None = None,
    ) -> list[tuple[str, str]]:
        """
        Read a binary semantic relation from JSON-style state data.
        """

        raw_value = state.get(key)

        if raw_value is None and fallback_key:
            raw_value = state.get(
                fallback_key,
                [],
            )

        if raw_value is None:
            raw_value = []

        return [
            (
                str(relation[0]).strip(),
                str(relation[1]).strip(),
            )
            for relation in raw_value
        ]


# Dynamic adapter loader entry point.
Adapter = GearboxAdapter