import hashlib
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.semantic_discovery.human_review.schemas import (
    ChunkReviewStatus, DocumentReviewStatus,
)
from app.modules.agents.implementation.semantic_discovery.human_review.service import HumanReviewService
from app.modules.agents.implementation.semantic_discovery.service import ChunkingNotFoundError
from app.modules.agents.implementation.semantic_discovery.schemas import ArtifactDetectionLabel
from app.modules.agents.implementation.storage import ImplementationUploadStorage
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from . import constants
from .extractors import extract_label
from .schemas import (
    CanonicalArtifact, CanonicalMetrics, CanonicalSourceRef, CanonicalStatus,
    DocumentCanonicalArtifactResult,
)


class SemanticChunksRequiredError(LookupError):
    pass


class HumanVerificationRequiredError(LookupError):
    pass


class StaleHumanVerificationError(ValueError):
    pass


class CanonicalArtifactsNotFoundError(LookupError):
    pass


class CanonicalArtifactStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CanonicalArtifactService:
    _lock = Lock()

    def __init__(self, standalone_service: StandaloneService,
                 storage: ImplementationUploadStorage, *, clock=utc_now) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, upload_id: str,
              current_user: UserPublicResponse, *, force: bool = False
              ) -> DocumentCanonicalArtifactResult:
        machine, review, review_digest = self._resolve(
            agent_project_id, upload_id, current_user
        )
        with self._lock:
            if not force:
                cached = self._load_valid_cache(machine, review, review_digest)
                if cached is not None:
                    return cached
            chunks = {item.chunk_id: item for item in machine["chunks"].chunks}
            now = self._clock()
            artifacts = []
            for chunk_review in sorted(review.chunks, key=lambda item: item.chunk_index):
                chunk = chunks[chunk_review.chunk_id]
                source = self._source_ref(chunk)
                for label in sorted(chunk_review.verified_labels, key=lambda item: item.value):
                    outcome = extract_label(label, chunk.text, source)
                    artifacts.append(CanonicalArtifact(
                        artifact_id=self._artifact_id(chunk, label),
                        artifact_type=label,
                        status=outcome.status,
                        data=outcome.data,
                        source_refs=[source],
                        unresolved_items=outcome.unresolved_items,
                        canonical_schema_version=constants.CANONICAL_SCHEMA_VERSION,
                        extractor_version=constants.DETERMINISTIC_EXTRACTOR_VERSION,
                        created_at=now,
                    ))
            metrics = self._metrics(artifacts, review.metrics.verified_chunks)
            status = self._document_status(artifacts)
            result = DocumentCanonicalArtifactResult(
                upload_id=review.upload_id,
                agent_project_id=review.agent_project_id,
                original_filename=review.original_filename,
                source_sha256=review.source_sha256,
                document_type=review.document_type,
                extraction_version=review.pipeline.extraction_version,
                chunker_version=review.pipeline.chunker_version,
                human_review_fingerprint=review.review_fingerprint,
                human_review_digest=review_digest,
                canonical_schema_version=constants.CANONICAL_SCHEMA_VERSION,
                extractor_version=constants.DETERMINISTIC_EXTRACTOR_VERSION,
                status=status,
                artifacts=artifacts,
                metrics=metrics,
                warnings=sorted({item.reason for artifact in artifacts
                                 for item in artifact.unresolved_items}),
                created_at=now,
            )
            self._persist(machine["staged"], result)
            return result

    def get_existing(self, agent_project_id: str, upload_id: str,
                     current_user: UserPublicResponse) -> DocumentCanonicalArtifactResult:
        machine, review, review_digest = self._resolve(
            agent_project_id, upload_id, current_user
        )
        cached = self._load_valid_cache(machine, review, review_digest)
        if cached is None:
            raise CanonicalArtifactsNotFoundError(upload_id)
        return cached

    def _resolve(self, agent_project_id, upload_id, current_user):
        reviews = HumanReviewService(self._standalone, self._storage, clock=self._clock)
        try:
            machine = reviews._resolve_machine(agent_project_id, upload_id, current_user)
        except ChunkingNotFoundError as exc:
            raise SemanticChunksRequiredError("SEMANTIC_CHUNKS_REQUIRED") from exc
        if not machine["staged"].human_reviews_path.exists():
            raise HumanVerificationRequiredError("HUMAN_VERIFICATION_REQUIRED")
        review, stale = reviews._current_or_blank(machine)
        if stale:
            raise StaleHumanVerificationError("STALE_HUMAN_VERIFICATION")
        if (review.review_status is not DocumentReviewStatus.COMPLETE
                or any(item.review_status is not ChunkReviewStatus.VERIFIED
                       for item in review.chunks)):
            raise HumanVerificationRequiredError("HUMAN_VERIFICATION_REQUIRED")
        try:
            review_digest = hashlib.sha256(
                machine["staged"].human_reviews_path.read_bytes()
            ).hexdigest()
        except OSError as exc:
            raise CanonicalArtifactStorageError(
                "Human-review sidecar is unavailable"
            ) from exc
        return machine, review, review_digest

    @staticmethod
    def _source_ref(chunk):
        provenance = chunk.provenance
        return CanonicalSourceRef(
            upload_id=provenance.upload_id,
            chunk_id=chunk.chunk_id,
            text_hash=chunk.text_hash,
            original_filename=provenance.original_filename,
            page_start=provenance.page_start, page_end=provenance.page_end,
            block_start=provenance.block_start, block_end=provenance.block_end,
            line_start=provenance.line_start, line_end=provenance.line_end,
            structured_path=provenance.structured_path,
        )

    @staticmethod
    def _artifact_id(chunk, label):
        identity = "\0".join((
            chunk.provenance.upload_id, chunk.chunk_id, chunk.text_hash,
            label.value, constants.CANONICAL_SCHEMA_VERSION,
            constants.DETERMINISTIC_EXTRACTOR_VERSION,
        ))
        return "CA-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24].upper()

    @staticmethod
    def _metrics(artifacts, verified_chunks):
        counts = {label: 0 for label in ArtifactDetectionLabel}
        statuses = {status: 0 for status in CanonicalStatus}
        for artifact in artifacts:
            counts[artifact.artifact_type] += 1
            statuses[artifact.status] += 1
        return CanonicalMetrics(
            verified_chunk_count=verified_chunks,
            canonical_artifact_count=len(artifacts),
            complete_artifact_count=statuses[CanonicalStatus.COMPLETE],
            partial_artifact_count=statuses[CanonicalStatus.PARTIAL],
            unresolved_artifact_count=statuses[CanonicalStatus.UNRESOLVED],
            per_artifact_type_counts=counts,
        )

    @staticmethod
    def _document_status(artifacts):
        if not artifacts or all(item.status is CanonicalStatus.UNRESOLVED for item in artifacts):
            return CanonicalStatus.UNRESOLVED
        if all(item.status is CanonicalStatus.COMPLETE for item in artifacts):
            return CanonicalStatus.COMPLETE
        return CanonicalStatus.PARTIAL

    @staticmethod
    def _load_valid_cache(machine, review, review_digest):
        staged = machine["staged"]
        try:
            result = DocumentCanonicalArtifactResult.model_validate_json(
                staged.canonical_artifacts_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        if (
            result.upload_id != review.upload_id
            or result.agent_project_id != review.agent_project_id
            or result.original_filename != review.original_filename
            or result.source_sha256 != review.source_sha256
            or result.document_type != review.document_type
            or result.extraction_version != review.pipeline.extraction_version
            or result.chunker_version != review.pipeline.chunker_version
            or result.human_review_fingerprint != review.review_fingerprint
            or result.human_review_digest != review_digest
            or result.canonical_schema_version != constants.CANONICAL_SCHEMA_VERSION
            or result.extractor_version != constants.DETERMINISTIC_EXTRACTOR_VERSION
        ):
            return None
        chunks = {item.chunk_id: item for item in machine["chunks"].chunks}
        expected_pairs = {
            (item.chunk_id, label) for item in review.chunks for label in item.verified_labels
        }
        actual_pairs = set()
        for artifact in result.artifacts:
            if len(artifact.source_refs) != 1:
                return None
            source = artifact.source_refs[0]
            chunk = chunks.get(source.chunk_id)
            if chunk is None or source != CanonicalArtifactService._source_ref(chunk):
                return None
            if artifact.artifact_id != CanonicalArtifactService._artifact_id(
                    chunk, artifact.artifact_type):
                return None
            actual_pairs.add((source.chunk_id, artifact.artifact_type))
        if actual_pairs != expected_pairs:
            return None
        if result.metrics != CanonicalArtifactService._metrics(
                result.artifacts, review.metrics.verified_chunks):
            return None
        if result.status is not CanonicalArtifactService._document_status(result.artifacts):
            return None
        return result

    @staticmethod
    def _persist(staged, result):
        try:
            staged.canonical_artifacts_partial_path.write_text(
                result.model_dump_json(by_alias=True), encoding="utf-8"
            )
            staged.canonical_artifacts_partial_path.replace(
                staged.canonical_artifacts_path
            )
        except OSError as exc:
            try:
                staged.canonical_artifacts_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise CanonicalArtifactStorageError(
                "Canonical artifact sidecar could not be stored"
            ) from exc
