from src.scene_config import (
    discover_scene_files,
    list_supported_scenes,
    load_scene_config,
)


def main() -> None:
    print("=" * 72)
    print("DOMAIN-INDEPENDENT SCENE CONFIGURATION TEST")
    print("=" * 72)

    discovered_files = discover_scene_files()

    if not discovered_files:
        raise AssertionError(
            "No scene JSON files were discovered."
        )

    scene_ids = list_supported_scenes()

    if scene_ids != sorted(scene_ids):
        raise AssertionError(
            "Scene IDs are not returned in sorted order."
        )

    if set(scene_ids) != set(discovered_files):
        raise AssertionError(
            "list_supported_scenes() and "
            "discover_scene_files() disagree."
        )

    for scene_id in scene_ids:
        config = load_scene_config(scene_id)

        if config.scene_id != scene_id:
            raise AssertionError(
                f"Loaded scene ID mismatch for {scene_id}."
            )

        if not config.domain_id:
            raise AssertionError(
                f"Scene '{scene_id}' has no domain_id."
            )

        if not config.objects:
            raise AssertionError(
                f"Scene '{scene_id}' has no objects."
            )

        if not isinstance(config.initial_state, dict):
            raise AssertionError(
                f"Scene '{scene_id}' initial_state "
                f"is not a dictionary."
            )

        if not isinstance(config.goal_state, dict):
            raise AssertionError(
                f"Scene '{scene_id}' goal_state "
                f"is not a dictionary."
            )

        print()
        print(f"Scene ID       : {config.scene_id}")
        print(f"Domain ID      : {config.domain_id}")
        print(f"Scene name     : {config.scene_name}")
        print(f"Difficulty     : {config.difficulty}")
        print(f"Object count   : {len(config.objects)}")
        print(f"Objects        : {config.objects}")
        print(
            "Object types   : "
            f"{config.object_types or 'untyped'}"
        )
        print(
            "Initial keys   : "
            f"{sorted(config.initial_state)}"
        )
        print(
            "Goal keys      : "
            f"{sorted(config.goal_state)}"
        )
        print(
            "Expected steps : "
            f"{len(config.expected_plan)}"
        )
        print(
            "Scene file     : "
            f"{config.scene_json_file}"
        )
        print(
            "Domain file    : "
            f"{config.domain_file}"
        )
        print(
            "Problem file   : "
            f"{config.problem_file}"
        )
        print(
            "Results dir    : "
            f"{config.results_directory}"
        )

    print()
    print("=" * 72)
    print("ALL SCENE CONFIGURATIONS LOADED SUCCESSFULLY")
    print("=" * 72)


if __name__ == "__main__":
    main()