from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType

from pydantic import ValidationError

from app.common.id_generator import generate_id
from app.common.status import (
    ApprovalDecision,
    ApprovalGate,
    EventType,
    WorkflowStage,
)
from app.modules.approvals.repository import (
    ApprovalRepository,
    ApprovalRepositoryError,
)
from app.modules.approvals.schemas import ApprovalCreateRequest
from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.orchestrator.policy import ORCHESTRATOR_COMPONENT
from app.schemas.approval import Approval
from app.schemas.workflow import WorkflowEvent


REVIEWER_COMPONENT = "Human Stakeholder / Reviewer"


@dataclass(frozen=True, slots=True)
class ApprovalGatePolicy:
    waiting_stage: WorkflowStage
    approved_next_stage: WorkflowStage


APPROVAL_GATE_POLICIES = MappingProxyType(
    {
        ApprovalGate.H1: ApprovalGatePolicy(
            WorkflowStage.H1_WAITING_APPROVAL,
            WorkflowStage.DESIGN_IN_PROGRESS,
        ),
        ApprovalGate.H2: ApprovalGatePolicy(
            WorkflowStage.H2_WAITING_APPROVAL,
            WorkflowStage.TEST_PLANNING_IN_PROGRESS,
        ),
        ApprovalGate.H3: ApprovalGatePolicy(
            WorkflowStage.H3_WAITING_APPROVAL,
            WorkflowStage.IMPLEMENTATION_IN_PROGRESS,
        ),
        ApprovalGate.H4: ApprovalGatePolicy(
            WorkflowStage.H4_WAITING_APPROVAL,
            WorkflowStage.VALIDATION_IN_PROGRESS,
        ),
        ApprovalGate.H5: ApprovalGatePolicy(
            WorkflowStage.H5_WAITING_APPROVAL,
            WorkflowStage.COMPLETED,
        ),
    }
)


class ApprovalStageConflictError(ValueError):
    """Raised when a gate does not match the Project's current stage."""

    def __init__(
        self,
        gate_id: ApprovalGate,
        current_stage: WorkflowStage,
        required_stage: WorkflowStage,
    ) -> None:
        self.gate_id = gate_id
        self.current_stage = current_stage
        self.required_stage = required_stage
        super().__init__(
            f"{gate_id.value} requires {required_stage.value}; "
            f"project is at {current_stage.value}"
        )


class ApprovalServiceError(RuntimeError):
    """Raised when an approval decision cannot be persisted safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalService:
    """Validate and append H1-H5 decisions without transitioning Projects."""

    def __init__(
        self,
        repository: ApprovalRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create_approval(
        self,
        project_id: str,
        gate_id: ApprovalGate,
        request: ApprovalCreateRequest,
        current_user: UserPublicResponse,
    ) -> Approval:
        try:
            project = authorize_project_access(
                project_id,
                current_user,
                self._repository,
            )
            policy = APPROVAL_GATE_POLICIES[gate_id]
            if project.current_stage is not policy.waiting_stage:
                raise ApprovalStageConflictError(
                    gate_id,
                    project.current_stage,
                    policy.waiting_stage,
                )

            next_stage = (
                policy.approved_next_stage
                if request.decision is ApprovalDecision.APPROVE
                else policy.waiting_stage
            )
            now = self._clock()
            approval = Approval(
                approval_id=generate_id(
                    "APP",
                    self._repository.next_approval_sequence(),
                ),
                project_id=project_id,
                gate_id=gate_id,
                reviewer_name=request.reviewer_name,
                reviewer_role=request.reviewer_role,
                decision=request.decision,
                comment=request.comment,
                timestamp=now,
                artifact_version=request.artifact_version,
                next_stage=next_stage,
            )
            event = WorkflowEvent(
                event_id=generate_id(
                    "EVT",
                    self._repository.next_event_sequence(),
                ),
                project_id=project_id,
                event_type=EventType.APPROVAL_DECISION,
                source_component=REVIEWER_COMPONENT,
                target_component=ORCHESTRATOR_COMPONENT,
                stage_before=policy.waiting_stage,
                stage_after=policy.waiting_stage,
                message=(
                    f"{gate_id.value} approval decision recorded: "
                    f"{request.decision.value}"
                ),
                metadata={
                    "approval_id": approval.approval_id,
                    "gate_id": gate_id.value,
                    "decision": request.decision.value,
                    "artifact_version": request.artifact_version,
                },
                created_at=now,
            )
            document = self._repository.create_approval_with_event(
                approval,
                event,
            )
            return Approval.model_validate(document)
        except (
            ProjectAccessNotFoundError,
            ApprovalStageConflictError,
            ApprovalServiceError,
        ):
            raise
        except (ApprovalRepositoryError, ValidationError) as exc:
            raise ApprovalServiceError(
                "Approval decision persistence failed"
            ) from exc


ApprovalProjectNotFoundError = ProjectAccessNotFoundError
