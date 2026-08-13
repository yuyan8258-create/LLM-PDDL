from __future__ import annotations

from src.llm_provider import DeepSeekProvider, OllamaProvider


def expect_value_error(
    *,
    model: str,
    expected_message: str,
) -> None:
    try:
        OllamaProvider(model=model)
    except ValueError as exc:
        if expected_message not in str(exc):
            raise AssertionError(
                f"Expected error containing "
                f"'{expected_message}', got '{exc}'."
            ) from exc
    else:
        raise AssertionError(
            "Expected ValueError, but no error was raised."
        )


def main() -> None:
    print("=" * 72)
    print("LLM PROVIDER TEST")
    print("=" * 72)

    provider = OllamaProvider(
        model="llama3.1:8b",
        temperature=0.0,
    )

    if provider.provider_name != "ollama":
        raise AssertionError(
            "Unexpected provider name."
        )

    if provider.model != "llama3.1:8b":
        raise AssertionError(
            "Unexpected model name."
        )

    if provider.temperature != 0.0:
        raise AssertionError(
            "Unexpected temperature."
        )

    print("Ollama provider construction : SUCCESS")

    trimmed_provider = OllamaProvider(
        model="  llama3.1:8b  ",
    )

    if trimmed_provider.model != "llama3.1:8b":
        raise AssertionError(
            "Model name was not trimmed."
        )

    print("Model-name normalization     : SUCCESS")

    expect_value_error(
        model="",
        expected_message="must not be empty",
    )

    expect_value_error(
        model="   ",
        expected_message="must not be empty",
    )

    print("Invalid model protection     : SUCCESS")

    deepseek_provider = DeepSeekProvider()

    if deepseek_provider.provider_name != "deepseek":
        raise AssertionError(
            "Unexpected DeepSeek provider name."
        )

    if deepseek_provider.model != "deepseek-v4-flash":
        raise AssertionError(
            "Unexpected default DeepSeek model."
        )

    if deepseek_provider.temperature != 0.0:
        raise AssertionError(
            "Unexpected DeepSeek temperature."
        )

    print("DeepSeek provider construction: SUCCESS")

    custom_deepseek_provider = DeepSeekProvider(
        model="  deepseek-v4-pro  ",
        temperature=0.0,
    )

    if custom_deepseek_provider.model != "deepseek-v4-pro":
        raise AssertionError(
            "DeepSeek model name was not normalized."
        )

    print("DeepSeek model normalization : SUCCESS")

    try:
        DeepSeekProvider(model="")
    except ValueError as exc:
        if "must not be empty" not in str(exc):
            raise
    else:
        raise AssertionError(
            "Expected empty DeepSeek model to be rejected."
        )

    print("DeepSeek model protection    : SUCCESS")

    print()
    print("=" * 72)
    print("ALL LLM PROVIDER TESTS PASSED")
    print("=" * 72)


if __name__ == "__main__":
    main()