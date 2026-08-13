from __future__ import annotations

from src.pyramid_demo_v3 import LLMPlanner


class FakeProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.model = "fake-model"
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)

        return """
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
""".strip()


def main() -> None:
    print("=" * 72)
    print("LLM PLANNER PROVIDER INJECTION TEST")
    print("=" * 72)

    provider = FakeProvider()

    planner = LLMPlanner(
        model="fake-model",
        provider=provider,
    )

    plan = planner.generate_from_prompt(
        "Generate a test plan."
    )

    if planner.provider is not provider:
        raise AssertionError(
            "LLMPlanner did not preserve the injected provider."
        )

    if len(provider.prompts) != 1:
        raise AssertionError(
            "Injected provider was not called exactly once."
        )

    if provider.prompts[0] != "Generate a test plan.":
        raise AssertionError(
            "Injected provider received an unexpected prompt."
        )

    if len(plan) != 2:
        raise AssertionError(
            f"Expected 2 parsed plan steps, got {len(plan)}."
        )

    if plan[0].action != "pick-up":
        raise AssertionError(
            "Unexpected first action."
        )

    if tuple(plan[0].args) != ("B4",):
        raise AssertionError(
            f"Unexpected first action arguments: {plan[0].args!r}"
    )

    if plan[1].action != "stack-bridge":
        raise AssertionError(
            "Unexpected second action."
        )

    print("Injected provider preserved : SUCCESS")
    print("Provider call routing       : SUCCESS")
    print("Plan parsing                : SUCCESS")

    print()
    print("=" * 72)
    print("ALL LLM PLANNER PROVIDER INJECTION TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()