import hashlib
import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.infrastructure.storage import (
    RequirementSourceStorage,
    StoredRequirementSource,
)
from app.modules.agents.requirements.inputs.upload.service import (
    require_requirements_project,
)
from app.modules.agents.requirements.processing.audio.schemas import (
    AudioProcessingResult,
)
from app.modules.agents.requirements.processing.audio.service import (
    AudioProcessingNotFoundError,
)
from app.modules.agents.requirements.processing.facade import RequirementProcessingService
from app.modules.agents.requirements.processing.preparation.chunker import (
    DeterministicChunker,
)
from app.modules.agents.requirements.processing.preparation.constants import (
    NORMALIZER_VERSION,
)
from app.modules.agents.requirements.processing.preparation.normalizer import (
    NormalizationUnit,
    normalize_units,
)
from app.modules.agents.requirements.processing.preparation.schemas import (
    DocumentBlockReference,
    EvidenceChunkResult,
    EvidencePreparationError,
    EvidencePreparationErrorCode,
    EvidencePreparationRecord,
    EvidencePreparationStatus,
    MediaSegmentReference,
    NormalizedEvidenceResult,
    NormalizedProvenanceSpan,
)
from app.modules.agents.requirements.processing.schemas import (
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.modules.agents.requirements.processing.service import (
    DocumentProcessingNotFoundError,
)
from app.modules.agents.requirements.processing.video.schemas import (
    VideoProcessingResult,
)
from app.modules.agents.requirements.processing.video.service import (
    VideoProcessingNotFoundError,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class EvidencePreparationNotFoundError(LookupError):
    pass


class EvidencePreparationStorageError(RuntimeError):
    pass


class _SafePreparationFailure(Exception):
    def __init__(self, code: EvidencePreparationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidencePreparationService:
    _preparation_lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: RequirementSourceStorage,
        processing: RequirementProcessingService,
        chunker: DeterministicChunker,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._processing = processing
        self._chunker = chunker
        self._clock = clock

    def prepare(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> EvidencePreparationRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._preparation_lock:
            started_at = self._clock()
            parent_fingerprint = None
            try:
                parent = self._require_completed_parent(
                    agent_project_id, source_id, current_user
                )
                parent_fingerprint = self._fingerprint(parent)
                existing = self._load_valid_record(
                    stored, agent_project_id, parent_fingerprint
                )
                if (
                    not force
                    and existing is not None
                    and existing.status is EvidencePreparationStatus.COMPLETED
                    and self._load_valid_normalized(
                        stored, agent_project_id, parent_fingerprint
                    )
                    is not None
                    and self._load_valid_chunks(
                        stored, agent_project_id, parent_fingerprint
                    )
                    is not None
                ):
                    return existing

                processing = self._record(
                    stored,
                    agent_project_id,
                    EvidencePreparationStatus.PROCESSING,
                    parent_fingerprint=parent_fingerprint,
                    started_at=started_at,
                )
                self._persist_record(stored, processing)
                self._remove_results(stored)
                normalized = self._normalize(
                    stored, agent_project_id, parent, parent_fingerprint
                )
                chunks = self._chunker.chunk(normalized)
                if not chunks:
                    raise _SafePreparationFailure(
                        EvidencePreparationErrorCode.NORMALIZED_TEXT_EMPTY,
                        "The processing result did not contain usable text to prepare.",
                    )
                chunk_result = EvidenceChunkResult(
                    source_id=stored.metadata.source_id,
                    agent_project_id=agent_project_id,
                    source_type=stored.metadata.source_type,
                    source_sha256=stored.metadata.sha256,
                    parent_result_fingerprint=parent_fingerprint,
                    normalizer_version=NORMALIZER_VERSION,
                    chunker=self._chunker.configuration,
                    chunks=chunks,
                    created_at=self._clock(),
                )
                self._persist_normalized(stored, normalized)
                self._persist_chunks(stored, chunk_result)
                completed = self._record(
                    stored,
                    agent_project_id,
                    EvidencePreparationStatus.COMPLETED,
                    parent_fingerprint=parent_fingerprint,
                    started_at=started_at,
                    completed_at=chunk_result.created_at,
                )
                self._persist_record(stored, completed)
                return completed
            except _SafePreparationFailure as exc:
                failure = exc
            except (
                DocumentProcessingNotFoundError,
                AudioProcessingNotFoundError,
                VideoProcessingNotFoundError,
            ):
                failure = _SafePreparationFailure(
                    EvidencePreparationErrorCode.PARENT_PROCESSING_RESULT_UNAVAILABLE,
                    "A valid completed processing result is required before preparing evidence.",
                )
            except EvidencePreparationStorageError:
                raise
            except Exception:
                failure = _SafePreparationFailure(
                    EvidencePreparationErrorCode.PREPARATION_FAILED,
                    "The source evidence could not be prepared safely.",
                )
            failed = self._record(
                stored,
                agent_project_id,
                EvidencePreparationStatus.FAILED,
                parent_fingerprint=parent_fingerprint,
                started_at=started_at,
                completed_at=self._clock(),
                error=EvidencePreparationError(
                    code=failure.code, message=failure.message
                ),
            )
            self._persist_record(stored, failed)
            return failed

    def get_status(
        self, agent_project_id: str, source_id: str, current_user: UserPublicResponse
    ) -> EvidencePreparationRecord:
        stored = self._require_source(agent_project_id, source_id, current_user)
        with self._preparation_lock:
            try:
                parent = self._require_completed_parent(
                    agent_project_id, source_id, current_user
                )
            except (
                _SafePreparationFailure,
                DocumentProcessingNotFoundError,
                AudioProcessingNotFoundError,
                VideoProcessingNotFoundError,
            ):
                return self._record(
                    stored, agent_project_id, EvidencePreparationStatus.READY
                )
            parent_fingerprint = self._fingerprint(parent)
            record = self._load_valid_record(
                stored, agent_project_id, parent_fingerprint
            )
            if record is None:
                return self._record(
                    stored,
                    agent_project_id,
                    EvidencePreparationStatus.READY,
                    parent_fingerprint=parent_fingerprint,
                )
            if record.status is EvidencePreparationStatus.COMPLETED:
                normalized = self._load_valid_normalized(
                    stored, agent_project_id, parent_fingerprint
                )
                chunks = self._load_valid_chunks(
                    stored, agent_project_id, parent_fingerprint
                )
                if normalized is None or chunks is None:
                    record = self._invalid_result_record(
                        stored, agent_project_id, parent_fingerprint, record
                    )
            return record

    def get_normalized(
        self, agent_project_id: str, source_id: str, current_user: UserPublicResponse
    ) -> NormalizedEvidenceResult:
        with self._preparation_lock:
            stored, parent_fingerprint, record = self._completed_context(
                agent_project_id, source_id, current_user
            )
            normalized = self._load_valid_normalized(
                stored, agent_project_id, parent_fingerprint
            )
            chunks = self._load_valid_chunks(
                stored, agent_project_id, parent_fingerprint
            )
            if normalized is None or chunks is None:
                self._invalid_result_record(
                    stored, agent_project_id, parent_fingerprint, record
                )
                raise EvidencePreparationNotFoundError(source_id)
            return normalized

    def get_chunks(
        self, agent_project_id: str, source_id: str, current_user: UserPublicResponse
    ) -> EvidenceChunkResult:
        with self._preparation_lock:
            stored, parent_fingerprint, record = self._completed_context(
                agent_project_id, source_id, current_user
            )
            normalized = self._load_valid_normalized(
                stored, agent_project_id, parent_fingerprint
            )
            chunks = self._load_valid_chunks(
                stored, agent_project_id, parent_fingerprint
            )
            if normalized is None or chunks is None:
                self._invalid_result_record(
                    stored, agent_project_id, parent_fingerprint, record
                )
                raise EvidencePreparationNotFoundError(source_id)
            return chunks

    def _completed_context(self, agent_project_id, source_id, current_user):
        stored = self._require_source(agent_project_id, source_id, current_user)
        try:
            parent = self._require_completed_parent(
                agent_project_id, source_id, current_user
            )
        except (
            _SafePreparationFailure,
            DocumentProcessingNotFoundError,
            AudioProcessingNotFoundError,
            VideoProcessingNotFoundError,
        ) as exc:
            raise EvidencePreparationNotFoundError(source_id) from exc
        parent_fingerprint = self._fingerprint(parent)
        record = self._load_valid_record(stored, agent_project_id, parent_fingerprint)
        if record is None or record.status is not EvidencePreparationStatus.COMPLETED:
            raise EvidencePreparationNotFoundError(source_id)
        return stored, parent_fingerprint, record

    def _require_source(self, agent_project_id, source_id, current_user):
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        return self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            source_id=source_id,
            require_file=False,
        )

    def _require_completed_parent(self, agent_project_id, source_id, current_user):
        status = self._processing.get_status(
            agent_project_id, source_id, current_user
        )
        if status.status is not DocumentProcessingStatus.COMPLETED:
            raise _SafePreparationFailure(
                EvidencePreparationErrorCode.PARENT_PROCESSING_NOT_COMPLETED,
                "Complete source processing before preparing evidence.",
            )
        return self._processing.get_result(
            agent_project_id, source_id, current_user
        )

    def _normalize(self, stored, agent_project_id, parent, parent_fingerprint):
        units, separator = self._normalization_units(parent)
        normalized_text, mappings = normalize_units(units, separator=separator)
        if not normalized_text:
            raise _SafePreparationFailure(
                EvidencePreparationErrorCode.NORMALIZED_TEXT_EMPTY,
                "The processing result did not contain usable text to prepare.",
            )
        provenance = [
            NormalizedProvenanceSpan(
                normalized_start_offset=start,
                normalized_end_offset=end,
                parent_start_offset=unit.parent_start_offset,
                parent_end_offset=unit.parent_end_offset,
                page_numbers=list(unit.page_numbers),
                document_blocks=[
                    DocumentBlockReference(
                        block_index=block_index, block_type=block_type
                    )
                    for block_index, block_type in unit.document_blocks
                ],
                media_segments=[
                    MediaSegmentReference(
                        segment_index=index,
                        start_seconds=start_seconds,
                        end_seconds=end_seconds,
                        parent_start_offset=parent_start,
                        parent_end_offset=parent_end,
                    )
                    for (
                        index,
                        start_seconds,
                        end_seconds,
                        parent_start,
                        parent_end,
                    ) in unit.media_segments
                ],
            )
            for unit, _, start, end in mappings
        ]
        transcription_fingerprint = None
        extraction_fingerprint = None
        if isinstance(parent, (AudioProcessingResult, VideoProcessingResult)):
            transcription_fingerprint = parent.transcription.fingerprint
        if isinstance(parent, VideoProcessingResult):
            extraction_fingerprint = parent.extraction.fingerprint
        return NormalizedEvidenceResult(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_type=stored.metadata.source_type,
            source_sha256=stored.metadata.sha256,
            parent_processor_version=parent.processor_version,
            parent_result_fingerprint=parent_fingerprint,
            transcription_fingerprint=transcription_fingerprint,
            extraction_fingerprint=extraction_fingerprint,
            normalizer_version=NORMALIZER_VERSION,
            normalized_text=normalized_text,
            provenance=provenance,
            created_at=self._clock(),
        )

    def _normalization_units(self, parent):
        if isinstance(parent, DocumentProcessingResult):
            structural = parent.structural_provenance
            if parent.document_type.value == "PDF":
                return [
                    NormalizationUnit(
                        text=page.text,
                        parent_start_offset=page.start_offset,
                        parent_end_offset=page.end_offset,
                        page_numbers=(page.page_number,),
                    )
                    for page in structural.pages
                ], "\n\n"
            if parent.document_type.value == "DOCX":
                return [
                    NormalizationUnit(
                        text=block.text,
                        parent_start_offset=block.start_offset,
                        parent_end_offset=block.end_offset,
                        document_blocks=((block.block_index, block.block_type.value),),
                    )
                    for block in structural.blocks
                ], "\n\n"
            text_range = structural.text_ranges[0]
            return [
                NormalizationUnit(
                    text=text_range.text,
                    parent_start_offset=text_range.start_offset,
                    parent_end_offset=text_range.end_offset,
                )
            ], "\n\n"
        return self._media_units(parent), " "

    @staticmethod
    def _media_units(parent):
        transcript = parent.transcript
        cursor = 0
        units = []
        for index, segment in enumerate(parent.segments):
            start = transcript.find(segment.text, cursor)
            matched_text = segment.text
            if start < 0 and segment.text.strip():
                matched_text = segment.text.strip()
                start = transcript.find(matched_text, cursor)
            if start < 0:
                parent_start = parent_end = None
            else:
                parent_start = start
                parent_end = start + len(matched_text)
                cursor = parent_end
            units.append(
                NormalizationUnit(
                    text=segment.text,
                    parent_start_offset=parent_start,
                    parent_end_offset=parent_end,
                    media_segments=(
                        (
                            index,
                            segment.start_seconds,
                            segment.end_seconds,
                            parent_start,
                            parent_end,
                        ),
                    ),
                )
            )
        if units:
            return units
        return [
            NormalizationUnit(
                text=transcript,
                parent_start_offset=0,
                parent_end_offset=len(transcript),
            )
        ]

    @staticmethod
    def _fingerprint(parent) -> str:
        payload = parent.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _record(
        self,
        stored,
        agent_project_id,
        status,
        *,
        parent_fingerprint=None,
        started_at=None,
        completed_at=None,
        error=None,
    ):
        return EvidencePreparationRecord(
            source_id=stored.metadata.source_id,
            agent_project_id=agent_project_id,
            source_type=stored.metadata.source_type,
            source_sha256=stored.metadata.sha256,
            parent_result_fingerprint=parent_fingerprint,
            normalizer_version=NORMALIZER_VERSION,
            chunker=self._chunker.configuration,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            error=error,
        )

    def _load_valid_record(self, stored, agent_project_id, parent_fingerprint):
        try:
            record = EvidencePreparationRecord.model_validate_json(
                stored.preparation_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if not self._compatible(record, stored, agent_project_id, parent_fingerprint):
            return None
        return record

    def _load_valid_normalized(self, stored, agent_project_id, parent_fingerprint):
        try:
            result = NormalizedEvidenceResult.model_validate_json(
                stored.normalized_result_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if not self._compatible(result, stored, agent_project_id, parent_fingerprint):
            return None
        return result

    def _load_valid_chunks(self, stored, agent_project_id, parent_fingerprint):
        try:
            result = EvidenceChunkResult.model_validate_json(
                stored.chunk_result_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if not self._compatible(result, stored, agent_project_id, parent_fingerprint):
            return None
        return result

    def _compatible(self, value, stored, agent_project_id, parent_fingerprint):
        return (
            value.source_id == stored.metadata.source_id
            and value.agent_project_id == agent_project_id
            and value.source_type is stored.metadata.source_type
            and value.source_sha256 == stored.metadata.sha256
            and value.parent_result_fingerprint == parent_fingerprint
            and value.normalizer_version == NORMALIZER_VERSION
            and (
                not hasattr(value, "chunker")
                or value.chunker == self._chunker.configuration
            )
        )

    def _invalid_result_record(
        self, stored, agent_project_id, parent_fingerprint, record
    ):
        failed = self._record(
            stored,
            agent_project_id,
            EvidencePreparationStatus.FAILED,
            parent_fingerprint=parent_fingerprint,
            started_at=record.started_at,
            completed_at=self._clock(),
            error=EvidencePreparationError(
                code=EvidencePreparationErrorCode.PREPARATION_RESULT_INVALID,
                message="Prepared evidence is missing or incompatible. Retry preparation.",
            ),
        )
        self._persist_record(stored, failed)
        return failed

    @staticmethod
    def _persist_json(partial_path, final_path, value):
        try:
            partial_path.write_text(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            partial_path.replace(final_path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise EvidencePreparationStorageError(
                "Evidence preparation state could not be persisted"
            ) from exc

    def _persist_record(self, stored, record):
        self._persist_json(
            stored.preparation_partial_path,
            stored.preparation_path,
            record.model_dump(mode="json"),
        )

    def _persist_normalized(self, stored, result):
        self._persist_json(
            stored.normalized_result_partial_path,
            stored.normalized_result_path,
            result.model_dump(mode="json"),
        )

    def _persist_chunks(self, stored, result):
        self._persist_json(
            stored.chunk_result_partial_path,
            stored.chunk_result_path,
            result.model_dump(mode="json"),
        )

    @staticmethod
    def _remove_results(stored):
        try:
            stored.normalized_result_path.unlink(missing_ok=True)
            stored.normalized_result_partial_path.unlink(missing_ok=True)
            stored.chunk_result_path.unlink(missing_ok=True)
            stored.chunk_result_partial_path.unlink(missing_ok=True)
        except OSError as exc:
            raise EvidencePreparationStorageError(
                "Previous prepared evidence could not be replaced"
            ) from exc
