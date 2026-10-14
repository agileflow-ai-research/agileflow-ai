import json
from typing import Any, Protocol

import httpx

from app.core.config import Settings


class ModelProviderError(RuntimeError):
    """A configured model provider could not produce a response."""


class ModelProviderConfigurationError(ModelProviderError):
    """No usable provider configuration is available."""


class ModelStructuredOutputError(ModelProviderError):
    """The provider responded, but its generated content was not JSON."""


class StructuredModelProvider(Protocol):
    """Vendor-neutral interface reusable by every specialist engine."""

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class UnavailableModelProvider:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        del system_prompt, user_prompt, json_schema
        raise ModelProviderConfigurationError(self._reason)


class OpenAICompatibleProvider:
    """Isolates the OpenAI-compatible chat-completions wire protocol."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "specialist_structured_output",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ModelProviderError("Structured model generation failed") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError("Structured model generation failed") from exc
        try:
            result = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ModelStructuredOutputError(
                "Model content was not valid structured JSON"
            ) from exc
        if not isinstance(result, dict):
            raise ModelStructuredOutputError(
                "Structured model response was not an object"
            )
        return result


def build_model_provider(settings: Settings) -> StructuredModelProvider:
    provider_name = settings.model_provider.strip().lower()
    if provider_name != "openai_compatible":
        return UnavailableModelProvider(
            "MODEL_PROVIDER must be configured as openai_compatible"
        )
    if not settings.model_api_key:
        return UnavailableModelProvider("MODEL_API_KEY is not configured")
    if not settings.model_name:
        return UnavailableModelProvider("MODEL_NAME is not configured")
    return OpenAICompatibleProvider(
        api_key=settings.model_api_key,
        model=settings.model_name,
        base_url=settings.model_base_url,
        timeout_seconds=settings.model_timeout_seconds,
    )
