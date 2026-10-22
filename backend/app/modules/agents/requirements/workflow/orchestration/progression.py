"""State-validated progression between requirement workflow nodes."""

from typing import Protocol

from app.modules.agents.requirements.workflow.contracts.n2 import RequirementN2Status
from app.modules.agents.requirements.workflow.contracts.n3 import RequirementN3Status
from app.modules.agents.requirements.workflow.orchestration.transitions import execution_by_id
from app.modules.agents.requirements.workflow.projection import confirmation_is_current
from app.modules.agents.requirements.workflow.storage import WORKFLOW_STATE_LOCK


class RequirementProgressionError(RuntimeError):
    """A safe boundary error raised when downstream progression cannot start."""


class N2CompletionProgression(Protocol):
    def advance_after_n2_complete(
        self, agent_project_id: str, owner_user_id: str, execution_id: str
    ) -> bool: ...


class NoOpN2CompletionProgression:
    def advance_after_n2_complete(
        self, agent_project_id: str, owner_user_id: str, execution_id: str
    ) -> bool:
        return False


class N3CompletionProgression(Protocol):
    def advance_after_n3_complete(self, agent_project_id: str, owner_user_id: str,
                                  execution_id: str) -> bool: ...


class NoOpN3CompletionProgression:
    def advance_after_n3_complete(self, agent_project_id, owner_user_id, execution_id): return False


class N4ProgressionCoordinator:
    def __init__(self, workflow_storage, n4_orchestration):
        self._states=workflow_storage; self._n4=n4_orchestration
    def advance_after_n3_complete(self, agent_project_id, owner_user_id, execution_id):
        with WORKFLOW_STATE_LOCK:
            record=self._states.load(agent_project_id=agent_project_id,owner_user_id=owner_user_id)
            current=next((x for x in record.n3_executions if x.execution_id==record.current_n3_execution_id),None) if record else None
            if current is None or current.execution_id!=execution_id or current.status is not RequirementN3Status.COMPLETE or current.result_summary is None:return False
            n4=next((x for x in record.n4_executions if x.execution_id==record.current_n4_execution_id),None)
            if n4 is not None and n4.status in {"FAILED","BLOCKED"}:return False
        self._n4.start(agent_project_id,owner_user_id); return True


class WorkflowProgressionCoordinator:
    """Validate persisted N2 authority before delegating N3 creation."""

    def __init__(self, workflow_storage, n3_orchestration) -> None:
        self._states = workflow_storage
        self._n3 = n3_orchestration

    def advance_after_n2_complete(
        self, agent_project_id: str, owner_user_id: str, execution_id: str
    ) -> bool:
        with WORKFLOW_STATE_LOCK:
            record = self._states.load(
                agent_project_id=agent_project_id, owner_user_id=owner_user_id
            )
            if record is None or record.current_n2_execution_id != execution_id:
                return False
            execution = execution_by_id(record, execution_id)
            if (
                execution is None
                or execution.status is not RequirementN2Status.COMPLETE
                or execution.result_summary is None
                or execution.chunk_set_digest is None
                or execution.result_summary.source_count != len(execution.input_sources)
                or execution.result_summary.completed_source_count
                != execution.result_summary.source_count
                or execution.result_summary.chunk_count < 1
                or not confirmation_is_current(record)
                or record.n1_confirmation is None
                or execution.confirmed_source_set_digest
                != record.n1_confirmation.source_set_digest
                or execution.confirmed_selection_digest
                != record.n1_confirmation.selection_digest
            ):
                return False
            current_n3 = next(
                (
                    item
                    for item in reversed(record.n3_executions)
                    if item.execution_id == record.current_n3_execution_id
                ),
                None,
            )
            if (
                current_n3 is not None
                and current_n3.n2_execution_id == execution_id
                and current_n3.status
                in {RequirementN3Status.FAILED, RequirementN3Status.BLOCKED}
            ):
                return False
        try:
            self._n3.start(agent_project_id, owner_user_id)
        except Exception as exc:
            raise RequirementProgressionError(
                "Automatic requirement discovery could not be started."
            ) from exc
        return True
