from __future__ import annotations

from src.llm_provider import DeepSeekProvider


def main() -> None:
    print("=" * 72)
    print("DEEPSEEK API SMOKE TEST")
    print("=" * 72)

    provider = DeepSeekProvider(
        model="deepseek-v4-flash",
        temperature=0.0,
    )

    response = provider.generate(
        "Reply with exactly the single word: OK"
    )

    print(f"Provider : {provider.provider_name}")
    print(f"Model    : {provider.model}")
    print(f"Response : {response}")

    if response.strip().upper() != "OK":
        raise AssertionError(
            f"Unexpected DeepSeek response: {response!r}"
        )

    print()
    print("DeepSeek API call: SUCCESS")


if __name__ == "__main__":
    main()