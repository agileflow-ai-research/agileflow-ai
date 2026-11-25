from copy import deepcopy
from enum import StrEnum

from pydantic import ValidationError

from app.common.status import AgentType
from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode,
)
from app.modules.agents.implementation.preparation.consolidation.constants import (
    ConflictStatus,
    ConsolidationStatus,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
    ReadinessStatus,
)
from app.modules.agents.implementation.preparation.readiness.trusted.policy import (
    digest,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    readiness_fingerprint,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.runs.constants import (
    IMPLEMENTATION_RUN_SCHEMA_VERSION,
    IMPLEMENTATION_RUN_SNAPSHOT_KIND,
)
from app.modules.agents.implementation.runs.schemas import (
    FinalApprovalDecision,
    ImplementationRunInputSnapshot,
    ImplementationRunStatus,
)
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    AgentRunNotFoundError,
    StandaloneServiceError,
)

from .schemas import ApprovedGenerationContext, ApprovedImplementationStack


class GenerationInputErrorCode(StrEnum):
    PROJECT_NOT_ACCESSIBLE = "PROJECT_NOT_ACCESSIBLE"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    WRONG_PROJECT = "WRONG_PROJECT"
    WRONG_AGENT_TYPE = "WRONG_AGENT_TYPE"
    MISSING_IMPLEMENTATION_SNAPSHOT = "MISSING_IMPLEMENTATION_SNAPSHOT"
    MISSING_FINAL_APPROVAL = "MISSING_FINAL_APPROVAL"
    INVALID_FINAL_APPROVAL = "INVALID_FINAL_APPROVAL"
    INVALID_GENERATION_READINESS = "INVALID_GENERATION_READINESS"
    MISSING_GENERATION_CONTEXT = "MISSING_GENERATION_CONTEXT"
    UNSUPPORTED_SELECTED_OUTPUT = "UNSUPPORTED_SELECTED_OUTPUT"
    MALFORMED_SNAPSHOT = "MALFORMED_SNAPSHOT"
    CORRUPTED_APPROVED_DATA = "CORRUPTED_APPROVED_DATA"
    STORAGE_UNAVAILABLE = "STORAGE_UNAVAILABLE"


class ApprovedGenerationInputError(ValueError):
    def __init__(self, code: GenerationInputErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class ApprovedGenerationInputLoader:
    """Loads and validates only the historical input stored on an AgentRun."""

    _REQUIRED_CONTEXT_FIELDS = frozenset(
        {
            "trusted_project_specification",
            "trusted_readiness",
            "selected_outputs",
            "implementation_stack",
            "delivery_snapshot",
            "traceability_root_refs",
        }
    )

    def __init__(self, standalone_service) -> None:
        self._standalone = standalone_service

    def load(self, project_id: str, run_id: str, current_user) -> ApprovedGenerationContext:
        project = self._load_project(project_id, current_user)
        if project.agent_type is not AgentType.IMPLEMENTATION:
            self._fail(
                GenerationInputErrorCode.WRONG_AGENT_TYPE,
                "The project is not an Agent 3 implementation project",
            )

        run = self._load_run(project_id, run_id, current_user)
        if run.agent_project_id != project_id:
            self._fail(
                GenerationInputErrorCode.WRONG_PROJECT,
                "The approved run does not belong to the specified project",
            )
        if run.agent_type is not AgentType.IMPLEMENTATION:
            self._fail(
                GenerationInputErrorCode.WRONG_AGENT_TYPE,
                "The approved run is not an Agent 3 implementation run",
            )

        raw = deepcopy(run.input_snapshot)
        if (
            not isinstance(raw, dict)
            or raw.get("snapshot_kind") != IMPLEMENTATION_RUN_SNAPSHOT_KIND
        ):
            self._fail(
                GenerationInputErrorCode.MISSING_IMPLEMENTATION_SNAPSHOT,
                "The run does not contain an approved implementation snapshot",
            )
        if "approval" not in raw or raw.get("approval") is None:
            self._fail(
                GenerationInputErrorCode.MISSING_FINAL_APPROVAL,
                "The implementation snapshot has no final approval",
            )
        raw_approval = raw.get("approval")
        if (
            not isinstance(raw_approval, dict)
            or raw_approval.get("decision") != FinalApprovalDecision.APPROVED
        ):
            self._fail(
                GenerationInputErrorCode.INVALID_FINAL_APPROVAL,
                "The implementation snapshot final approval is invalid",
            )
        if raw.get("run_status") != ImplementationRunStatus.READY_FOR_GENERATION:
            self._fail(
                GenerationInputErrorCode.INVALID_GENERATION_READINESS,
                "The approved snapshot is not ready for generation",
            )
        if missing := self._REQUIRED_CONTEXT_FIELDS.difference(raw):
            self._fail(
                GenerationInputErrorCode.MISSING_GENERATION_CONTEXT,
                "The approved snapshot is missing mandatory generation context",
            )
        self._validate_raw_outputs(raw.get("selected_outputs"))

        try:
            snapshot = ImplementationRunInputSnapshot.model_validate(raw)
        except ValidationError as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.MALFORMED_SNAPSHOT,
                "The approved implementation snapshot is malformed",
            ) from exc

        self._validate_consistency(project_id, run, snapshot)
        try:
            effective_stack = ApprovedImplementationStack.model_validate(
                snapshot.implementation_stack
            )
        except ValidationError as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.MISSING_GENERATION_CONTEXT,
                "The approved snapshot has no valid effective implementation stack",
            ) from exc

        requested_stack_items = tuple(
            snapshot.trusted_project_specification.categories.get(
                ArtifactDetectionLabel.TECHNOLOGY_STACK, []
            )
        )
        return ApprovedGenerationContext(
            run_id=run.run_id,
            agent_project_id=run.agent_project_id,
            owner_user_id=run.owner_user_id,
            created_at=run.created_at,
            operational_status=run.status,
            snapshot_schema_version=snapshot.schema_version,
            trusted_project_specification=snapshot.trusted_project_specification,
            trusted_readiness=snapshot.trusted_readiness,
            selected_outputs=tuple(snapshot.selected_outputs),
            effective_implementation_stack=effective_stack,
            requested_stack_items=requested_stack_items,
            stack_adaptation_decision=snapshot.stack_adaptation_decision,
            approval=snapshot.approval,
            delivery_snapshot=snapshot.delivery_snapshot,
            traceability_root_refs=tuple(snapshot.traceability_root_refs),
            project_specification_source_set_digest=(
                snapshot.project_specification_source_set_digest
            ),
            project_specification_decision_digest=(
                snapshot.project_specification_decision_digest
            ),
            readiness_fingerprint=snapshot.readiness_fingerprint,
            selected_outputs_digest=snapshot.selected_outputs_digest,
            approval_fingerprint=snapshot.approval.approval_fingerprint,
        )

    def _load_project(self, project_id, current_user):
        try:
            return self._standalone.get_project(project_id, current_user)
        except AgentProjectNotFoundError as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.PROJECT_NOT_ACCESSIBLE,
                "The project is unavailable",
            ) from exc
        except (StandaloneServiceError, ValidationError, ValueError) as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.STORAGE_UNAVAILABLE,
                "The approved generation input is unavailable",
            ) from exc

    def _load_run(self, project_id, run_id, current_user):
        try:
            return self._standalone.get_run(project_id, run_id, current_user)
        except (AgentRunNotFoundError, LookupError) as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.RUN_NOT_FOUND,
                "The approved run was not found",
            ) from exc
        except (StandaloneServiceError, ValidationError, ValueError) as exc:
            raise ApprovedGenerationInputError(
                GenerationInputErrorCode.STORAGE_UNAVAILABLE,
                "The approved generation input is unavailable",
            ) from exc

    def _validate_raw_outputs(self, values) -> None:
        if not isinstance(values, list) or not values:
            self._fail(
                GenerationInputErrorCode.MISSING_GENERATION_CONTEXT,
                "The approved snapshot has no selected outputs",
            )
        supported = {item.value for item in ImplementationOutputCode}
        if any(not isinstance(value, str) or value not in supported for value in values):
            self._fail(
                GenerationInputErrorCode.UNSUPPORTED_SELECTED_OUTPUT,
                "The approved snapshot contains an unsupported selected output",
            )
        if len(values) != len(set(values)):
            self._fail(
                GenerationInputErrorCode.CORRUPTED_APPROVED_DATA,
                "The approved snapshot contains inconsistent selected outputs",
            )

    def _validate_consistency(self, project_id, run, snapshot) -> None:
        specification = snapshot.trusted_project_specification
        readiness = snapshot.trusted_readiness
        approval = snapshot.approval
        outputs = [item.value for item in snapshot.selected_outputs]

        consistent = (
            snapshot.snapshot_kind == IMPLEMENTATION_RUN_SNAPSHOT_KIND
            and snapshot.schema_version == IMPLEMENTATION_RUN_SCHEMA_VERSION
            and snapshot.run_status is ImplementationRunStatus.READY_FOR_GENERATION
            and specification.status is ConsolidationStatus.READY
            and specification.agent_project_id == project_id
            and snapshot.project_specification_id == specification.project_specification_id
            and snapshot.project_specification_source_set_digest == specification.source_set_digest
            and snapshot.project_specification_decision_digest == specification.decision_digest
            and all(
                conflict.status is ConflictStatus.RESOLVED
                for conflict in specification.conflict_decisions
            )
            and readiness.agent_project_id == project_id
            and readiness.readiness_id == snapshot.readiness_id
            and readiness.project_specification_id == snapshot.project_specification_id
            and readiness.source_set_digest == snapshot.project_specification_source_set_digest
            and readiness.project_specification_decision_digest
            == snapshot.project_specification_decision_digest
            and readiness.policy_version == snapshot.readiness_policy_version
            and readiness.status.value == snapshot.readiness_status
            and readiness.status in {ReadinessStatus.READY, ReadinessStatus.READY_WITH_WARNINGS}
            and readiness.current
            and readiness.readiness_fingerprint == snapshot.readiness_fingerprint
            and readiness_fingerprint(readiness) == snapshot.readiness_fingerprint
            and readiness.selected_outputs == snapshot.selected_outputs
            and readiness.selected_outputs_digest == snapshot.selected_outputs_digest
            and digest(sorted(outputs)) == snapshot.selected_outputs_digest
            and run.selected_outputs == outputs
            and readiness.effective_stack == snapshot.implementation_stack
            and readiness.stack_adaptation == snapshot.stack_adaptation_decision
            and (
                snapshot.stack_adaptation_decision is None
                or snapshot.stack_adaptation_decision.approved
            )
            and approval.decision is FinalApprovalDecision.APPROVED
            and approval.agent_project_id == project_id
            and approval.reviewer_owner_id == run.owner_user_id
            and approval.project_specification_id == snapshot.project_specification_id
            and approval.project_specification_source_set_digest
            == snapshot.project_specification_source_set_digest
            and approval.project_specification_decision_digest
            == snapshot.project_specification_decision_digest
            and approval.readiness_id == snapshot.readiness_id
            and approval.readiness_fingerprint == snapshot.readiness_fingerprint
            and approval.selected_outputs_digest == snapshot.selected_outputs_digest
            and approval.readiness_continuation_decision_id
            == readiness.continuation_decision_id
            and sorted(approval.acknowledged_warning_codes)
            == self._warning_codes(readiness)
            and set(snapshot.traceability_root_refs)
            == self._traceability_refs(specification, readiness)
            and len(snapshot.traceability_root_refs)
            == len(set(snapshot.traceability_root_refs))
            and approval.approval_fingerprint
            == self._approval_fingerprint(snapshot)
        )
        if not consistent:
            self._fail(
                GenerationInputErrorCode.CORRUPTED_APPROVED_DATA,
                "The approved snapshot is internally inconsistent",
            )

    @staticmethod
    def _warning_codes(readiness):
        return sorted(
            {
                item.issue_code
                for item in readiness.findings
                if item.severity is FindingSeverity.WARNING and not item.resolved
            }
        )

    @staticmethod
    def _traceability_refs(specification, readiness):
        refs = {
            specification.project_specification_id,
            readiness.readiness_id,
            *specification.source_artifact_refs,
            *specification.traceability.keys(),
        }
        for items in specification.categories.values():
            refs.update(item.project_item_id for item in items)
        refs.update(item.conflict_id for item in specification.conflict_decisions)
        return refs

    @staticmethod
    def _approval_fingerprint(snapshot):
        approval = snapshot.approval
        return digest(
            {
                "agent_project_id": approval.agent_project_id,
                "reviewer_owner_id": approval.reviewer_owner_id,
                "decision": approval.decision,
                "acknowledged_warning_codes": approval.acknowledged_warning_codes,
                "readiness_continuation_decision_id": (
                    approval.readiness_continuation_decision_id
                ),
                "project_specification_id": approval.project_specification_id,
                "project_specification_source_set_digest": (
                    approval.project_specification_source_set_digest
                ),
                "project_specification_decision_digest": (
                    approval.project_specification_decision_digest
                ),
                "readiness_id": approval.readiness_id,
                "readiness_fingerprint": approval.readiness_fingerprint,
                "selected_outputs_digest": approval.selected_outputs_digest,
                "idempotency_key": approval.idempotency_key,
                "stack_adaptation": (
                    snapshot.stack_adaptation_decision.model_dump(mode="json")
                    if snapshot.stack_adaptation_decision
                    else None
                ),
                "delivery": snapshot.delivery_snapshot.model_dump(mode="json"),
            }
        )

    @staticmethod
    def _fail(code, message):
        raise ApprovedGenerationInputError(code, message)
