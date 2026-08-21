from src.domain_adapters import (
    get_domain_adapter,
)
from src.domain_config import (
    load_domain_config,
)
from src.plan_model import (
    PlanStep,
    load_expected_plan,
)
from src.scene_config import (
    list_supported_scenes,
    load_scene_config,
)
from src.verifiers import (
    get_symbolic_verifier,
)
from src.verifiers.block_building import (
    BlockBuildingVerifier,
)


def main() -> None:
    print("=" * 72)
    print("BLOCK BUILDING SYMBOLIC VERIFIER TEST")
    print("=" * 72)

    domain = load_domain_config(
        "block_building"
    )

    adapter = get_domain_adapter(domain)
    verifier = get_symbolic_verifier(
        domain
    )

    if not isinstance(
        verifier,
        BlockBuildingVerifier,
    ):
        raise AssertionError(
            "Dynamic verifier loader did not return "
            "BlockBuildingVerifier."
        )

    expected_lengths = {
        "scene_01_blocksworld_basic": 4,
        "scene_02_pyramid": 6,
        "scene_03_large_pyramid": 12,
    }

    for scene_id in list_supported_scenes():
        original_scene = load_scene_config(
            scene_id
        )

        if original_scene.domain_id != (
            "block_building"
        ):
            continue

        prepared_scene = adapter.prepare_scene(
            original_scene
        )

        plan = load_expected_plan(
            scene=prepared_scene,
            domain=domain,
        )

        result = verifier.verify(
            plan=plan,
            scene=prepared_scene,
            verbose=False,
        )

        if not result.success:
            raise AssertionError(
                f"Expected plan failed for '{scene_id}':\n"
                f"{result.to_feedback_text()}"
            )

        if len(plan) != expected_lengths[
            scene_id
        ]:
            raise AssertionError(
                f"Unexpected plan length for "
                f"'{scene_id}'."
            )

        print()
        print(f"Scene ID      : {scene_id}")
        print(f"Plan steps    : {len(plan)}")
        print("Plan result   : SUCCESS")
        print("Goal result   : SUCCESS")

    # Scene 01 must fail when its ordinary on goal is omitted.
    scene_01 = adapter.prepare_scene(
        load_scene_config(
            "scene_01_blocksworld_basic"
        )
    )

    incomplete_scene_01_plan = [
        PlanStep(
            action="unstack",
            args=("blockA", "blockB"),
        ),
        PlanStep(
            action="put-down",
            args=("blockA",),
        ),
    ]

    scene_01_failure = verifier.verify(
        plan=incomplete_scene_01_plan,
        scene=scene_01,
    )

    if scene_01_failure.success:
        raise AssertionError(
            "Scene 01 incomplete plan incorrectly passed."
        )

    if scene_01_failure.failed_step != (
        "goal_check"
    ):
        raise AssertionError(
            "Scene 01 incomplete plan did not fail "
            "during goal checking."
        )

    if "on(blockB,blockC)" not in (
        scene_01_failure.message
    ):
        raise AssertionError(
            "Scene 01 ordinary on goal was not checked."
        )

    print()
    print("Scene 01 ordinary on-goal test: SUCCESS")

    # Deliberately violate handempty in Scene 02.
    scene_02 = adapter.prepare_scene(
        load_scene_config(
            "scene_02_pyramid"
        )
    )

    invalid_scene_02_plan = [
        PlanStep(
            action="pick-up",
            args=("B4",),
        ),
        PlanStep(
            action="pick-up",
            args=("B5",),
        ),
    ]

    scene_02_failure = verifier.verify(
        plan=invalid_scene_02_plan,
        scene=scene_02,
    )

    if scene_02_failure.success:
        raise AssertionError(
            "Invalid Scene 02 plan incorrectly passed."
        )

    if scene_02_failure.failed_step != 2:
        raise AssertionError(
            "Invalid Scene 02 plan did not fail at step 2."
        )

    if "handempty" not in (
        scene_02_failure.message
    ):
        raise AssertionError(
            "Scene 02 handempty failure was not reported."
        )

    if (
        scene_02_failure
        .state_before_failure
        is None
    ):
        raise AssertionError(
            "Failure state context was not recorded."
        )

    print("Scene 02 failure diagnosis test: SUCCESS")

    print()
    print("=" * 72)
    print("ALL BLOCK BUILDING VERIFIER TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()