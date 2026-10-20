from collections.abc import Callable
from datetime import datetime, timezone

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.projection import (
    build_agent4_workflow_response,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    AGENT4_TEST_GENERATION_NODE_ORDER,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
    Agent4WorkflowNodeState,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
    Agent4WorkflowStorage,
    Agent4WorkflowStorageError,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class WrongAgent4WorkflowProjectError(ValueError):
    pass


class Agent4WorkflowStageError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4WorkflowService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        workflow_storage: Agent4WorkflowStorage,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._workflow = workflow_storage
        self._clock = clock

    def get(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._standalone.require_active_project(
                current_user.user_id, agent_project_id
            )
            if project.agent_type is not AgentType.TESTING_VALIDATION:
                raise WrongAgent4WorkflowProjectError(
                    "Agent project must have agent_type TESTING_VALIDATION"
                )
            if project.agent_stage is not AgentStage.TEST_GENERATION:
                raise Agent4WorkflowStageError(
                    "Agent project must have agent_stage TEST_GENERATION"
                )

            record = self._workflow.load(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
            )
            if record is None:
                record = self._initial_record(
                    project.agent_project_id, current_user.user_id
                )
                self._workflow.save(record)
            elif (
                record.schema_version
                != AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION
                or record.workflow_version
                != AGENT4_TEST_GENERATION_WORKFLOW_VERSION
            ):
                raise Agent4WorkflowStorageError(
                    "Agent 4 workflow version is not supported"
                )
            return build_agent4_workflow_response(record)

    def _initial_record(
        self, agent_project_id: str, owner_user_id: str
    ) -> Agent4TestGenerationWorkflowRecord:
        now = self._clock()
        return Agent4TestGenerationWorkflowRecord(
            schema_version=AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
            workflow_version=AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
            agent_stage=AgentStage.TEST_GENERATION,
            pipeline_status=Agent4PipelineStatus.WAITING_FOR_HUMAN,
            current_node_id=Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP,
            nodes=[
                Agent4WorkflowNodeState(
                    node_id=node_id,
                    status=(
                        Agent4WorkflowNodeStatus.WAITING_FOR_HUMAN
                        if node_id is Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP
                        else Agent4WorkflowNodeStatus.LOCKED
                    ),
                    updated_at=now,
                )
                for node_id in AGENT4_TEST_GENERATION_NODE_ORDER
            ],
            created_at=now,
            updated_at=now,
        )
