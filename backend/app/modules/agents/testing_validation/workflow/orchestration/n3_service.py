import hashlib
import json
from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.modules.agents.testing_validation.contracts.sources import TestGenerationInputSourceType
from app.modules.agents.testing_validation.intelligence.effective.service import Agent4EffectiveClassificationService
from app.modules.agents.testing_validation.intelligence.hybrid.service import manifest_fingerprint
from app.modules.agents.testing_validation.intelligence.taxonomy import TESTING_INTELLIGENCE_TAXONOMY
from app.modules.agents.testing_validation.workflow.orchestration.executor import AGENT4_N3_EXECUTOR
from app.modules.agents.testing_validation.workflow.projection import build_agent4_workflow_response
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionStatus,
    Agent4N2Message,
    Agent4N3Execution,
    Agent4N3ExecutionStatus,
    Agent4N3ReviewEvent,
    Agent4N3ReviewItem,
    Agent4N3ReviewProjection,
    Agent4N3ReviewResolution,
    Agent4N3ReviewSubmission,
    Agent4N3SourceExecution,
    Agent4N3SourceStatus,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.service import Agent4WorkflowGateError
from app.modules.agents.testing_validation.workflow.storage import AGENT4_WORKFLOW_STATE_LOCK


def utc_now():
    return datetime.now(timezone.utc)


ACTIVE_N3_STATES = {Agent4N3ExecutionStatus.QUEUED, Agent4N3ExecutionStatus.RUNNING}


class Agent4N3ReviewError(ValueError):
    pass


class Agent4N3OrchestrationService:
    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(
        self, workflow_service, workflow_storage, chunk_storage,
        rule_service, zero_shot_service, hybrid_service, semantic_service,
        effective_service: Agent4EffectiveClassificationService,
        hybrid_storage, rule_storage, zero_shot_storage,
        *, executor: Executor = AGENT4_N3_EXECUTOR,
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
        self._executor = executor
        self._clock = clock

    def get(self, project_id, user):
        self._workflow_service.get(project_id, user)
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, user.user_id)
            current = self._current(record)
            if current and current.status in ACTIVE_N3_STATES:
                with self._active_lock:
                    active = current.execution_id in self._active_execution_ids
                if not active:
                    now = self._clock()
                    current.status = Agent4N3ExecutionStatus.INTERRUPTED
                    current.interrupted_at = now
                    current.updated_at = now
                    current.retryable = True
                    current.error = Agent4N2Message(
                        code="N3_EXECUTION_INTERRUPTED",
                        message="Testing Intelligence was interrupted and can be retried safely.",
                    )
                    for source in current.sources:
                        if source.status not in {
                            Agent4N3SourceStatus.COMPLETE,
                            Agent4N3SourceStatus.PENDING_ANALYSIS,
                            Agent4N3SourceStatus.WAITING_FOR_HUMAN,
                        }:
                            source.status = Agent4N3SourceStatus.FAILED
                            source.updated_at = now
                            source.error = Agent4N2Message(
                                code="N3_EXECUTION_INTERRUPTED",
                                message="Intelligence processing for this source was interrupted.",
                            )
                    self._mark_failed(record, now)
                    self._workflow.save(record)
            return build_agent4_workflow_response(record)

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
            self._workflow.save(record)
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
            self._workflow.save(record)
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
            if target is None or target.status is not Agent4N3SourceStatus.FAILED:
                raise Agent4WorkflowGateError("Only a failed current source can be retried.")
            sources = [s.model_copy(deep=True) for s in previous.sources]
            target = next(s for s in sources if s.source_id == source_id)
            target.status = Agent4N3SourceStatus.QUEUED
            target.error = None
            target.completed_at = None
            target.updated_at = self._clock()
            execution = self._new_execution(
                record, self._current_n2(record), trigger="SOURCE_RETRY",
                now=self._clock(), sources=sources, retry_source_id=source_id,
                review_id=previous.review_id,
            )
            self._queue(record, execution)
            self._workflow.save(record)
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
            # Build all effective snapshots before committing the append-only event.
            for source_id in sorted({item.source_id for item in event.resolutions}):
                hybrid = self._hybrid_storage.load(
                    agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id
                )
                if hybrid is None:
                    raise Agent4N3ReviewError("Current hybrid evidence is unavailable")
                self._effective.build(hybrid, owner_user_id=user.user_id, review=event)
            record.n3_review_history.append(event)
            sources = [s.model_copy(deep=True) for s in execution.sources]
            for source in sources:
                if source.status is Agent4N3SourceStatus.WAITING_FOR_HUMAN:
                    source.status = Agent4N3SourceStatus.QUEUED
                    source.pending_review_items = 0
                    source.effective_complete = True
                    source.error = None
                    source.updated_at = now
            continuation = self._new_execution(
                record, self._current_n2(record), trigger="HUMAN_REVIEW_RESUME",
                now=now, sources=sources, review_id=review_id,
            )
            self._queue(record, continuation)
            self._workflow.save(record)
        self._submit(project_id, continuation, user)
        return build_agent4_workflow_response(self._require_record(project_id, user.user_id))

    def _submit(self, project_id, execution, user):
        with self._active_lock:
            if execution.execution_id in self._active_execution_ids:
                return
            self._active_execution_ids.add(execution.execution_id)
        try:
            self._executor.submit(self._run, project_id, execution.execution_id, user)
        except Exception:
            with self._active_lock:
                self._active_execution_ids.discard(execution.execution_id)
            self._fail_submission(project_id, execution.execution_id, user.user_id)

    def _run(self, project_id, execution_id, user):
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
                self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE).status = Agent4WorkflowNodeStatus.RUNNING
                record.updated_at = now
                self._workflow.save(record)
            for source in list(execution.sources):
                if execution.retry_source_id and source.source_id != execution.retry_source_id:
                    continue
                if source.status in {Agent4N3SourceStatus.COMPLETE, Agent4N3SourceStatus.PENDING_ANALYSIS}:
                    continue
                self._process_source(project_id, user.user_id, execution_id, source.source_id, user)
            self._finish(project_id, user.user_id, execution_id)
        except Exception:
            self._fail_execution(project_id, user.user_id, execution_id)
        finally:
            with self._active_lock:
                self._active_execution_ids.discard(execution_id)

    def _process_source(self, project_id, owner_id, execution_id, source_id, user):
        try:
            execution = self._load_execution(project_id, owner_id, execution_id)
            source = self._source(execution, source_id)
            if source.source_type is TestGenerationInputSourceType.IMAGE:
                self._set_source(project_id, owner_id, execution_id, source_id,
                    status=Agent4N3SourceStatus.PENDING_ANALYSIS,
                    warnings=[Agent4N2Message(code="IMAGE_ANALYSIS_NOT_IMPLEMENTED", message="Visual semantic analysis is not implemented.")],
                    completed_at=self._clock())
                return
            resume = execution.trigger == "HUMAN_REVIEW_RESUME"
            if not resume:
                self._stage(project_id, owner_id, execution_id, source_id, Agent4N3SourceStatus.RULE_CLASSIFICATION)
                rules = self._rules.build(project_id, source_id, user, force=False)
                self._set_source(project_id, owner_id, execution_id, source_id, rules_complete=True)
                self._stage(project_id, owner_id, execution_id, source_id, Agent4N3SourceStatus.ZERO_SHOT_CLASSIFICATION)
                self._zero.build(project_id, source_id, user, force=False)
                self._set_source(project_id, owner_id, execution_id, source_id, zero_shot_complete=True)
                self._stage(project_id, owner_id, execution_id, source_id, Agent4N3SourceStatus.HYBRID_DECISION)
                hybrid = self._hybrid.build(project_id, source_id, user, force=False)
                self._set_source(project_id, owner_id, execution_id, source_id,
                    hybrid_complete=True,
                    accepted_label_count=hybrid.summary.accepted_label_count,
                    pending_review_items=hybrid.summary.review_label_count)
            else:
                hybrid = self._hybrid_storage.load(
                    agent_project_id=project_id, owner_user_id=owner_id, source_id=source_id
                )
                if hybrid is None:
                    raise Agent4WorkflowGateError("Current hybrid classification is unavailable")
            review = next(
                (item for item in reversed(self._require_record(project_id, owner_id).n3_review_history)
                 if item.review_id == execution.review_id), None
            )
            effective = None
            if hybrid.summary.review_label_count == 0 or review is not None:
                effective = self._effective.build(hybrid, owner_user_id=owner_id, review=review)
                self._set_source(project_id, owner_id, execution_id, source_id,
                    effective_complete=True,
                    accepted_label_count=effective.counts.accepted_label_count)
            self._stage(project_id, owner_id, execution_id, source_id, Agent4N3SourceStatus.SEMANTIC_EXTRACTION)
            semantic = self._semantic.build(
                project_id, source_id, user, force=False, effective=effective
            )
            if hybrid.summary.review_label_count and review is None:
                self._set_source(project_id, owner_id, execution_id, source_id,
                    status=Agent4N3SourceStatus.WAITING_FOR_HUMAN,
                    semantic_complete=False,
                    semantic_fact_count=semantic.metrics.fact_count,
                    completed_at=self._clock())
            else:
                self._set_source(project_id, owner_id, execution_id, source_id,
                    status=Agent4N3SourceStatus.COMPLETE,
                    semantic_complete=True,
                    pending_review_items=0,
                    semantic_fact_count=semantic.metrics.fact_count,
                    completed_at=self._clock())
        except Exception:
            current = self._source(
                self._load_execution(project_id, owner_id, execution_id), source_id
            )
            self._set_source(project_id, owner_id, execution_id, source_id,
                status=Agent4N3SourceStatus.FAILED,
                failed_stage=current.status.value,
                error=Agent4N2Message(code="N3_SOURCE_FAILED", message="Testing Intelligence failed for this source at its current stage."),
                completed_at=self._clock())

    def _finish(self, project_id, owner_id, execution_id):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            now = self._clock()
            failed = [s for s in execution.sources if s.status is Agent4N3SourceStatus.FAILED]
            waiting = [s for s in execution.sources if s.status is Agent4N3SourceStatus.WAITING_FOR_HUMAN]
            if failed:
                execution.status = Agent4N3ExecutionStatus.FAILED
                execution.failed_at = now
                execution.retryable = True
                execution.error = Agent4N2Message(code="N3_SOURCE_FAILED", message="One or more sources could not complete Testing Intelligence.")
                self._mark_failed(record, now)
            elif waiting:
                projection = self._build_review_projection(record, execution, owner_id)
                execution.status = Agent4N3ExecutionStatus.WAITING_FOR_HUMAN
                execution.waiting_at = now
                execution.review_snapshot_fingerprint = projection.review_snapshot_fingerprint
                node = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
                node.status = Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
                node.updated_at = now
                record.pipeline_status = Agent4PipelineStatus.WAITING_FOR_HUMAN
                record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
            else:
                execution.status = Agent4N3ExecutionStatus.COMPLETED
                execution.completed_at = now
                execution.retryable = False
                n3 = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
                n4 = self._node(record, Agent4TestGenerationNodeId.CONTEXT_TESTABILITY)
                n3.status = Agent4WorkflowNodeStatus.COMPLETED
                n3.updated_at = now
                n4.status = Agent4WorkflowNodeStatus.NOT_STARTED
                n4.updated_at = now
                record.current_node_id = Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
                record.pipeline_status = Agent4PipelineStatus.RUNNING
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _build_review_projection(self, record, execution, owner_id):
        items = []
        identity = []
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
                    if decision.status.value != "REVIEW_REQUIRED":
                        continue
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
                updated_at=now,
            ) for item in n2.sources]
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
            trigger in {"SOURCE_RETRY", "HUMAN_REVIEW_RESUME"}
            and record.n3_executions
            and snapshot != record.n3_executions[-1].chunk_snapshot_fingerprint
        ):
            raise Agent4WorkflowGateError("Prepared chunk evidence changed; restart preparation before continuing")
        return Agent4N3Execution(
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

    def _queue(self, record, execution):
        record.n3_executions.append(execution)
        record.current_n3_execution_id = execution.execution_id
        record.pipeline_status = Agent4PipelineStatus.RUNNING
        record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
        node = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
        node.status = Agent4WorkflowNodeStatus.QUEUED
        node.updated_at = execution.queued_at
        record.updated_at = execution.queued_at

    def _stage(self, project_id, owner_id, execution_id, source_id, status):
        self._set_source(project_id, owner_id, execution_id, source_id, status=status, started_at=self._clock())

    def _set_source(self, project_id, owner_id, execution_id, source_id, **updates):
        with AGENT4_WORKFLOW_STATE_LOCK:
            record = self._require_record(project_id, owner_id)
            execution = self._execution(record, execution_id)
            source = self._source(execution, source_id)
            for key, value in updates.items():
                setattr(source, key, value)
            now = self._clock()
            source.updated_at = now
            execution.updated_at = now
            record.updated_at = now
            self._workflow.save(record)

    def _fail_submission(self, project_id, execution_id, owner_id):
        record = self._require_record(project_id, owner_id)
        with AGENT4_WORKFLOW_STATE_LOCK:
            execution = self._execution(record, execution_id)
            now = self._clock()
            execution.status = Agent4N3ExecutionStatus.FAILED
            execution.failed_at = now
            execution.updated_at = now
            execution.retryable = True
            execution.error = Agent4N2Message(code="N3_EXECUTOR_UNAVAILABLE", message="Testing Intelligence could not be queued and can be retried.")
            self._mark_failed(record, now)
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
            self._mark_failed(record, now)
            self._workflow.save(record)

    def _mark_failed(self, record, now):
        node = self._node(record, Agent4TestGenerationNodeId.TESTING_INTELLIGENCE)
        node.status = Agent4WorkflowNodeStatus.FAILED
        node.updated_at = now
        record.pipeline_status = Agent4PipelineStatus.FAILED
        record.current_node_id = Agent4TestGenerationNodeId.TESTING_INTELLIGENCE
        record.updated_at = now

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
