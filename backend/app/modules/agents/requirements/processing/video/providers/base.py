from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class VideoAudioExtractorError(RuntimeError):
    pass


class VideoAudioExtractorUnavailableError(VideoAudioExtractorError):
    pass


class VideoUnreadableError(VideoAudioExtractorError):
    pass


class VideoNoAudioTrackError(VideoAudioExtractorError):
    pass


class VideoAudioExtractionError(VideoAudioExtractorError):
    pass


@dataclass(frozen=True)
class VideoAudioExtractionConfiguration:
    provider: str
    provider_version: str
    executable: str
    timeout_seconds: float
    sample_rate_hz: int
    channels: int
    fingerprint: str


class VideoAudioExtractor(Protocol):
    @property
    def configuration(self) -> VideoAudioExtractionConfiguration: ...

    def extract_audio(self, input_video_path: Path, output_audio_path: Path) -> None: ...
