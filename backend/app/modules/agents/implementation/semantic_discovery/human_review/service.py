import hashlib
import json
from datetime import datetime, timezone
from threading import Lock

from pydantic import ValidationError

from app.modules.agents.implementation.semantic_discovery.hybrid.schemas import (
    HybridDecisionState, HybridEvidenceState,
)
from app.modules.agents.implementation.semantic_discovery.hybrid.service import (
    HybridDetectionService, StaleClassificationInputError,
)
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.storage import ImplementationUploadStorage
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from . import constants
from .schemas import (
    ChunkHumanReview, ChunkHumanReviewUpdate, ChunkReviewStatus,
    DocumentHumanReviewResult, DocumentReviewStatus, HumanReviewAction,
    HumanReviewDecision, HumanReviewMetrics, HumanReviewPipelineIdentity,
    HumanReviewQueueItem, HumanReviewStateResponse, MachineReviewSnapshot,
)


class HybridReviewRequiredError(LookupError):
    pass


class HumanReviewValidationError(ValueError):
    pass


class StaleHumanReviewError(ValueError):
    pass


class HumanReviewStorageError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HumanReviewService:
    _lock = Lock()

    def __init__(self, standalone_service: StandaloneService,
                 storage: ImplementationUploadStorage, *, clock=utc_now) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._clock = clock

    def get_state(self, agent_project_id: str, upload_id: str,
                  current_user: UserPublicResponse) -> HumanReviewStateResponse:
        machine = self._resolve_machine(agent_project_id, upload_id, current_user)
        current, stale = self._current_or_blank(machine)
        return self._response(machine, current, stale)

    def save_chunk(self, agent_project_id: str, upload_id: str, chunk_id: str,
                   request: ChunkHumanReviewUpdate,
                   current_user: UserPublicResponse) -> HumanReviewStateResponse:
        machine = self._resolve_machine(agent_project_id, upload_id, current_user)
        if request.expected_review_fingerprint != machine["fingerprint"]:
            raise StaleHumanReviewError("STALE_HUMAN_REVIEW")
        chunk_by_id = {chunk.chunk_id: chunk for chunk in machine["chunks"].chunks}
        if chunk_id not in chunk_by_id:
            raise HumanReviewValidationError("UNKNOWN_CHUNK_ID")
        with self._lock:
            current, stale = self._current_or_blank(machine)
            if stale:
                current = self._blank(machine)
            hybrid_by_id = {item.chunk_id: item for item in machine["hybrid"].chunks}
            updated = self._review_chunk(
                next(item for item in current.chunks if item.chunk_id == chunk_id),
                hybrid_by_id[chunk_id], request, current_user.user_id,
            )
            records = [updated if item.chunk_id == chunk_id else item
                       for item in current.chunks]
            now = self._clock()
            result = current.model_copy(update={
                "reviewer_owner_id": current_user.user_id,
                "chunks": records,
                "metrics": self._metrics(records),
                "review_status": self._document_status(records),
                "created_at": current.created_at or now,
                "updated_at": now,
            })
            self._persist(machine["staged"], result)
        return self._response(machine, result, False)

    def _resolve_machine(self, agent_project_id, upload_id, current_user):
        hybrid_service = HybridDetectionService(
            self._standalone, self._storage, clock=self._clock
        )
        project, staged, chunks, rules, model = hybrid_service._resolve(
            agent_project_id, upload_id, current_user
        )
        rule_digest = hybrid_service._digest(staged.rule_detections_path)
        model_digest = hybrid_service._digest(staged.zero_shot_detections_path)
        hybrid = hybrid_service._load_valid_cache(
            staged, project.agent_project_id, chunks, rules, model,
            rule_digest, model_digest,
        )
        if hybrid is None:
            if staged.hybrid_detections_path.exists():
                raise StaleClassificationInputError("STALE_CLASSIFICATION_INPUT")
            raise HybridReviewRequiredError("HYBRID_DETECTION_REQUIRED")
        hybrid_digest = hybrid_service._digest(staged.hybrid_detections_path)
        pipeline = HumanReviewPipelineIdentity(
            extraction_version=chunks.extraction_version,
            chunker_version=chunks.chunker_version,
            rule_detector_version=rules.rule_detector_version,
            zero_shot_classifier_version=model.classifier_version,
            zero_shot_model_id=model.model.model_id,
            zero_shot_model_revision=model.model.revision,
            zero_shot_label_map_version=model.model.label_map_version,
            hybrid_decision_version=hybrid.policy.decision_version,
            hybrid_policy_version=hybrid.policy.policy_version,
            human_review_schema_version=constants.HUMAN_REVIEW_SCHEMA_VERSION,
            human_review_policy_version=constants.HUMAN_REVIEW_POLICY_VERSION,
        )
        fingerprint = self._fingerprint(
            chunks.source_sha256, pipeline, rule_digest, model_digest,
            hybrid_digest, chunks.chunks,
        )
        return {
            "project": project, "staged": staged, "chunks": chunks,
            "rules": rules, "model": model, "hybrid": hybrid,
            "rule_digest": rule_digest, "model_digest": model_digest,
            "hybrid_digest": hybrid_digest, "pipeline": pipeline,
            "fingerprint": fingerprint,
        }

    def _current_or_blank(self, machine):
        try:
            raw = machine["staged"].human_reviews_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self._blank(machine), False
        except OSError as exc:
            raise HumanReviewStorageError("Human-review sidecar is unavailable") from exc
        try:
            current = DocumentHumanReviewResult.model_validate_json(raw)
        except ValidationError as exc:
            raise HumanReviewStorageError("Human-review sidecar is malformed") from exc
        if current.review_fingerprint != machine["fingerprint"]:
            return self._blank(machine), True
        expected = self._blank(machine)
        if (
            current.upload_id != expected.upload_id
            or current.agent_project_id != expected.agent_project_id
            or current.original_filename != expected.original_filename
            or current.source_sha256 != expected.source_sha256
            or current.document_type != expected.document_type
            or current.pipeline != expected.pipeline
            or current.rule_result_digest != expected.rule_result_digest
            or current.zero_shot_result_digest != expected.zero_shot_result_digest
            or current.hybrid_result_digest != expected.hybrid_result_digest
            or len(current.chunks) != len(expected.chunks)
        ):
            raise HumanReviewStorageError("Human-review identity validation failed")
        for stored, blank in zip(current.chunks, expected.chunks, strict=True):
            if (
                stored.chunk_id != blank.chunk_id
                or stored.chunk_index != blank.chunk_index
                or stored.text_hash != blank.text_hash
                or stored.provenance != blank.provenance
                or stored.machine_snapshot != blank.machine_snapshot
            ):
                raise HumanReviewStorageError("Human-review chunk validation failed")
            if not stored.decisions:
                if (stored.review_status is not ChunkReviewStatus.UNREVIEWED
                        or stored.verified_labels or stored.reviewed_at is not None):
                    raise HumanReviewStorageError("Human-review decision validation failed")
                continue
            try:
                request = ChunkHumanReviewUpdate(
                    expected_review_fingerprint=current.review_fingerprint,
                    decisions=[{
                        "action": decision.action,
                        "source_candidate_label": decision.source_candidate_label,
                        "final_label": decision.final_label,
                        "note": decision.note,
                    } for decision in stored.decisions],
                )
                validated = self._review_chunk(
                    blank,
                    next(item for item in machine["hybrid"].chunks
                         if item.chunk_id == stored.chunk_id),
                    request,
                    stored.decisions[0].reviewer_owner_id,
                )
            except (HumanReviewValidationError, ValidationError, StopIteration) as exc:
                raise HumanReviewStorageError(
                    "Human-review decision validation failed"
                ) from exc
            if (validated.verified_labels != stored.verified_labels
                    or validated.review_status is not stored.review_status
                    or any(decision.reviewer_owner_id != current.reviewer_owner_id
                           for decision in stored.decisions)):
                raise HumanReviewStorageError("Human-review decision validation failed")
        if current.metrics != self._metrics(current.chunks):
            raise HumanReviewStorageError("Human-review metrics validation failed")
        if current.review_status is not self._document_status(current.chunks):
            raise HumanReviewStorageError("Human-review status validation failed")
        return current, False

    @staticmethod
    def _fingerprint(source_sha, pipeline, rule_digest, model_digest,
                     hybrid_digest, chunks):
        identity = {
            "source_sha256": source_sha,
            "pipeline": pipeline.model_dump(mode="json"),
            "rule_result_digest": rule_digest,
            "zero_shot_result_digest": model_digest,
            "hybrid_result_digest": hybrid_digest,
            "chunks": [{"chunk_id": item.chunk_id, "text_hash": item.text_hash}
                       for item in chunks],
        }
        canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _blank(machine):
        hybrid_by_id = {item.chunk_id: item for item in machine["hybrid"].chunks}
        reviews = []
        for chunk in machine["chunks"].chunks:
            candidates = hybrid_by_id[chunk.chunk_id].candidates
            reviews.append(ChunkHumanReview(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                text_hash=chunk.text_hash,
                provenance=chunk.provenance,
                machine_snapshot=MachineReviewSnapshot(
                    hybrid_result_digest=machine["hybrid_digest"],
                    candidate_labels=[item.label for item in candidates],
                ),
                decisions=[], verified_labels=[],
                review_status=ChunkReviewStatus.UNREVIEWED,
            ))
        return DocumentHumanReviewResult(
            upload_id=machine["chunks"].upload_id,
            agent_project_id=machine["chunks"].agent_project_id,
            original_filename=machine["staged"].metadata.original_filename,
            source_sha256=machine["chunks"].source_sha256,
            document_type=machine["chunks"].document_type,
            pipeline=machine["pipeline"],
            rule_result_digest=machine["rule_digest"],
            zero_shot_result_digest=machine["model_digest"],
            hybrid_result_digest=machine["hybrid_digest"],
            review_fingerprint=machine["fingerprint"],
            reviewer_owner_id=None,
            review_status=DocumentReviewStatus.NOT_STARTED,
            chunks=reviews,
            metrics=HumanReviewService._metrics(reviews),
            created_at=None, updated_at=None,
        )

    def _review_chunk(self, existing, hybrid, request, reviewer_id):
        candidate_labels = [item.label for item in hybrid.candidates]
        candidate_set = set(candidate_labels)
        source_actions = {}
        verified = []
        now = self._clock()
        persisted = []
        for decision in request.decisions:
            action, source, final = (
                decision.action, decision.source_candidate_label,
                decision.final_label,
            )
            if action in {HumanReviewAction.ACCEPT, HumanReviewAction.RELABEL,
                          HumanReviewAction.EXCLUDE}:
                if source not in candidate_set:
                    raise HumanReviewValidationError("UNKNOWN_SOURCE_CANDIDATE")
                if source in source_actions:
                    raise HumanReviewValidationError("DUPLICATE_CANDIDATE_DECISION")
                source_actions[source] = action
            if action is HumanReviewAction.ACCEPT:
                if final != source:
                    raise HumanReviewValidationError("ACCEPT_LABEL_MUST_MATCH_CANDIDATE")
                verified.append(final)
            elif action is HumanReviewAction.RELABEL:
                if source is None or final is None:
                    raise HumanReviewValidationError("RELABEL_REQUIRES_SOURCE_AND_FINAL_LABEL")
                if source == final:
                    raise HumanReviewValidationError("SAME_LABEL_RELABEL_NOT_ALLOWED")
                verified.append(final)
            elif action is HumanReviewAction.EXCLUDE:
                if final is not None:
                    raise HumanReviewValidationError("EXCLUDE_CANNOT_HAVE_FINAL_LABEL")
            elif action is HumanReviewAction.ADD_LABEL:
                if source is not None or final is None:
                    raise HumanReviewValidationError("ADD_LABEL_REQUIRES_ONLY_FINAL_LABEL")
                if final in candidate_set:
                    raise HumanReviewValidationError("ADD_LABEL_MUST_BE_MISSING_CANDIDATE")
                verified.append(final)
            persisted.append(HumanReviewDecision(
                action=action, source_candidate_label=source, final_label=final,
                note=decision.note, reviewer_owner_id=reviewer_id,
                reviewed_at=now,
            ))
        if len(verified) != len(set(verified)):
            raise HumanReviewValidationError("DUPLICATE_FINAL_LABEL")
        verified_set = set(verified)
        other = ArtifactDetectionLabel.OTHER_CONTEXT
        if other in verified_set and len(verified_set) > 1:
            raise HumanReviewValidationError("OTHER_CONTEXT_MUST_BE_EXCLUSIVE")
        status = (
            ChunkReviewStatus.VERIFIED
            if set(source_actions) == candidate_set
            else ChunkReviewStatus.IN_REVIEW
        )
        return existing.model_copy(update={
            "decisions": persisted,
            "verified_labels": sorted(verified_set, key=lambda item: item.value),
            "review_status": status,
            "reviewed_at": now,
        })

    @staticmethod
    def _metrics(records):
        decisions = [decision for item in records for decision in item.decisions]
        verified = sum(item.review_status is ChunkReviewStatus.VERIFIED for item in records)
        total = len(records)
        return HumanReviewMetrics(
            total_chunks=total,
            verified_chunks=verified,
            remaining_chunks=total - verified,
            accepted_candidate_count=sum(d.action is HumanReviewAction.ACCEPT for d in decisions),
            relabeled_candidate_count=sum(d.action is HumanReviewAction.RELABEL for d in decisions),
            excluded_candidate_count=sum(d.action is HumanReviewAction.EXCLUDE for d in decisions),
            added_label_count=sum(d.action is HumanReviewAction.ADD_LABEL for d in decisions),
            review_completion_percentage=round(verified * 100 / total, 2) if total else 100,
        )

    @staticmethod
    def _document_status(records):
        if records and all(item.review_status is ChunkReviewStatus.VERIFIED for item in records):
            return DocumentReviewStatus.COMPLETE
        if any(item.review_status is not ChunkReviewStatus.UNREVIEWED for item in records):
            return DocumentReviewStatus.IN_PROGRESS
        return DocumentReviewStatus.NOT_STARTED

    @staticmethod
    def _priority(hybrid):
        if any(item.evidence_state is HybridEvidenceState.RULE_MODEL_DISAGREEMENT
               for item in hybrid.candidates):
            return 1
        if hybrid.diagnostics.model_label_explosion:
            return 2
        if hybrid.diagnostics.model_ambiguous:
            return 3
        if any(item.decision is HybridDecisionState.REVIEW_REQUIRED
               for item in hybrid.candidates):
            return 4
        if any(item.decision is HybridDecisionState.AUTO_CANDIDATE
               for item in hybrid.candidates):
            return 5
        return 6

    @staticmethod
    def _response(machine, review, stale):
        chunks = {item.chunk_id: item for item in machine["chunks"].chunks}
        rules = {item.chunk_id: item for item in machine["rules"].detections}
        models = {item.chunk_id: item for item in machine["model"].chunks}
        hybrids = {item.chunk_id: item for item in machine["hybrid"].chunks}
        reviews = {item.chunk_id: item for item in review.chunks}
        queue = [HumanReviewQueueItem(
            priority=HumanReviewService._priority(hybrids[chunk_id]),
            chunk=chunk, rule=rules[chunk_id], model=models[chunk_id],
            hybrid=hybrids[chunk_id], review=reviews[chunk_id],
        ) for chunk_id, chunk in chunks.items()]
        queue.sort(key=lambda item: (item.priority, item.chunk.chunk_index))
        return HumanReviewStateResponse(
            review=review, review_queue=queue, stale=stale,
            stale_message=(
                "Artifact analysis changed. Human verification must be performed again."
                if stale else None
            ),
        )

    @staticmethod
    def _persist(staged, result):
        try:
            staged.human_reviews_partial_path.write_text(
                result.model_dump_json(), encoding="utf-8"
            )
            staged.human_reviews_partial_path.replace(staged.human_reviews_path)
        except OSError as exc:
            try:
                staged.human_reviews_partial_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HumanReviewStorageError(
                "Human-review sidecar could not be stored"
            ) from exc
