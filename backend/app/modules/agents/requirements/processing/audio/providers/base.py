from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class SpeechToTextProviderError(RuntimeError):
    pass


class SpeechToTextProviderNotConfiguredError(SpeechToTextProviderError):
    pass


class AudioUnreadableError(SpeechToTextProviderError):
    pass


class AudioTranscriptionError(SpeechToTextProviderError):
    pass


@dataclass(frozen=True)
class SpeechToTextConfiguration:
    provider: str
    provider_version: str
    model_name: str
    device: str
    compute_type: str
    language: str | None
    fingerprint: str


@dataclass(frozen=True)
class SpeechToTextSegment:
    start_seconds: float
    end_seconds: float
    text: str


@dataclass(frozen=True)
class SpeechToTextResult:
    transcript: str
    segments: tuple[SpeechToTextSegment, ...]
    detected_language: str | None = None
    language_probability: float | None = None


class SpeechToTextProvider(Protocol):
    @property
    def configuration(self) -> SpeechToTextConfiguration: ...

    def transcribe(self, audio_path: Path) -> SpeechToTextResult: ...
