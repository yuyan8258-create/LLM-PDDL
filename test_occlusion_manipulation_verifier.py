import json

from src.domain_config import (
    load_domain_config,
)
from src.plan_model import (
    PlanStep,
    load_expected_plan,
)
from src.scene_config import (
    load_scene_config,
)
from src.verifiers import (
    get_symbolic_verifier,
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    print("=" * 72)
    print("OCCLUSION MANIPULATION VERIFIER TEST")
    print("=" * 72)

    domain = load_domain_config(
        "occlusion_manipulation"
    )

    scene = load_scene_config(
        "occlusion_easy"
    )

    verifier = get_symbolic_verifier(
        domain
    )

    reference_plan = load_expected_plan(
        scene=scene,
        domain=domain,
    )

    # ================================================================
    # A. Valid Easy reference plan
    # ================================================================

    result = verifier.verify(
        plan=reference_plan,
        scene=scene,
    )

    require(
        result.success,
        (
            "Expected Easy reference plan "
            f"to succeed: {result.message}"
        ),
    )

    require(
        ["T1", "goal_region"]
        in result.final_state["at"],
        "Target was not at goal_region.",
    )

    require(
        result.final_state[
            "target_relocated"
        ]
        is True,
        "target_relocated was not true.",
    )

    require(
        result.final_state["handempty"]
        is True,
        "Robot hand was not empty.",
    )

    # VerificationResult must remain JSON serializable.
    json.dumps(
        result.to_dict(),
        ensure_ascii=False,
    )

    print()
    print("Reference plan: SUCCESS")
    print("  4-step Easy plan verified.")
    print("  Final state is JSON serializable.")

    # ================================================================
    # B. Target picked before occlusion removal
    # ================================================================

    early_target_plan = [
        PlanStep(
            action="pick-up-target",
            args=(
                "T1",
                "target_slot",
            ),
        ),
    ]

    result = verifier.verify(
        plan=early_target_plan,
        scene=scene,
    )

    require(
        not result.success,
        "Early target pickup unexpectedly succeeded.",
    )

    require(
        result.failed_step == 1,
        "Early target failure step was incorrect.",
    )

    require(
        "accessible(T1)"
        in (result.error or ""),
        (
            "Early target failure did not report "
            "accessible(T1)."
        ),
    )

    json.dumps(
        result.to_dict(),
        ensure_ascii=False,
    )

    require(
        result.state_before_failure
        is not None,
        "Missing state_before_failure.",
    )

    json.dumps(
        result.state_before_failure,
        ensure_ascii=False,
    )

    print()
    print("Early target access: SUCCESS")
    print("  Missing accessible(T1) diagnosed.")
    print("  Failure state is JSON serializable.")

    # ================================================================
    # C. Robot still holding occluder
    # ================================================================

    occupied_hand_plan = [
        PlanStep(
            action="remove-ground-occluder",
            args=(
                "O1",
                "front_slot",
                "T1",
            ),
        ),
        PlanStep(
            action="pick-up-target",
            args=(
                "T1",
                "target_slot",
            ),
        ),
    ]

    result = verifier.verify(
        plan=occupied_hand_plan,
        scene=scene,
    )

    require(
        not result.success,
        "Occupied-hand plan unexpectedly succeeded.",
    )

    require(
        result.failed_step == 2,
        "Occupied-hand failure step was incorrect.",
    )

    require(
        "handempty"
        in (result.error or ""),
        (
            "Occupied-hand failure did not report "
            "handempty."
        ),
    )

    print()
    print("Occupied hand: SUCCESS")
    print("  Missing handempty diagnosed.")

    # ================================================================
    # D. Valid actions but incomplete goal
    # ================================================================

    incomplete_plan = [
        PlanStep(
            action="remove-ground-occluder",
            args=(
                "O1",
                "front_slot",
                "T1",
            ),
        ),
        PlanStep(
            action="put-down-occluder",
            args=(
                "O1",
                "temp_A",
            ),
        ),
    ]

    result = verifier.verify(
        plan=incomplete_plan,
        scene=scene,
    )

    require(
        not result.success,
        "Incomplete plan unexpectedly satisfied goal.",
    )

    require(
        result.failed_step == "goal_check",
        "Incomplete plan did not fail at goal check.",
    )

    require(
        "at(T1,goal_region)"
        in (result.error or ""),
        (
            "Incomplete-plan goal error did not "
            "report target goal location."
        ),
    )

    print()
    print("Incomplete goal: SUCCESS")
    print("  Goal-check failure diagnosed.")

    # ================================================================
    # E. Restoration before target relocation
    # ================================================================

    early_restore_plan = [
        PlanStep(
            action="remove-ground-occluder",
            args=(
                "O1",
                "front_slot",
                "T1",
            ),
        ),
        PlanStep(
            action="put-down-occluder",
            args=(
                "O1",
                "temp_A",
            ),
        ),
        PlanStep(
            action="pick-up-temp-occluder",
            args=(
                "O1",
                "temp_A",
            ),
        ),
        PlanStep(
            action="restore-ground-occluder",
            args=(
                "O1",
                "front_slot",
            ),
        ),
    ]

    result = verifier.verify(
        plan=early_restore_plan,
        scene=scene,
    )

    require(
        not result.success,
        "Early restoration unexpectedly succeeded.",
    )

    require(
        result.failed_step == 4,
        "Early restoration failure step was incorrect.",
    )

    require(
        "target-relocated"
        in (result.error or ""),
        (
            "Restoration failure did not report "
            "target-relocated."
        ),
    )

    print()
    print("Restoration phase guard: SUCCESS")
    print("  Missing target-relocated diagnosed.")

    # ================================================================
    # F. Typed PDDL argument-role mismatch
    #
    # Structurally valid:
    # - known action
    # - correct arity
    # - both objects declared
    #
    # But the third parameter of remove-ground-occluder must be a
    # target-brick. O1 is an occluder-brick, so Python verification
    # must reject it exactly as the typed PDDL domain would.
    # ================================================================

    typed_role_mismatch_plan = [
        PlanStep(
            action="remove-ground-occluder",
            args=(
                "O1",
                "front_slot",
                "O1",
            ),
        ),
    ]

    result = verifier.verify(
        plan=typed_role_mismatch_plan,
        scene=scene,
    )

    require(
        not result.success,
        (
            "Typed argument-role mismatch "
            "unexpectedly succeeded."
        ),
    )

    require(
        result.failed_step == 1,
        "Typed-role failure step was incorrect.",
    )

    require(
        "must be 'target-brick'"
        in (result.error or ""),
        (
            "Typed-role failure did not report "
            "target-brick requirement."
        ),
    )

    print()
    print("Typed PDDL argument roles: SUCCESS")
    print(
        "  Declared object with wrong PDDL type "
        "was rejected."
    )

    print()
    print("=" * 72)
    print(
        "ALL OCCLUSION MANIPULATION "
        "VERIFIER TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()