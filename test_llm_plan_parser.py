from __future__ import annotations

from src.pyramid_demo_v3 import (
    normalize_llm_json_plan,
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    print("=" * 72)
    print("LLM PLAN PARSER TEST")
    print("=" * 72)

    # ------------------------------------------------------------
    # A. Existing ideal dict-based JSON format
    # ------------------------------------------------------------

    ideal_json = """
    [
      {
        "action": "pick-up",
        "args": ["B4"]
      },
      {
        "action": "stack-bridge",
        "args": ["B4", "B1", "B2"]
      }
    ]
    """

    plan = normalize_llm_json_plan(
        ideal_json
    )

    require(
        len(plan) == 2,
        "Ideal JSON plan length was incorrect.",
    )

    require(
        plan[0].action == "pick-up",
        "Ideal JSON first action was incorrect.",
    )

    require(
        plan[0].args == ["B4"],
        "Ideal JSON first arguments were incorrect.",
    )

    print()
    print("Ideal dict JSON format: SUCCESS")

    # ------------------------------------------------------------
    # B. Real DeepSeek Medium output shape
    #
    # The model emitted comma-separated action arrays but omitted
    # the outer plan list.
    # ------------------------------------------------------------

    deepseek_medium_output = (
        '["remove-stacked-occluder", "O2", "O1"],'
        '["remove-ground-occluder", "O1", '
        '"front_slot", "T1"],'
        '["pick-up-target", "T1", "target_slot"],'
        '["put-down-target", "T1", "goal_region"],'
        '["restore-ground-occluder", "O1", '
        '"front_slot"],'
        '["stack-occluder", "O2", "O1"]'
    )

    plan = normalize_llm_json_plan(
        deepseek_medium_output
    )

    require(
        len(plan) == 6,
        (
            "DeepSeek action-array plan should "
            "contain six parsed actions."
        ),
    )

    require(
        plan[0].action
        == "remove-stacked-occluder",
        (
            "DeepSeek first action was parsed "
            "incorrectly."
        ),
    )

    require(
        plan[0].args == [
            "O2",
            "O1",
        ],
        (
            "DeepSeek first action arguments "
            "were parsed incorrectly."
        ),
    )

    require(
        plan[-1].action
        == "stack-occluder",
        (
            "DeepSeek final action was parsed "
            "incorrectly."
        ),
    )

    require(
        plan[-1].args == [
            "O2",
            "O1",
        ],
        (
            "DeepSeek final arguments were "
            "parsed incorrectly."
        ),
    )

    print()
    print(
        "DeepSeek action-array fallback: SUCCESS"
    )

    # ------------------------------------------------------------
    # C. DeepSeek nested argument-array representation
    # ------------------------------------------------------------

    nested_argument_output = """
    [
      [
        "remove-stacked-occluder",
        ["O2", "O1"]
      ],
      [
        "put-down-occluder",
        ["O2", "temp_A"]
      ],
      [
        "remove-ground-occluder",
        ["O1", "front_slot", "T1"]
      ],
      [
        "put-down-occluder",
        ["O1", "temp_B"]
      ],
      [
        "pick-up-target",
        ["T1", "target_slot"]
      ],
      [
        "put-down-target",
        ["T1", "goal_region"]
      ]
    ]
    """

    plan = normalize_llm_json_plan(
        nested_argument_output
    )

    require(
        len(plan) == 6,
        (
            "Nested argument-array plan should "
            "contain six actions."
        ),
    )

    require(
        plan[0].action
        == "remove-stacked-occluder",
        (
            "Nested argument-array first action "
            "was incorrect."
        ),
    )

    require(
        plan[0].args == [
            "O2",
            "O1",
        ],
        (
            "Nested argument list was not "
            "flattened correctly."
        ),
    )

    require(
        plan[2].args == [
            "O1",
            "front_slot",
            "T1",
        ],
        (
            "Three-argument nested list was not "
            "flattened correctly."
        ),
    )

    print()
    print(
        "Nested argument-array fallback: SUCCESS"
    )

    # ------------------------------------------------------------
    # C. Parser must remain domain-agnostic.
    #
    # It may structurally parse an unknown action. DomainConfig /
    # validate_plan() remains responsible for rejecting legality.
    # ------------------------------------------------------------

    unknown_action_output = (
        '["completely-fake-action", "O2"]'
    )

    plan = normalize_llm_json_plan(
        unknown_action_output
    )

    require(
        len(plan) == 1,
        (
            "Domain-agnostic parser did not "
            "return one structured step."
        ),
    )

    require(
        plan[0].action
        == "completely-fake-action",
        (
            "Parser unexpectedly filtered an "
            "unknown action name."
        ),
    )

    require(
        plan[0].args == ["O2"],
        (
            "Unknown-action arguments were "
            "parsed incorrectly."
        ),
    )

    print()
    print(
        "Parser legality separation: SUCCESS"
    )

    print()
    print("=" * 72)
    print(
        "ALL LLM PLAN PARSER TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()