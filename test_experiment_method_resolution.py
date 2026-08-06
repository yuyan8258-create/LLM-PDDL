from __future__ import annotations

from src.external_val_feedback_loop import (
    resolve_experiment_method,
)


def expect_value(
    mode: str,
    max_iterations: int,
    expected: str,
) -> None:
    actual = resolve_experiment_method(
        mode=mode,
        max_iterations=max_iterations,
    )

    if actual != expected:
        raise AssertionError(
            f"Expected '{expected}', got '{actual}'."
        )


def expect_error(
    mode: str,
    max_iterations: int,
) -> None:
    try:
        resolve_experiment_method(
            mode=mode,
            max_iterations=max_iterations,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError, but no error was raised."
    )


def main() -> None:
    print("=" * 72)
    print("EXPERIMENT METHOD RESOLUTION TEST")
    print("=" * 72)

    expect_value(
        mode="llm",
        max_iterations=1,
        expected="pure_llm",
    )

    expect_value(
        mode="llm",
        max_iterations=2,
        expected="hybrid_feedback",
    )

    expect_value(
        mode="llm",
        max_iterations=5,
        expected="hybrid_feedback",
    )

    expect_value(
        mode="mock",
        max_iterations=1,
        expected="mock",
    )

    expect_value(
        mode="mock",
        max_iterations=3,
        expected="mock",
    )

    expect_error(
        mode="llm",
        max_iterations=0,
    )

    expect_error(
        mode="unsupported",
        max_iterations=1,
    )

    print("Pure LLM mapping : SUCCESS")
    print("Hybrid mapping   : SUCCESS")
    print("Mock mapping     : SUCCESS")
    print("Invalid inputs   : SUCCESS")
    print()
    print("=" * 72)
    print(
        "ALL EXPERIMENT METHOD "
        "RESOLUTION TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()