from __future__ import annotations

import sys

import requests


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:latest"


def call_local_model(prompt: str) -> str:
    """Send one prompt to the locally running Ollama model."""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
        },
        "keep_alive": "5m",
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=600,
        )
        response.raise_for_status()

    except requests.ConnectionError as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Make sure Ollama is running."
        ) from exc

    except requests.Timeout as exc:
        raise RuntimeError(
            "The local model request timed out."
        ) from exc

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Ollama request failed: {exc}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Ollama returned a non-JSON response: {response.text}"
        ) from exc

    try:
        output = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Unexpected Ollama response structure: {data}"
        ) from exc

    if not output or not output.strip():
        raise RuntimeError("The model returned an empty response.")

    return output.strip()


def main() -> None:
    prompt = "Reply with exactly the word SUCCESS and nothing else."

    print(f"Model: {MODEL_NAME}")
    print("Sending request to local Ollama API...")
    print("The first request may take longer because the model must be loaded.")

    result = call_local_model(prompt)

    print("\nModel response:")
    print(result)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)