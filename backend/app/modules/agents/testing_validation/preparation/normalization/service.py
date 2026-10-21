import hashlib
import json
from datetime import datetime, timezone
from threading import RLock

from app.common.document_extraction.schemas import DOCXBlockType
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.preparation.extraction.schemas import (
    Agent4DocumentExtractionResult,
    Agent4DocumentFormat,
    Agent4ExtractionStatus,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4DocumentExtractionService,
)
from app.modules.agents.testing_validation.preparation.normalization import constants
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    DocumentExtractionProvenance,
    NormalizationFailure,
    NormalizationFailureCode,
    NormalizationStatus,
    NormalizedSegment,
    NormalizedSegmentKind,
    NormalizedTestingArtifact,
)
from app.modules.agents.testing_validation.preparation.normalization.storage import (
    Agent4NormalizationStorage,
)
from app.modules.agents.testing_validation.sources.storage import StoredAgent4Source
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
)
from app.modules.auth.schemas import UserPublicResponse


NORMALIZATION_LOCK = RLock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4NormalizationService:
    def __init__(
        self,
        extraction_service: Agent4DocumentExtractionService,
        storage: Agent4NormalizationStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._extraction = extraction_service
        self._storage = storage
        self._clock = clock

    def normalize(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> NormalizedTestingArtifact:
        with AGENT4_WORKFLOW_STATE_LOCK, NORMALIZATION_LOCK:
            stored = self._extraction.require_confirmed_source(
                agent_project_id, source_id, current_user
            )
            extraction = None
            if stored.metadata.source_type is TestGenerationInputSourceType.DOCUMENT:
                extraction = self._extraction.get_existing(
                    agent_project_id, source_id, current_user
                )
            else:
                self._extraction.require_source_integrity(stored)
            artifact = self._build(stored, extraction)
            if not force:
                cached = self._storage.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(cached, artifact):
                    return cached
            self._storage.save(artifact, owner_user_id=current_user.user_id)
            return artifact

    def _build(
        self,
        stored: StoredAgent4Source,
        extraction: Agent4DocumentExtractionResult | None,
    ) -> NormalizedTestingArtifact:
        metadata = stored.metadata
        source_hash = (
            self._sha256(metadata.text_content)
            if metadata.source_type is TestGenerationInputSourceType.TEXT
            else metadata.sha256
        )
        fingerprint = self._input_fingerprint(stored, extraction, source_hash)
        artifact_id = f"A4ART-{fingerprint[:32]}"
        normalized_text = None
        structured_content = None
        segments: list[NormalizedSegment] = []
        extraction_provenance = None
        warnings = []
        truncated = False
        failure = None

        if metadata.source_type is TestGenerationInputSourceType.TEXT:
            normalized_text = metadata.text_content
            status = NormalizationStatus.READY
            usable = True
            segments = [
                self._segment(
                    artifact_id,
                    NormalizedSegmentKind.TEXT,
                    1,
                    normalized_text,
                )
            ]
        elif metadata.source_type is TestGenerationInputSourceType.IMAGE:
            status = NormalizationStatus.PENDING_ANALYSIS
            usable = False
        else:
            extraction_provenance = DocumentExtractionProvenance(
                extraction_id=extraction.extraction_id,
                document_format=extraction.document_format,
                extraction_status=extraction.status,
                extraction_schema_version=extraction.schema_version,
                extractor_name=extraction.extractor_name,
                extractor_version=extraction.extractor_version,
            )
            warnings = extraction.warnings
            truncated = extraction.truncated
            if (
                extraction.status is Agent4ExtractionStatus.FAILED
                or not extraction.extracted_text
            ):
                status = NormalizationStatus.FAILED
                usable = False
                failure = NormalizationFailure(
                    code=NormalizationFailureCode.DOCUMENT_EXTRACTION_FAILED,
                    message=(
                        "The current document extraction does not contain usable "
                        "textual context."
                    ),
                )
            else:
                normalized_text = extraction.extracted_text
                structured_content = extraction.structured_content
                status = (
                    NormalizationStatus.READY
                    if extraction.status is Agent4ExtractionStatus.SUCCESS
                    else NormalizationStatus.READY_WITH_WARNINGS
                )
                usable = True
                segments = self._document_segments(artifact_id, extraction)

        return NormalizedTestingArtifact(
            schema_version=constants.NORMALIZATION_SCHEMA_VERSION,
            normalizer_version=constants.NORMALIZER_VERSION,
            normalized_artifact_id=artifact_id,
            input_fingerprint=fingerprint,
            agent_project_id=metadata.agent_project_id,
            source_id=metadata.source_id,
            artifact_type=metadata.artifact_type,
            source_type=metadata.source_type,
            normally_supplied_by=metadata.normally_supplied_by,
            supplied_via=metadata.supplied_via,
            collection_status=metadata.collection_status,
            normalization_status=status,
            textual_context_usable=usable,
            source_evidence_sha256=source_hash,
            normalized_text=normalized_text,
            structured_content=structured_content,
            normalized_segments=segments,
            original_filename=metadata.original_filename,
            extension=metadata.extension,
            mime_type=metadata.mime_type,
            size_bytes=metadata.size_bytes,
            source_sha256=metadata.sha256,
            extraction=extraction_provenance,
            extraction_warnings=warnings,
            truncated=truncated,
            failure=failure,
            normalized_at=self._clock(),
        )

    @staticmethod
    def _input_fingerprint(stored, extraction, source_hash: str) -> str:
        metadata = stored.metadata
        payload = {
            "source_id": metadata.source_id,
            "artifact_type": metadata.artifact_type.value,
            "source_type": metadata.source_type.value,
            "normally_supplied_by": metadata.normally_supplied_by.value,
            "supplied_via": metadata.supplied_via.value,
            "collection_status": metadata.collection_status.value,
            "label": metadata.label,
            "source_evidence_sha256": source_hash,
            "normalizer_version": constants.NORMALIZER_VERSION,
            "schema_version": constants.NORMALIZATION_SCHEMA_VERSION,
        }
        if extraction is not None:
            payload["extraction"] = {
                "extraction_id": extraction.extraction_id,
                "schema_version": extraction.schema_version,
                "extractor_name": extraction.extractor_name,
                "extractor_version": extraction.extractor_version,
                "status": extraction.status.value,
                "extracted_text_sha256": Agent4NormalizationService._sha256(
                    extraction.extracted_text
                ),
                "structured_content_sha256": Agent4NormalizationService._sha256(
                    json.dumps(
                        extraction.structured_content,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                ),
                "warnings": [
                    item.model_dump(mode="json") for item in extraction.warnings
                ],
                "truncated": extraction.truncated,
            }
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return Agent4NormalizationService._sha256(canonical)

    @staticmethod
    def _document_segments(artifact_id, extraction):
        if extraction.document_format is Agent4DocumentFormat.PDF:
            return [
                Agent4NormalizationService._segment(
                    artifact_id,
                    NormalizedSegmentKind.PDF_PAGE,
                    position,
                    page.text,
                    page_number=page.page_number,
                )
                for position, page in enumerate(extraction.pages, 1)
            ]
        if extraction.document_format is Agent4DocumentFormat.DOCX:
            segments = []
            for position, block in enumerate(extraction.blocks, 1):
                kind = {
                    DOCXBlockType.HEADING: NormalizedSegmentKind.DOCX_HEADING,
                    DOCXBlockType.PARAGRAPH: NormalizedSegmentKind.DOCX_PARAGRAPH,
                    DOCXBlockType.TABLE: NormalizedSegmentKind.DOCX_TABLE,
                }[block.type]
                text = (
                    "\n".join("\t".join(row) for row in block.rows)
                    if block.rows is not None
                    else block.text
                )
                segments.append(
                    Agent4NormalizationService._segment(
                        artifact_id,
                        kind,
                        position,
                        text,
                        block_index=block.block_index,
                        heading_level=block.level,
                        table_rows=block.rows,
                    )
                )
            return segments
        kind = (
            NormalizedSegmentKind.STRUCTURED_DOCUMENT
            if extraction.document_format
            in {
                Agent4DocumentFormat.JSON,
                Agent4DocumentFormat.YAML,
                Agent4DocumentFormat.YML,
            }
            else NormalizedSegmentKind.DOCUMENT_TEXT
        )
        return [
            Agent4NormalizationService._segment(
                artifact_id, kind, 1, extraction.extracted_text
            )
        ]

    @staticmethod
    def _segment(
        artifact_id,
        kind,
        position,
        text,
        *,
        page_number=None,
        block_index=None,
        heading_level=None,
        table_rows=None,
    ):
        identity = json.dumps(
            {
                "artifact_id": artifact_id,
                "kind": kind.value,
                "position": position,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return NormalizedSegment(
            segment_id=f"A4SEG-{Agent4NormalizationService._sha256(identity)[:32]}",
            kind=kind,
            position=position,
            text=text,
            text_sha256=Agent4NormalizationService._sha256(text),
            page_number=page_number,
            block_index=block_index,
            heading_level=heading_level,
            table_rows=table_rows,
        )

    @staticmethod
    def _cache_is_current(cached, expected):
        if cached is None:
            return False
        return cached.model_copy(update={"normalized_at": expected.normalized_at}) == expected

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
