"""Vendor-neutral speech-to-text providers for persisted audio sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

import httpx

from app.core.config import Settings


class TranscriptionProviderError(RuntimeError):
    """A configured provider could not produce a usable transcription."""


class TranscriptionProviderConfigurationError(TranscriptionProviderError):
    """No usable speech-to-text provider configuration is available."""


class SpeechToTextProvider(Protocol):
    def transcribe(self, file_path: Path) -> str: ...


class UnavailableSpeechToTextProvider:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def transcribe(self, file_path: Path) -> str:
        del file_path
        raise TranscriptionProviderConfigurationError(self._reason)


class OpenAICompatibleSpeechToTextProvider:
    """Implements the OpenAI-compatible multipart transcription protocol."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        language: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._language = language

    def transcribe(self, file_path: Path) -> str:
        data = {"model": self._model, "response_format": "json"}
        if self._language:
            data["language"] = self._language
        try:
            with file_path.open("rb") as audio_file:
                response = httpx.post(
                    f"{self._base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files={"file": (file_path.name, audio_file, "application/octet-stream")},
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
            body = response.json()
        except (OSError, httpx.HTTPError, json.JSONDecodeError) as exc:
            raise TranscriptionProviderError("Audio transcription failed") from exc
        transcript = body.get("text") if isinstance(body, dict) else None
        if not isinstance(transcript, str):
            raise TranscriptionProviderError("Audio transcription failed")
        return transcript


def build_transcription_provider(settings: Settings) -> SpeechToTextProvider:
    provider_name = settings.transcription_provider.strip().lower()
    if provider_name != "openai_compatible":
        return UnavailableSpeechToTextProvider(
            "TRANSCRIPTION_PROVIDER must be configured as openai_compatible"
        )
    if not settings.transcription_api_key:
        return UnavailableSpeechToTextProvider(
            "TRANSCRIPTION_API_KEY is not configured"
        )
    if not settings.transcription_model:
        return UnavailableSpeechToTextProvider(
            "TRANSCRIPTION_MODEL is not configured"
        )
    return OpenAICompatibleSpeechToTextProvider(
        api_key=settings.transcription_api_key,
        model=settings.transcription_model,
        base_url=settings.transcription_base_url,
        timeout_seconds=settings.transcription_timeout_seconds,
        language=settings.transcription_language,
    )
