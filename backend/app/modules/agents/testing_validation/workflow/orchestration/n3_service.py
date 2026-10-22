import hashlib
import json
import logging
from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.modules.agents.testing_validation.contracts.sources import TestGenerationInputSourceType
from app.modules.agents.testing_validation.intelligence.effective.service import Agent4EffectiveClassificationService
from app.modules.agents.testing_validation.intelligence.hybrid.service import manifest_fingerprint
from app.modules.agents.testing_validation.intelligence.taxonomy import TESTING_INTELLIGENCE_TAXONOMY
from app.modules.agents.testing_validation.workflow.orchestration.executor import (
    AGENT4_N3_EXECUTOR,
    AGENT4_N3_SEMANTIC_EXECUTOR,
)
from app.modules.agents.testing_validation.intelligence.semantic.extractor import (
    SemanticExtractionFailedError,
)
from app.modules.agents.testing_validation.intelligence.semantic.runtime import (
    SemanticGenerationError,
    SemanticInputTooLargeError,
    SemanticModelLoadError,
)
from app.modules.agents.testing_validation.intelligence.semantic.storage import (
    Agent4SemanticStorageError,
)
from app.modules.agents.testing_validation.workflow.orchestration.n3_progression import (
    N3_SUB_STAGE_ORDER,
    SUCCESSFUL_SUB_STAGE_STATUSES,
    derive_n3_execution_status,
    get_next_n3_substage,
    new_n3_sub_stages,
)
from app.modules.agents.testing_validation.workflow.projection import build_agent4_workflow_response
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionStatus,
    Agent4N2Message,
    Agent4N3Execution,
    Agent4N3ExecutionStatus,
    Agent4N3ChunkDisposition,
    Agent4N3ChunkProgress,
    Agent4N3ReviewEvent,
    Agent4N3ReviewItem,
    Agent4N3ReviewProjection,
    Agent4N3ReviewResolution,
    Agent4N3ReviewSubmission,
    Agent4N3SourceExecution,
    Agent4N3SourceStatus,
    Agent4N3SubStageName,
    Agent4N3SubStageProgress,
    Agent4N3SubStageStatus,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowGateError
from app.modules.agents.testing_validation.workflow.storage import AGENT4_WORKFLOW_STATE_LOCK


def utc_now():
    return datetime.now(timezone.utc)


ACTIVE_N3_STATES = {Agent4N3ExecutionStatus.QUEUED, Agent4N3ExecutionStatus.RUNNING}
LOGGER = logging.getLogger(__name__)


class Agent4N3ReviewError(ValueError):
    pass


def _safe_stage_error(stage, exc):
    if stage is Agent4N3SubStageName.FACT_EXTRACTION:
        if isinstance(exc, SemanticModelLoadError):
            return Agent4N2Message(
                code="SEMANTIC_MODEL_LOAD_FAILED",
                message="Testing fact extraction could not start because the semantic model was unavailable.",
            ), True
        if isinstance(exc, SemanticInputTooLargeError):
            return Agent4N2Message(
                code="SEMANTIC_INPUT_TOO_LARGE",
                message="The source chunk is too large for testing fact extraction.",
            ), False
        if isinstance(exc, SemanticGenerationError):
            return Agent4N2Message(
                code="SEMANTIC_GENERATION_FAILED",
                message="The semantic model could not generate testing facts.",
            ), True
        if isinstance(exc, Agent4SemanticStorageError):
            return Agent4N2Message(
                code="SEMANTIC_STORAGE_FAILED",
                message="Generated testing facts could not be stored safely.",
            ), True
        if isinstance(exc, SemanticExtractionFailedError):
            code = str(exc)
            if code == "SEMANTIC_GROUNDING_FAILED":
                message = "Generated semantic facts could not be grounded in the source evidence."
            elif code == "SEMANTIC_INVALID_JSON":
                message = "The semantic model returned invalid structured output."
            elif code == "SEMANTIC_SCHEMA_VALIDATION_FAILED":
                message = (
                    "The semantic model returned unsupported or missing fact fields "
                    "after a corrective retry."
                )
            else:
                code = "SEMANTIC_OUTPUT_INVALID"
                message = "Generated testing facts did not match the required validated format."
            return Agent4N2Message(code=code, message=message), True
    return Agent4N2Message(
        code=f"{stage.value}_FAILED",
        message=f"{stage.value.replace('TI_', '').replace('_', ' ').title()} failed for this source.",
    ), True


class Agent4N3OrchestrationService:
    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(
        self, workflow_service, workflow_storage, chunk_storage,
        rule_service, zero_shot_service, hybrid_service, semantic_service,
        effective_service: Agent4EffectiveClassificationService,
        hybrid_storage, rule_storage, zero_shot_storage,
        n4_handoff=None,
        *, executor: Executor = AGENT4_N3_EXECUTOR,
        semantic_executor: Executor | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self._workflow_service = workflow_service
        self._workflow = workflow_storage
        self._chunks = chunk_storage
        self._rules = rule_service
        self._zero = zero_shot_service
        self._hybrid = hybrid_service
        self._semantic = semantic_service
        self._effective = effective_service
        self._hybrid_storage = hybrid_storage
        self._rule_storage = rule_storage
        self._zero_storage = zero_shot_storage
        # Retained as a constructor compatibility seam. N3 completion only
        # unlocks N4; starting N4 remains an explicit action.
        self._n4_handoff = n4_handoff
        self._executor = executor
        self._semantic_executor = semantic_executor or (
            AGENT4_N3_SEMANTIC_EXECUTOR
            if executor is AGENT4_N3_EXECUTOR else executor
        )
        self._clock = clock

    def get(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            migrated = any(
                not execution.sub_stages for execution in record.n3_executions
            )
            for execution in record.n3_executions:
                self._ensure_execution_sub_stages(execution)
            current = self._current(record)
            continuation = None
            if current and current.status in ACTIVE_N3_STATES:
                with self._active_lock:
                    active = current.execution_id in self._active_execution_ids
                if not active:
                    continuation = self._recover_orphaned_execution(record, current)
                    if continuation is not None:
                        self._reserve_and_save(record, continuation)
                    else:
                        self._workflow.save(record)
                    migrated = False
            if migrated:
                record.updated_at = self._clock()
                self._workflow.save(record)
            response = build_agent4_workflow_response(record)
        if continuation is not None:
            self._submit(project_id, continuation, user)
        return response

    def start(self, project_id, user, *, trigger="LEGACY_START"):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            current = self._current(record)
            if current is not None:
                return build_agent4_workflow_response(record)
            n2 = self._current_n2(record)
            n3_node = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
            if (
                n2 is None or n2.status is not Agent4N2ExecutionStatus.COMPLETED
                or self._node(record, Agent4TestGenerationNodeId.INPUT_PREPARATION).status
                is not Agent4WorkflowNodeStatus.COMPLETED
                or n3_node.status is not Agent4WorkflowNodeStatus.NOT_STARTED
                or record.current_node_id is not Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
            ):
                raise Agent4WorkflowGateError("Testing Intelligence cannot be started from its current state.")
            execution = self._new_execution(record, n2, trigger=trigger, now=self._clock())
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def start_after_n2(self, project_id, owner_id, n2_execution_id, user):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            current = self._current(record)
            if current is not None:
                return
            n2 = self._current_n2(record)
            if n2 is None or n2.execution_id != n2_execution_id or n2.status is not Agent4N2ExecutionStatus.COMPLETED:
                return
            execution = self._new_execution(record, n2, trigger="N2_COMPLETION", now=self._clock())
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)

    def retry_source(self, project_id, source_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            previous = self._current(record)
            if previous is None or previous.status not in {
                Agent4N3ExecutionStatus.FAILED, Agent4N3ExecutionStatus.INTERRUPTED,
            }:
                raise Agent4WorkflowGateError("Testing Intelligence has no retryable execution.")
            target = next((s for s in previous.sources if s.source_id == source_id), None)
            if (
                target is None
                or target.status is not Agent4N3SourceStatus.FAILED
                or not target.retryable
            ):
                raise Agent4WorkflowGateError("Only a failed current source can be retried.")
            sources = [s.model_copy(deep=True) for s in previous.sources]
            target = next(s for s in sources if s.source_id == source_id)
            self._ensure_source_sub_stages(target)
            failed = next((
                item for item in target.sub_stages
                if item.status in {
                    Agent4N3SubStageStatus.FAILED,
                    Agent4N3SubStageStatus.INTERRUPTED,
                }
            ), None)
            if failed is None:
                raise Agent4WorkflowGateError(
                    "The failed Testing Intelligence sub-stage is unavailable."
                )
            failed.status = Agent4N3SubStageStatus.QUEUED
            failed.started_at = None
            failed.completed_at = None
            failed.failed_at = None
            failed.safe_error = None
            failed.retryable = False
            target.status = Agent4N3SourceStatus.QUEUED
            target.error = None
            target.retryable = False
            target.failed_stage = None
            target.completed_at = None
            target.updated_at = self._clock()
            execution = self._new_execution(
                record, self._current_n2(record), trigger="SOURCE_RETRY",
                now=self._clock(), sources=sources, retry_source_id=source_id,
                review_id=previous.review_id,
            )
            self._queue(record, execution)
            self._reserve_and_save(record, execution)
        self._submit(project_id, execution, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def review_projection(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            execution = self._current(record)
            if execution is None or execution.status is not Agent4N3ExecutionStatus.WAITING_FOR_HUMAN:
                raise Agent4N3ReviewError("Testing Intelligence is not waiting for classification review")
            projection = self._build_review_projection(record, execution, user.user_id)
            if projection.review_snapshot_fingerprint != execution.review_snapshot_fingerprint:
                raise Agent4N3ReviewError("Classification review evidence is stale")
            return projection

    def submit_review(self, project_id, request: Agent4N3ReviewSubmission, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            execution = self._current(record)
            if execution is None or execution.status is not Agent4N3ExecutionStatus.WAITING_FOR_HUMAN:
                raise Agent4N3ReviewError("Testing Intelligence is not waiting for classification review")
            projection = self._build_review_projection(record, execution, user.user_id)
            if (
                request.review_snapshot_fingerprint != projection.review_snapshot_fingerprint
                or execution.review_snapshot_fingerprint != projection.review_snapshot_fingerprint
            ):
                raise Agent4N3ReviewError("Classification review snapshot is stale")
            expected = {(item.chunk_id, item.label): item for item in projection.items}
            supplied = [(item.chunk_id, item.label) for item in request.resolutions]
            if len(supplied) != len(set(supplied)):
                raise Agent4N3ReviewError("Duplicate classification review resolution")
            if set(supplied) != set(expected):
                raise Agent4N3ReviewError("Exactly one resolution is required for every pending review item")
            now = self._clock()
            review_id = f"A4N3R-{uuid4().hex}"
            event = Agent4N3ReviewEvent(
                review_id=review_id,
                execution_id=execution.execution_id,
                review_snapshot_fingerprint=projection.review_snapshot_fingerprint,
                resolutions=[
                    Agent4N3ReviewResolution(
                        source_id=expected[(item.chunk_id, item.label)].source_id,
                        chunk_id=item.chunk_id,
                        label=item.label,
                        decision=item.decision,
                        note=item.note,
                        hybrid_result_id=expected[(item.chunk_id, item.label)].hybrid_result_id,
                        hybrid_manifest_fingerprint=expected[(item.chunk_id, item.label)].hybrid_manifest_fingerprint,
                    )
                    for item in request.resolutions
                ],
                reviewed_at=now,
                reviewer_user_id=user.user_id,
            )
            effective_by_source = {}
            for source in execution.sources:
                if source.status is not Agent4N3SourceStatus.WAITING_FOR_HUMAN:
                    continue
                hybrid = self._require_hybrid(project_id, user.user_id, source.source_id)
                effective_by_source[source.source_id] = self._effective.build(
                    hybrid, owner_user_id=user.user_id, review=event,
                )
            record.n3_review_history.append(event)
            sources = [s.model_copy(deep=True) for s in execution.sources]
            for source in sources:
                self._ensure_source_sub_stages(source)
                if source.status is Agent4N3SourceStatus.WAITING_FOR_HUMAN:
                    source.status = Agent4N3SourceStatus.QUEUED
                    source.pending_review_items = 0
                    human = self._sub_stage(source, Agent4N3SubStageName.HUMAN_REVIEW)
                    human.status = Agent4N3SubStageStatus.COMPLETED
                    human.completed_at = now
                    human.artifact_reference = "workflow.json#n3_review_history"
                    human.summary = {"reviewed_item_count": len([
                        item for item in event.resolutions
                        if item.source_id == source.source_id
                    ])}
                    effective = self._sub_stage(
                        source, Agent4N3SubStageName.EFFECTIVE_CLASSIFICATION
                    )
                    effective_manifest = effective_by_source[source.source_id]
                    effective.status = Agent4N3SubStageStatus.COMPLETED
                    effective.completed_at = now
                    effective.artifact_reference = (
                        f"intelligence/{source.source_id}.effective-classification.json"
                    )
                    effective.summary = {
                        "accepted_label_count": effective_manifest.counts.accepted_label_count,
                        "rejected_label_count": effective_manifest.counts.rejected_label_count,
                    }
                    effective.safe_error = None
                    effective.retryable = False
                    source.effective_complete = True
                    source.accepted_label_count = (
                        effective_manifest.counts.accepted_label_count
                    )
                    source.error = None
                    source.retryable = False
                    source.updated_at = now
            continuation = self._new_execution(
                record, self._current_n2(record), trigger="HUMAN_REVIEW_RESUME",
                now=now, sources=sources, review_id=review_id,
            )
            self._queue(record, continuation)
            self._reserve_and_save(record, continuation)
        self._submit(project_id, continuation, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def _reserve_and_save(self, record, execution):
        """Publish QUEUED only after stale recovery can see scheduled work."""
        with self._active_lock:
            if execution.execution_id in self._active_execution_ids:
                raise Agent4WorkflowGateError(
                    "Testing Intelligence execution is already scheduled"
                )
            self._active_execution_ids.add(execution.execution_id)
        try:
            self._workflow.save(record)
        except Exception:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            raise

    def _submit(self, project_id, execution, user):
        with self._active_lock:
            if execution.execution_id not in self._active_execution_ids:
                return
        try:
            self._executor.submit(self._run, project_id, execution.execution_id, user)
        except Exception:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            self._fail_submission(project_id, execution.execution_id, user.user_id)

    def _run(self, project_id, execution_id, user):
        handed_off_to_semantic = False
        try:
            with AGENT4_WORKFLOW_STATE_LOCK:
                record = self._require_record(project_id, user.user_id)
                execution = self._execution(record, execution_id)
                if execution.status is not Agent4N3ExecutionStatus.QUEUED:
                    return
                now = self._clock()
                execution.status = Agent4N3ExecutionStatus.RUNNING
                execution.started_at = now
                execution.updated_at = now
                active_node = self._execution_node(execution)
                self._set_processing_node(record, active_node, Agent4WorkflowNodeStatus.RUNNING, now)
                record.updated_at = now
                self._workflow.save(record)
            # Classification and human review are a workflow barrier across all
            # sources. No source may enter fact extraction while another source
            # still has an unresolved classification decision.
            for source in list(execution.sources):
                if execution.retry_source_id and source.source_id != execution.retry_source_id:
                    continue
                if source.status in {Agent4N3SourceStatus.COMPLETE, Agent4N3SourceStatus.PENDING_ANALYSIS}:
                    continue
                self._process_source(
                    project_id, user.user_id, execution_id, source.source_id,
                    user, allow_fact_extraction=False,
                )
            checkpoint = self._load_execution(project_id, user.user_id, execution_id)
            next_stages = [
                get_next_n3_substage(source.sub_stages)
                for source in checkpoint.sources
                if source.status is not Agent4N3SourceStatus.PENDING_ANALYSIS
            ]
            fact_sources = [
                source for source in checkpoint.sources
                if (
                    (not execution.retry_source_id
                     or source.source_id == execution.retry_source_id)
                    and get_next_n3_substage(source.sub_stages)
                    is Agent4N3SubStageName.FACT_EXTRACTION
                )
            ]
            if (
                Agent4N3SubStageName.HUMAN_REVIEW not in next_stages
                and fact_sources
            ):
                for source in fact_sources:
                    self._begin_sub_stage(
                        project_id, user.user_id, execution_id,
                        source.source_id, Agent4N3SubStageName.FACT_EXTRACTION,
                    )
                self._semantic_executor.submit(
                    self._run_fact_phase, project_id, execution_id, user,
                )
                handed_off_to_semantic = True
                return
            self._finish(project_id, user.user_id, execution_id, user)
        except Exception:
            self._fail_execution(project_id, user.user_id, execution_id)
        finally:
            if not handed_off_to_semantic:
                with self._active_lock:
                    self._active_execution_ids.discard(execution_id)

    def _run_fact_phase(self, project_id, execution_id, user):
        """Run serialized Qwen work without occupying a general N3 worker."""
        try:
            execution = self._load_execution(
                project_id, user.user_id, execution_id
            )
            for source in list(execution.sources):
                if (
                    execution.retry_source_id
                    and source.source_id != execution.retry_source_id
                ):
                    continue
                if source.status in {
                    Agent4N3SourceStatus.COMPLETE,
                    Agent4N3SourceStatus.FAILED,
                    Agent4N3SourceStatus.PENDING_ANALYSIS,
                }:
                    continue
                if (
                    get_next_n3_substage(source.sub_stages)
                    is not Agent4N3SubStageName.FACT_EXTRACTION
                ):
                    continue
                self._process_source(
                    project_id, user.user_id, execution_id,
                    source.source_id, user, allow_fact_extraction=True,
                )
            self._finish(project_id, user.user_id, execution_id, user)
        except Exception:
            self._fail_execution(project_id, user.user_id, execution_id)
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _process_source(
        self, project_id, owner_id, execution_id, source_id, user,
        *, allow_fact_extraction=True,
    ):
        execution = self._load_execution(project_id, owner_id, execution_id)
        source = self._source(execution, source_id)
        self._ensure_source_sub_stages(source)
        if source.source_type is TestGenerationInputSourceType.IMAGE:
            now = self._clock()
            for stage in source.sub_stages:
                stage.status = Agent4N3SubStageStatus.NOT_APPLICABLE
                stage.completed_at = now
            self._set_source(
                project_id, owner_id, execution_id, source_id,
                status=Agent4N3SourceStatus.PENDING_ANALYSIS,
                warnings=[Agent4N2Message(
                    code="IMAGE_ANALYSIS_NOT_IMPLEMENTED",
                    message="Visual semantic analysis is not implemented.",
                )],
                sub_stages=source.sub_stages,
                completed_at=now,
            )
            return

        while True:
            execution = self._load_execution(project_id, owner_id, execution_id)
            source = self._source(execution, source_id)
            stage_name = get_next_n3_substage(source.sub_stages)
            if stage_name is None:
                self._set_source(
                    project_id, owner_id, execution_id, source_id,
                    status=Agent4N3SourceStatus.COMPLETE,
                    pending_review_items=0,
                    completed_at=self._clock(),
                    error=None,
                    failed_stage=None,
                )
                return
            stage = self._sub_stage(source, stage_name)
            if stage.status is Agent4N3SubStageStatus.WAITING_FOR_HUMAN:
                self._set_source(
                    project_id, owner_id, execution_id, source_id,
                    status=Agent4N3SourceStatus.WAITING_FOR_HUMAN,
                )
                return
            if (
                stage_name is Agent4N3SubStageName.FACT_EXTRACTION
                and not allow_fact_extraction
            ):
                return
            self._begin_sub_stage(
                project_id, owner_id, execution_id, source_id, stage_name
            )
            LOGGER.info(
                "N3 stage start project_id=%s execution_id=%s stage=%s source_id=%s",
                project_id, execution_id, stage_name.value, source_id,
            )
            try:
                if stage_name is Agent4N3SubStageName.RULE_ANALYSIS:
                    manifest = self._rules.build(project_id, source_id, user, force=False)
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id, stage_name,
                        artifact_reference=f"intelligence/{source_id}.rules.json",
                        summary={"chunk_count": len(manifest.results)},
                        rules_complete=True,
                    )
                elif stage_name is Agent4N3SubStageName.AI_CLASSIFICATION:
                    manifest = self._zero.build(project_id, source_id, user, force=False)
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id, stage_name,
                        artifact_reference=f"intelligence/{source_id}.zero-shot.json",
                        summary={"chunk_count": len(manifest.results)},
                        zero_shot_complete=True,
                    )
                elif stage_name is Agent4N3SubStageName.HYBRID_DECISION:
                    hybrid = self._hybrid.build(project_id, source_id, user, force=False)
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id, stage_name,
                        artifact_reference=f"intelligence/{source_id}.hybrid.json",
                        summary={
                            "accepted_label_count": hybrid.summary.accepted_label_count,
                            "review_label_count": hybrid.summary.review_label_count,
                        },
                        hybrid_complete=True,
                        accepted_label_count=hybrid.summary.accepted_label_count,
                        pending_review_items=hybrid.summary.review_label_count,
                    )
                    if hybrid.summary.review_label_count:
                        self._wait_for_human(
                            project_id, owner_id, execution_id, source_id,
                            hybrid.summary.review_label_count,
                        )
                        return
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id,
                        Agent4N3SubStageName.HUMAN_REVIEW,
                        status=Agent4N3SubStageStatus.NOT_APPLICABLE,
                        summary={"reason": "NO_REVIEW_REQUIRED"},
                    )
                elif stage_name is Agent4N3SubStageName.HUMAN_REVIEW:
                    self._wait_for_human(
                        project_id, owner_id, execution_id, source_id,
                        source.pending_review_items,
                    )
                    return
                elif stage_name is Agent4N3SubStageName.EFFECTIVE_CLASSIFICATION:
                    hybrid = self._require_hybrid(project_id, owner_id, source_id)
                    review = self._review_for_execution(
                        project_id, owner_id, execution.review_id
                    )
                    effective = self._effective.build(
                        hybrid, owner_user_id=owner_id, review=review
                    )
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id, stage_name,
                        artifact_reference=(
                            f"intelligence/{source_id}.effective-classification.json"
                        ),
                        summary={
                            "accepted_label_count": effective.counts.accepted_label_count,
                            "rejected_label_count": effective.counts.rejected_label_count,
                        },
                        effective_complete=True,
                        accepted_label_count=effective.counts.accepted_label_count,
                    )
                else:
                    effective = self._effective.get_current(
                        project_id, source_id, owner_id
                    )
                    if effective is None:
                        raise Agent4WorkflowGateError(
                            "Current effective classification is unavailable"
                        )
                    semantic = self._semantic.build(
                        project_id, source_id, user, force=False,
                        effective=effective,
                        started_callback=lambda: self._start_fact_extraction(
                            project_id, owner_id, execution_id, source_id,
                        ),
                        progress_callback=lambda results, chunk_count: self._checkpoint_semantic_progress(
                            project_id, owner_id, execution_id, source_id,
                            results, chunk_count,
                        ),
                    )
                    dispositions = self._semantic_chunk_progress(semantic)
                    not_applicable = bool(dispositions) and all(
                        item.status is Agent4N3ChunkDisposition.NOT_APPLICABLE
                        for item in dispositions
                    )
                    self._complete_sub_stage(
                        project_id, owner_id, execution_id, source_id, stage_name,
                        status=(Agent4N3SubStageStatus.NOT_APPLICABLE
                                if not_applicable
                                else Agent4N3SubStageStatus.COMPLETED),
                        artifact_reference=f"intelligence/{source_id}.semantic-facts.json",
                        summary={
                            "fact_count": semantic.metrics.fact_count,
                            "eligible_chunk_count": semantic.metrics.eligible_count,
                            "empty_chunk_count": sum(
                                item.status is Agent4N3ChunkDisposition.EMPTY
                                for item in dispositions
                            ),
                        },
                        semantic_complete=True,
                        semantic_fact_count=semantic.metrics.fact_count,
                        fact_extraction_chunks=dispositions,
                    )
                LOGGER.info(
                    "N3 stage complete project_id=%s execution_id=%s stage=%s source_id=%s",
                    project_id, execution_id, stage_name.value, source_id,
                )
            except Exception as exc:
                error, retryable = _safe_stage_error(stage_name, exc)
                self._fail_sub_stage(
                    project_id, owner_id, execution_id, source_id,
                    stage_name, error, retryable,
                )
                LOGGER.warning(
                    "N3 stage failed project_id=%s execution_id=%s stage=%s source_id=%s error_code=%s",
                    project_id, execution_id, stage_name.value, source_id,
                    error.code,
                )
                return

    def _begin_sub_stage(
        self, project_id, owner_id, execution_id, source_id, stage_name,
    ):
        legacy_status = {
            Agent4N3SubStageName.RULE_ANALYSIS: Agent4N3SourceStatus.RULE_CLASSIFICATION,
            Agent4N3SubStageName.AI_CLASSIFICATION: Agent4N3SourceStatus.ZERO_SHOT_CLASSIFICATION,
            Agent4N3SubStageName.HYBRID_DECISION: Agent4N3SourceStatus.HYBRID_DECISION,
            Agent4N3SubStageName.HUMAN_REVIEW: Agent4N3SourceStatus.WAITING_FOR_HUMAN,
            Agent4N3SubStageName.EFFECTIVE_CLASSIFICATION: Agent4N3SourceStatus.QUEUED,
            Agent4N3SubStageName.FACT_EXTRACTION: Agent4N3SourceStatus.SEMANTIC_EXTRACTION,
        }[stage_name]
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            self._ensure_source_sub_stages(source)
            stage = self._sub_stage(source, stage_name)
            now = self._clock()
            queued_for_capacity = stage_name is Agent4N3SubStageName.FACT_EXTRACTION
            stage.status = (
                Agent4N3SubStageStatus.QUEUED
                if queued_for_capacity else Agent4N3SubStageStatus.RUNNING
            )
            stage.started_at = None if queued_for_capacity else now
            stage.completed_at = None
            stage.failed_at = None
            if not queued_for_capacity:
                stage.attempt_count += 1
            stage.safe_error = None
            stage.retryable = False
            source.status = legacy_status
            source.started_at = source.started_at or now
            source.updated_at = now
            source.error = None
            source.retryable = False
            source.failed_stage = None
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            if queued_for_capacity:
                self._set_processing_node(
                    record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION,
                    Agent4WorkflowNodeStatus.QUEUED, now,
                )
            record.updated_at = now
            self._workflow.save(record)

    def _start_fact_extraction(
        self, project_id, owner_id, execution_id, source_id,
    ):
        """Publish RUNNING only after this source owns semantic model capacity."""
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            stage = self._sub_stage(source, Agent4N3SubStageName.FACT_EXTRACTION)
            now = self._clock()
            stage.status = Agent4N3SubStageStatus.RUNNING
            stage.started_at = now
            stage.attempt_count += 1
            source.status = Agent4N3SourceStatus.SEMANTIC_EXTRACTION
            source.updated_at = now
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            self._set_processing_node(
                record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION,
                Agent4WorkflowNodeStatus.RUNNING, now,
            )
            record.updated_at = now
            self._workflow.save(record)

    def _complete_sub_stage(
        self, project_id, owner_id, execution_id, source_id, stage_name,
        *, status=Agent4N3SubStageStatus.COMPLETED,
        artifact_reference=None, summary=None, **source_updates,
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            self._ensure_source_sub_stages(source)
            stage = self._sub_stage(source, stage_name)
            now = self._clock()
            stage.status = status
            stage.completed_at = now
            stage.failed_at = None
            stage.artifact_reference = artifact_reference
            stage.summary = summary or {}
            stage.safe_error = None
            stage.retryable = False
            for key, value in source_updates.items():
                setattr(source, key, value)
            source.updated_at = now
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)

    def _wait_for_human(
        self, project_id, owner_id, execution_id, source_id, pending_count,
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            self._ensure_source_sub_stages(source)
            stage = self._sub_stage(source, Agent4N3SubStageName.HUMAN_REVIEW)
            now = self._clock()
            stage.status = Agent4N3SubStageStatus.WAITING_FOR_HUMAN
            stage.started_at = stage.started_at or now
            stage.summary = {"pending_review_item_count": pending_count}
            source.status = Agent4N3SourceStatus.WAITING_FOR_HUMAN
            source.pending_review_items = pending_count
            source.updated_at = now
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)

    def _fail_sub_stage(
        self, project_id, owner_id, execution_id, source_id,
        stage_name, error, retryable,
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            self._ensure_source_sub_stages(source)
            stage = self._sub_stage(source, stage_name)
            now = self._clock()
            stage.status = Agent4N3SubStageStatus.FAILED
            stage.failed_at = now
            stage.safe_error = error
            stage.retryable = retryable
            source.status = Agent4N3SourceStatus.FAILED
            source.failed_stage = stage_name.value
            source.error = error
            source.retryable = retryable
            source.completed_at = now
            source.updated_at = now
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)

    def _checkpoint_semantic_progress(
        self, project_id, owner_id, execution_id, source_id, results, chunk_count,
    ):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            stage = self._sub_stage(source, Agent4N3SubStageName.FACT_EXTRACTION)
            now = self._clock()
            source.fact_extraction_chunks = self._semantic_result_progress(results)
            source.semantic_fact_count = sum(len(item.facts) for item in results)
            source.updated_at = now
            stage.summary = {
                "processed_chunk_count": len(results),
                "chunk_count": chunk_count,
                "fact_count": source.semantic_fact_count,
            }
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)

    @staticmethod
    def _semantic_chunk_progress(semantic):
        return Agent4N3OrchestrationService._semantic_result_progress(
            semantic.results
        )

    @staticmethod
    def _semantic_result_progress(results):
        dispositions = {
            "SUCCESS": Agent4N3ChunkDisposition.SUCCESS,
            "SUCCESS_WITH_WARNINGS": Agent4N3ChunkDisposition.SUCCESS_WITH_WARNINGS,
            "EMPTY": Agent4N3ChunkDisposition.EMPTY,
            "NOT_APPLICABLE": Agent4N3ChunkDisposition.NOT_APPLICABLE,
        }
        return [
            Agent4N3ChunkProgress(
                chunk_id=result.chunk.chunk_id,
                status=dispositions[result.status.value],
                fact_count=len(result.facts),
                warning_count=len(result.warnings),
            )
            for result in results
        ]

    def _require_hybrid(self, project_id, owner_id, source_id):
        hybrid = self._hybrid_storage.load(
            agent_project_id=project_id,
            owner_user_id=owner_id,
            source_id=source_id,
        )
        if hybrid is None:
            raise Agent4WorkflowGateError(
                "Current hybrid classification is unavailable"
            )
        return hybrid

    def _review_for_execution(self, project_id, owner_id, review_id):
        if review_id is None:
            return None
        record = self._require_record(project_id, owner_id)
        return next((
            item for item in reversed(record.n3_review_history)
            if item.review_id == review_id
        ), None)

    @staticmethod
    def _sub_stage(source, stage_name):
        return next(item for item in source.sub_stages if item.stage is stage_name)

    @staticmethod
    def _ensure_source_sub_stages(source):
        if source.sub_stages:
            return
        source.sub_stages = new_n3_sub_stages()
        by_name = {item.stage: item for item in source.sub_stages}
        completed = []
        if source.rules_complete:
            completed.append(Agent4N3SubStageName.RULE_ANALYSIS)
        if source.zero_shot_complete:
            completed.append(Agent4N3SubStageName.AI_CLASSIFICATION)
        if source.hybrid_complete:
            completed.append(Agent4N3SubStageName.HYBRID_DECISION)
        if source.effective_complete:
            completed.extend([
                Agent4N3SubStageName.HUMAN_REVIEW,
                Agent4N3SubStageName.EFFECTIVE_CLASSIFICATION,
            ])
        if source.semantic_complete:
            completed.append(Agent4N3SubStageName.FACT_EXTRACTION)
        for name in completed:
            by_name[name].status = Agent4N3SubStageStatus.COMPLETED
            by_name[name].completed_at = source.completed_at or source.updated_at
        if source.source_type is TestGenerationInputSourceType.IMAGE:
            for stage in source.sub_stages:
                stage.status = Agent4N3SubStageStatus.NOT_APPLICABLE
                stage.completed_at = source.completed_at or source.updated_at
        elif source.status is Agent4N3SourceStatus.WAITING_FOR_HUMAN:
            by_name[Agent4N3SubStageName.HUMAN_REVIEW].status = (
                Agent4N3SubStageStatus.WAITING_FOR_HUMAN
            )
        elif source.status is Agent4N3SourceStatus.FAILED:
            source.retryable = True
            mapping = {
                "RULE_CLASSIFICATION": Agent4N3SubStageName.RULE_ANALYSIS,
                "ZERO_SHOT_CLASSIFICATION": Agent4N3SubStageName.AI_CLASSIFICATION,
                "HYBRID_DECISION": Agent4N3SubStageName.HYBRID_DECISION,
                "SEMANTIC_EXTRACTION": Agent4N3SubStageName.FACT_EXTRACTION,
                "TI_FACT_EXTRACTION": Agent4N3SubStageName.FACT_EXTRACTION,
            }
            failed = mapping.get(source.failed_stage)
            if failed is None and source.effective_complete and not source.semantic_complete:
                failed = Agent4N3SubStageName.FACT_EXTRACTION
            if failed is not None:
                stage = by_name[failed]
                stage.status = (
                    Agent4N3SubStageStatus.INTERRUPTED
                    if source.error and source.error.code in {
                        "N3_EXECUTION_INTERRUPTED", "SEMANTIC_EXECUTION_INTERRUPTED"
                    }
                    else Agent4N3SubStageStatus.FAILED
                )
                stage.failed_at = source.updated_at
                stage.safe_error = source.error
                stage.retryable = True

    def _ensure_execution_sub_stages(self, execution):
        for source in execution.sources:
            self._ensure_source_sub_stages(source)
        self._refresh_execution_sub_stages(execution)

    @staticmethod
    def _refresh_execution_sub_stages(execution):
        for source in execution.sources:
            pending = next((
                item.stage for item in source.sub_stages
                if item.status not in SUCCESSFUL_SUB_STAGE_STATUSES
            ), None)
            source.current_sub_stage = pending
            source.last_completed_sub_stage = next((
                item.stage for item in reversed(source.sub_stages)
                if item.status in SUCCESSFUL_SUB_STAGE_STATUSES
            ), None)
        aggregate = []
        priority = (
            Agent4N3SubStageStatus.FAILED,
            Agent4N3SubStageStatus.INTERRUPTED,
            Agent4N3SubStageStatus.WAITING_FOR_HUMAN,
            Agent4N3SubStageStatus.RUNNING,
            Agent4N3SubStageStatus.QUEUED,
            Agent4N3SubStageStatus.NOT_STARTED,
        )
        for name in N3_SUB_STAGE_ORDER:
            values = [
                next(item for item in source.sub_stages if item.stage is name)
                for source in execution.sources
            ]
            statuses = {item.status for item in values}
            if statuses == {Agent4N3SubStageStatus.NOT_APPLICABLE}:
                status = Agent4N3SubStageStatus.NOT_APPLICABLE
            elif statuses.issubset(SUCCESSFUL_SUB_STAGE_STATUSES):
                status = Agent4N3SubStageStatus.COMPLETED
            else:
                status = next(item for item in priority if item in statuses)
            errors = [item.safe_error for item in values if item.safe_error]
            aggregate.append(Agent4N3SubStageProgress(
                stage=name,
                status=status,
                started_at=min(
                    (item.started_at for item in values if item.started_at),
                    default=None,
                ),
                completed_at=max(
                    (item.completed_at for item in values if item.completed_at),
                    default=None,
                ),
                failed_at=max(
                    (item.failed_at for item in values if item.failed_at),
                    default=None,
                ),
                attempt_count=sum(item.attempt_count for item in values),
                summary={
                    "source_count": len(values),
                    "completed_source_count": sum(
                        item.status in SUCCESSFUL_SUB_STAGE_STATUSES
                        for item in values
                    ),
                },
                safe_error=errors[0] if errors else None,
                retryable=any(item.retryable for item in values),
            ))
        execution.sub_stages = aggregate

    def _finish(self, project_id, owner_id, execution_id, user):
        completed = False
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            self._ensure_execution_sub_stages(execution)
            now = self._clock()
            derived = derive_n3_execution_status(execution.sub_stages)
            if derived in {
                Agent4N3ExecutionStatus.FAILED,
                Agent4N3ExecutionStatus.INTERRUPTED,
            }:
                execution.status = derived
                execution.failed_at = now
                execution.retryable = any(
                    source.retryable for source in execution.sources
                )
                execution.error = Agent4N2Message(code="N3_SOURCE_FAILED", message="One or more sources could not complete Testing Intelligence.")
                self._mark_failed(record, now, execution)
            elif derived is Agent4N3ExecutionStatus.WAITING_FOR_HUMAN:
                projection = self._build_review_projection(record, execution, owner_id)
                execution.status = Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
                execution.waiting_at = now
                execution.review_snapshot_fingerprint = projection.review_snapshot_fingerprint
                node = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
                node.status = Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
                node.updated_at = now
                fact = self._node(
                    record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION
                )
                fact.status = Agent4WorkflowNodeStatus.LOCKED
                fact.updated_at = now
                record.pipeline_status = Agent4PipelineStatus.WAITING_FOR_HUMAN
                record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
            elif derived is Agent4N3ExecutionStatus.COMPLETED:
                completed = True
                execution.status = Agent4N3ExecutionStatus.COMPLETED
                execution.completed_at = now
                execution.retryable = False
                n3 = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
                facts = self._node(record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION)
                n4 = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
                n3.status = Agent4WorkflowNodeStatus.COMPLETED
                n3.updated_at = now
                facts.status = Agent4WorkflowNodeStatus.COMPLETED
                facts.updated_at = now
                n4.status = Agent4WorkflowNodeStatus.NOT_STARTED
                n4.updated_at = now
                record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
                record.pipeline_status = Agent4PipelineStatus.RUNNING
            else:
                raise Agent4WorkflowGateError(
                    "Testing Intelligence stopped before reaching a terminal checkpoint"
                )
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)
        if completed and self._n4_handoff is not None and user is not None:
            try:
                self._n4_handoff(project_id, owner_id, execution_id, user)
            except Exception:
                # N3 evidence is already durably complete. N4 start failures must
                # never roll it back or fabricate an N3 processing failure.
                with AGENT4_WORKFLOW_STATE_LOCK:
                    record = self._require_record(project_id, owner_id)
                    now = self._clock()
                    n4 = self._node(
                        record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
                    )
                    n4.status = Agent4WorkflowNodeStatus.FAILED
                    n4.updated_at = now
                    record.current_node_id = (
                        Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
                    )
                    record.pipeline_status = Agent4PipelineStatus.FAILED
                    record.updated_at = now
                    self._workflow.save(record)

    def _recover_orphaned_execution(self, record, execution):
        """Create one append-only continuation for process-local worker loss."""
        now = self._clock()
        derived = derive_n3_execution_status(execution.sub_stages)
        source_next_stages = [
            get_next_n3_substage(source.sub_stages)
            for source in execution.sources
        ]
        if (
            derived is Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
            and all(stage in {None, Agent4N3SubStageName.HUMAN_REVIEW}
                    for stage in source_next_stages)
        ):
            execution.status = Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
            execution.waiting_at = execution.waiting_at or now
            execution.updated_at = now
            node = self._node(
                record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
            )
            node.status = Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
            node.updated_at = now
            record.pipeline_status = Agent4PipelineStatus.WAITING_FOR_HUMAN
            record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
            record.updated_at = now
            return None
        if derived is Agent4N3ExecutionStatus.COMPLETED:
            execution.status = Agent4N3ExecutionStatus.COMPLETED
            execution.completed_at = now
            execution.updated_at = now
            execution.retryable = False
            n3 = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
            facts = self._node(record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION)
            n4 = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
            n3.status = Agent4WorkflowNodeStatus.COMPLETED
            n3.updated_at = now
            facts.status = Agent4WorkflowNodeStatus.COMPLETED
            facts.updated_at = now
            n4.status = Agent4WorkflowNodeStatus.NOT_STARTED
            n4.updated_at = now
            record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            record.pipeline_status = Agent4PipelineStatus.RUNNING
            record.updated_at = now
            return None
        sources = [source.model_copy(deep=True) for source in execution.sources]
        interruption = Agent4N2Message(
            code="N3_EXECUTION_INTERRUPTED",
            message="Testing Intelligence worker stopped; persisted progress was preserved.",
        )
        execution.status = Agent4N3ExecutionStatus.INTERRUPTED
        execution.interrupted_at = now
        execution.updated_at = now
        execution.retryable = True
        execution.error = interruption
        for source in execution.sources:
            if source.status in {
                Agent4N3SourceStatus.COMPLETE,
                Agent4N3SourceStatus.PENDING_ANALYSIS,
                Agent4N3SourceStatus.WAITING_FOR_HUMAN,
            }:
                continue
            active_stage = next((
                stage for stage in source.sub_stages
                if stage.status in {
                    Agent4N3SubStageStatus.NOT_STARTED,
                    Agent4N3SubStageStatus.QUEUED,
                    Agent4N3SubStageStatus.RUNNING,
                }
            ), None)
            source.status = Agent4N3SourceStatus.FAILED
            source.error = interruption
            source.retryable = True
            source.failed_stage = active_stage.stage.value if active_stage else None
            source.updated_at = now
            if active_stage:
                active_stage.status = Agent4N3SubStageStatus.INTERRUPTED
                active_stage.failed_at = now
                active_stage.safe_error = interruption
                active_stage.retryable = True
        self._refresh_execution_sub_stages(execution)
        for source in sources:
            if source.status in {
                Agent4N3SourceStatus.COMPLETE,
                Agent4N3SourceStatus.PENDING_ANALYSIS,
                Agent4N3SourceStatus.WAITING_FOR_HUMAN,
            }:
                continue
            active_stage = next((
                stage for stage in source.sub_stages
                if stage.status in {
                    Agent4N3SubStageStatus.NOT_STARTED,
                    Agent4N3SubStageStatus.QUEUED,
                    Agent4N3SubStageStatus.RUNNING,
                }
            ), None)
            if active_stage is None:
                self._mark_failed(record, now, execution)
                return None
            active_stage.status = Agent4N3SubStageStatus.QUEUED
            active_stage.started_at = None
            active_stage.failed_at = None
            active_stage.safe_error = None
            active_stage.retryable = False
            source.status = Agent4N3SourceStatus.QUEUED
            source.error = None
            source.retryable = False
            source.failed_stage = None
            source.completed_at = None
            source.updated_at = now
        try:
            continuation = self._new_execution(
                record, self._current_n2(record), trigger="RESTART_RECOVERY",
                now=now, sources=sources, retry_source_id=execution.retry_source_id,
                review_id=execution.review_id,
            )
        except (Agent4WorkflowGateError, ValueError):
            self._mark_failed(record, now, execution)
            return None
        self._queue(record, continuation)
        return continuation

    def _build_review_projection(self, record, execution, owner_id):
        items = []
        identity = []
        auto_accepted_count = 0
        auto_rejected_count = 0
        review_relationship_counts = {}
        auto_accepted_label_counts = {}
        source_progress = {item.source_id: item for item in execution.sources}
        for source_id in sorted(source_progress):
            hybrid = self._hybrid_storage.load(agent_project_id=record.agent_project_id, owner_user_id=owner_id, source_id=source_id)
            if hybrid is None:
                continue
            chunks = self._chunks.load(agent_project_id=record.agent_project_id, owner_user_id=owner_id, source_id=source_id)
            rules = self._rule_storage.load(agent_project_id=record.agent_project_id, owner_user_id=owner_id, source_id=source_id)
            if chunks is None or rules is None:
                raise Agent4N3ReviewError("Current classification evidence is unavailable")
            if (
                hybrid.chunk_set_fingerprint != chunks.chunk_set_fingerprint
                or hybrid.chunk_ids != chunks.chunk_ids
                or rules.chunk_set_fingerprint != chunks.chunk_set_fingerprint
                or rules.chunk_ids != chunks.chunk_ids
            ):
                raise Agent4N3ReviewError("Classification review evidence is stale")
            chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks.chunks}
            rule_by_id = {result.chunk.chunk_id: result for result in rules.results}
            fingerprint = manifest_fingerprint(hybrid)
            progress = source_progress[source_id]
            for result in hybrid.results:
                for decision in result.decisions:
                    if decision.status.value == "ACCEPTED":
                        auto_accepted_count += 1
                        auto_accepted_label_counts[decision.label.value] = (
                            auto_accepted_label_counts.get(decision.label.value, 0) + 1
                        )
                    elif decision.status.value == "REJECTED":
                        auto_rejected_count += 1
                    if decision.status.value != "REVIEW_REQUIRED":
                        continue
                    review_relationship_counts[decision.evidence_state.value] = (
                        review_relationship_counts.get(decision.evidence_state.value, 0) + 1
                    )
                    evidence = {item.evidence_id: item for item in rule_by_id[result.chunk.chunk_id].rule_evidence}
                    quotes = [evidence[eid].quote for eid in decision.rule_evidence_ids if eid in evidence and evidence[eid].quote]
                    item = Agent4N3ReviewItem(
                        source_id=source_id,
                        source_label=progress.label or progress.original_filename,
                        artifact_type=result.chunk.artifact_type,
                        chunk_id=result.chunk.chunk_id,
                        chunk_context=chunk_by_id[result.chunk.chunk_id].text[:4000],
                        label=decision.label.value,
                        label_description=TESTING_INTELLIGENCE_TAXONOMY[decision.label].definition,
                        relationship=decision.evidence_state.value,
                        reason_codes=list(decision.reason_codes),
                        explanation=decision.explanation,
                        model_score=decision.model_score,
                        rule_detected=decision.rule_detected,
                        rule_evidence_quotes=quotes,
                        hybrid_result_id=result.result_id,
                        hybrid_manifest_fingerprint=fingerprint,
                        auto_accepted_labels=[label.value for label in result.accepted_labels],
                    )
                    items.append(item)
                    identity.append({
                        "source_id": source_id, "chunk_id": item.chunk_id,
                        "label": item.label, "hybrid_result_id": item.hybrid_result_id,
                        "hybrid_manifest_fingerprint": fingerprint,
                        "taxonomy_version": hybrid.taxonomy_version,
                        "hybrid_policy_version": hybrid.hybrid_policy_version,
                    })
        items.sort(key=lambda item: (item.source_id, item.chunk_id, item.label))
        identity.sort(key=lambda item: (item["source_id"], item["chunk_id"], item["label"]))
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return Agent4N3ReviewProjection(
            review_snapshot_fingerprint=fingerprint,
            execution_id=execution.execution_id,
            auto_accepted_count=auto_accepted_count,
            auto_rejected_count=auto_rejected_count,
            pending_review_count=len(items),
            review_relationship_counts=dict(sorted(review_relationship_counts.items())),
            auto_accepted_label_counts=dict(sorted(auto_accepted_label_counts.items())),
            items=items,
        )

    def _new_execution(self, record, n2, *, trigger, now, sources=None, retry_source_id=None, review_id=None):
        if n2 is None:
            raise Agent4WorkflowGateError("Completed Input Preparation evidence is required")
        if sources is None:
            sources = [Agent4N3SourceExecution(
                source_id=item.source_id,
                artifact_type=item.artifact_type,
                source_type=item.source_type,
                label=item.label,
                original_filename=item.original_filename,
                status=(Agent4N3SourceStatus.PENDING_ANALYSIS if item.source_type is TestGenerationInputSourceType.IMAGE else Agent4N3SourceStatus.QUEUED),
                chunk_count=item.chunk_count,
                sub_stages=new_n3_sub_stages(),
                updated_at=now,
            ) for item in n2.sources]
        for source in sources:
            self._ensure_source_sub_stages(source)
            if source.source_type is TestGenerationInputSourceType.IMAGE:
                for stage in source.sub_stages:
                    stage.status = Agent4N3SubStageStatus.NOT_APPLICABLE
                    stage.completed_at = source.completed_at or now
        snapshot_sources = []
        for item in n2.sources:
            snapshot_item = {"source_id": item.source_id, "chunk_count": item.chunk_count}
            if item.source_type is not TestGenerationInputSourceType.IMAGE:
                chunks = self._chunks.load(
                    agent_project_id=record.agent_project_id,
                    owner_user_id=record.owner_user_id,
                    source_id=item.source_id,
                )
                if chunks is None:
                    raise Agent4WorkflowGateError("Current prepared chunks are unavailable")
                snapshot_item.update(
                    chunk_set_fingerprint=chunks.chunk_set_fingerprint,
                    chunk_ids=chunks.chunk_ids,
                )
            snapshot_sources.append(snapshot_item)
        snapshot = hashlib.sha256(json.dumps({
            "confirmation_id": n2.confirmation_id,
            "n2_execution_id": n2.execution_id,
            "sources": snapshot_sources,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (
            trigger in {"SOURCE_RETRY", "HUMAN_REVIEW_RESUME", "RESTART_RECOVERY"}
            and record.n3_executions
            and snapshot != record.n3_executions[-1].chunk_snapshot_fingerprint
        ):
            raise Agent4WorkflowGateError("Prepared chunk evidence changed; restart preparation before continuing")
        execution = Agent4N3Execution(
            execution_id=f"A4N3E-{uuid4().hex}",
            attempt_number=len(record.n3_executions) + 1,
            trigger=trigger,
            retry_source_id=retry_source_id,
            status=Agent4N3ExecutionStatus.QUEUED,
            confirmation_id=n2.confirmation_id,
            n2_execution_id=n2.execution_id,
            chunk_snapshot_fingerprint=snapshot,
            sources=sources,
            review_id=review_id,
            created_at=now, queued_at=now, updated_at=now,
        )
        self._refresh_execution_sub_stages(execution)
        return execution

    def _queue(self, record, execution):
        record.n3_executions.append(execution)
        record.current_n3_execution_id = execution.execution_id
        record.pipeline_status = Agent4PipelineStatus.RUNNING
        active_node = self._execution_node(execution)
        self._set_processing_node(
            record, active_node, Agent4WorkflowNodeStatus.QUEUED,
            execution.queued_at,
        )
        record.updated_at = execution.queued_at

    def _stage(self, project_id, owner_id, execution_id, source_id, status):
        self._set_source(project_id, owner_id, execution_id, source_id, status=status, started_at=self._clock())

    def _set_source(self, project_id, owner_id, execution_id, source_id, **updates):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            self._ensure_source_sub_stages(source)
            for key, value in updates.items():
                setattr(source, key, value)
            now = self._clock()
            source.updated_at = now
            execution.updated_at = now
            self._refresh_execution_sub_stages(execution)
            record.updated_at = now
            self._workflow.save(record)

    def _fail_submission(self, project_id, execution_id, owner_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            now = self._clock()
            execution.status = Agent4N3ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(code="N3_EXECUTOR_UNAVAILABLE", message="Testing Intelligence could not be queued and can be retried.")
            for source in execution.sources:
                if execution.retry_source_id and source.source_id != execution.retry_source_id:
                    continue
                if source.status in {
                    Agent4N3SourceStatus.COMPLETE,
                    Agent4N3SourceStatus.PENDING_ANALYSIS,
                }:
                    continue
                self._ensure_source_sub_stages(source)
                next_stage = get_next_n3_substage(source.sub_stages)
                if next_stage is not None:
                    stage = self._sub_stage(source, next_stage)
                    stage.status = Agent4N3SubStageStatus.FAILED
                    stage.failed_at = now
                    stage.safe_error = execution.error
                    stage.retryable = True
                    source.status = Agent4N3SourceStatus.FAILED
                    source.failed_stage = next_stage.value
                    source.error = execution.error
                    source.retryable = True
                    source.updated_at = now
            self._refresh_execution_sub_stages(execution)
            self._mark_failed(record, now, execution)
            self._workflow.save(record)

    def _fail_execution(self, project_id, owner_id, execution_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            if execution.status not in ACTIVE_N3_STATES:
                return
            now = self._clock()
            execution.status = Agent4N3ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(code="N3_EXECUTION_FAILED", message="Testing Intelligence could not complete safely.")
            for source in execution.sources:
                self._ensure_source_sub_stages(source)
                active = next((
                    stage for stage in source.sub_stages
                    if stage.status in {
                        Agent4N3SubStageStatus.QUEUED,
                        Agent4N3SubStageStatus.RUNNING,
                    }
                ), None)
                if active is None:
                    continue
                active.status = Agent4N3SubStageStatus.FAILED
                active.failed_at = now
                active.safe_error = execution.error
                active.retryable = True
                source.status = Agent4N3SourceStatus.FAILED
                source.failed_stage = active.stage.value
                source.error = execution.error
                source.retryable = True
                source.updated_at = now
            self._refresh_execution_sub_stages(execution)
            self._mark_failed(record, now, execution)
            self._workflow.save(record)

    def _mark_failed(self, record, now, execution):
        node_id = self._execution_node(execution)
        node = self._node(record, node_id)
        node.status = Agent4WorkflowNodeStatus.FAILED
        node.updated_at = now
        record.pipeline_status = Agent4PipelineStatus.FAILED
        record.current_node_id = node_id
        record.updated_at = now

    @staticmethod
    def _execution_node(execution):
        """Map the persisted N3 checkpoint to its authoritative canvas node."""
        processable = [
            source for source in execution.sources
            if source.status is not Agent4N3SourceStatus.PENDING_ANALYSIS
        ]
        if processable and all(
            all(
                stage.status in SUCCESSFUL_SUB_STAGE_STATUSES
                for stage in source.sub_stages
                if stage.stage is not Agent4N3SubStageName.FACT_EXTRACTION
            )
            for source in processable
        ):
            return Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION
        return Agent4TestGenerationNodeId.TESTING_INTELLIGENCE

    def _set_processing_node(self, record, node_id, status, now):
        intelligence = self._node(
            record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
        )
        facts = self._node(
            record, Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION
        )
        if node_id is Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION:
            intelligence.status = Agent4WorkflowNodeStatus.COMPLETED
            intelligence.updated_at = now
            facts.status = status
            facts.updated_at = now
        else:
            intelligence.status = status
            intelligence.updated_at = now
            facts.status = Agent4WorkflowNodeStatus.LOCKED
            facts.updated_at = now
        record.current_node_id = node_id

    def _load_execution(self, project_id, owner_id, execution_id):
        return self._execution(self._require_record(project_id, owner_id), execution_id)

    def _require_record(self, project_id, owner_id):
        record = self._workflow.load(agent_project_id=project_id, owner_user_id=owner_id)
        if record is None:
            raise Agent4WorkflowGateError("Test Generation workflow is unavailable")
        return record

    @staticmethod
    def _node(record, node_id):
        return next(item for item in record.nodes if item.node_id is node_id)

    @staticmethod
    def _execution(record, execution_id):
        execution = next((item for item in record.n3_executions if item.execution_id == execution_id), None)
        if execution is None:
            raise Agent4WorkflowGateError("Testing Intelligence execution is unavailable")
        return execution

    @staticmethod
    def _source(execution, source_id):
        return next(item for item in execution.sources if item.source_id == source_id)

    @staticmethod
    def _current(record):
        if record.current_n3_execution_id is None:
            return None
        return Agent4N3OrchestrationService._execution(record, record.current_n3_execution_id)

    @staticmethod
    def _current_n2(record):
        return next((item for item in record.n2_executions if item.execution_id == record.current_n2_execution_id), None)
