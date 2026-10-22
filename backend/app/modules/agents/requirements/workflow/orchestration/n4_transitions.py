from app.modules.agents.requirements.workflow.contracts.n4 import RequirementN4Error, RequirementN4Status

def n4_by_id(r, i): return next((x for x in r.n4_executions if x.execution_id == i), None)
def current_n4(r): return n4_by_id(r, r.current_n4_execution_id) if r.current_n4_execution_id else None
def queue_n4(r, e, *, updated_at): r.n4_executions.append(e); r.current_n4_execution_id=e.execution_id; r.updated_at=updated_at
def running(r,e,*,at): e.status=RequirementN4Status.RUNNING; e.started_at=at; r.updated_at=at
def complete(r,e,s,*,at): e.status=RequirementN4Status.COMPLETE; e.completed_at=at; e.result_summary=s; e.retryable=False; r.updated_at=at
def failed(r,e,code,message,*,at): e.status=RequirementN4Status.FAILED; e.failed_at=at; e.retryable=True; e.error=RequirementN4Error(code=code,message=message); r.updated_at=at
def blocked(r,e,*,at): e.status=RequirementN4Status.BLOCKED; e.failed_at=at; e.retryable=False; e.error=RequirementN4Error(code="QUALITY_EXECUTION_INPUT_STALE",message="Authoritative quality input changed."); r.updated_at=at
