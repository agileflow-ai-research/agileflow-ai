from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
)
from app.modules.agents.implementation.preparation import constants as chunk_constants
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
    ChunkingStatus,
    DocumentChunkingResult,
)
from app.modules.agents.implementation.preparation.service import (
    ChunkingNotFoundError,
    SemanticChunkingService,
)
from app.modules.agents.implementation.inputs.upload.service import require_implementation_project
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
    StagedUpload,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from .classifier import ClassificationOutcome, ZeroShotClassifier
from .constants import (
    HYPOTHESIS_TEMPLATE,
    MODEL_ID,
    MODEL_REVISION,
    MODEL_TASK,
    ZERO_SHOT_CLASSIFIER_VERSION,
    ZERO_SHOT_LABEL_MAP_VERSION,
    ZERO_SHOT_TEMPLATE_VERSION,
)
from .model_loader import ZeroShotModelUnavailableError
from .schemas import (
    ChunkZeroShotDetection,
    DocumentZeroShotDetectionResult,
    ZeroShotMetrics,
    ZeroShotModelMetadata,
    ZeroShotStatus,
    ZeroShotWarning,
    ZeroShotWarningCode,
)


class ZeroShotDetectionNotFoundError(LookupError):
    pass


class ZeroShotDetectionStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ZeroShotDetectionService:
    _lock = Lock()

    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: ImplementationUploadStorage,
        classifier: ZeroShotClassifier,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._classifier = classifier
        self._clock = clock

    def build(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> DocumentZeroShotDetectionResult:
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
            try:
                loaded, outcomes = self._classifier.classify_chunks(chunks.chunks)
            except ZeroShotModelUnavailableError:
                return self._model_unavailable(staged, chunks)
            result = self._result(
                staged, chunks, loaded.device, outcomes
            )
            self._persist(staged, result)
            return result

    def get_existing(
        self,
        agent_project_id: str,
        upload_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentZeroShotDetectionResult:
        project, staged, chunks = self._resolve(
            agent_project_id, upload_id, current_user
        )
        cached = self._load_valid_cache(
            staged, project.agent_project_id, chunks
        )
        if cached is None:
            raise ZeroShotDetectionNotFoundError(upload_id)
        return cached

    def _resolve(self, agent_project_id, upload_id, current_user):
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
    def _metadata(device: str) -> ZeroShotModelMetadata:
        return ZeroShotModelMetadata(
            model_id=MODEL_ID,
            revision=MODEL_REVISION,
            task=MODEL_TASK,
            hypothesis_template=HYPOTHESIS_TEMPLATE,
            multi_label=True,
            label_map_version=ZERO_SHOT_LABEL_MAP_VERSION,
            template_version=ZERO_SHOT_TEMPLATE_VERSION,
            device=device,
        )

    def _result(self, staged, chunks, device, outcomes):
        warnings: list[ZeroShotWarning] = []
        records: list[ChunkZeroShotDetection] = []
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks.chunks}
        for outcome in outcomes:
            source_chunk = chunk_by_id[outcome.chunk_id]
            records.append(ChunkZeroShotDetection(
                chunk_id=outcome.chunk_id,
                text_hash=outcome.text_hash,
                provenance=source_chunk.provenance,
                model_token_count=outcome.model_token_count,
                model_max_length=outcome.model_max_length,
                input_truncated=outcome.input_truncated,
                classification_succeeded=not outcome.error,
                inference_ms=outcome.inference_ms,
                scores=outcome.scores,
                display_predictions=outcome.display_predictions,
            ))
            if outcome.input_truncated:
                warnings.append(ZeroShotWarning(
                    code=ZeroShotWarningCode.MODEL_INPUT_TRUNCATED,
                    message="The chunk exceeded the model input length and was explicitly truncated for inference.",
                    chunk_id=outcome.chunk_id,
                ))
            if outcome.error:
                warnings.append(ZeroShotWarning(
                    code=ZeroShotWarningCode.CHUNK_CLASSIFICATION_FAILED,
                    message="This chunk could not be classified by the local zero-shot model.",
                    chunk_id=outcome.chunk_id,
                ))
        metrics = self._metrics(records)
        status = (
            ZeroShotStatus.FAILED
            if metrics.classified_chunk_count == 0
            else ZeroShotStatus.PARTIAL
            if warnings
            else ZeroShotStatus.SUCCESS
        )
        return DocumentZeroShotDetectionResult(
            upload_id=chunks.upload_id,
            agent_project_id=chunks.agent_project_id,
            original_filename=staged.metadata.original_filename,
            source_sha256=chunks.source_sha256,
            document_type=chunks.document_type,
            extraction_version=chunks.extraction_version,
            chunker_version=chunks.chunker_version,
            classifier_version=ZERO_SHOT_CLASSIFIER_VERSION,
            model=self._metadata(device),
            status=status,
            chunks=records,
            metrics=metrics,
            warnings=warnings,
            created_at=self._clock(),
        )

    def _model_unavailable(self, staged, chunks):
        records = [ChunkZeroShotDetection(
            chunk_id=chunk.chunk_id,
            text_hash=chunk.text_hash,
            provenance=chunk.provenance,
            model_token_count=0,
            model_max_length=512,
            input_truncated=False,
            classification_succeeded=False,
            inference_ms=0,
            scores=[],
            display_predictions=[],
        ) for chunk in chunks.chunks]
        return DocumentZeroShotDetectionResult(
            upload_id=chunks.upload_id,
            agent_project_id=chunks.agent_project_id,
            original_filename=staged.metadata.original_filename,
            source_sha256=chunks.source_sha256,
            document_type=chunks.document_type,
            extraction_version=chunks.extraction_version,
            chunker_version=chunks.chunker_version,
            classifier_version=ZERO_SHOT_CLASSIFIER_VERSION,
            model=self._metadata("unavailable"),
            status=ZeroShotStatus.FAILED,
            chunks=records,
            metrics=self._metrics(records),
            warnings=[ZeroShotWarning(
                code=ZeroShotWarningCode.MODEL_UNAVAILABLE,
                message="The local zero-shot model is unavailable. Verify that its pinned files are present and the model runtime can load them.",
            )],
            created_at=self._clock(),
        )

    @staticmethod
    def _metrics(records):
        successful = [record for record in records if record.classification_succeeded]
        total_ms = round(sum(record.inference_ms for record in records), 3)
        top_counts = {label: 0 for label in ArtifactDetectionLabel}
        for record in successful:
            top = max(record.scores, key=lambda item: item.score)
            top_counts[top.label] += 1
        return ZeroShotMetrics(
            chunk_count=len(records),
            classified_chunk_count=len(successful),
            truncated_chunk_count=sum(record.input_truncated for record in records),
            failed_chunk_count=len(records) - len(successful),
            average_inference_ms_per_chunk=round(total_ms / len(records), 3) if records else 0,
            total_inference_ms=total_ms,
            top_label_counts=top_counts,
        )

    @staticmethod
    def _load_valid_cache(
        staged: StagedUpload,
        agent_project_id: str,
        chunks: DocumentChunkingResult,
    ) -> DocumentZeroShotDetectionResult | None:
        try:
            result = DocumentZeroShotDetectionResult.model_validate_json(
                staged.zero_shot_detections_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        model = result.model
        if (
            result.upload_id != chunks.upload_id
            or result.agent_project_id != agent_project_id
            or result.original_filename != staged.metadata.original_filename
            or result.source_sha256 != chunks.source_sha256
            or result.document_type != chunks.document_type
            or result.extraction_version != chunks.extraction_version
            or result.chunker_version != chunk_constants.CHUNKER_VERSION
            or result.classifier_version != ZERO_SHOT_CLASSIFIER_VERSION
            or model.model_id != MODEL_ID
            or model.revision != MODEL_REVISION
            or model.task != MODEL_TASK
            or model.hypothesis_template != HYPOTHESIS_TEMPLATE
            or model.multi_label is not True
            or model.label_map_version != ZERO_SHOT_LABEL_MAP_VERSION
            or model.template_version != ZERO_SHOT_TEMPLATE_VERSION
            or len(result.chunks) != len(chunks.chunks)
        ):
            return None
        for record, chunk in zip(result.chunks, chunks.chunks, strict=True):
            if (
                record.chunk_id != chunk.chunk_id
                or record.text_hash != chunk.text_hash
                or record.provenance != chunk.provenance
            ):
                return None
        if result.metrics != ZeroShotDetectionService._metrics(result.chunks):
            return None
        return result

    @staticmethod
    def _persist(staged, result):
        try:
            staged.zero_shot_detections_partial_path.write_text(
                result.model_dump_json(), encoding="utf-8"
            )
            staged.zero_shot_detections_partial_path.replace(
                staged.zero_shot_detections_path
            )
        except OSError as exc:
            try:
                staged.zero_shot_detections_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise ZeroShotDetectionStorageError(
                "Zero-shot detection sidecar could not be stored"
            ) from exc
