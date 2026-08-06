from dataclasses import replace

from src.domain_adapters.base import (
    DomainAdapter,
)
from src.domain_config import (
    load_domain_config,
)
from src.scene_config import (
    SceneConfig,
    load_scene_config,
)


class TestAdapter(DomainAdapter):
    """
    Small concrete adapter used only to test the common interface.
    """

    def validate_scene(
        self,
        scene: SceneConfig,
    ) -> None:
        self.validate_domain_link(scene)

        if not scene.objects:
            raise ValueError(
                f"Scene '{scene.scene_id}' has no objects."
            )

    def prepare_scene(
        self,
        scene: SceneConfig,
    ) -> SceneConfig:
        self.validate_scene(scene)

        return replace(
            scene,
            initial_state=dict(scene.initial_state),
            goal_state=dict(scene.goal_state),
        )

    def build_plan_prompt(
        self,
        scene: SceneConfig,
        feedback: str | None = None,
    ) -> str:
        self.validate_scene(scene)

        prompt = (
            f"Scene: {scene.scene_id}\n"
            f"Domain: {self.domain.domain_id}\n"
            f"Objects: {', '.join(scene.objects)}"
        )

        if feedback:
            prompt += f"\nFeedback: {feedback}"

        return prompt


def main() -> None:
    print("=" * 72)
    print("DOMAIN ADAPTER BASE TEST")
    print("=" * 72)

    domain = load_domain_config(
        "block_building"
    )

    scene = load_scene_config(
        "scene_01_blocksworld_basic"
    )

    adapter = TestAdapter(domain)

    adapter.validate_scene(scene)

    prepared_scene = adapter.prepare_scene(
        scene
    )

    if prepared_scene is scene:
        raise AssertionError(
            "prepare_scene() returned the original SceneConfig."
        )

    if prepared_scene.initial_state is scene.initial_state:
        raise AssertionError(
            "prepare_scene() reused the original initial_state."
        )

    if prepared_scene.goal_state is scene.goal_state:
        raise AssertionError(
            "prepare_scene() reused the original goal_state."
        )

    prompt = adapter.build_plan_prompt(
        scene,
        feedback="Example verifier feedback.",
    )

    if scene.scene_id not in prompt:
        raise AssertionError(
            "Prompt does not contain the scene ID."
        )

    if domain.domain_id not in prompt:
        raise AssertionError(
            "Prompt does not contain the domain ID."
        )

    feedback = adapter.build_feedback(
        scene=scene,
        verifier_feedback="Missing precondition.",
        context={
            "failed_step": 2,
            "action": "stack",
        },
    )

    if "Missing precondition." not in feedback:
        raise AssertionError(
            "Feedback message was not preserved."
        )

    if "failed_step" not in feedback:
        raise AssertionError(
            "Feedback context was not added."
        )

    print()
    print(f"Adapter class  : {type(adapter).__name__}")
    print(f"Scene ID       : {scene.scene_id}")
    print(f"Domain ID      : {domain.domain_id}")
    print("Domain link    : SUCCESS")
    print("Scene copy     : SUCCESS")
    print("Prompt method  : SUCCESS")
    print("Feedback method: SUCCESS")

    print()
    print("=" * 72)
    print("ALL DOMAIN ADAPTER BASE TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()