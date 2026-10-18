import hashlib
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.extraction.service import DocumentExtractionService
from app.modules.agents.implementation.semantic_discovery import constants as semantic_constants
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel, ChunkingStatus, DocumentChunkingResult,
    DocumentRuleDetectionResult,
)
from app.modules.agents.implementation.semantic_discovery.service import (
    ChunkingNotFoundError, RuleDetectionService, SemanticChunkingService,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.constants import (
    ZERO_SHOT_CLASSIFIER_VERSION, ZERO_SHOT_LABEL_MAP_VERSION,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.schemas import (
    DocumentZeroShotDetectionResult,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.service import (
    ZeroShotDetectionService,
)
from app.modules.agents.implementation.service import require_implementation_project
from app.modules.agents.implementation.storage import ImplementationUploadStorage, StagedUpload
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from . import constants
from .policy import decide_chunk
from .schemas import (
    BaselineReference, DocumentHybridDetectionResult, HybridDecisionState,
    HybridEvidenceState, HybridMetrics, HybridPolicyMetadata,
)


class RuleDetectionRequiredError(LookupError):
    pass


class ZeroShotDetectionRequiredError(LookupError):
    pass


class StaleClassificationInputError(ValueError):
    pass


class HybridDetectionNotFoundError(LookupError):
    pass


class HybridDetectionStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HybridDetectionService:
    _lock = Lock()

    def __init__(self, standalone_service: StandaloneService,
                 storage: ImplementationUploadStorage, *, clock=utc_now) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, upload_id: str,
              current_user: UserPublicResponse, *, force: bool = False
              ) -> DocumentHybridDetectionResult:
        project, staged, chunks, rules, model = self._resolve(
            agent_project_id, upload_id, current_user
        )
        rule_digest = self._digest(staged.rule_detections_path)
        model_digest = self._digest(staged.zero_shot_detections_path)
        with self._lock:
            if not force:
                cached = self._load_valid_cache(
                    staged, project.agent_project_id, chunks, rules, model,
                    rule_digest, model_digest,
                )
                if cached is not None:
                    return cached
            rule_by_id = {item.chunk_id: item for item in rules.detections}
            model_by_id = {item.chunk_id: item for item in model.chunks}
            self._validate_alignment(chunks, rule_by_id, model_by_id)
            records = [decide_chunk(rule_by_id[chunk.chunk_id],
                                    model_by_id[chunk.chunk_id])
                       for chunk in chunks.chunks]
            result = DocumentHybridDetectionResult(
                upload_id=chunks.upload_id,
                agent_project_id=chunks.agent_project_id,
                original_filename=staged.metadata.original_filename,
                source_sha256=chunks.source_sha256,
                document_type=chunks.document_type,
                extraction_version=chunks.extraction_version,
                chunker_version=chunks.chunker_version,
                rule_baseline=BaselineReference(
                    result_sha256=rule_digest,
                    detector_version=rules.rule_detector_version,
                ),
                model_baseline=BaselineReference(
                    result_sha256=model_digest,
                    classifier_version=model.classifier_version,
                    model_id=model.model.model_id,
                    model_revision=model.model.revision,
                    label_map_version=model.model.label_map_version,
                ),
                policy=self._policy_metadata(),
                chunks=records,
                metrics=self._metrics(records),
                warnings=self._warnings(records),
                created_at=self._clock(),
            )
            self._persist(staged, result)
            return result

    def get_existing(self, agent_project_id: str, upload_id: str,
                     current_user: UserPublicResponse) -> DocumentHybridDetectionResult:
        project, staged, chunks, rules, model = self._resolve(
            agent_project_id, upload_id, current_user
        )
        cached = self._load_valid_cache(
            staged, project.agent_project_id, chunks, rules, model,
            self._digest(staged.rule_detections_path),
            self._digest(staged.zero_shot_detections_path),
        )
        if cached is None:
            raise HybridDetectionNotFoundError(upload_id)
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
        rules = RuleDetectionService._load_valid_cache(
            staged, project.agent_project_id, chunks
        )
        if rules is None:
            if staged.rule_detections_path.exists():
                raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT")
            raise RuleDetectionRequiredError("RULE_DETECTION_REQUIRED")
        model = ZeroShotDetectionService._load_valid_cache(
            staged, project.agent_project_id, chunks
        )
        if model is None:
            if staged.zero_shot_detections_path.exists():
                raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT")
            raise ZeroShotDetectionRequiredError("ZERO_SHOT_DETECTION_REQUIRED")
        return project, staged, chunks, rules, model

    @staticmethod
    def _validate_alignment(chunks, rules, model):
        expected = {item.chunk_id: item.text_hash for item in chunks.chunks}
        if set(rules) != set(expected) or set(model) != set(expected):
            raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT")
        if any(rules[key].text_hash != value or model[key].text_hash != value
               for key, value in expected.items()):
            raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT")

    @staticmethod
    def _policy_metadata():
        return HybridPolicyMetadata(
            decision_version=constants.HYBRID_DECISION_VERSION,
            policy_version=constants.HYBRID_POLICY_VERSION,
            threshold_semantics="EXPERIMENTAL_ENGINEERING_DEFAULTS_NOT_VALIDATED",
            model_strong_support=constants.MODEL_STRONG_SUPPORT,
            model_moderate_support=constants.MODEL_MODERATE_SUPPORT,
            model_weak_support=constants.MODEL_WEAK_SUPPORT,
            label_explosion_count=constants.MODEL_LABEL_EXPLOSION_COUNT,
            label_explosion_threshold=constants.MODEL_LABEL_EXPLOSION_THRESHOLD,
            top_score_margin_threshold=constants.TOP_SCORE_MARGIN_THRESHOLD,
        )

    @staticmethod
    def _metrics(records):
        candidates = [candidate for record in records for candidate in record.candidates]
        decisions = {state: sum(c.decision is state for c in candidates)
                     for state in HybridDecisionState}
        evidence = {state: sum(c.evidence_state is state for c in candidates)
                    for state in HybridEvidenceState}
        labels = {label: 0 for label in ArtifactDetectionLabel}
        for candidate in candidates:
            labels[candidate.label] += 1
        return HybridMetrics(
            chunk_count=len(records),
            auto_candidate_count=decisions[HybridDecisionState.AUTO_CANDIDATE],
            review_required_count=decisions[HybridDecisionState.REVIEW_REQUIRED],
            rejected_count=decisions[HybridDecisionState.REJECTED],
            rule_and_model_count=evidence[HybridEvidenceState.RULE_AND_MODEL],
            rule_only_count=evidence[HybridEvidenceState.RULE_ONLY],
            model_only_count=evidence[HybridEvidenceState.MODEL_ONLY],
            disagreement_count=evidence[HybridEvidenceState.RULE_MODEL_DISAGREEMENT],
            insufficient_evidence_count=evidence[HybridEvidenceState.INSUFFICIENT_EVIDENCE],
            label_explosion_chunk_count=sum(r.diagnostics.model_label_explosion for r in records),
            ambiguous_chunk_count=sum(r.diagnostics.model_ambiguous for r in records),
            per_label_candidate_counts=labels,
        )

    @staticmethod
    def _warnings(records):
        warnings = []
        if any(record.diagnostics.model_label_explosion for record in records):
            warnings.append("MODEL_LABEL_EXPLOSION")
        if any(record.diagnostics.model_ambiguous for record in records):
            warnings.append("MODEL_AMBIGUOUS")
        return warnings

    @staticmethod
    def _digest(path):
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT") from exc

    @staticmethod
    def _load_valid_cache(staged: StagedUpload, agent_project_id: str,
                          chunks: DocumentChunkingResult,
                          rules: DocumentRuleDetectionResult,
                          model: DocumentZeroShotDetectionResult,
                          rule_digest: str, model_digest: str):
        try:
            result = DocumentHybridDetectionResult.model_validate_json(
                staged.hybrid_detections_path.read_text(encoding="utf-8")
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
            or result.chunker_version != semantic_constants.CHUNKER_VERSION
            or result.rule_baseline.result_sha256 != rule_digest
            or result.rule_baseline.detector_version != rules.rule_detector_version
            or result.model_baseline.result_sha256 != model_digest
            or result.model_baseline.classifier_version != ZERO_SHOT_CLASSIFIER_VERSION
            or result.model_baseline.model_id != model.model.model_id
            or result.model_baseline.model_revision != model.model.revision
            or result.model_baseline.label_map_version != ZERO_SHOT_LABEL_MAP_VERSION
            or result.policy != HybridDetectionService._policy_metadata()
            or len(result.chunks) != len(chunks.chunks)
        ):
            return None
        for record, chunk in zip(result.chunks, chunks.chunks, strict=True):
            if record.chunk_id != chunk.chunk_id or record.text_hash != chunk.text_hash:
                return None
        if result.metrics != HybridDetectionService._metrics(result.chunks):
            return None
        return result

    @staticmethod
    def _persist(staged, result):
        try:
            staged.hybrid_detections_partial_path.write_text(
                result.model_dump_json(), encoding="utf-8"
            )
            staged.hybrid_detections_partial_path.replace(
                staged.hybrid_detections_path
            )
        except OSError as exc:
            try:
                staged.hybrid_detections_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HybridDetectionStorageError(
                "Hybrid detection sidecar could not be stored"
            ) from exc
