from src.scene_config import (
    list_supported_scenes,
    load_scene_config,
)


def main() -> None:
    print("=" * 72)
    print("SCENE CONFIGURATION TEST")
    print("=" * 72)

    for scene_id in list_supported_scenes():
        config = load_scene_config(scene_id)

        print()
        print(f"Scene ID       : {config.scene_id}")
        print(f"Scene name     : {config.scene_name}")
        print(f"Difficulty     : {config.difficulty}")
        print(f"Object count   : {len(config.objects)}")
        print(f"Objects        : {config.objects}")
        print(f"Initial on     : {config.initial_state['on']}")
        print(
            "Initial bridges: "
            f"{config.initial_state['on_bridge']}"
        )
        print(
            "Initial left-free count : "
            f"{len(config.initial_state['left_free'])}"
        )
        print(
            "Initial right-free count: "
            f"{len(config.initial_state['right_free'])}"
        )
        print(f"Goal on        : {config.goal_state['on']}")
        print(
            "Goal bridges   : "
            f"{config.goal_state['on_bridge']}"
        )
        print(f"Expected steps : {len(config.expected_plan)}")
        print(f"Domain path    : {config.domain_file}")
        print(f"Problem path   : {config.problem_file}")

    print()
    print("=" * 72)
    print("ALL SCENE CONFIGURATIONS LOADED SUCCESSFULLY")
    print("=" * 72)


if __name__ == "__main__":
    main()