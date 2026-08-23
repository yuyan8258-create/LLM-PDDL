from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.domain_config import DomainConfig
from src.scene_config import SceneConfig


def normalise_pddl_identifier(value: str) -> str:
    """
    Convert a project identifier into a safe PDDL identifier.

    Underscores and unsupported characters are converted to hyphens.
    """

    cleaned = value.strip().replace("_", "-")
    cleaned = re.sub(
        r"[^A-Za-z0-9-]",
        "-",
        cleaned,
    )
    cleaned = re.sub(
        r"-+",
        "-",
        cleaned,
    ).strip("-")

    if not cleaned:
        raise ValueError(
            f"Cannot create a PDDL identifier from: {value!r}"
        )

    return cleaned


def pddl_atom(
    predicate_name: str,
    *arguments: str,
) -> str:
    """
    Format one positive PDDL atom.
    """

    if arguments:
        return (
            f"({predicate_name} "
            f"{' '.join(arguments)})"
        )

    return f"({predicate_name})"


def resolve_predicate_name(
    state_key: str,
    domain: DomainConfig,
) -> str:
    """
    Resolve a JSON state key to a predicate in the domain.

    Direct PDDL spelling is accepted:

        "on-bridge"

    Python/JSON underscore spelling is also accepted when the matching
    hyphenated predicate exists:

        "on_bridge" -> "on-bridge"
    """

    direct_name = state_key.strip()

    if direct_name in domain.predicate_arities:
        return direct_name

    hyphenated_name = direct_name.replace("_", "-")

    if hyphenated_name in domain.predicate_arities:
        return hyphenated_name

    available = ", ".join(
        sorted(domain.predicate_arities)
    )

    raise ValueError(
        f"State key '{state_key}' is not a predicate in domain "
        f"'{domain.domain_id}'. Available predicates: {available}"
    )


def _validate_object_reference(
    object_name: Any,
    scene: SceneConfig,
    predicate_name: str,
) -> str:
    """
    Require one predicate argument to reference a declared object.
    """

    if not isinstance(object_name, str):
        raise ValueError(
            f"Predicate '{predicate_name}' in scene "
            f"'{scene.scene_id}' contains a non-string argument: "
            f"{object_name!r}"
        )

    normalised_name = object_name.strip()

    if not normalised_name:
        raise ValueError(
            f"Predicate '{predicate_name}' in scene "
            f"'{scene.scene_id}' contains an empty argument."
        )

    if normalised_name not in scene.objects:
        raise ValueError(
            f"Predicate '{predicate_name}' in scene "
            f"'{scene.scene_id}' references undeclared object "
            f"'{normalised_name}'."
        )

    return normalised_name


def state_section_to_pddl_atoms(
    state_section: dict[str, Any],
    scene: SceneConfig,
    domain: DomainConfig,
    section_name: str,
) -> list[str]:
    """
    Convert one initial-state or goal-state dictionary into PDDL atoms.

    Supported JSON representations:

    Zero-arity predicate:
        "handempty": true

    Unary predicate:
        "clear": ["blockA", "blockB"]

    Binary or higher-arity predicate:
        "on": [["blockA", "blockB"]]
        "on_bridge": [["B4", "B1", "B2"]]
    """

    if not isinstance(state_section, dict):
        raise ValueError(
            f"Scene '{scene.scene_id}' {section_name} "
            f"must be a dictionary."
        )

    atoms: list[str] = []

    for state_key, raw_value in state_section.items():
        predicate_name = resolve_predicate_name(
            state_key=state_key,
            domain=domain,
        )

        arity = domain.predicate_arities[
            predicate_name
        ]

        if arity == 0:
            if not isinstance(raw_value, bool):
                raise ValueError(
                    f"Zero-arity predicate '{predicate_name}' in "
                    f"scene '{scene.scene_id}' {section_name} "
                    f"must use true or false."
                )

            if raw_value:
                atoms.append(
                    pddl_atom(predicate_name)
                )

            continue

        if not isinstance(raw_value, list):
            raise ValueError(
                f"Predicate '{predicate_name}' in scene "
                f"'{scene.scene_id}' {section_name} must use a list."
            )

        if arity == 1:
            for raw_object in raw_value:
                object_name = _validate_object_reference(
                    object_name=raw_object,
                    scene=scene,
                    predicate_name=predicate_name,
                )

                atoms.append(
                    pddl_atom(
                        predicate_name,
                        object_name,
                    )
                )

            continue

        for raw_relation in raw_value:
            if not isinstance(
                raw_relation,
                (list, tuple),
            ):
                raise ValueError(
                    f"Predicate '{predicate_name}' in scene "
                    f"'{scene.scene_id}' {section_name} requires "
                    f"relations containing {arity} arguments."
                )

            if len(raw_relation) != arity:
                raise ValueError(
                    f"Predicate '{predicate_name}' in scene "
                    f"'{scene.scene_id}' {section_name} requires "
                    f"{arity} arguments, but received "
                    f"{len(raw_relation)}: {raw_relation!r}"
                )

            arguments = [
                _validate_object_reference(
                    object_name=raw_argument,
                    scene=scene,
                    predicate_name=predicate_name,
                )
                for raw_argument in raw_relation
            ]

            atoms.append(
                pddl_atom(
                    predicate_name,
                    *arguments,
                )
            )

    return atoms


def format_pddl_objects(
    scene: SceneConfig,
) -> str:
    """
    Format flat or typed PDDL object declarations.

    Flat scenes:
        blockA blockB blockC

    Typed scenes:
        gear1 gear2 - gear
        shaft1 shaft2 - shaft
    """

    if not scene.object_types:
        return "    " + " ".join(scene.objects)

    declared_objects: list[str] = []
    object_lines: list[str] = []

    for object_type, objects in (
        scene.object_types.items()
    ):
        if not objects:
            raise ValueError(
                f"Object type '{object_type}' in scene "
                f"'{scene.scene_id}' cannot be empty."
            )

        safe_type = normalise_pddl_identifier(
            object_type
        )

        object_lines.append(
            "    "
            + " ".join(objects)
            + f" - {safe_type}"
        )

        declared_objects.extend(objects)

    if set(declared_objects) != set(scene.objects):
        raise ValueError(
            f"Typed object groups in scene '{scene.scene_id}' "
            f"do not match the scene's flat object list."
        )

    if len(declared_objects) != len(
        set(declared_objects)
    ):
        raise ValueError(
            f"Scene '{scene.scene_id}' contains an object in "
            f"more than one type group."
        )

    return "\n".join(object_lines)


def build_pddl_problem(
    scene: SceneConfig,
    domain: DomainConfig,
) -> str:
    """
    Build one complete PDDL problem from SceneConfig and DomainConfig.
    """

    if scene.domain_id != domain.domain_id:
        raise ValueError(
            f"Scene '{scene.scene_id}' uses domain "
            f"'{scene.domain_id}', but builder received "
            f"'{domain.domain_id}'."
        )

    init_atoms = state_section_to_pddl_atoms(
        state_section=scene.initial_state,
        scene=scene,
        domain=domain,
        section_name="initial_state",
    )

    goal_atoms = state_section_to_pddl_atoms(
        state_section=scene.goal_state,
        scene=scene,
        domain=domain,
        section_name="goal_state",
    )

    negative_goal_atoms = state_section_to_pddl_atoms(
        state_section=scene.negative_goal_state,
        scene=scene,
        domain=domain,
        section_name="negative_goal_state",
    )

    if not goal_atoms and not negative_goal_atoms:
        raise ValueError(
            f"Scene '{scene.scene_id}' has no goal literals."
        )

    problem_name = normalise_pddl_identifier(
        scene.scene_id
    )

    object_text = format_pddl_objects(scene)

    init_text = "\n".join(
        f"    {atom}"
        for atom in init_atoms
    )

    goal_lines = [
        f"      {atom}"
        for atom in goal_atoms
    ]

    goal_lines.extend(
        f"      (not {atom})"
        for atom in negative_goal_atoms
    )

    goal_text = "\n".join(goal_lines)

    return f"""(define (problem {problem_name})
  (:domain {domain.pddl_domain_name})

  (:objects
{object_text}
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


def write_pddl_problem(
    scene: SceneConfig,
    domain: DomainConfig,
) -> Path:
    """
    Build and write a scene's generated problem.pddl file.

    The canonical domain remains in:

        domains/<domain_id>/domain.pddl
    """

    problem_text = build_pddl_problem(
        scene=scene,
        domain=domain,
    )

    scene.generated_pddl_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    scene.problem_file.write_text(
        problem_text,
        encoding="utf-8",
    )

    return scene.problem_file