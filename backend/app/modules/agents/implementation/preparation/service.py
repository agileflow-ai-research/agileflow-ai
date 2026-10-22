import hashlib
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.inputs.extraction.schemas import (
    DocumentExtractionResult, DocumentType, ExtractionStatus,
)
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService, ExtractionNotFoundError, UnsupportedExtractionSourceError,
)
from app.modules.agents.implementation.inputs.upload.service import require_implementation_project
from app.modules.agents.implementation.infrastructure.storage import ImplementationUploadStorage, StagedUpload
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService
from . import constants
from .chunking.chunker import DraftChunk, chunk_unstructured
from .schemas import (
    ArtifactDetectionLabel, ChunkContext, ChunkMetrics, ChunkProvenance,
    ChunkWarningCode, ChunkingStatus, DocumentChunkingResult,
    DocumentRuleDetectionResult, RuleDetectionMetrics, RuleStrength,
    SemanticChunk,
)
from .classification.rule_based.detector import detect_chunk, strength_for_score
from .chunking.structured_chunker import chunk_structured
from .chunking.tokenizer import count_tokens, normalize_text


class ChunkingNotFoundError(LookupError):
    pass


class ChunkingUnavailableError(ValueError):
    pass


class ChunkingStorageError(RuntimeError):
    pass


class RuleDetectionNotFoundError(LookupError):
    pass


class RuleDetectionStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SemanticChunkingService:
    _lock = Lock()

    def __init__(self, standalone_service: StandaloneService, storage: ImplementationUploadStorage, *, clock=utc_now) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, upload_id: str, current_user: UserPublicResponse, *, force: bool = False) -> DocumentChunkingResult:
        project, staged = self._resolve(agent_project_id, upload_id, current_user)
        with self._lock:
            extraction = self._load_extraction(staged, project.agent_project_id)
            if not force:
                cached = self._load_valid_cache(staged, project.agent_project_id, extraction)
                if cached is not None:
                    return cached
            result = self._build_result(extraction)
            self._persist(staged, result)
            return result

    def get_existing(self, agent_project_id: str, upload_id: str, current_user: UserPublicResponse) -> DocumentChunkingResult:
        project, staged = self._resolve(agent_project_id, upload_id, current_user)
        extraction = self._load_extraction(staged, project.agent_project_id)
        cached = self._load_valid_cache(staged, project.agent_project_id, extraction)
        if cached is None:
            raise ChunkingNotFoundError(upload_id)
        return cached

    def _resolve(self, agent_project_id: str, upload_id: str, current_user: UserPublicResponse):
        project = require_implementation_project(self._standalone, agent_project_id, current_user)
        staged = self._storage.locate(agent_project_id=project.agent_project_id, owner_user_id=current_user.user_id, upload_id=upload_id)
        DocumentExtractionService._require_document(staged)
        return project, staged

    @staticmethod
    def _load_extraction(staged: StagedUpload, agent_project_id: str) -> DocumentExtractionResult:
        result = DocumentExtractionService._load_valid_cache(staged, agent_project_id)
        if result is None:
            raise ExtractionNotFoundError(staged.metadata.upload_id)
        if result.status is ExtractionStatus.FAILED:
            raise ChunkingUnavailableError("A failed extraction cannot be chunked")
        return result

    def _build_result(self, extraction: DocumentExtractionResult) -> DocumentChunkingResult:
        if extraction.document_type in {DocumentType.JSON, DocumentType.YAML}:
            drafts, warnings = chunk_structured(extraction.content.structured_content)
        else:
            drafts, warnings = chunk_unstructured(extraction)
        if extraction.status is ExtractionStatus.PARTIAL:
            warnings.insert(0, ChunkWarningCode.SOURCE_EXTRACTION_PARTIAL)
        drafts = [draft for draft in drafts if normalize_text(draft.text)]
        if len(drafts) > constants.MAX_CHUNKS_PER_DOCUMENT:
            drafts = drafts[: constants.MAX_CHUNKS_PER_DOCUMENT]
            warnings.append(ChunkWarningCode.CONTENT_TRUNCATED)
        chunks = [self._finalize(extraction, draft, index) for index, draft in enumerate(drafts)]
        warnings = list(dict.fromkeys(warnings))
        if not chunks:
            warnings.append(ChunkWarningCode.NO_USABLE_CONTENT)
        counts = [chunk.token_count for chunk in chunks]
        status = ChunkingStatus.FAILED if not chunks else (ChunkingStatus.PARTIAL if warnings else ChunkingStatus.SUCCESS)
        total = sum(counts)
        return DocumentChunkingResult(
            upload_id=extraction.upload_id, agent_project_id=extraction.agent_project_id,
            source_sha256=extraction.source_sha256, document_type=extraction.document_type,
            extraction_version=extraction.extractor_version, chunker_version=constants.CHUNKER_VERSION,
            status=status,
            metrics=ChunkMetrics(chunk_count=len(chunks), total_lexical_tokens=total,
                average_chunk_tokens=round(total / len(chunks), 2) if chunks else 0,
                min_chunk_tokens=min(counts, default=0), max_chunk_tokens=max(counts, default=0)),
            warnings=warnings, chunks=chunks, created_at=self._clock(),
        )

    @staticmethod
    def _finalize(extraction: DocumentExtractionResult, draft: DraftChunk, index: int) -> SemanticChunk:
        text = normalize_text(draft.text)
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        chunk_id = SemanticChunkingService._chunk_id(
            extraction.upload_id, extraction.source_sha256, index, text_hash,
            draft.page_start, draft.page_end, draft.block_start, draft.block_end,
            draft.line_start, draft.line_end, draft.structured_path,
        )
        return SemanticChunk(
            chunk_id=chunk_id, chunk_index=index, text=text, text_hash=text_hash,
            token_count=count_tokens(text), character_count=len(text),
            context=ChunkContext(heading_path=draft.heading_path,
                section_title=draft.heading_path[-1] if draft.heading_path else None,
                heading_depth=len(draft.heading_path), structure_type=draft.structure_type,
                structural_warning=draft.structural_warning),
            provenance=ChunkProvenance(upload_id=extraction.upload_id,
                agent_project_id=extraction.agent_project_id,
                original_filename=extraction.original_filename,
                source_sha256=extraction.source_sha256, document_type=extraction.document_type,
                page_start=draft.page_start, page_end=draft.page_end,
                block_start=draft.block_start, block_end=draft.block_end,
                line_start=draft.line_start, line_end=draft.line_end,
                structured_path=draft.structured_path),
        )

    @staticmethod
    def _chunk_id(upload_id, source_sha256, index, text_hash, page_start, page_end,
                  block_start, block_end, line_start, line_end, structured_path) -> str:
        identity = "\0".join((
            upload_id, source_sha256, constants.CHUNKER_VERSION, str(index), text_hash,
            str(page_start), str(page_end), str(block_start), str(block_end),
            str(line_start), str(line_end), structured_path or "",
        ))
        return "CHK-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20].upper()

    @staticmethod
    def _load_valid_cache(staged: StagedUpload, agent_project_id: str, extraction: DocumentExtractionResult) -> DocumentChunkingResult | None:
        try:
            result = DocumentChunkingResult.model_validate_json(staged.chunks_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.upload_id != staged.metadata.upload_id or result.agent_project_id != agent_project_id
            or result.source_sha256 != staged.metadata.sha256 or result.document_type != extraction.document_type
            or result.extraction_version != extraction.extractor_version
            or result.chunker_version != constants.CHUNKER_VERSION
        ):
            return None
        counts: list[int] = []
        for index, chunk in enumerate(result.chunks):
            provenance = chunk.provenance
            normalized = normalize_text(chunk.text)
            text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            expected_id = SemanticChunkingService._chunk_id(
                result.upload_id, result.source_sha256, index, text_hash,
                provenance.page_start, provenance.page_end,
                provenance.block_start, provenance.block_end,
                provenance.line_start, provenance.line_end,
                provenance.structured_path,
            )
            if (
                chunk.chunk_index != index or chunk.text != normalized
                or chunk.text_hash != text_hash or chunk.chunk_id != expected_id
                or chunk.token_count != count_tokens(chunk.text)
                or chunk.character_count != len(chunk.text)
                or provenance.upload_id != result.upload_id
                or provenance.agent_project_id != result.agent_project_id
                or provenance.source_sha256 != result.source_sha256
                or provenance.document_type != result.document_type
                or provenance.original_filename != staged.metadata.original_filename
            ):
                return None
            counts.append(chunk.token_count)
        total = sum(counts)
        metrics = result.metrics
        if (
            metrics.chunk_count != len(result.chunks)
            or metrics.total_lexical_tokens != total
            or metrics.average_chunk_tokens != (round(total / len(counts), 2) if counts else 0)
            or metrics.min_chunk_tokens != min(counts, default=0)
            or metrics.max_chunk_tokens != max(counts, default=0)
        ):
            return None
        return result

    @staticmethod
    def _persist(staged: StagedUpload, result: DocumentChunkingResult) -> None:
        try:
            staged.chunks_partial_path.write_text(result.model_dump_json(), encoding="utf-8")
            staged.chunks_partial_path.replace(staged.chunks_path)
        except OSError as exc:
            try:
                staged.chunks_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ChunkingStorageError("Semantic chunk sidecar could not be stored") from exc


class RuleDetectionService:
    _lock = Lock()

    def __init__(self, standalone_service: StandaloneService,
                 storage: ImplementationUploadStorage, *, clock=utc_now) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, upload_id: str,
              current_user: UserPublicResponse, *, force: bool = False
              ) -> DocumentRuleDetectionResult:
        project, staged, chunks = self._resolve(
            agent_project_id, upload_id, current_user
        )
        with self._lock:
            if not force:
                cached = self._load_valid_cache(
                    staged, project.agent_project_id, chunks
                )
                if cached is not None:
                    return cached
            detections = [detect_chunk(chunk) for chunk in chunks.chunks]
            result = DocumentRuleDetectionResult(
                upload_id=chunks.upload_id,
                agent_project_id=chunks.agent_project_id,
                original_filename=staged.metadata.original_filename,
                source_sha256=chunks.source_sha256,
                document_type=chunks.document_type,
                extraction_version=chunks.extraction_version,
                chunker_version=chunks.chunker_version,
                rule_detector_version=constants.RULE_DETECTOR_VERSION,
                metrics=self._metrics(detections),
                detections=detections,
                created_at=self._clock(),
            )
            self._persist(staged, result)
            return result

    def get_existing(self, agent_project_id: str, upload_id: str,
                     current_user: UserPublicResponse
                     ) -> DocumentRuleDetectionResult:
        project, staged, chunks = self._resolve(
            agent_project_id, upload_id, current_user
        )
        cached = self._load_valid_cache(
            staged, project.agent_project_id, chunks
        )
        if cached is None:
            raise RuleDetectionNotFoundError(upload_id)
        return cached

    def _resolve(self, agent_project_id: str, upload_id: str,
                 current_user: UserPublicResponse):
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        staged = self._storage.locate(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            upload_id=upload_id,
        )
        DocumentExtractionService._require_document(staged)
        extraction = SemanticChunkingService._load_extraction(
            staged, project.agent_project_id
        )
        chunks = SemanticChunkingService._load_valid_cache(
            staged, project.agent_project_id, extraction
        )
        if chunks is None or chunks.status is ChunkingStatus.FAILED:
            raise ChunkingNotFoundError(upload_id)
        return project, staged, chunks

    @staticmethod
    def _metrics(detections) -> RuleDetectionMetrics:
        counts = {label: 0 for label in ArtifactDetectionLabel}
        strengths = {strength: 0 for strength in RuleStrength}
        prediction_count = 0
        classified = 0
        for detection in detections:
            if detection.unclassified:
                counts[ArtifactDetectionLabel.OTHER_CONTEXT] += 1
                continue
            classified += 1
            for prediction in detection.predictions:
                counts[prediction.label] += 1
                strengths[prediction.strength] += 1
                prediction_count += 1
        return RuleDetectionMetrics(
            chunk_count=len(detections),
            classified_chunk_count=classified,
            other_context_chunk_count=len(detections) - classified,
            prediction_count=prediction_count,
            per_label_counts=counts,
            strong_prediction_count=strengths[RuleStrength.STRONG],
            moderate_prediction_count=strengths[RuleStrength.MODERATE],
            weak_prediction_count=strengths[RuleStrength.WEAK],
        )

    @staticmethod
    def _load_valid_cache(staged: StagedUpload, agent_project_id: str,
                          chunks: DocumentChunkingResult
                          ) -> DocumentRuleDetectionResult | None:
        try:
            result = DocumentRuleDetectionResult.model_validate_json(
                staged.rule_detections_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.upload_id != chunks.upload_id
            or result.agent_project_id != agent_project_id
            or result.original_filename != staged.metadata.original_filename
            or result.source_sha256 != chunks.source_sha256
            or result.document_type != chunks.document_type
            or result.extraction_version != chunks.extraction_version
            or result.chunker_version != chunks.chunker_version
            or result.rule_detector_version != constants.RULE_DETECTOR_VERSION
            or len(result.detections) != len(chunks.chunks)
        ):
            return None
        for detection, chunk in zip(result.detections, chunks.chunks, strict=True):
            if detection.chunk_id != chunk.chunk_id or detection.text_hash != chunk.text_hash:
                return None
            if len(detection.predictions) > constants.MAX_LABELS_PER_CHUNK:
                return None
            for prediction in detection.predictions:
                if prediction.strength is not strength_for_score(prediction.rule_score):
                    return None
        if result.metrics != RuleDetectionService._metrics(result.detections):
            return None
        return result

    @staticmethod
    def _persist(staged: StagedUpload,
                 result: DocumentRuleDetectionResult) -> None:
        try:
            staged.rule_detections_partial_path.write_text(
                result.model_dump_json(), encoding="utf-8"
            )
            staged.rule_detections_partial_path.replace(
                staged.rule_detections_path
            )
        except OSError as exc:
            try:
                staged.rule_detections_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuleDetectionStorageError(
                "Rule-detection sidecar could not be stored"
            ) from exc
