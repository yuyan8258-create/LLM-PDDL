from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENES_DIRECTORY = PROJECT_ROOT / "data" / "scenes"
GENERATED_PDDL_DIRECTORY = PROJECT_ROOT / "generated_pddl"


SUPPORTED_SCENES = (
    "scene_01_blocksworld_basic",
    "scene_02_pyramid",
    "scene_03_large_pyramid",
)


@dataclass(frozen=True)
class SceneConfig:
    """
    Normalised configuration for one planning scene.

    The original JSON data is preserved in `scene_data`.
    Frequently used paths and fields are exposed separately.
    """

    scene_id: str
    scene_name: str
    description: str
    difficulty: str
    objects: list[str]
    initial_state: dict[str, Any]
    goal_state: dict[str, Any]
    expected_plan: list[str]
    scene_json_file: Path
    domain_file: Path
    problem_file: Path
    results_directory: Path
    scene_data: dict[str, Any]


def _normalise_initial_state(
    raw_initial_state: dict[str, Any],
    objects: list[str],
) -> dict[str, Any]:
    """
    Return an initial state containing every state key used by the
    existing SymbolicVerifier.

    Bridge support slots are assumed to be initially free when the
    scene JSON does not explicitly provide them.
    """

    return {
        "on": [
            list(relation)
            for relation in raw_initial_state.get("on", [])
        ],
        "on_bridge": [
            list(relation)
            for relation in raw_initial_state.get("on_bridge", [])
        ],
        "ontable": list(
            raw_initial_state.get("ontable", [])
        ),
        "clear": list(
            raw_initial_state.get("clear", [])
        ),
        "holding": list(
            raw_initial_state.get("holding", [])
        ),
        "handempty": bool(
            raw_initial_state.get("handempty", True)
        ),
        "left_free": list(
            raw_initial_state.get("left_free", objects)
        ),
        "right_free": list(
            raw_initial_state.get("right_free", objects)
        ),
    }


def _normalise_goal_state(
    raw_goal_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Return a goal state with all supported goal categories present.

    This does not invent new goals. Missing categories are represented
    as empty lists.
    """

    return {
        "on": [
            list(relation)
            for relation in raw_goal_state.get("on", [])
        ],
        "on_bridge": [
            list(relation)
            for relation in raw_goal_state.get("on_bridge", [])
        ],
        "ontable": list(
            raw_goal_state.get("ontable", [])
        ),
        "clear": list(
            raw_goal_state.get("clear", [])
        ),
        "holding": list(
            raw_goal_state.get("holding", [])
        ),
        "handempty": bool(
            raw_goal_state.get("handempty", False)
        ),
        "left_free": list(
            raw_goal_state.get("left_free", [])
        ),
        "right_free": list(
            raw_goal_state.get("right_free", [])
        ),
    }


def _validate_scene_data(
    scene_id: str,
    scene_data: dict[str, Any],
    scene_json_file: Path,
) -> None:
    """
    Check only the minimum structure needed by the current project.

    More detailed PDDL and plan validation will be added in later steps.
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

    if scene_data["scene_id"] != scene_id:
        raise ValueError(
            "Scene identifier mismatch: "
            f"requested '{scene_id}', but JSON contains "
            f"'{scene_data['scene_id']}'."
        )

    objects = scene_data["objects"]

    if not isinstance(objects, list) or not objects:
        raise ValueError(
            f"Scene '{scene_id}' must contain a non-empty objects list."
        )

    if len(objects) != len(set(objects)):
        raise ValueError(
            f"Scene '{scene_id}' contains duplicate object names."
        )

    if not isinstance(scene_data["initial_state"], dict):
        raise ValueError(
            f"Scene '{scene_id}' initial_state must be an object."
        )

    if not isinstance(scene_data["goal_state"], dict):
        raise ValueError(
            f"Scene '{scene_id}' goal_state must be an object."
        )


def load_scene_config(scene_id: str) -> SceneConfig:
    """
    Load and normalise one scene from data/scenes.

    This function does not require the PDDL files to exist yet. Scene 01
    and Scene 03 PDDL files will be generated in a later step.
    """

    if scene_id not in SUPPORTED_SCENES:
        supported_text = ", ".join(SUPPORTED_SCENES)

        raise ValueError(
            f"Unsupported scene '{scene_id}'. "
            f"Supported scenes: {supported_text}"
        )

    scene_json_file = (
        SCENES_DIRECTORY / f"{scene_id}.json"
    )

    if not scene_json_file.exists():
        raise FileNotFoundError(
            f"Scene JSON file does not exist: {scene_json_file}"
        )

    try:
        scene_data = json.loads(
            scene_json_file.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Scene JSON is invalid: {scene_json_file}\n{exc}"
        ) from exc

    if not isinstance(scene_data, dict):
        raise ValueError(
            f"Scene JSON must contain one top-level object: "
            f"{scene_json_file}"
        )

    _validate_scene_data(
        scene_id=scene_id,
        scene_data=scene_data,
        scene_json_file=scene_json_file,
    )

    objects = [
        str(object_name)
        for object_name in scene_data["objects"]
    ]

    initial_state = _normalise_initial_state(
        raw_initial_state=scene_data["initial_state"],
        objects=objects,
    )

    goal_state = _normalise_goal_state(
        raw_goal_state=scene_data["goal_state"],
    )

    pddl_directory = (
        GENERATED_PDDL_DIRECTORY / scene_id
    )

    return SceneConfig(
        scene_id=scene_id,
        scene_name=str(scene_data["scene_name"]),
        description=str(scene_data["description"]),
        difficulty=str(
            scene_data.get("difficulty", "unspecified")
        ),
        objects=objects,
        initial_state=initial_state,
        goal_state=goal_state,
        expected_plan=[
            str(step)
            for step in scene_data.get("expected_plan", [])
        ],
        scene_json_file=scene_json_file,
        domain_file=pddl_directory / "domain.pddl",
        problem_file=pddl_directory / "problem.pddl",
        results_directory=(
            PROJECT_ROOT
            / "results"
            / "refinement"
            / scene_id
        ),
        scene_data=scene_data,
    )


def list_supported_scenes() -> list[str]:
    """
    Return supported scene identifiers as a new list.
    """

    return list(SUPPORTED_SCENES)