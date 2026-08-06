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

    expected_bridge_counts = {
        "scene_01_blocksworld_basic": None,
        "scene_02_pyramid": 6,
        "scene_03_large_pyramid": 10,
    }

    for scene_id, bridge_count in (
        expected_bridge_counts.items()
    ):
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
        print("Context result : SUCCESS")

    print()
    print("=" * 72)
    print("ALL EXTERNAL VAL RUNTIME CONTEXT TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()