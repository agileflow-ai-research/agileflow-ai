"""Deterministic source processing for Agent 1; no model calls belong here."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from app.common.transcription_provider import SpeechToTextProvider
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


class ProcessorNotConfiguredError(LookupError):
    pass


class SourceProcessorResolver:
    def __init__(
        self,
        document_processor: SourceProcessor | None = None,
        audio_processor: SourceProcessor | None = None,
    ) -> None:
        self._document_processor = document_processor or DocumentProcessor()
        self._audio_processor = audio_processor

    def resolve(self, source_type: RequirementSourceType) -> SourceProcessor:
        if source_type is RequirementSourceType.DOCUMENT:
            return self._document_processor
        if source_type is RequirementSourceType.AUDIO and self._audio_processor:
            return self._audio_processor
        raise ProcessorNotConfiguredError(
            f"A processor is not configured for {source_type.value} sources."
        )
