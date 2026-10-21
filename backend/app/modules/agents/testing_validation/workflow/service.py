from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.contracts.sources import (
    get_test_generation_artifact_policy,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode
from app.modules.agents.testing_validation.sources.storage import Agent4SourceStorage
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
    AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
)
from app.modules.agents.testing_validation.workflow.digests import (
    output_selection_digest,
    source_set_digest,
)
from app.modules.agents.testing_validation.workflow.projection import (
    build_agent4_workflow_response,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    AGENT4_TEST_GENERATION_NODE_ORDER,
    Agent4PipelineStatus,
    Agent4N1ConfirmationRecord,
    Agent4TestGenerationNodeId,
    Agent4TestGenerationWorkflowRecord,
    Agent4TestGenerationWorkflowResponse,
    Agent4WorkflowNodeState,
    Agent4WorkflowNodeStatus,
    canonical_test_generation_outputs,
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


class Agent4WorkflowGateError(ValueError):
    pass


class Agent4SetupConfirmedError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4WorkflowService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        workflow_storage: Agent4WorkflowStorage,
        source_storage: Agent4SourceStorage,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._workflow = workflow_storage
        self._sources = source_storage
        self._clock = clock

    def get(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            record = self._load_or_initialize(
                project.agent_project_id, current_user.user_id
            )
            return build_agent4_workflow_response(record)

    def update_outputs(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        outputs: list[TestGenerationOutputCode],
    ) -> Agent4TestGenerationWorkflowResponse:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            record = self._load_or_initialize(
                project.agent_project_id, current_user.user_id
            )
            if record.n1_confirmation is not None:
                raise Agent4SetupConfirmedError(
                    "Input and output setup has already been confirmed."
                )
            next_outputs = canonical_test_generation_outputs(outputs)
            if next_outputs != record.selected_outputs:
                now = self._clock()
                record = record.model_copy(
                    update={
                        "selected_outputs": next_outputs,
                        "selection_revision": record.selection_revision + 1,
                        "selection_updated_at": now,
                        "updated_at": now,
                    }
                )
                self._workflow.save(record)
            return build_agent4_workflow_response(record)

    def confirm_n1(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> Agent4TestGenerationWorkflowResponse:
        with AGENT4_WORKFLOW_STATE_LOCK:
            project = self._require_project(agent_project_id, current_user)
            record = self._load_or_initialize(
                project.agent_project_id, current_user.user_id
            )
            sources = self._sources.list_for_project(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
            )
            current_source_digest = source_set_digest(sources)
            current_selection_digest = output_selection_digest(
                record.selected_outputs
            )
            if record.n1_confirmation is not None:
                if self._confirmation_is_current(
                    record,
                    sources,
                    current_source_digest,
                    current_selection_digest,
                ):
                    return build_agent4_workflow_response(record)
                raise Agent4SetupConfirmedError(
                    "The confirmed setup no longer matches persisted inputs."
                )
            if not sources:
                raise Agent4WorkflowGateError(
                    "Add at least one source before confirming setup."
                )
            if not record.selected_outputs:
                raise Agent4WorkflowGateError(
                    "Save at least one desired output before confirming setup."
                )
            if not any(
                get_test_generation_artifact_policy(source.artifact_type)
                .primary_functional
                for source in sources
            ):
                raise Agent4WorkflowGateError(
                    "Add at least one primary functional source before "
                    "confirming setup."
                )

            now = self._clock()
            confirmation = Agent4N1ConfirmationRecord(
                confirmation_id=f"A4N1C-{uuid4().hex}",
                source_set_digest=current_source_digest,
                selection_digest=current_selection_digest,
                selection_revision=record.selection_revision,
                source_ids=sorted(source.source_id for source in sources),
                selected_outputs=record.selected_outputs,
                source_count=len(sources),
                selected_output_count=len(record.selected_outputs),
                confirmed_at=now,
                confirmed_by_user_id=current_user.user_id,
            )
            nodes = [
                node.model_copy(
                    update={
                        "status": (
                            Agent4WorkflowNodeStatus.COMPLETED
                            if node.node_id
                            is Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP
                            else Agent4WorkflowNodeStatus.NOT_STARTED
                        ),
                        "updated_at": now,
                    }
                )
                if node.node_id
                in {
                    Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP,
                    Agent4TestGenerationNodeId.INPUT_PREPARATION,
                }
                else node
                for node in record.nodes
            ]
            confirmed = record.model_copy(
                update={
                    "pipeline_status": Agent4PipelineStatus.RUNNING,
                    "current_node_id": Agent4TestGenerationNodeId.INPUT_PREPARATION,
                    "nodes": nodes,
                    "n1_confirmation": confirmation,
                    "updated_at": now,
                }
            )
            self._workflow.save(confirmed)
            return build_agent4_workflow_response(confirmed)

    @staticmethod
    def _confirmation_is_current(
        record: Agent4TestGenerationWorkflowRecord,
        sources,
        current_source_digest: str,
        current_selection_digest: str,
    ) -> bool:
        confirmation = record.n1_confirmation
        return bool(
            confirmation
            and confirmation.source_set_digest == current_source_digest
            and confirmation.selection_digest == current_selection_digest
            and confirmation.selection_revision == record.selection_revision
            and confirmation.source_ids
            == sorted(source.source_id for source in sources)
            and confirmation.selected_outputs == record.selected_outputs
        )

    def _require_project(
        self, agent_project_id: str, current_user: UserPublicResponse
    ):
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
        return project

    def _load_or_initialize(
        self, agent_project_id: str, owner_user_id: str
    ) -> Agent4TestGenerationWorkflowRecord:
        record = self._workflow.load(
            agent_project_id=agent_project_id,
            owner_user_id=owner_user_id,
        )
        if record is None:
            record = self._initial_record(agent_project_id, owner_user_id)
            self._workflow.save(record)
        elif (record.schema_version, record.workflow_version) == ("1", "W1"):
            record = record.model_copy(
                update={
                    "schema_version": AGENT4_TEST_GENERATION_WORKFLOW_SCHEMA_VERSION,
                    "workflow_version": AGENT4_TEST_GENERATION_WORKFLOW_VERSION,
                    "updated_at": self._clock(),
                }
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
        return record

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
