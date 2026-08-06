from pathlib import Path

from src.external_val_feedback_loop import (
    RuntimeContext,
    initialise_runtime_context,
)


def require_existing_file(
    file_path: Path,
    description: str,
) -> None:
    if not file_path.exists():
        raise AssertionError(
            f"{description} does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise AssertionError(
            f"{description} is not a file: {file_path}"
        )


def main() -> None:
    print("=" * 72)
    print("EXTERNAL VAL RUNTIME CONTEXT TEST")
    print("=" * 72)

    expected_scenes = {
        "scene_01_blocksworld_basic": {
            "bridge_count": None,
            "plan_length": 4,
            "first_action": "unstack",
            "last_action": "stack",
        },
        "scene_02_pyramid": {
            "bridge_count": 6,
            "plan_length": 6,
            "first_action": "pick-up",
            "last_action": "stack-bridge",
        },
        "scene_03_large_pyramid": {
            "bridge_count": 10,
            "plan_length": 12,
            "first_action": "pick-up",
            "last_action": "stack-bridge",
        },
    }

    for scene_id, expected in (
        expected_scenes.items()
    ):
        bridge_count = expected[
            "bridge_count"
        ]
        context = initialise_runtime_context(
            scene_id
        )

        if not isinstance(
            context,
            RuntimeContext,
        ):
            raise AssertionError(
                f"'{scene_id}' did not return RuntimeContext."
            )

        if context.scene.scene_id != scene_id:
            raise AssertionError(
                f"Requested '{scene_id}', but loaded "
                f"'{context.scene.scene_id}'."
            )

        if context.domain.domain_id != (
            "block_building"
        ):
            raise AssertionError(
                f"Unexpected domain for '{scene_id}': "
                f"{context.domain.domain_id}"
            )

        if context.prepared_scene.domain_id != (
            context.domain.domain_id
        ):
            raise AssertionError(
                f"Prepared scene/domain mismatch for "
                f"'{scene_id}'."
            )

        if context.problem_file != (
            context.prepared_scene.problem_file
        ):
            raise AssertionError(
                f"Problem path mismatch for '{scene_id}'."
            )

        if context.domain_file != (
            context.domain.domain_file
        ):
            raise AssertionError(
                f"Domain path mismatch for '{scene_id}'."
            )

        if context.results_root != (
            context.prepared_scene.results_directory
        ):
            raise AssertionError(
                f"Results path mismatch for '{scene_id}'."
            )

        require_existing_file(
            context.domain_file,
            "Domain PDDL file",
        )

        require_existing_file(
            context.problem_file,
            "Generated problem PDDL file",
        )

        expected_plan = context.expected_plan

        if len(expected_plan) != expected[
            "plan_length"
        ]:
            raise AssertionError(
                f"'{scene_id}' expected "
                f"{expected['plan_length']} plan steps, "
                f"but received {len(expected_plan)}."
            )

        if expected_plan[0].action != expected[
            "first_action"
        ]:
            raise AssertionError(
                f"'{scene_id}' has unexpected first action: "
                f"{expected_plan[0].action}"
            )

        if expected_plan[-1].action != expected[
            "last_action"
        ]:
            raise AssertionError(
                f"'{scene_id}' has unexpected last action: "
                f"{expected_plan[-1].action}"
            )

        for step in expected_plan:
            if not isinstance(step.args, tuple):
                raise AssertionError(
                    f"'{scene_id}' expected DomainPlanStep "
                    f"arguments to be tuples."
                )

            if not step.to_pddl_text().startswith("("):
                raise AssertionError(
                    f"'{scene_id}' produced invalid PDDL plan "
                    f"text for action '{step.action}'."
                )


        left_free = (
            context.prepared_scene
            .initial_state
            .get("left_free")
        )

        right_free = (
            context.prepared_scene
            .initial_state
            .get("right_free")
        )

        if bridge_count is None:
            if left_free is not None:
                raise AssertionError(
                    "Scene 01 unexpectedly received "
                    "left_free defaults."
                )

            if right_free is not None:
                raise AssertionError(
                    "Scene 01 unexpectedly received "
                    "right_free defaults."
                )

        else:
            if left_free is None:
                raise AssertionError(
                    f"'{scene_id}' is missing left_free."
                )

            if right_free is None:
                raise AssertionError(
                    f"'{scene_id}' is missing right_free."
                )

            if len(left_free) != bridge_count:
                raise AssertionError(
                    f"'{scene_id}' expected "
                    f"{bridge_count} left_free objects, "
                    f"but received {len(left_free)}."
                )

            if len(right_free) != bridge_count:
                raise AssertionError(
                    f"'{scene_id}' expected "
                    f"{bridge_count} right_free objects, "
                    f"but received {len(right_free)}."
                )

        print()
        print(f"Scene ID       : {context.scene.scene_id}")
        print(f"Domain ID      : {context.domain.domain_id}")
        print(
            f"Adapter        : "
            f"{type(context.adapter).__name__}"
        )
        print(
            f"Verifier       : "
            f"{type(context.verifier).__name__}"
        )
        print(f"Domain file    : {context.domain_file}")
        print(f"Problem file   : {context.problem_file}")
        print(f"Results root   : {context.results_root}")
        print(
            f"Plan steps     : "
            f"{len(context.expected_plan)}"
        )
        print(
            f"First plan step: "
            f"{context.expected_plan[0].to_function_text()}"
        )
        print(
            f"Last plan step : "
            f"{context.expected_plan[-1].to_function_text()}"
        )
        print("Context result : SUCCESS")

    print()
    print("=" * 72)
    print("ALL EXTERNAL VAL RUNTIME CONTEXT TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()