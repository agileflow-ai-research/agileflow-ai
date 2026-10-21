import hashlib
import json
import re
from dataclasses import dataclass, field

from app.modules.agents.testing_validation.preparation.chunking import constants
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunk,
    TestingChunkSourceSpan,
)
from app.modules.agents.testing_validation.preparation.chunking.tokenizer import (
    bounded_token_slices,
    count_tokens,
)
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizationStatus,
    NormalizedSegment,
    NormalizedSegmentKind,
    NormalizedTestingArtifact,
)


MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class DraftChunk:
    text: str
    source_spans: list[TestingChunkSourceSpan]
    heading_path: list[str] = field(default_factory=list)
    structure_type: str = "TEXT"
    overlap_token_count: int = 0
    allow_combine: bool = True


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _span(
    segment: NormalizedSegment,
    start: int = 0,
    end: int | None = None,
    *,
    structured_path: str | None = None,
) -> TestingChunkSourceSpan:
    return TestingChunkSourceSpan(
        source_segment_id=segment.segment_id,
        segment_kind=segment.kind,
        start_offset=start,
        end_offset=len(segment.text) if end is None else end,
        page_number=segment.page_number,
        block_index=segment.block_index,
        structured_path=structured_path,
    )


def _paragraph_units(segment: NormalizedSegment) -> list[tuple[str, int, int]]:
    matches = list(
        re.finditer(r"\S(?:.*?\S)?(?=\n[ \t]*\n|\Z)", segment.text, re.DOTALL)
    )
    if not matches and segment.text.strip():
        start = len(segment.text) - len(segment.text.lstrip())
        end = len(segment.text.rstrip())
        return [(segment.text[start:end], start, end)]
    return [(match.group(), match.start(), match.end()) for match in matches]


def _text_heading(value: str) -> tuple[str, int] | None:
    if "\n" in value or len(value) > 120:
        return None
    markdown = MARKDOWN_HEADING.match(value)
    if markdown:
        return markdown.group(2).strip(), len(markdown.group(1))
    stripped = value.strip().rstrip(":")
    words = stripped.split()
    if value.rstrip().endswith(":") and 1 <= len(words) <= 8:
        return stripped, 1
    if 2 <= len(words) <= 10 and stripped == stripped.upper() and any(
        character.isalpha() for character in stripped
    ):
        return stripped, 1
    return None


def _update_heading(path: list[str], title: str, level: int) -> list[str]:
    return path[: level - 1] + [title]


def _natural_units(artifact: NormalizedTestingArtifact) -> list[DraftChunk]:
    segments = artifact.normalized_segments
    if not segments:
        return []
    if segments[0].kind in {
        NormalizedSegmentKind.TEXT,
        NormalizedSegmentKind.DOCUMENT_TEXT,
    }:
        units: list[DraftChunk] = []
        heading_path: list[str] = []
        pending: list[tuple[NormalizedSegment, str, int, int]] = []
        for segment in segments:
            for text, start, end in _paragraph_units(segment):
                heading = _text_heading(text)
                if heading:
                    heading_path = _update_heading(heading_path, *heading)
                    pending.append((segment, text, start, end))
                    continue
                spans = [_span(segment, start, end)]
                value = text
                if pending:
                    value = "\n\n".join([*(item[1] for item in pending), text])
                    spans = [
                        _span(item[0], item[2], item[3]) for item in pending
                    ] + spans
                    pending = []
                units.append(
                    DraftChunk(value, spans, heading_path.copy(), "PARAGRAPH")
                )
        for segment, text, start, end in pending:
            units.append(
                DraftChunk(
                    text,
                    [_span(segment, start, end)],
                    heading_path.copy(),
                    "HEADING",
                )
            )
        return units

    if segments[0].kind is NormalizedSegmentKind.PDF_PAGE:
        return [
            DraftChunk(
                segment.text,
                [_span(segment)],
                structure_type="PDF_PAGE",
                allow_combine=False,
            )
            for segment in segments
            if segment.text.strip()
        ]

    if any(
        segment.kind
        in {
            NormalizedSegmentKind.DOCX_HEADING,
            NormalizedSegmentKind.DOCX_PARAGRAPH,
            NormalizedSegmentKind.DOCX_TABLE,
        }
        for segment in segments
    ):
        units = []
        heading_path: list[str] = []
        pending: list[NormalizedSegment] = []
        for segment in segments:
            if segment.kind is NormalizedSegmentKind.DOCX_HEADING:
                heading_path = _update_heading(
                    heading_path, segment.text, segment.heading_level or 1
                )
                pending.append(segment)
                continue
            value = segment.text
            spans = [_span(segment)]
            if pending:
                value = "\n\n".join(
                    [*(heading.text for heading in pending), segment.text]
                )
                spans = [_span(heading) for heading in pending] + spans
                pending = []
            structure = (
                "DOCX_TABLE"
                if segment.kind is NormalizedSegmentKind.DOCX_TABLE
                else "DOCX_SECTION"
            )
            units.append(DraftChunk(value, spans, heading_path.copy(), structure))
        for heading in pending:
            units.append(
                DraftChunk(
                    heading.text,
                    [_span(heading)],
                    heading_path.copy(),
                    "DOCX_HEADING",
                )
            )
        return units

    return [
        DraftChunk(
            segment.text,
            [_span(segment, structured_path="$")],
            structure_type="STRUCTURED",
            allow_combine=False,
        )
        for segment in segments
        if segment.text.strip()
    ]


def _bounded(unit: DraftChunk) -> list[DraftChunk]:
    if count_tokens(unit.text) <= constants.MAX_CHUNK_TOKENS:
        return [unit]
    slices = bounded_token_slices(
        unit.text,
        maximum=constants.MAX_CHUNK_TOKENS,
        overlap=constants.OVERLAP_TOKENS,
    )
    single_span = len(unit.source_spans) == 1
    result = []
    for item in slices:
        spans = unit.source_spans
        if single_span:
            parent = unit.source_spans[0]
            spans = [
                parent.model_copy(
                    update={
                        "start_offset": parent.start_offset + item.start_offset,
                        "end_offset": parent.start_offset + item.end_offset,
                    }
                )
            ]
        result.append(
            DraftChunk(
                text=item.text,
                source_spans=spans,
                heading_path=unit.heading_path,
                structure_type=unit.structure_type,
                overlap_token_count=item.overlap_token_count,
                allow_combine=False,
            )
        )
    return result


def _pack(units: list[DraftChunk]) -> list[DraftChunk]:
    chunks: list[DraftChunk] = []
    for unit in units:
        for part in _bounded(unit):
            previous = chunks[-1] if chunks else None
            candidate = f"{previous.text}\n\n{part.text}" if previous else part.text
            if (
                previous is not None
                and previous.allow_combine
                and part.allow_combine
                and previous.heading_path == part.heading_path
                and previous.structure_type == part.structure_type
                and count_tokens(candidate) <= constants.TARGET_CHUNK_TOKENS
            ):
                previous.text = candidate
                previous.source_spans.extend(part.source_spans)
            else:
                chunks.append(part)
    return chunks


def build_chunks(
    artifact: NormalizedTestingArtifact,
    *,
    policy_fingerprint: str,
) -> list[TestingChunk]:
    drafts = _pack(_natural_units(artifact))
    if len(drafts) > constants.MAX_CHUNKS_PER_ARTIFACT:
        raise ValueError("Normalized artifact exceeds the chunk-count safety limit")
    warning_codes = sorted(
        {
            *(warning.code for warning in artifact.extraction_warnings),
            *(
                ["NORMALIZED_INPUT_TRUNCATED"]
                if artifact.truncated
                else []
            ),
            *(
                ["NORMALIZED_INPUT_READY_WITH_WARNINGS"]
                if artifact.normalization_status
                is NormalizationStatus.READY_WITH_WARNINGS
                else []
            ),
        }
    )
    chunks = []
    for draft in drafts:
        token_count = count_tokens(draft.text)
        if not draft.text.strip() or token_count == 0:
            continue
        sequence = len(chunks) + 1
        identity = json.dumps(
            {
                "normalized_artifact_id": artifact.normalized_artifact_id,
                "normalization_fingerprint": artifact.input_fingerprint,
                "sequence": sequence,
                "text_sha256": _sha256(draft.text),
                "source_spans": [
                    span.model_dump(mode="json") for span in draft.source_spans
                ],
                "policy_fingerprint": policy_fingerprint,
                "chunker_version": constants.CHUNKER_VERSION,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        chunks.append(
            TestingChunk(
                chunk_id=f"A4CHK-{_sha256(identity)[:32]}",
                agent_project_id=artifact.agent_project_id,
                source_id=artifact.source_id,
                normalized_artifact_id=artifact.normalized_artifact_id,
                artifact_type=artifact.artifact_type,
                source_type=artifact.source_type,
                sequence=sequence,
                heading_path=draft.heading_path,
                structure_type=draft.structure_type,
                text=draft.text,
                text_sha256=_sha256(draft.text),
                token_count=token_count,
                overlap_token_count=draft.overlap_token_count,
                source_segment_ids=list(
                    dict.fromkeys(
                        span.source_segment_id for span in draft.source_spans
                    )
                ),
                source_spans=draft.source_spans,
                source_evidence_sha256=artifact.source_evidence_sha256,
                normalization_fingerprint=artifact.input_fingerprint,
                inherited_warning_codes=warning_codes,
            )
        )
    return chunks
