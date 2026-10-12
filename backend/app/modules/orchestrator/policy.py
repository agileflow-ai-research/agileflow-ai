from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from app.common.status import ApprovalGate, WorkflowStage


ORCHESTRATOR_COMPONENT = "Central SDLC Orchestrator"
HUMAN_REVIEWER_COMPONENT = "Human Stakeholder / Reviewer"
REQUIREMENTS_COMPONENT = "Requirement Gathering and Analysis Agent"
DESIGN_COMPONENT = "Project Management and Design Agent"
TESTING_COMPONENT = "Testing, Validation and Security Agent"
IMPLEMENTATION_COMPONENT = "Implementation and Git Automation Agent"


class TransitionPrerequisite(str, Enum):
    CLIENT_INPUT = "CLIENT_INPUT"
    SPECIALIST_HANDOFF = "SPECIALIST_HANDOFF"
    EFFECTIVE_APPROVAL = "EFFECTIVE_APPROVAL"


STAGE_OWNERS = MappingProxyType(
    {
        WorkflowStage.PROJECT_CREATED: (
            "Central SDLC Orchestrator / shared foundation"
        ),
        WorkflowStage.REQUIREMENTS_IN_PROGRESS: REQUIREMENTS_COMPONENT,
        WorkflowStage.H1_WAITING_APPROVAL: (
            "Human approval managed by Central SDLC Orchestrator"
        ),
        WorkflowStage.DESIGN_IN_PROGRESS: DESIGN_COMPONENT,
        WorkflowStage.H2_WAITING_APPROVAL: (
            "Human approval managed by Central SDLC Orchestrator"
        ),
        WorkflowStage.TEST_PLANNING_IN_PROGRESS: TESTING_COMPONENT,
        WorkflowStage.H3_WAITING_APPROVAL: (
            "Human approval managed by Central SDLC Orchestrator"
        ),
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS: IMPLEMENTATION_COMPONENT,
        WorkflowStage.H4_WAITING_APPROVAL: (
            "Human approval managed by Central SDLC Orchestrator"
        ),
        WorkflowStage.VALIDATION_IN_PROGRESS: TESTING_COMPONENT,
        WorkflowStage.H5_WAITING_APPROVAL: (
            "Human approval managed by Central SDLC Orchestrator"
        ),
        WorkflowStage.COMPLETED: (
            "Central SDLC Orchestrator / completed workflow"
        ),
    }
)


@dataclass(frozen=True, slots=True)
class TransitionDefinition:
    source_stage: WorkflowStage
    target_stage: WorkflowStage
    responsible_component: str
    approval_gate: ApprovalGate | None = None
    prerequisite: TransitionPrerequisite | None = None
    executable: bool = False


TRANSITIONS = (
    TransitionDefinition(
        WorkflowStage.PROJECT_CREATED,
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        REQUIREMENTS_COMPONENT,
        prerequisite=TransitionPrerequisite.CLIENT_INPUT,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.REQUIREMENTS_IN_PROGRESS,
        WorkflowStage.H1_WAITING_APPROVAL,
        STAGE_OWNERS[WorkflowStage.H1_WAITING_APPROVAL],
        ApprovalGate.H1,
        TransitionPrerequisite.SPECIALIST_HANDOFF,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.H1_WAITING_APPROVAL,
        WorkflowStage.DESIGN_IN_PROGRESS,
        DESIGN_COMPONENT,
        ApprovalGate.H1,
        TransitionPrerequisite.EFFECTIVE_APPROVAL,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.DESIGN_IN_PROGRESS,
        WorkflowStage.H2_WAITING_APPROVAL,
        STAGE_OWNERS[WorkflowStage.H2_WAITING_APPROVAL],
        ApprovalGate.H2,
        TransitionPrerequisite.SPECIALIST_HANDOFF,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.H2_WAITING_APPROVAL,
        WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        TESTING_COMPONENT,
        ApprovalGate.H2,
        TransitionPrerequisite.EFFECTIVE_APPROVAL,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        WorkflowStage.H3_WAITING_APPROVAL,
        STAGE_OWNERS[WorkflowStage.H3_WAITING_APPROVAL],
        ApprovalGate.H3,
        TransitionPrerequisite.SPECIALIST_HANDOFF,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.H3_WAITING_APPROVAL,
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        IMPLEMENTATION_COMPONENT,
        ApprovalGate.H3,
        TransitionPrerequisite.EFFECTIVE_APPROVAL,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        WorkflowStage.H4_WAITING_APPROVAL,
        STAGE_OWNERS[WorkflowStage.H4_WAITING_APPROVAL],
        ApprovalGate.H4,
        TransitionPrerequisite.SPECIALIST_HANDOFF,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.H4_WAITING_APPROVAL,
        WorkflowStage.VALIDATION_IN_PROGRESS,
        TESTING_COMPONENT,
        ApprovalGate.H4,
        TransitionPrerequisite.EFFECTIVE_APPROVAL,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.VALIDATION_IN_PROGRESS,
        WorkflowStage.H5_WAITING_APPROVAL,
        STAGE_OWNERS[WorkflowStage.H5_WAITING_APPROVAL],
        ApprovalGate.H5,
        TransitionPrerequisite.SPECIALIST_HANDOFF,
        executable=True,
    ),
    TransitionDefinition(
        WorkflowStage.H5_WAITING_APPROVAL,
        WorkflowStage.COMPLETED,
        STAGE_OWNERS[WorkflowStage.COMPLETED],
        ApprovalGate.H5,
        TransitionPrerequisite.EFFECTIVE_APPROVAL,
        executable=True,
    ),
)


TRANSITION_BY_SOURCE = MappingProxyType(
    {transition.source_stage: transition for transition in TRANSITIONS}
)


def get_stage_owner(stage: WorkflowStage) -> str:
    return STAGE_OWNERS[stage]


def get_transition(stage: WorkflowStage) -> TransitionDefinition | None:
    return TRANSITION_BY_SOURCE.get(stage)


def is_legal_transition(
    source_stage: WorkflowStage,
    target_stage: WorkflowStage,
) -> bool:
    transition = get_transition(source_stage)
    return transition is not None and transition.target_stage is target_stage
