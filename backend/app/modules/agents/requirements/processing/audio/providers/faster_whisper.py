import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import Lock
from typing import Any

from app.modules.agents.requirements.processing.audio.providers.base import (
    AudioTranscriptionError,
    AudioUnreadableError,
    SpeechToTextConfiguration,
    SpeechToTextProviderNotConfiguredError,
    SpeechToTextResult,
    SpeechToTextSegment,
)


class FasterWhisperProvider:
    """Lazy, reusable local faster-whisper speech-to-text provider."""

    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        language: str = "",
    ) -> None:
        self._model_name = model_name.strip()
        self._device = device.strip()
        self._compute_type = compute_type.strip()
        self._language = language.strip() or None
        self._model: Any | None = None
        self._model_lock = Lock()
        self._transcription_lock = Lock()

    @property
    def configuration(self) -> SpeechToTextConfiguration:
        try:
            provider_version = version("faster-whisper")
        except PackageNotFoundError:
            provider_version = "unavailable"
        values = {
            "provider": "faster_whisper",
            "provider_version": provider_version,
            "model_name": self._model_name,
            "device": self._device,
            "compute_type": self._compute_type,
            "language": self._language,
        }
        fingerprint = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return SpeechToTextConfiguration(**values, fingerprint=fingerprint)

    def transcribe(self, audio_path: Path) -> SpeechToTextResult:
        model = self._get_model()
        try:
            with self._transcription_lock:
                raw_segments, info = model.transcribe(
                    str(audio_path), language=self._language
                )
                segments = tuple(
                    SpeechToTextSegment(
                        start_seconds=float(segment.start),
                        end_seconds=float(segment.end),
                        text=segment.text,
                    )
                    for segment in raw_segments
                )
        except Exception as exc:
            if type(exc).__module__.startswith("av."):
                raise AudioUnreadableError(
                    "Local audio decoding failed"
                ) from exc
            raise AudioTranscriptionError(
                "Local audio transcription failed"
            ) from exc
        return SpeechToTextResult(
            transcript="".join(segment.text for segment in segments),
            segments=segments,
            detected_language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
        )

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            if not self._model_name or not self._device or not self._compute_type:
                raise SpeechToTextProviderNotConfiguredError(
                    "The local transcription provider is not configured"
                )
            try:
                from faster_whisper import WhisperModel
            except (ImportError, OSError) as exc:
                raise SpeechToTextProviderNotConfiguredError(
                    "The local transcription provider is unavailable"
                ) from exc
            try:
                self._model = WhisperModel(
                    self._model_name,
                    device=self._device,
                    compute_type=self._compute_type,
                )
            except Exception as exc:
                raise SpeechToTextProviderNotConfiguredError(
                    "The local transcription model is unavailable"
                ) from exc
            return self._model


class UnconfiguredSpeechToTextProvider:
    def __init__(self, provider_name: str) -> None:
        self._provider_name = provider_name.strip() or "unconfigured"

    @property
    def configuration(self) -> SpeechToTextConfiguration:
        values = {
            "provider": self._provider_name,
            "provider_version": "unavailable",
            "model_name": "unconfigured",
            "device": "unconfigured",
            "compute_type": "unconfigured",
            "language": None,
        }
        fingerprint = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return SpeechToTextConfiguration(**values, fingerprint=fingerprint)

    def transcribe(self, audio_path: Path) -> SpeechToTextResult:
        del audio_path
        raise SpeechToTextProviderNotConfiguredError(
            "The selected transcription provider is not configured"
        )
