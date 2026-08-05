from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENES_DIRECTORY = PROJECT_ROOT / "data" / "scenes"
DOMAINS_DIRECTORY = PROJECT_ROOT / "domains"
GENERATED_PDDL_DIRECTORY = PROJECT_ROOT / "generated_pddl"
RESULTS_DIRECTORY = PROJECT_ROOT / "results"





@dataclass(frozen=True)
class SceneConfig:
    """
    Domain-independent configuration for one planning scene.

    The loader preserves arbitrary predicates in initial_state and
    goal_state. Domain-specific interpretation is deliberately left to
    the relevant domain adapter.
    """

    scene_id: str
    domain_id: str
    scene_name: str
    description: str
    difficulty: str

    # Flat object list used by the existing project.
    objects: list[str]

    # Optional typed object groups for future PDDL domains.
    #
    # Example:
    # {
    #     "gear": ["gear1", "gear2"],
    #     "shaft": ["shaft1", "shaft2"]
    # }
    object_types: dict[str, list[str]]

    # Arbitrary domain-specific predicates are preserved here.
    initial_state: dict[str, Any]
    goal_state: dict[str, Any]

    expected_plan: list[str]
    planning_guidance: dict[str, Any]

    scene_json_file: Path

    # Source domain pack paths.
    domain_directory: Path
    domain_file: Path
    domain_config_file: Path

    # Generated PDDL problem paths.
    generated_pddl_directory: Path
    problem_file: Path

    # Experiment output location.
    results_directory: Path

    # Original unmodified JSON data.
    scene_data: dict[str, Any]


def discover_scene_files() -> dict[str, Path]:
    """
    Recursively discover every scene JSON below data/scenes.

    This supports structures such as:

        data/scenes/block_building/*.json
        data/scenes/occlusion_manipulation/*.json
        data/scenes/gearbox_assembly/*.json

    Scene IDs must be unique across the whole project.
    """

    if not SCENES_DIRECTORY.exists():
        raise FileNotFoundError(
            f"Scene directory does not exist: {SCENES_DIRECTORY}"
        )

    discovered: dict[str, Path] = {}

    for scene_json_file in sorted(
        SCENES_DIRECTORY.rglob("*.json")
    ):
        scene_data = _read_json_object(scene_json_file)

        raw_scene_id = scene_data.get("scene_id")

        if not isinstance(raw_scene_id, str):
            raise ValueError(
                f"Scene file must contain a string scene_id: "
                f"{scene_json_file}"
            )

        scene_id = raw_scene_id.strip()

        if not scene_id:
            raise ValueError(
                f"Scene file contains an empty scene_id: "
                f"{scene_json_file}"
            )

        if scene_id in discovered:
            raise ValueError(
                f"Duplicate scene_id '{scene_id}' found in:\n"
                f"  {discovered[scene_id]}\n"
                f"  {scene_json_file}"
            )

        discovered[scene_id] = scene_json_file

    return discovered


def _read_json_object(json_file: Path) -> dict[str, Any]:
    """
    Read one JSON file and require a top-level object.
    """

    try:
        loaded_data = json.loads(
            json_file.read_text(encoding="utf-8-sig")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON file: {json_file}\n{exc}"
        ) from exc

    if not isinstance(loaded_data, dict):
        raise ValueError(
            f"JSON file must contain one top-level object: "
            f"{json_file}"
        )

    return loaded_data


def _resolve_domain_id(
    scene_id: str,
    scene_data: dict[str, Any],
    scene_json_file: Path,
) -> str:
    """
    Read and validate the scene's explicit domain identifier.

    Every scene must declare domain_id in its JSON file.
    """

    raw_domain_id = scene_data.get("domain_id")

    if not isinstance(raw_domain_id, str):
        raise ValueError(
            f"Scene '{scene_id}' must define domain_id as a string: "
            f"{scene_json_file}"
        )

    domain_id = raw_domain_id.strip()

    if not domain_id:
        raise ValueError(
            f"Scene '{scene_id}' contains an empty domain_id: "
            f"{scene_json_file}"
        )

    return domain_id


def _normalise_objects(
    scene_id: str,
    raw_objects: Any,
) -> tuple[list[str], dict[str, list[str]]]:
    """
    Support both flat and typed object declarations.

    Flat form:
        "objects": ["blockA", "blockB"]

    Typed form:
        "objects": {
            "gear": ["gear1", "gear2"],
            "shaft": ["shaft1", "shaft2"]
        }
    """

    if isinstance(raw_objects, list):
        objects = [
            str(object_name).strip()
            for object_name in raw_objects
        ]

        object_types: dict[str, list[str]] = {}

    elif isinstance(raw_objects, dict):
        object_types = {}
        objects = []

        for object_type, typed_objects in raw_objects.items():
            type_name = str(object_type).strip()

            if not type_name:
                raise ValueError(
                    f"Scene '{scene_id}' contains an empty "
                    f"object type name."
                )

            if not isinstance(typed_objects, list):
                raise ValueError(
                    f"Object type '{type_name}' in scene "
                    f"'{scene_id}' must contain a list."
                )

            normalised_group = [
                str(object_name).strip()
                for object_name in typed_objects
            ]

            object_types[type_name] = normalised_group
            objects.extend(normalised_group)

    else:
        raise ValueError(
            f"Scene '{scene_id}' objects must be either "
            f"a list or an object containing typed lists."
        )

    if not objects:
        raise ValueError(
            f"Scene '{scene_id}' must contain at least one object."
        )

    if any(not object_name for object_name in objects):
        raise ValueError(
            f"Scene '{scene_id}' contains an empty object name."
        )

    if len(objects) != len(set(objects)):
        raise ValueError(
            f"Scene '{scene_id}' contains duplicate object names."
        )

    return objects, object_types


def _copy_state_section(
    scene_id: str,
    section_name: str,
    raw_section: Any,
) -> dict[str, Any]:
    """
    Preserve arbitrary predicates without applying block-specific rules.

    Examples of supported future keys include:
        occludes
        accessible
        on_shaft
        shaft_free
        compatible
        aligned
        meshed
    """

    if not isinstance(raw_section, dict):
        raise ValueError(
            f"Scene '{scene_id}' {section_name} must be an object."
        )

    return copy.deepcopy(raw_section)


def _validate_scene_data(
    requested_scene_id: str,
    scene_data: dict[str, Any],
    scene_json_file: Path,
) -> None:
    """
    Validate only domain-independent scene structure.

    Predicate arities and domain-specific rules will be validated later
    by DomainConfig and the selected domain adapter.
    """

    required_top_level_keys = {
        "scene_id",
        "scene_name",
        "description",
        "objects",
        "initial_state",
        "goal_state",
    }

    missing_keys = sorted(
        required_top_level_keys - set(scene_data)
    )

    if missing_keys:
        raise ValueError(
            f"Scene file {scene_json_file} is missing required "
            f"field(s): {', '.join(missing_keys)}"
        )

    json_scene_id = scene_data["scene_id"]

    if not isinstance(json_scene_id, str):
        raise ValueError(
            f"scene_id must be a string: {scene_json_file}"
        )

    if json_scene_id.strip() != requested_scene_id:
        raise ValueError(
            "Scene identifier mismatch: "
            f"requested '{requested_scene_id}', but JSON contains "
            f"'{json_scene_id}'."
        )

    if not isinstance(scene_data["scene_name"], str):
        raise ValueError(
            f"Scene '{requested_scene_id}' scene_name "
            f"must be a string."
        )

    if not isinstance(scene_data["description"], str):
        raise ValueError(
            f"Scene '{requested_scene_id}' description "
            f"must be a string."
        )


def load_scene_config(scene_id: str) -> SceneConfig:
    """
    Load one scene using automatic recursive discovery.
    """

    requested_scene_id = scene_id.strip()

    if not requested_scene_id:
        raise ValueError("scene_id cannot be empty.")

    scene_files = discover_scene_files()

    if requested_scene_id not in scene_files:
        supported_text = ", ".join(sorted(scene_files))

        raise ValueError(
            f"Unsupported scene '{requested_scene_id}'. "
            f"Discovered scenes: {supported_text}"
        )

    scene_json_file = scene_files[requested_scene_id]
    scene_data = _read_json_object(scene_json_file)

    _validate_scene_data(
        requested_scene_id=requested_scene_id,
        scene_data=scene_data,
        scene_json_file=scene_json_file,
    )

    domain_id = _resolve_domain_id(
        scene_id=requested_scene_id,
        scene_data=scene_data,
        scene_json_file=scene_json_file,
    )

    objects, object_types = _normalise_objects(
        scene_id=requested_scene_id,
        raw_objects=scene_data["objects"],
    )

    initial_state = _copy_state_section(
        scene_id=requested_scene_id,
        section_name="initial_state",
        raw_section=scene_data["initial_state"],
    )

    goal_state = _copy_state_section(
        scene_id=requested_scene_id,
        section_name="goal_state",
        raw_section=scene_data["goal_state"],
    )

    raw_expected_plan = scene_data.get(
        "expected_plan",
        [],
    )

    if not isinstance(raw_expected_plan, list):
        raise ValueError(
            f"Scene '{requested_scene_id}' expected_plan "
            f"must be a list."
        )

    raw_planning_guidance = scene_data.get(
        "planning_guidance",
        {},
    )

    if not isinstance(raw_planning_guidance, dict):
        raise ValueError(
            f"Scene '{requested_scene_id}' planning_guidance "
            f"must be an object."
        )

    domain_directory = (
        DOMAINS_DIRECTORY
        / domain_id
    )

    generated_pddl_directory = (
        GENERATED_PDDL_DIRECTORY
        / domain_id
        / requested_scene_id
    )

    return SceneConfig(
        scene_id=requested_scene_id,
        domain_id=domain_id,
        scene_name=scene_data["scene_name"].strip(),
        description=scene_data["description"].strip(),
        difficulty=str(
            scene_data.get("difficulty", "unspecified")
        ),
        objects=objects,
        object_types=object_types,
        initial_state=initial_state,
        goal_state=goal_state,
        expected_plan=[
            str(step)
            for step in raw_expected_plan
        ],
        planning_guidance=copy.deepcopy(
            raw_planning_guidance
        ),
        scene_json_file=scene_json_file,
        domain_directory=domain_directory,
        domain_file=domain_directory / "domain.pddl",
        domain_config_file=(
            domain_directory
            / "domain_config.json"
        ),
        generated_pddl_directory=(
            generated_pddl_directory
        ),
        problem_file=(
            generated_pddl_directory
            / "problem.pddl"
        ),
        results_directory=(
            RESULTS_DIRECTORY
            / "refinement"
            / domain_id
            / requested_scene_id
        ),
        scene_data=copy.deepcopy(scene_data),
    )


def list_supported_scenes() -> list[str]:
    """
    Return every discovered scene ID in stable sorted order.
    """

    return sorted(discover_scene_files())