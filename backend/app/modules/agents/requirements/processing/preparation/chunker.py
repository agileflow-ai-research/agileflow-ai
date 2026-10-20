import hashlib
import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from threading import Lock

from app.modules.agents.requirements.processing.preparation.constants import (
    CHUNKER_VERSION,
)
from app.modules.agents.requirements.processing.preparation.schemas import (
    ChunkerConfiguration,
    EvidenceChunk,
    NormalizedEvidenceResult,
    NormalizedProvenanceSpan,
)


@dataclass(frozen=True)
class SentenceSpan:
    start: int
    end: int


class SentenceSegmenter:
    """Lazy local spaCy sentencizer with a deterministic no-model fallback."""

    def __init__(self) -> None:
        self._pipeline = None
        self._lock = Lock()
        try:
            self._spacy_version = version("spacy")
        except PackageNotFoundError:
            self._spacy_version = None

    @property
    def identity(self) -> tuple[str, str]:
        if self._spacy_version:
            return "spacy_blank_en_sentencizer", self._spacy_version
        return "deterministic_sentence_fallback", "1"

    def segment(self, text: str) -> list[SentenceSpan]:
        if not text:
            return []
        if self._spacy_version:
            pipeline = self._get_pipeline()
            return [SentenceSpan(sentence.start_char, sentence.end_char) for sentence in pipeline(text).sents]
        spans: list[SentenceSpan] = []
        start = 0
        for match in re.finditer(r"(?<=[.!?])(?:[\"')\]]*)\s+|\n+", text):
            end = match.start()
            if text[start:end].strip():
                left = start + len(text[start:end]) - len(text[start:end].lstrip())
                right = end - (len(text[start:end]) - len(text[start:end].rstrip()))
                spans.append(SentenceSpan(left, right))
            start = match.end()
        if text[start:].strip():
            left = start + len(text[start:]) - len(text[start:].lstrip())
            spans.append(SentenceSpan(left, len(text.rstrip())))
        return spans or [SentenceSpan(0, len(text))]

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        with self._lock:
            if self._pipeline is None:
                import spacy

                self._pipeline = spacy.blank("en")
                self._pipeline.add_pipe("sentencizer")
        return self._pipeline


def build_chunker_configuration(
    *, target_chars: int, max_chars: int, overlap_sentences: int, segmenter: SentenceSegmenter
) -> ChunkerConfiguration:
    segmenter_name, segmenter_version = segmenter.identity
    values = {
        "chunker_version": CHUNKER_VERSION,
        "target_chars": target_chars,
        "max_chars": max_chars,
        "overlap_sentences": overlap_sentences,
        "sentence_segmenter": segmenter_name,
        "sentence_segmenter_version": segmenter_version,
    }
    fingerprint = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ChunkerConfiguration(**values, fingerprint=fingerprint)


class DeterministicChunker:
    def __init__(self, configuration: ChunkerConfiguration, segmenter: SentenceSegmenter):
        self.configuration = configuration
        self._segmenter = segmenter

    def chunk(self, normalized: NormalizedEvidenceResult) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        for provenance in normalized.provenance:
            if provenance.normalized_end_offset <= provenance.normalized_start_offset:
                continue
            unit_text = normalized.normalized_text[
                provenance.normalized_start_offset : provenance.normalized_end_offset
            ]
            sentence_spans = self._bounded_sentences(unit_text)
            for local_start, local_end in self._group_sentences(sentence_spans):
                start = provenance.normalized_start_offset + local_start
                end = provenance.normalized_start_offset + local_end
                content = normalized.normalized_text[start:end]
                chunk_provenance = provenance.model_copy(
                    update={
                        "normalized_start_offset": start,
                        "normalized_end_offset": end,
                    }
                )
                chunks.append(
                    EvidenceChunk(
                        chunk_id=self._chunk_id(
                            normalized, start, end, content, chunk_provenance
                        ),
                        content=content,
                        normalized_start_offset=start,
                        normalized_end_offset=end,
                        provenance=[chunk_provenance],
                    )
                )
        return chunks

    def _bounded_sentences(self, text: str) -> list[SentenceSpan]:
        bounded: list[SentenceSpan] = []
        for sentence in self._segmenter.segment(text):
            start = sentence.start
            while sentence.end - start > self.configuration.max_chars:
                limit = start + self.configuration.max_chars
                split_at = text.rfind(" ", start, limit + 1)
                if split_at <= start:
                    split_at = limit
                bounded.append(SentenceSpan(start, split_at))
                start = split_at
                while start < sentence.end and text[start].isspace():
                    start += 1
            if start < sentence.end:
                bounded.append(SentenceSpan(start, sentence.end))
        return bounded

    def _group_sentences(self, sentences: list[SentenceSpan]) -> list[tuple[int, int]]:
        if not sentences:
            return []
        groups: list[tuple[int, int]] = []
        index = 0
        while index < len(sentences):
            end_index = index
            while end_index + 1 < len(sentences):
                candidate_length = sentences[end_index + 1].end - sentences[index].start
                if candidate_length > self.configuration.target_chars:
                    break
                end_index += 1
            groups.append((sentences[index].start, sentences[end_index].end))
            next_index = end_index + 1
            if next_index >= len(sentences):
                break
            overlap = min(
                self.configuration.overlap_sentences,
                max(0, end_index - index),
            )
            index = next_index - overlap
        return groups

    def _chunk_id(
        self,
        normalized: NormalizedEvidenceResult,
        start: int,
        end: int,
        content: str,
        provenance: NormalizedProvenanceSpan,
    ) -> str:
        identity = {
            "agent_project_id": normalized.agent_project_id,
            "source_id": normalized.source_id,
            "parent_result_fingerprint": normalized.parent_result_fingerprint,
            "normalizer_version": normalized.normalizer_version,
            "chunker_fingerprint": self.configuration.fingerprint,
            "normalized_range": [start, end],
            "content": content,
            "provenance": provenance.model_dump(mode="json"),
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return f"CHK-{digest[:16].upper()}"
