from src.domain_config import (
    load_domain_config,
)
from src.plan_model import (
    PlanStep,
    load_expected_plan,
    parse_external_plan_actions,
    parse_plan_step,
    plan_to_json,
    plan_to_pddl_text,
    validate_plan,
)
from src.scene_config import (
    list_supported_scenes,
    load_scene_config,
)


def main() -> None:
    print("=" * 72)
    print("DOMAIN-INDEPENDENT PLAN MODEL TEST")
    print("=" * 72)

    expected_lengths = {
        "occlusion_easy": 4,
        "scene_01_blocksworld_basic": 4,
        "scene_02_pyramid": 6,
        "scene_03_large_pyramid": 12,
    }

    for scene_id in list_supported_scenes():
        scene = load_scene_config(
            scene_id
        )

        domain = load_domain_config(
            scene.domain_id
        )

        plan = load_expected_plan(
            scene=scene,
            domain=domain,
        )

        expected_length = expected_lengths[
            scene_id
        ]

        if len(plan) != expected_length:
            raise AssertionError(
                f"Scene '{scene_id}' expected "
                f"{expected_length} steps, but loaded "
                f"{len(plan)}."
            )

        json_text = plan_to_json(plan)
        pddl_text = plan_to_pddl_text(plan)

        if '"action"' not in json_text:
            raise AssertionError(
                f"Scene '{scene_id}' JSON plan is missing "
                f"action fields."
            )

        if '"args"' not in json_text:
            raise AssertionError(
                f"Scene '{scene_id}' JSON plan is missing "
                f"args fields."
            )

        for step in plan:
            if step.to_pddl_text() not in pddl_text:
                raise AssertionError(
                    f"Scene '{scene_id}' PDDL plan is missing "
                    f"{step.to_pddl_text()}."
                )

        print()
        print(f"Scene ID       : {scene.scene_id}")
        print(f"Domain ID      : {domain.domain_id}")
        print(f"Step count     : {len(plan)}")
        print(
            f"First step     : "
            f"{plan[0].to_function_text()}"
        )
        print(
            f"Last step      : "
            f"{plan[-1].to_function_text()}"
        )
        print("Action checks  : SUCCESS")
        print("Arity checks   : SUCCESS")
        print("Object checks  : SUCCESS")
        print("JSON output    : SUCCESS")
        print("PDDL output    : SUCCESS")

    function_step = parse_plan_step(
        "stack-bridge(B4, B1, B2)"
    )

    pddl_step = parse_plan_step(
        "(stack-bridge B4 B1 B2)"
    )

    if function_step != pddl_step:
        raise AssertionError(
            "Function-style and PDDL-style parsing disagree."
        )

    if function_step != PlanStep(
        action="stack-bridge",
        args=("B4", "B1", "B2"),
    ):
        raise AssertionError(
            "Parsed bridge action has unexpected content."
        )

    print()
    print("Cross-format parsing: SUCCESS")


    scene_01 = load_scene_config(
        "scene_01_blocksworld_basic"
    )

    block_domain = load_domain_config(
        "block_building"
    )

    external_plan = parse_external_plan_actions(
        actions=[
            "unstack blocka blockb",
            "put-down blocka",
            "pick-up blockb",
            "stack blockb blockc",
        ],
        scene=scene_01,
        domain=block_domain,
    )

    expected_external_plan = [
        PlanStep(
            action="unstack",
            args=("blockA", "blockB"),
        ),
        PlanStep(
            action="put-down",
            args=("blockA",),
        ),
        PlanStep(
            action="pick-up",
            args=("blockB",),
        ),
        PlanStep(
            action="stack",
            args=("blockB", "blockC"),
        ),
    ]

    if external_plan != expected_external_plan:
        raise AssertionError(
            "External planner actions were not converted "
            "to canonical scene object names."
        )

    if external_plan[0].args != (
        "blockA",
        "blockB",
    ):
        raise AssertionError(
            "External plan did not restore canonical "
            "Scene 01 object casing."
        )

    print(
        "External planner parsing: SUCCESS"
    )
    print(
        "Canonical object casing : SUCCESS"
    )


    try:
        validate_plan(
            plan=[
                PlanStep(
                    action="unknown-action",
                    args=("blockA",),
                )
            ],
            scene=scene_01,
            domain=block_domain,
        )
    except ValueError as exc:
        if "unknown action" not in str(exc).lower():
            raise
    else:
        raise AssertionError(
            "Unknown action was not rejected."
        )

    try:
        validate_plan(
            plan=[
                PlanStep(
                    action="stack",
                    args=("blockA",),
                )
            ],
            scene=scene_01,
            domain=block_domain,
        )
    except ValueError as exc:
        if "requires 2 argument" not in str(exc):
            raise
    else:
        raise AssertionError(
            "Incorrect action arity was not rejected."
        )

    try:
        validate_plan(
            plan=[
                PlanStep(
                    action="pick-up",
                    args=("not-a-scene-object",),
                )
            ],
            scene=scene_01,
            domain=block_domain,
        )
    except ValueError as exc:
        if "undeclared object" not in str(exc).lower():
            raise
    else:
        raise AssertionError(
            "Undeclared object was not rejected."
        )

    print("Unknown action test : SUCCESS")
    print("Incorrect arity test: SUCCESS")
    print("Unknown object test : SUCCESS")


    try:
        parse_external_plan_actions(
            actions=[
                "unknown-action blocka",
            ],
            scene=scene_01,
            domain=block_domain,
        )
    except ValueError as exc:
        if "unknown action" not in str(exc).lower():
            raise
    else:
        raise AssertionError(
            "Unknown external action was not rejected."
        )

    try:
        parse_external_plan_actions(
            actions=[
                "pick-up missing-object",
            ],
            scene=scene_01,
            domain=block_domain,
        )
    except ValueError as exc:
        if "undeclared object" not in str(exc).lower():
            raise
    else:
        raise AssertionError(
            "Unknown external object was not rejected."
        )

    print(
        "External unknown action: SUCCESS"
    )
    print(
        "External unknown object: SUCCESS"
    )


    print()
    print("=" * 72)
    print("ALL DOMAIN-INDEPENDENT PLAN MODEL TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()