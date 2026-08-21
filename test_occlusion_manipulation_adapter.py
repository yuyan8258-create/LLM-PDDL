from dataclasses import replace

from src.domain_adapters import get_domain_adapter
from src.domain_adapters.occlusion_manipulation import (
    OcclusionManipulationAdapter,
)
from src.domain_config import load_domain_config
from src.scene_config import (
    SceneConfig,
    load_scene_config,
)


def require_text(
    text: str,
    expected: str,
    description: str,
) -> None:

    if expected not in text:
        raise AssertionError(
            f"Missing {description}: {expected}"
        )


def require_value_error(
    description: str,
    function,
) -> None:

    try:
        function()
    except ValueError:
        return

    raise AssertionError(
        f"Expected ValueError: {description}"
    )


def make_valid_occlusion_scene() -> SceneConfig:

    template = load_scene_config(
        "scene_01_blocksworld_basic"
    )

    object_types = {

        "target-brick": [
            "T1",
        ],

        "occluder-brick": [
            "O1",
            "O2",
        ],

        "target-structural-location": [
            "target_slot",
        ],

        "occluder-structural-location": [
            "front_slot",
        ],

        "temporary-location": [
            "temp_a",
            "temp_b",
        ],

        "goal-location": [
            "goal_region",
        ],
    }


    objects = [
        obj
        for group in object_types.values()
        for obj in group
    ]


    initial_state = {

        "at": [
            ["T1", "target_slot"],
            ["O1", "front_slot"],
        ],

        "on": [
            ["O2", "O1"],
        ],

        "clear": [
            "T1",
            "O2",
        ],

        "occludes": [
            ["O2", "O1"],
            ["O1", "T1"],
        ],

        "accessible": [
            "O2",
        ],

        "holding": [],

        "handempty": True,

        "free": [
            "temp_a",
            "temp_b",
            "goal_region",
        ],

        "target-relocated": False,
    }


    goal_state = {

        "at": [
            ["T1", "goal_region"],
        ],

        "handempty": True,
    }


    return replace(
        template,

        scene_id=(
            "test_occlusion_adapter_scene"
        ),

        domain_id=(
            "occlusion_manipulation"
        ),

        scene_name=(
            "Occlusion Adapter Test Scene"
        ),

        description=(
            "Temporary in-memory scene "
            "for adapter validation."
        ),

        difficulty="test",

        objects=objects,

        object_types=object_types,

        initial_state=initial_state,

        goal_state=goal_state,

        expected_plan=[],

        planning_guidance={},

        scene_data={
            "scene_id":
                "test_occlusion_adapter_scene",
            "domain_id":
                "occlusion_manipulation",
        },
    )


def main() -> None:

    print("=" * 72)
    print(
        "OCCLUSION MANIPULATION ADAPTER TEST"
    )
    print("=" * 72)


    domain = load_domain_config(
        "occlusion_manipulation"
    )


    adapter = get_domain_adapter(domain)


    if not isinstance(
        adapter,
        OcclusionManipulationAdapter,
    ):
        raise AssertionError(
            "Wrong adapter loaded."
        )


    scene = make_valid_occlusion_scene()


    adapter.validate_scene(scene)


    prepared = adapter.prepare_scene(scene)


    if prepared is scene:
        raise AssertionError(
            "prepare_scene returned original object"
        )


    if (
        prepared.initial_state
        is scene.initial_state
    ):
        raise AssertionError(
            "initial_state not copied"
        )


    prompt = adapter.build_plan_prompt(
        scene
    )


    require_text(
        prompt,
        "AVAILABLE ACTIONS",
        "available actions section",
    )


    require_text(
        prompt,
        "ACTION ARGUMENT GUIDANCE",
        "argument guidance section",
    )


    require_text(
        prompt,
        (
            "remove-ground-occluder: "
            "(occluder, "
            "occluder_structural_location, target)"
        ),
        "remove-ground argument guidance",
    )


    require_text(
        prompt,
        (
            "stack-occluder: "
            "(occluder, support_occluder)"
        ),
        "stack argument guidance",
    )


    require_text(
        prompt,
        (
            "The AVAILABLE ACTIONS section is "
            "authoritative"
        ),
        "DomainConfig authority statement",
    )


    require_text(
        prompt,
        (
            "benchmark dependency abstractions "
            "rather than full"
        ),
        "benchmark abstraction wording",
    )


    # semantic validation examples

    invalid_on = replace(
        scene,
        initial_state={
            **scene.initial_state,
            "on": [
                ["O2", "T1"],
            ],
        },
    )


    require_value_error(
        "target used in stacked relation",
        lambda:
            adapter.validate_scene(
                invalid_on
            ),
    )


    invalid_occludes = replace(
        scene,
        initial_state={
            **scene.initial_state,
            "occludes": [
                ["T1", "O1"],
            ],
        },
    )


    require_value_error(
        "target used as occluder",
        lambda:
            adapter.validate_scene(
                invalid_occludes
            ),
    )


    print()
    print(
        "ALL OCCLUSION ADAPTER TESTS PASSED"
    )


if __name__ == "__main__":
    main()