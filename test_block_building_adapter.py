from dataclasses import replace

from src.domain_adapters import (
    get_domain_adapter,
)
from src.domain_adapters.block_building import (
    BlockBuildingAdapter,
)
from src.domain_config import (
    load_domain_config,
)
from src.pddl_problem_builder import (
    build_pddl_problem,
)
from src.scene_config import (
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


def main() -> None:
    print("=" * 72)
    print("BLOCK BUILDING ADAPTER TEST")
    print("=" * 72)

    domain = load_domain_config(
        "block_building"
    )

    adapter = get_domain_adapter(domain)

    if not isinstance(
        adapter,
        BlockBuildingAdapter,
    ):
        raise AssertionError(
            "Dynamic adapter loading did not return "
            "BlockBuildingAdapter."
        )

    print()
    print(
        f"Loaded adapter : "
        f"{type(adapter).__name__}"
    )
    print(
        f"Domain ID      : "
        f"{adapter.domain.domain_id}"
    )

    # -----------------------------------------------------------------
    # Scene 01: ordinary BlocksWorld
    # -----------------------------------------------------------------

    scene_01 = load_scene_config(
        "scene_01_blocksworld_basic"
    )

    prepared_01 = adapter.prepare_scene(
        scene_01
    )

    if prepared_01 is scene_01:
        raise AssertionError(
            "Scene 01 adapter returned the original SceneConfig."
        )

    if prepared_01.initial_state is (
        scene_01.initial_state
    ):
        raise AssertionError(
            "Scene 01 prepared state reused the original dictionary."
        )

    if "left_free" in scene_01.initial_state:
        raise AssertionError(
            "Original Scene 01 was unexpectedly modified."
        )

    if "right_free" in scene_01.initial_state:
        raise AssertionError(
            "Original Scene 01 was unexpectedly modified."
        )

    if "left_free" in prepared_01.initial_state:
        raise AssertionError(
            "Ordinary Scene 01 should not receive left_free."
        )

    if "right_free" in prepared_01.initial_state:
        raise AssertionError(
            "Ordinary Scene 01 should not receive right_free."
        )

    scene_01_problem = build_pddl_problem(
        scene=prepared_01,
        domain=domain,
    )

    require_text(
        scene_01_problem,
        "(on blockA blockB)",
        "Scene 01 initial relation",
    )

    require_text(
        scene_01_problem,
        "(on blockB blockC)",
        "Scene 01 ordinary stacking goal",
    )

    scene_01_prompt = adapter.build_plan_prompt(
        scene_01
    )

    require_text(
        scene_01_prompt,
        scene_01.scene_id,
        "Scene 01 ID in prompt",
    )

    require_text(
        scene_01_prompt,
        "blockA",
        "Scene 01 object in prompt",
    )

    require_text(
        scene_01_prompt,
        '"on"',
        "Scene 01 on relation in prompt",
    )

    print()
    print("Scene 01 preparation: SUCCESS")
    print("  Ordinary stacking state preserved.")
    print("  Bridge defaults were not added.")
    print("  Scene-specific prompt generated.")

    # -----------------------------------------------------------------
    # Scene 02 and Scene 03: bridge construction
    # -----------------------------------------------------------------

    expected_counts = {
        "scene_02_pyramid": 6,
        "scene_03_large_pyramid": 10,
    }

    for scene_id, expected_count in (
        expected_counts.items()
    ):
        original_scene = load_scene_config(
            scene_id
        )

        prepared_scene = adapter.prepare_scene(
            original_scene
        )

        if "left_free" in (
            original_scene.initial_state
        ):
            raise AssertionError(
                f"Original '{scene_id}' was unexpectedly modified."
            )

        if "right_free" in (
            original_scene.initial_state
        ):
            raise AssertionError(
                f"Original '{scene_id}' was unexpectedly modified."
            )

        left_free = prepared_scene.initial_state.get(
            "left_free"
        )

        right_free = prepared_scene.initial_state.get(
            "right_free"
        )

        if left_free != original_scene.objects:
            raise AssertionError(
                f"Prepared '{scene_id}' has incorrect "
                f"left_free defaults."
            )

        if right_free != original_scene.objects:
            raise AssertionError(
                f"Prepared '{scene_id}' has incorrect "
                f"right_free defaults."
            )

        if len(left_free) != expected_count:
            raise AssertionError(
                f"Prepared '{scene_id}' expected "
                f"{expected_count} left_free objects, but got "
                f"{len(left_free)}."
            )

        if len(right_free) != expected_count:
            raise AssertionError(
                f"Prepared '{scene_id}' expected "
                f"{expected_count} right_free objects, but got "
                f"{len(right_free)}."
            )

        problem_text = build_pddl_problem(
            scene=prepared_scene,
            domain=domain,
        )

        for object_name in original_scene.objects:
            require_text(
                problem_text,
                f"(left-free {object_name})",
                f"{scene_id} left support slot",
            )

            require_text(
                problem_text,
                f"(right-free {object_name})",
                f"{scene_id} right support slot",
            )

        prompt = adapter.build_plan_prompt(
            original_scene,
            feedback=(
                "Missing precondition: "
                "right-free(B2)"
            ),
        )

        require_text(
            prompt,
            original_scene.scene_id,
            f"{scene_id} ID in prompt",
        )

        require_text(
            prompt,
            "stack-bridge",
            f"{scene_id} bridge action in prompt",
        )

        require_text(
            prompt,
            "PREVIOUS VERIFICATION FEEDBACK",
            f"{scene_id} feedback section",
        )

        feedback = adapter.build_feedback(
            scene=prepared_scene,
            verifier_feedback=(
                "Missing precondition: "
                "right-free(B2)"
            ),
            context={
                "failed_step": 4,
                "scene_id": scene_id,
            },
        )

        require_text(
            feedback,
            "BLOCK-DOMAIN REPAIR GUIDANCE",
            f"{scene_id} block feedback guidance",
        )

        require_text(
            feedback,
            "support slot",
            f"{scene_id} support-slot guidance",
        )

        print()
        print(
            f"{scene_id} preparation: SUCCESS"
        )
        print(
            f"  Added left_free count : "
            f"{len(left_free)}"
        )
        print(
            f"  Added right_free count: "
            f"{len(right_free)}"
        )
        print(
            "  Complete bridge PDDL generated."
        )
        print(
            "  Scene-specific prompt generated."
        )
        print(
            "  Block feedback guidance generated."
        )

    # -----------------------------------------------------------------
    # Explicit empty support slots must not be overwritten.
    # -----------------------------------------------------------------

    original_scene_02 = load_scene_config(
        "scene_02_pyramid"
    )

    explicit_empty_scene = replace(
        original_scene_02,
        initial_state={
            **original_scene_02.initial_state,
            "left_free": [],
            "right_free": [],
        },
    )

    prepared_explicit_empty = adapter.prepare_scene(
        explicit_empty_scene
    )

    if (
        prepared_explicit_empty
        .initial_state["left_free"]
        != []
    ):
        raise AssertionError(
            "Explicit empty left_free was overwritten."
        )

    if (
        prepared_explicit_empty
        .initial_state["right_free"]
        != []
    ):
        raise AssertionError(
            "Explicit empty right_free was overwritten."
        )

    print()
    print("Explicit-state preservation: SUCCESS")
    print("  Explicit empty support-slot lists were preserved.")

    print()
    print("=" * 72)
    print("ALL BLOCK BUILDING ADAPTER TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()