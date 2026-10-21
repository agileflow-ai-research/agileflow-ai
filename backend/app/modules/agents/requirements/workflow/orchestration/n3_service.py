from collections.abc import Callable
from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock

from app.modules.agents.requirements.discovery.structuring import STRUCTURING_CONTRACT_VERSION
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from app.modules.agents.requirements.workflow.executor import AGENT1_N3_EXECUTOR
from app.modules.agents.requirements.workflow.orchestration.n3_identity import (
    build_n3_execution, n3_execution_key,
)
from app.modules.agents.requirements.workflow.orchestration.n3_runner import RequirementN3Runner
from app.modules.agents.requirements.workflow.orchestration.n3_transitions import (
    current_n3_execution, mark_n3_interrupted, queue_n3,
)
from app.modules.agents.requirements.workflow.storage import WORKFLOW_STATE_LOCK


def utc_now(): return datetime.now(timezone.utc)


class RequirementN3OrchestrationError(ValueError): pass


class RequirementN3OrchestrationService:
    _active_lock = Lock()
    _active_execution_ids: set[str] = set()

    def __init__(self, workflow_storage, input_loader, detector, classifier,
                 structuring, discovery_storage, *, executor: Executor = AGENT1_N3_EXECUTOR,
                 clock: Callable[[], datetime] = utc_now):
        self._states = workflow_storage; self._inputs = input_loader
        self._detector = detector; self._classifier = classifier
        self._executor = executor; self._clock = clock
        self._runner = RequirementN3Runner(
            workflow_storage, input_loader, detector, classifier, structuring,
            discovery_storage, clock=clock,
        )

    def start(self, agent_project_id: str, owner_user_id: str):
        input_value = self._inputs.load(agent_project_id=agent_project_id, owner_user_id=owner_user_id)
        detector_fp = self._detector.configuration_fingerprint
        classifier_fp = self._classifier.model_identity.configuration_fingerprint
        key = n3_execution_key(
            agent_project_id=agent_project_id,
            n2_execution_id=input_value.reference.n2_execution_id,
            chunk_set_digest=input_value.reference.chunk_set_digest,
            discovery_input_identity=input_value.input_identity,
            candidate_detector_fingerprint=detector_fp,
            classifier_configuration_fingerprint=classifier_fp,
            structuring_contract_version=STRUCTURING_CONTRACT_VERSION,
        )
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            existing = next((item for item in reversed(record.n3_executions) if item.execution_key == key), None)
            if existing is not None:
                record.current_n3_execution_id = existing.execution_id; self._states.save(record)
                return existing
            execution = build_n3_execution(
                key=key, input_value=input_value, detector_fingerprint=detector_fp,
                classifier_fingerprint=classifier_fp,
                structuring_version=STRUCTURING_CONTRACT_VERSION,
                attempt_number=1, created_at=self._clock(),
            )
            queue_n3(record, execution, updated_at=self._clock()); self._states.save(record)
        self._submit(agent_project_id, owner_user_id, execution.execution_id)
        return execution

    def retry(self, agent_project_id: str, owner_user_id: str):
        input_value = self._inputs.load(agent_project_id=agent_project_id, owner_user_id=owner_user_id)
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id)
            previous = current_n3_execution(record)
            if previous is None: raise RequirementN3OrchestrationError("No N3 execution is available to retry")
            if previous.status is not RequirementN3Status.FAILED or not previous.retryable:
                return previous
            if (previous.n2_execution_id != input_value.reference.n2_execution_id
                    or previous.chunk_set_digest != input_value.reference.chunk_set_digest
                    or previous.discovery_input_identity != input_value.input_identity):
                raise RequirementN3OrchestrationError("N3 input changed; start a new execution")
            execution = build_n3_execution(
                key=previous.execution_key, input_value=input_value,
                detector_fingerprint=previous.candidate_detector_fingerprint,
                classifier_fingerprint=previous.classifier_configuration_fingerprint,
                structuring_version=previous.structuring_contract_version,
                attempt_number=previous.attempt_number + 1, created_at=self._clock(),
            )
            queue_n3(record, execution, updated_at=self._clock()); self._states.save(record)
        self._submit(agent_project_id, owner_user_id, execution.execution_id)
        return execution

    def reconcile(self, agent_project_id, owner_user_id):
        with WORKFLOW_STATE_LOCK:
            record = self._require_record(agent_project_id, owner_user_id); execution = current_n3_execution(record)
            if execution and execution.status in {RequirementN3Status.QUEUED, RequirementN3Status.RUNNING}:
                with self._active_lock: active = execution.execution_id in self._active_execution_ids
                if not active:
                    mark_n3_interrupted(record, execution, failed_at=self._clock(), updated_at=self._clock()); self._states.save(record)
            return execution

    def _submit(self, project, owner, execution_id):
        with self._active_lock:
            if execution_id in self._active_execution_ids: return
            self._active_execution_ids.add(execution_id)
        try: self._executor.submit(self._run, project, owner, execution_id)
        except RuntimeError:
            self._active_execution_ids.discard(execution_id)
            self._runner._fail(project, owner, execution_id, "N3_EXECUTOR_UNAVAILABLE", "Requirement discovery could not be started.")

    def _run(self, project, owner, execution_id):
        try: self._runner.run(project, owner, execution_id)
        finally:
            with self._active_lock: self._active_execution_ids.discard(execution_id)

    def _require_record(self, project, owner):
        record = self._states.load(agent_project_id=project, owner_user_id=owner)
        if record is None: raise RequirementN3OrchestrationError("Requirements workflow is unavailable")
        return record
