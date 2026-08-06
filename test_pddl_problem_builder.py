from pathlib import Path

from src.domain_config import (
    load_domain_config,
)
from src.pddl_problem_builder import (
    build_pddl_problem,
    write_pddl_problem,
)
from src.scene_config import (
    list_supported_scenes,
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
    print("GENERIC PDDL PROBLEM BUILDER TEST")
    print("=" * 72)

    generated_files: list[Path] = []

    for scene_id in list_supported_scenes():
        scene = load_scene_config(scene_id)
        domain = load_domain_config(
            scene.domain_id
        )

        problem_text = build_pddl_problem(
            scene=scene,
            domain=domain,
        )

        require_text(
            problem_text,
            f"(problem {scene_id.replace('_', '-')})",
            "problem name",
        )

        require_text(
            problem_text,
            f"(:domain {domain.pddl_domain_name})",
            "domain name",
        )

        for object_name in scene.objects:
            require_text(
                problem_text,
                object_name,
                f"object '{object_name}'",
            )

        problem_file = write_pddl_problem(
            scene=scene,
            domain=domain,
        )

        if not problem_file.exists():
            raise AssertionError(
                f"Problem file was not created: "
                f"{problem_file}"
            )

        saved_text = problem_file.read_text(
            encoding="utf-8"
        )

        if saved_text != problem_text:
            raise AssertionError(
                f"Saved PDDL differs from generated PDDL "
                f"for scene '{scene_id}'."
            )

        generated_files.append(problem_file)

        print()
        print(f"Scene ID     : {scene.scene_id}")
        print(f"Domain ID    : {domain.domain_id}")
        print(f"Problem file : {problem_file}")
        print(
            f"Initial keys : "
            f"{sorted(scene.initial_state)}"
        )
        print(
            f"Goal keys    : "
            f"{sorted(scene.goal_state)}"
        )
        print("Build result : SUCCESS")

    scene_01 = load_scene_config(
        "scene_01_blocksworld_basic"
    )

    scene_01_text = scene_01.problem_file.read_text(
        encoding="utf-8"
    )

    require_text(
        scene_01_text,
        "(on blockA blockB)",
        "Scene 01 initial on relation",
    )

    require_text(
        scene_01_text,
        "(on blockB blockC)",
        "Scene 01 goal on relation",
    )

    scene_02 = load_scene_config(
        "scene_02_pyramid"
    )

    scene_02_text = scene_02.problem_file.read_text(
        encoding="utf-8"
    )

    require_text(
        scene_02_text,
        "(on-bridge B4 B1 B2)",
        "Scene 02 bridge goal",
    )

    scene_03 = load_scene_config(
        "scene_03_large_pyramid"
    )

    scene_03_text = scene_03.problem_file.read_text(
        encoding="utf-8"
    )

    require_text(
        scene_03_text,
        "(on-bridge top U1 U2)",
        "Scene 03 top bridge goal",
    )

    print()
    print("Generated files:")

    for problem_file in generated_files:
        print(f"  {problem_file}")

    print()
    print("=" * 72)
    print("ALL GENERIC PDDL PROBLEM BUILDER TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()