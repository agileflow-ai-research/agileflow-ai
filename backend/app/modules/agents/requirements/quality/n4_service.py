from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

from app.modules.agents.requirements.quality.n4_identity import build_n4_execution, n4_execution_key
from app.modules.agents.requirements.quality.n4_runner import RequirementN4Runner
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Status
from app.modules.agents.requirements.workflow.orchestration.n4_transitions import current_n4, failed, queue_n4
from app.modules.agents.requirements.workflow.storage import WORKFLOW_STATE_LOCK

N4_EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix="agent1-n4")
def utc_now(): return datetime.now(timezone.utc)

class RequirementN4OrchestrationError(ValueError): pass

class RequirementN4OrchestrationService:
    _active_lock=Lock(); _active=set()
    def __init__(self,states,inputs,exact,semantic,conflicts,clarity,findings,artifacts,*,configuration_fingerprint,executor=N4_EXECUTOR,clock=utc_now):
        self._states=states; self._inputs=inputs; self._config=configuration_fingerprint; self._executor=executor; self._clock=clock
        self._runner=RequirementN4Runner(states,inputs,exact,semantic,conflicts,clarity,findings,artifacts,clock=clock)
    def start(self,project,owner):
        value=self._inputs.load(agent_project_id=project,owner_user_id=owner)
        with WORKFLOW_STATE_LOCK:
            r=self._require(project,owner); n3=next((x for x in r.n3_executions if x.execution_id==r.current_n3_execution_id),None)
            if n3 is None or n3.status is not RequirementN3Status.COMPLETE or n3.result_summary is None: raise RequirementN4OrchestrationError("Authoritative N3 is not complete")
            key=n4_execution_key(agent_project_id=project,n3_execution_id=n3.execution_id,n3_attempt=n3.attempt_number,structured_digest=n3.result_summary.structured_artifact_digest,quality_input_identity=value.input_identity,configuration_fingerprint=self._config)
            existing=next((x for x in reversed(r.n4_executions) if x.execution_key==key),None)
            if existing is not None: r.current_n4_execution_id=existing.execution_id; self._states.save(r); return existing
            e=build_n4_execution(key=key,n3=n3,quality_input_identity=value.input_identity,configuration_fingerprint=self._config,attempt_number=1,created_at=self._clock())
            queue_n4(r,e,updated_at=self._clock()); self._states.save(r)
        self._submit(project,owner,e.execution_id); return e
    def retry(self,project,owner):
        with WORKFLOW_STATE_LOCK:
            r=self._require(project,owner); old=current_n4(r)
            if old is None or old.status is not RequirementN4Status.FAILED or not old.retryable: return old
            n3=next((x for x in r.n3_executions if x.execution_id==r.current_n3_execution_id),None)
            if n3 is None or n3.execution_id!=old.authoritative_n3_execution_id or n3.status is not RequirementN3Status.COMPLETE: raise RequirementN4OrchestrationError("N4 input changed")
            e=build_n4_execution(key=old.execution_key,n3=n3,quality_input_identity=old.quality_input_identity,configuration_fingerprint=old.configuration_fingerprint,attempt_number=old.attempt_number+1,created_at=self._clock())
            queue_n4(r,e,updated_at=self._clock()); self._states.save(r)
        self._submit(project,owner,e.execution_id); return e
    def reconcile(self,project,owner):
        with WORKFLOW_STATE_LOCK:
            r=self._require(project,owner); e=current_n4(r)
            if e and e.status in {RequirementN4Status.QUEUED,RequirementN4Status.RUNNING}:
                with self._active_lock: active=e.execution_id in self._active
                if not active: failed(r,e,"QUALITY_EXECUTION_INTERRUPTED","Quality execution was interrupted and can be retried safely.",at=self._clock()); self._states.save(r)
            return e
    def _submit(self,p,o,i):
        with self._active_lock:
            if i in self._active:return
            self._active.add(i)
        self._executor.submit(self._run,p,o,i)
    def _run(self,p,o,i):
        try:self._runner.run(p,o,i)
        finally:
            with self._active_lock:self._active.discard(i)
    def _require(self,p,o):
        r=self._states.load(agent_project_id=p,owner_user_id=o)
        if r is None:raise RequirementN4OrchestrationError("Workflow unavailable")
        return r
