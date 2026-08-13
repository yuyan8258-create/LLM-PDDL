from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """
    Common interface for text-generation providers used by the planning pipeline.
    """

    provider_name: str
    model: str

    def generate(self, prompt: str) -> str:
        """
        Generate a raw text response for the supplied prompt.
        """
        ...


class OllamaProvider:
    """
    Ollama implementation of the common LLM provider interface.

    This preserves the behaviour of the existing LLMPlanner._call_ollama()
    implementation.
    """

    provider_name = "ollama"

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
    ) -> None:
        cleaned_model = model.strip()

        if not cleaned_model:
            raise ValueError(
                "Ollama model name must not be empty."
            )

        self.model = cleaned_model
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        cleaned_prompt = prompt.strip()

        if not cleaned_prompt:
            raise ValueError(
                "LLM prompt must not be empty."
            )

        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError(
                "The 'ollama' Python package is not installed. "
                "Install it with: pip install ollama"
            ) from exc

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": cleaned_prompt,
                }
            ],
            options={
                "temperature": self.temperature,
            },
        )

        return response["message"]["content"].strip()

class DeepSeekProvider:
    """
    DeepSeek implementation of the common LLM provider interface.
    """

    provider_name = "deepseek"

    def __init__(
        self,
        model: str = "deepseek-v4-flash",
        temperature: float = 0.0,
        api_key: str | None = None,
    ) -> None:
        cleaned_model = model.strip()

        if not cleaned_model:
            raise ValueError(
                "DeepSeek model name must not be empty."
            )

        self.model = cleaned_model
        self.temperature = temperature
        self.api_key = api_key

    def generate(self, prompt: str) -> str:
        cleaned_prompt = prompt.strip()

        if not cleaned_prompt:
            raise ValueError(
                "LLM prompt must not be empty."
            )

        try:
            import os
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' Python package is not installed. "
                "Install it with: pip install openai"
            ) from exc

        resolved_api_key = (
            self.api_key
            or os.environ.get("DEEPSEEK_API_KEY")
        )

        if not resolved_api_key:
            raise RuntimeError(
                "DeepSeek API key is not configured. "
                "Set the DEEPSEEK_API_KEY environment variable."
            )

        client = OpenAI(
            api_key=resolved_api_key,
            base_url="https://api.deepseek.com",
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": cleaned_prompt,
                }
            ],
            temperature=self.temperature,
            stream=False,
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError(
                "DeepSeek returned an empty response."
            )

        return content.strip()