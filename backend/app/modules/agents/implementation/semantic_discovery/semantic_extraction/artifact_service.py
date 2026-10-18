import hashlib
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.semantic_discovery.canonical.schemas import (
    CanonicalStatus,
)
from app.modules.agents.implementation.semantic_discovery.canonical.service import (
    CanonicalArtifactService,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.storage import ImplementationUploadStorage
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from . import constants
from .local_model import constants as model_constants
from .local_model.adapter import (
    LocalSemanticExtractorAdapter, SemanticModelGenerationError,
    SemanticModelOutputInvalidError,
)
from .local_model.model_loader import SemanticModelUnavailableError
from .schemas import (
    DocumentSemanticArtifactResult, SemanticArtifactMetrics,
    SemanticArtifactRunResult, SemanticArtifactRunStatus,
    SemanticExtractionRequest, SemanticGenerationMetrics,
    SemanticModelMetadata,
)
from .service import SemanticExtractionContractError, SemanticExtractionService


class CanonicalArtifactsRequiredError(LookupError):
    pass


class SemanticArtifactsNotFoundError(LookupError):
    pass


class SemanticArtifactStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SemanticArtifactService:
    _inference_lock = Lock()

    def __init__(
        self, standalone_service: StandaloneService,
        storage: ImplementationUploadStorage,
        adapter: LocalSemanticExtractorAdapter, *, clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._adapter = adapter
        self._clock = clock
        self._contract = SemanticExtractionService()

    def build(
        self, agent_project_id: str, upload_id: str,
        current_user: UserPublicResponse, *, force: bool = False,
    ) -> DocumentSemanticArtifactResult:
        resolved = self._resolve(agent_project_id, upload_id, current_user)
        with self._inference_lock:
            if not force:
                cached = self._load_valid_cache(resolved)
                if cached is not None:
                    return cached
            results = [self._run_artifact(resolved, artifact)
                       for artifact in resolved["canonical"].artifacts]
            result = self._document_result(resolved, results)
            self._persist(resolved["machine"]["staged"], result)
            return result

    def get_existing(
        self, agent_project_id: str, upload_id: str,
        current_user: UserPublicResponse,
    ) -> DocumentSemanticArtifactResult:
        resolved = self._resolve(agent_project_id, upload_id, current_user)
        cached = self._load_valid_cache(resolved)
        if cached is None:
            raise SemanticArtifactsNotFoundError(upload_id)
        return cached

    def _resolve(self, agent_project_id, upload_id, current_user):
        canonical_service = CanonicalArtifactService(
            self._standalone, self._storage, clock=self._clock
        )
        machine, review, review_digest = canonical_service._resolve(
            agent_project_id, upload_id, current_user
        )
        canonical = canonical_service._load_valid_cache(
            machine, review, review_digest
        )
        if canonical is None:
            raise CanonicalArtifactsRequiredError("CANONICAL_ARTIFACTS_REQUIRED")
        staged = machine["staged"]
        try:
            canonical_digest = hashlib.sha256(
                staged.canonical_artifacts_path.read_bytes()
            ).hexdigest()
        except OSError as exc:
            raise SemanticArtifactStorageError(
                "Canonical artifact sidecar is unavailable"
            ) from exc
        return {
            "machine": machine, "review": review,
            "canonical": canonical,
            "canonical_digest": canonical_digest,
            "chunks": {chunk.chunk_id: chunk for chunk in machine["chunks"].chunks},
            "reviews": {item.chunk_id: item for item in review.chunks},
        }

    def _run_artifact(self, resolved, artifact):
        if artifact.status is CanonicalStatus.COMPLETE:
            return SemanticArtifactRunResult(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                deterministic_status=artifact.status,
                status=SemanticArtifactRunStatus.SKIPPED_COMPLETE,
            )
        if artifact.artifact_type is ArtifactDetectionLabel.OTHER_CONTEXT:
            return SemanticArtifactRunResult(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                deterministic_status=artifact.status,
                status=SemanticArtifactRunStatus.REJECTED,
            )
        source = artifact.source_refs[0]
        chunk = resolved["chunks"][source.chunk_id]
        review = resolved["reviews"][source.chunk_id]
        request = SemanticExtractionRequest(
            project_id=resolved["canonical"].agent_project_id,
            upload_id=resolved["canonical"].upload_id,
            chunk_id=chunk.chunk_id, chunk_text_hash=chunk.text_hash,
            artifact_type=artifact.artifact_type,
            verified_labels=review.verified_labels,
            source_text=chunk.text,
            deterministic_artifact=artifact,
            unresolved_items=artifact.unresolved_items,
            target_schema_version=artifact.canonical_schema_version,
            semantic_contract_version=constants.SEMANTIC_CONTRACT_VERSION,
        )
        try:
            session = self._contract.run(request, self._adapter)
            generation, model = self._runtime_metadata()
            return SemanticArtifactRunResult(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                deterministic_status=artifact.status,
                status=SemanticArtifactRunStatus(
                    session.validation.proposal_status.value
                ),
                model=model, generation=generation,
                semantic_proposal=session.proposal,
                validation=session.validation,
                merged_preview=session.merged_artifact,
            )
        except SemanticModelUnavailableError:
            raise
        except SemanticModelOutputInvalidError:
            generation, model = self._runtime_metadata()
            return SemanticArtifactRunResult(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                deterministic_status=artifact.status,
                status=SemanticArtifactRunStatus.MODEL_OUTPUT_INVALID,
                model=model, generation=generation,
                error_code="MODEL_OUTPUT_INVALID",
            )
        except (SemanticModelGenerationError, SemanticExtractionContractError):
            generation, model = self._runtime_metadata()
            return SemanticArtifactRunResult(
                artifact_id=artifact.artifact_id,
                artifact_type=artifact.artifact_type,
                deterministic_status=artifact.status,
                status=SemanticArtifactRunStatus.MODEL_ERROR,
                model=model, generation=generation,
                error_code="MODEL_ERROR",
            )

    def _runtime_metadata(self):
        metadata = self._adapter.last_generation_metadata
        if metadata is None:
            return None, None
        return (
            SemanticGenerationMetrics(
                attempt_count=metadata.attempt_count,
                input_token_count=metadata.input_token_count,
                output_token_count=metadata.output_token_count,
                generation_ms=metadata.generation_ms,
                first_model_load_ms=metadata.first_model_load_ms,
            ),
            SemanticModelMetadata(
                model_id=metadata.model_id, revision=metadata.revision,
                device=metadata.device,
            ),
        )

    def _document_result(self, resolved, results):
        canonical = resolved["canonical"]
        metrics = self._metrics(results)
        return DocumentSemanticArtifactResult(
            upload_id=canonical.upload_id,
            agent_project_id=canonical.agent_project_id,
            original_filename=canonical.original_filename,
            source_sha256=canonical.source_sha256,
            human_review_fingerprint=canonical.human_review_fingerprint,
            canonical_artifact_digest=resolved["canonical_digest"],
            chunk_id_hashes={key: value.text_hash
                             for key, value in sorted(resolved["chunks"].items())},
            semantic_contract_version=constants.SEMANTIC_CONTRACT_VERSION,
            grounding_version=constants.EVIDENCE_GROUNDING_VERSION,
            merge_policy_version=constants.SEMANTIC_MERGE_POLICY_VERSION,
            adapter_version=model_constants.SEMANTIC_MODEL_ADAPTER_VERSION,
            model_id=self._adapter.configured_model[0],
            model_revision=self._adapter.configured_model[1],
            prompt_version=model_constants.SEMANTIC_PROMPT_VERSION,
            generation_policy_version=model_constants.SEMANTIC_GENERATION_POLICY_VERSION,
            results=results, metrics=metrics,
            warnings=sorted({result.status.value for result in results if result.status in {
                SemanticArtifactRunStatus.HUMAN_REVIEW_REQUIRED,
                SemanticArtifactRunStatus.MODEL_OUTPUT_INVALID,
                SemanticArtifactRunStatus.MODEL_ERROR,
            }}),
            created_at=self._clock(),
        )

    @staticmethod
    def _metrics(results):
        def count(status):
            return sum(item.status is status for item in results)
        validations = [item.validation for item in results if item.validation]
        generations = [item.generation for item in results if item.generation]
        targets = [item for item in results
                   if item.status is not SemanticArtifactRunStatus.SKIPPED_COMPLETE]
        return SemanticArtifactMetrics(
            artifact_count=len(results), target_artifact_count=len(targets),
            skipped_complete_count=count(SemanticArtifactRunStatus.SKIPPED_COMPLETE),
            grounded_count=count(SemanticArtifactRunStatus.GROUNDED),
            partially_grounded_count=count(SemanticArtifactRunStatus.PARTIALLY_GROUNDED),
            human_review_required_count=count(SemanticArtifactRunStatus.HUMAN_REVIEW_REQUIRED),
            rejected_count=count(SemanticArtifactRunStatus.REJECTED),
            model_output_invalid_count=count(SemanticArtifactRunStatus.MODEL_OUTPUT_INVALID),
            model_error_count=count(SemanticArtifactRunStatus.MODEL_ERROR),
            accepted_fact_count=sum(item.accepted_facts for item in validations),
            rejected_fact_count=sum(item.rejected_facts for item in validations),
            conflict_count=sum(item.conflict_count for item in validations),
            total_attempt_count=sum(item.attempt_count for item in generations),
            total_generation_ms=sum(item.generation_ms for item in generations),
            first_model_load_ms=max(
                (item.first_model_load_ms for item in generations), default=0
            ),
        )

    def _load_valid_cache(self, resolved):
        staged = resolved["machine"]["staged"]
        try:
            cached = DocumentSemanticArtifactResult.model_validate_json(
                staged.semantic_artifacts_path.read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError, ValidationError):
            return None
        canonical = resolved["canonical"]
        expected_chunks = {key: value.text_hash
                           for key, value in sorted(resolved["chunks"].items())}
        if (
            cached.upload_id != canonical.upload_id
            or cached.agent_project_id != canonical.agent_project_id
            or cached.source_sha256 != canonical.source_sha256
            or cached.human_review_fingerprint != canonical.human_review_fingerprint
            or cached.canonical_artifact_digest != resolved["canonical_digest"]
            or cached.chunk_id_hashes != expected_chunks
            or cached.semantic_contract_version != constants.SEMANTIC_CONTRACT_VERSION
            or cached.grounding_version != constants.EVIDENCE_GROUNDING_VERSION
            or cached.merge_policy_version != constants.SEMANTIC_MERGE_POLICY_VERSION
            or cached.adapter_version != model_constants.SEMANTIC_MODEL_ADAPTER_VERSION
            or cached.model_id != self._adapter.configured_model[0]
            or cached.model_revision != self._adapter.configured_model[1]
            or cached.prompt_version != model_constants.SEMANTIC_PROMPT_VERSION
            or cached.generation_policy_version != model_constants.SEMANTIC_GENERATION_POLICY_VERSION
            or [item.artifact_id for item in cached.results]
            != [item.artifact_id for item in canonical.artifacts]
            or cached.metrics != self._metrics(cached.results)
        ):
            return None
        return cached

    @staticmethod
    def _persist(staged, result):
        try:
            staged.semantic_artifacts_partial_path.write_text(
                result.model_dump_json(by_alias=True), encoding="utf-8"
            )
            staged.semantic_artifacts_partial_path.replace(
                staged.semantic_artifacts_path
            )
        except OSError as exc:
            try:
                staged.semantic_artifacts_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise SemanticArtifactStorageError(
                "Semantic artifact sidecar could not be stored"
            ) from exc
