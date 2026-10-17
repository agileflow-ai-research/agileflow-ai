"""Deterministic source processing for Agent 1; no model calls belong here."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from app.common.transcription_provider import (
    SpeechToTextProvider,
    TranscriptionProviderError,
)
from app.modules.agent1.extractor import extract_text
from app.modules.agent1.schemas import RequirementSourceType


class SourceProcessor(Protocol):
    def process(self, file_path: str | Path) -> str: ...


class SourceNormalizer:
    """Normalize formatting without rewriting or interpreting source content."""

    MIN_USABLE_CHARACTERS = 10

    def normalize(self, content: str) -> str:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
        text = "\n".join(lines).strip()
        text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
        if len(text.strip()) < self.MIN_USABLE_CHARACTERS:
            raise ValueError("No usable text could be extracted.")
        return text


class DocumentProcessor:
    def __init__(self, normalizer: SourceNormalizer | None = None) -> None:
        self._normalizer = normalizer or SourceNormalizer()

    def process(self, file_path: str | Path) -> str:
        extracted = extract_text(
            source_type=RequirementSourceType.DOCUMENT,
            file_path=file_path,
        )
        return self._normalizer.normalize(extracted)


class AudioProcessor:
    def __init__(
        self,
        provider: SpeechToTextProvider,
        normalizer: SourceNormalizer | None = None,
    ) -> None:
        self._provider = provider
        self._normalizer = normalizer or SourceNormalizer()

    def process(self, file_path: str | Path) -> str:
        transcript = self._provider.transcribe(Path(file_path))
        return self._normalizer.normalize(transcript)


class VideoProcessorNotConfiguredError(RuntimeError):
    pass


class VideoAudioExtractionError(RuntimeError):
    pass


class NoUsableAudioError(RuntimeError):
    pass


class VideoTranscriptionError(RuntimeError):
    pass


class FFmpegAudioExtractor:
    """Extract mono PCM audio with a bounded, shell-free FFmpeg invocation."""

    def __init__(self, ffmpeg_path: str, timeout_seconds: float) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._timeout_seconds = timeout_seconds

    def extract(self, video_path: Path, output_path: Path) -> None:
        arguments = [
            self._ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
        try:
            subprocess.run(
                arguments,
                shell=False,
                check=True,
                timeout=self._timeout_seconds,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise VideoProcessorNotConfiguredError(
                "Video processing is not configured."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise VideoAudioExtractionError("Video audio extraction timed out.") from exc
        except subprocess.CalledProcessError as exc:
            raise VideoAudioExtractionError("Video audio extraction failed.") from exc
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise NoUsableAudioError("No usable audio track could be extracted.")


class VideoProcessor:
    """Extract video audio temporarily, then reuse the existing AudioProcessor."""

    def __init__(self, extractor: FFmpegAudioExtractor, audio_processor: AudioProcessor) -> None:
        self._extractor = extractor
        self._audio_processor = audio_processor

    def process(self, file_path: str | Path) -> str:
        video_path = Path(file_path)
        with tempfile.TemporaryDirectory(prefix="agileflow-video-") as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            self._extractor.extract(video_path, audio_path)
            try:
                return self._audio_processor.process(audio_path)
            except TranscriptionProviderError as exc:
                raise VideoTranscriptionError(
                    "The extracted video audio could not be transcribed."
                ) from exc
            except ValueError as exc:
                raise NoUsableAudioError(
                    "No usable transcript could be produced from the video audio."
                ) from exc


class ProcessorNotConfiguredError(LookupError):
    pass


class SourceProcessorResolver:
    def __init__(
        self,
        document_processor: SourceProcessor | None = None,
        audio_processor: SourceProcessor | None = None,
        video_processor: SourceProcessor | None = None,
    ) -> None:
        self._document_processor = document_processor or DocumentProcessor()
        self._audio_processor = audio_processor
        self._video_processor = video_processor

    def resolve(self, source_type: RequirementSourceType) -> SourceProcessor:
        if source_type is RequirementSourceType.DOCUMENT:
            return self._document_processor
        if source_type is RequirementSourceType.AUDIO and self._audio_processor:
            return self._audio_processor
        if source_type is RequirementSourceType.VIDEO and self._video_processor:
            return self._video_processor
        raise ProcessorNotConfiguredError(
            f"A processor is not configured for {source_type.value} sources."
        )
