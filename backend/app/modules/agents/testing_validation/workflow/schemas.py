from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.common.status import AgentStage


class StrictAgent4WorkflowContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Agent4TestGenerationNodeId(StrEnum):
    INPUT_OUTPUT_SETUP = "INPUT_OUTPUT_SETUP"
    INPUT_PREPARATION = "INPUT_PREPARATION"
    TESTING_INTELLIGENCE = "TESTING_INTELLIGENCE"
    CONTEXT_TESTABILITY = "CONTEXT_TESTABILITY"
    TEST_PLANNING_REVIEW = "TEST_PLANNING_REVIEW"
    TEST_GENERATION_RESULTS = "TEST_GENERATION_RESULTS"


AGENT4_TEST_GENERATION_NODE_ORDER = tuple(Agent4TestGenerationNodeId)


class Agent4WorkflowNodeStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    LOCKED = "LOCKED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Agent4PipelineStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class Agent4WorkflowNodeState(StrictAgent4WorkflowContract):
    node_id: Agent4TestGenerationNodeId
    status: Agent4WorkflowNodeStatus
    updated_at: datetime


class Agent4TestGenerationWorkflowRecord(StrictAgent4WorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    owner_user_id: str
    agent_stage: Literal[AgentStage.TEST_GENERATION]
    pipeline_status: Agent4PipelineStatus
    current_node_id: Agent4TestGenerationNodeId
    nodes: list[Agent4WorkflowNodeState]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_node_contract(self) -> "Agent4TestGenerationWorkflowRecord":
        if tuple(node.node_id for node in self.nodes) != AGENT4_TEST_GENERATION_NODE_ORDER:
            raise ValueError("nodes must match the Agent 4 Test Generation workflow order")
        return self


class Agent4TestGenerationWorkflowResponse(StrictAgent4WorkflowContract):
    schema_version: str
    workflow_version: str
    agent_project_id: str
    agent_stage: Literal[AgentStage.TEST_GENERATION]
    pipeline_status: Agent4PipelineStatus
    current_node_id: Agent4TestGenerationNodeId
    nodes: list[Agent4WorkflowNodeState]
    created_at: datetime
    updated_at: datetime
