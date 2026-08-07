from __future__ import annotations

from src.external_val_feedback_loop import (
    resolve_experiment_method,
)


def expect_value(
    requested_method: str | None,
    max_iterations: int,
    expected: str,
) -> None:
    actual = resolve_experiment_method(
        mode="llm",
        max_iterations=max_iterations,
        requested_method=requested_method,
    )

    if actual != expected:
        raise AssertionError(
            f"Expected '{expected}', got '{actual}'."
        )


def expect_error(
    requested_method: str,
    max_iterations: int,
) -> None:
    try:
        resolve_experiment_method(
            mode="llm",
            max_iterations=max_iterations,
            requested_method=requested_method,
        )
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError, but no error was raised."
    )


def main() -> None:
    print("=" * 72)
    print("EXPLICIT EXPERIMENT METHOD TEST")
    print("=" * 72)

    expect_value(
        requested_method=None,
        max_iterations=1,
        expected="pure_llm",
    )

    expect_value(
        requested_method=None,
        max_iterations=3,
        expected="hybrid_feedback",
    )

    expect_value(
        requested_method="pure_llm",
        max_iterations=1,
        expected="pure_llm",
    )

    expect_value(
        requested_method="hybrid_feedback",
        max_iterations=3,
        expected="hybrid_feedback",
    )

    expect_error(
        requested_method="pure_llm",
        max_iterations=3,
    )

    expect_error(
        requested_method="hybrid_feedback",
        max_iterations=1,
    )

    expect_error(
        requested_method="unsupported",
        max_iterations=1,
    )

    print("Legacy inference       : SUCCESS")
    print("Explicit Pure LLM      : SUCCESS")
    print("Explicit Hybrid        : SUCCESS")
    print("Conflict protection    : SUCCESS")
    print("Unsupported protection : SUCCESS")
    print()
    print("=" * 72)
    print(
        "ALL EXPLICIT EXPERIMENT "
        "METHOD TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()