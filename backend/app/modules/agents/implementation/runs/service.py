from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from pydantic import ValidationError

from app.common.status import AgentRunMode, AgentType
from app.modules.agents.implementation.contracts.enums import ImplementationOutputCode
from app.modules.agents.implementation.contracts.schemas import (
    GitHubConnection,
    GitHubRepositoryBinding,
)
from app.modules.agents.implementation.preparation.consolidation.constants import (
    ConflictStatus,
    ConsolidationStatus,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
    ReadinessStatus,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.preparation.readiness.trusted.constants import (
    TRUSTED_READINESS_POLICY_VERSION,
)
from app.modules.agents.implementation.preparation.readiness.trusted.policy import (
    digest,
    evaluate_stack,
)
from app.modules.agents.implementation.preparation.readiness.trusted.service import (
    readiness_fingerprint,
)
from app.modules.standalone.schemas import AgentRun

from .constants import (
    DELIVERY_POLICY_VERSION,
    IMPLEMENTATION_RUN_SCHEMA_VERSION,
    IMPLEMENTATION_RUN_SNAPSHOT_KIND,
)
from .schemas import (
    DeliveryConnectionSnapshot,
    DeliveryRepositorySnapshot,
    DeliverySnapshot,
    FinalApprovalDecision,
    FinalApprovalSnapshot,
    ImplementationRunCreateRequest,
    ImplementationRunInputSnapshot,
    ImplementationRunListItem,
    ImplementationRunResponse,
    ImplementationRunStatus,
)


class ImplementationRunApprovalError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ImplementationRunNotFoundError(LookupError):
    pass


class ImplementationRunStorageError(RuntimeError):
    pass


_creation_lock = Lock()


def utc_now():
    return datetime.now(timezone.utc)


class ImplementationRunService:
    """Creates approved Agent 3 snapshots using the shared AgentRun store."""

    def __init__(
        self,
        standalone_service,
        consolidation_service,
        readiness_service,
        connection_repository,
        binding_repository,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._consolidation = consolidation_service
        self._readiness = readiness_service
        self._connections = connection_repository
        self._bindings = binding_repository
        self._clock = clock

    def create(self, project_id, request, current_user):
        with _creation_lock:
            existing = self._find_idempotent(
                project_id, request.idempotency_key, current_user
            )
            if existing is not None:
                try:
                    self._assert_replay_matches(existing, request)
                    return self._response(existing), True
                except ValidationError as exc:
                    raise ImplementationRunStorageError(
                        "Stored implementation run snapshot is invalid"
                    ) from exc

            specification, readiness, continuation = self._validate_current_state(
                project_id, request, current_user
            )
            delivery = self._delivery_snapshot(
                project_id, current_user.user_id, readiness.selected_outputs
            )
            now = self._clock()
            approval_values = {
                "agent_project_id": project_id,
                "reviewer_owner_id": current_user.user_id,
                "decision": FinalApprovalDecision.APPROVED,
                "acknowledged_warning_codes": sorted(
                    item.issue_code
                    for item in readiness.findings
                    if item.severity is FindingSeverity.WARNING
                    and not item.resolved
                ),
                "readiness_continuation_decision_id": (
                    continuation.decision_id if continuation else None
                ),
                "project_specification_id": specification.project_specification_id,
                "project_specification_source_set_digest": specification.source_set_digest,
                "project_specification_decision_digest": specification.decision_digest,
                "readiness_id": readiness.readiness_id,
                "readiness_fingerprint": readiness.readiness_fingerprint,
                "selected_outputs_digest": readiness.selected_outputs_digest,
                "idempotency_key": request.idempotency_key,
            }
            approval = FinalApprovalSnapshot(
                approval_id=f"APR-{uuid4().hex}",
                approval_fingerprint=digest(
                    {
                        **approval_values,
                        "stack_adaptation": (
                            readiness.stack_adaptation.model_dump(mode="json")
                            if readiness.stack_adaptation
                            else None
                        ),
                        "delivery": delivery.model_dump(mode="json"),
                    }
                ),
                created_at=now,
                **approval_values,
            )
            snapshot = ImplementationRunInputSnapshot(
                snapshot_kind=IMPLEMENTATION_RUN_SNAPSHOT_KIND,
                schema_version=IMPLEMENTATION_RUN_SCHEMA_VERSION,
                run_status=ImplementationRunStatus.READY_FOR_GENERATION,
                project_specification_id=specification.project_specification_id,
                project_specification_source_set_digest=specification.source_set_digest,
                project_specification_decision_digest=specification.decision_digest,
                trusted_project_specification=specification,
                readiness_id=readiness.readiness_id,
                readiness_policy_version=readiness.policy_version,
                readiness_status=readiness.status.value,
                readiness_fingerprint=readiness.readiness_fingerprint,
                trusted_readiness=readiness,
                selected_outputs=readiness.selected_outputs,
                selected_outputs_digest=readiness.selected_outputs_digest,
                implementation_stack=readiness.effective_stack,
                stack_adaptation_decision=readiness.stack_adaptation,
                approval=approval,
                delivery_snapshot=delivery,
                traceability_root_refs=self._traceability_refs(
                    specification, readiness
                ),
            )
            try:
                run = self._standalone.create_run(
                    current_user.user_id,
                    project_id,
                    AgentRunMode.DEFAULT,
                    [item.value for item in readiness.selected_outputs],
                    snapshot.model_dump(mode="json"),
                )
            except (ValueError, RuntimeError) as exc:
                raise ImplementationRunStorageError(
                    "Implementation run could not be created"
                ) from exc
            return self._response(run), False

    def list(self, project_id, current_user):
        try:
            runs = self._standalone.list_runs(project_id, current_user)
            return [
                self._list_item(run)
                for run in runs
                if run.agent_type is AgentType.IMPLEMENTATION
                and run.input_snapshot.get("snapshot_kind")
                == IMPLEMENTATION_RUN_SNAPSHOT_KIND
            ]
        except (ValidationError, ValueError, RuntimeError) as exc:
            raise ImplementationRunStorageError(
                "Implementation run history is unavailable"
            ) from exc

    def get(self, project_id, run_id, current_user):
        try:
            run = self._standalone.get_run(project_id, run_id, current_user)
        except LookupError as exc:
            raise ImplementationRunNotFoundError(run_id) from exc
        try:
            if (
                run.agent_type is not AgentType.IMPLEMENTATION
                or run.input_snapshot.get("snapshot_kind")
                != IMPLEMENTATION_RUN_SNAPSHOT_KIND
            ):
                raise ImplementationRunNotFoundError(run_id)
            return self._response(run)
        except ImplementationRunNotFoundError:
            raise
        except (ValidationError, ValueError, TypeError) as exc:
            raise ImplementationRunStorageError(
                "Implementation run snapshot is invalid"
            ) from exc

    def _validate_current_state(self, project_id, request, current_user):
        status = self._consolidation.get_status(project_id, current_user)
        if status.status is not ConsolidationStatus.READY:
            raise ImplementationRunApprovalError(
                "PROJECT_SPECIFICATION_NOT_READY",
                "The current trusted project specification is not ready",
            )
        specification = self._consolidation.get_final(project_id, current_user)
        if (
            specification.status is not ConsolidationStatus.READY
            or specification.agent_project_id != project_id
            or specification.source_set_digest != status.source_set_digest
        ):
            raise ImplementationRunApprovalError(
                "PROJECT_SPECIFICATION_STALE",
                "The displayed project specification is stale",
            )
        if specification.project_specification_id != request.expected_project_specification_id:
            raise ImplementationRunApprovalError(
                "PROJECT_SPECIFICATION_STALE",
                "The project specification changed before approval",
            )
        if any(
            conflict.status is not ConflictStatus.RESOLVED
            for conflict in specification.conflict_decisions
        ):
            raise ImplementationRunApprovalError(
                "UNRESOLVED_PROJECT_CONFLICTS",
                "Project specification conflicts must be resolved before approval",
            )

        readiness = self._readiness.get(project_id, current_user)
        if not readiness.current:
            raise ImplementationRunApprovalError(
                "READINESS_STALE", "Implementation readiness is stale"
            )
        if readiness.status is ReadinessStatus.NOT_READY:
            raise ImplementationRunApprovalError(
                "IMPLEMENTATION_NOT_READY", "Implementation is not ready"
            )
        if readiness.status not in {
            ReadinessStatus.READY,
            ReadinessStatus.READY_WITH_WARNINGS,
        }:
            raise ImplementationRunApprovalError(
                "IMPLEMENTATION_NOT_READY", "Implementation is not ready"
            )
        if (
            readiness.readiness_id != request.expected_readiness_id
            or readiness.readiness_fingerprint
            != request.expected_readiness_fingerprint
            or readiness.readiness_fingerprint != readiness_fingerprint(readiness)
        ):
            raise ImplementationRunApprovalError(
                "READINESS_STALE", "Implementation readiness changed before approval"
            )
        if (
            readiness.project_specification_id
            != specification.project_specification_id
            or readiness.source_set_digest != specification.source_set_digest
            or readiness.project_specification_decision_digest
            != specification.decision_digest
        ):
            raise ImplementationRunApprovalError(
                "READINESS_STALE",
                "Implementation readiness does not match the current specification",
            )
        expected_outputs_digest = digest(
            sorted(item.value for item in readiness.selected_outputs)
        )
        if (
            not readiness.selected_outputs
            or readiness.selected_outputs_digest != expected_outputs_digest
            or request.expected_selected_outputs_digest != expected_outputs_digest
        ):
            raise ImplementationRunApprovalError(
                "SELECTED_OUTPUTS_STALE", "Selected outputs changed before approval"
            )

        warning_codes = sorted(
            {
                item.issue_code
                for item in readiness.findings
                if item.severity is FindingSeverity.WARNING and not item.resolved
            }
        )
        unresolved_errors = [
            item
            for item in readiness.findings
            if item.severity is FindingSeverity.ERROR and not item.resolved
        ]
        if (
            unresolved_errors
            or (warning_codes and readiness.status is ReadinessStatus.READY)
            or (
                not warning_codes
                and readiness.status is ReadinessStatus.READY_WITH_WARNINGS
            )
        ):
            raise ImplementationRunApprovalError(
                "READINESS_INCONSISTENT",
                "Implementation readiness findings do not match its status",
            )
        continuation = self._readiness.valid_continuation(
            readiness, current_user
        )
        acknowledged = sorted(request.acknowledged_warning_codes)
        if readiness.status is ReadinessStatus.READY_WITH_WARNINGS:
            if continuation is None and acknowledged != warning_codes:
                raise ImplementationRunApprovalError(
                    "WARNING_ACKNOWLEDGEMENT_STALE",
                    "All current readiness warnings must be acknowledged exactly",
                )
            if continuation is not None and acknowledged not in ([], warning_codes):
                raise ImplementationRunApprovalError(
                    "WARNING_ACKNOWLEDGEMENT_STALE",
                    "Readiness warning acknowledgement changed before approval",
                )
        elif acknowledged:
            raise ImplementationRunApprovalError(
                "WARNING_ACKNOWLEDGEMENT_STALE",
                "There are no current readiness warnings to acknowledge",
            )

        stack_findings = evaluate_stack(
            specification.categories.get(ArtifactDetectionLabel.TECHNOLOGY_STACK, [])
        )
        expected_stack_fingerprint = (
            digest(
                {
                    "project_id": project_id,
                    "project_specification_id": specification.project_specification_id,
                    "decision_digest": specification.decision_digest,
                    "policy_version": TRUSTED_READINESS_POLICY_VERSION,
                    "stack_findings": [
                        (
                            item.provided_value,
                            item.supported_value,
                            item.related_project_item_ids,
                        )
                        for item in stack_findings
                    ],
                }
            )
            if stack_findings
            else None
        )
        current_stack_fingerprint = (
            readiness.stack_adaptation.fingerprint
            if readiness.stack_adaptation
            else None
        )
        if (
            expected_stack_fingerprint != current_stack_fingerprint
            or request.expected_stack_adaptation_fingerprint
            != current_stack_fingerprint
            or (
                readiness.stack_adaptation is not None
                and not readiness.stack_adaptation.approved
            )
        ):
            raise ImplementationRunApprovalError(
                "STACK_ADAPTATION_STALE",
                "The implementation stack adaptation changed before approval",
            )
        return specification, readiness, continuation

    def _delivery_snapshot(self, project_id, owner_id, selected_outputs):
        connection = None
        repository = None
        try:
            connection_document = self._connections.find_by_owner(owner_id)
            if connection_document is not None:
                value = GitHubConnection.model_validate(connection_document)
                connection = DeliveryConnectionSnapshot(
                    owner_id=value.owner_id,
                    github_user_id=value.github_user_id,
                    github_login=value.github_login,
                    installation_account_login=value.installation_account_login,
                    account_type=value.installation_account_type,
                    status=value.status,
                )
            binding_document = self._bindings.find_by_project(project_id, owner_id)
            if binding_document is not None:
                value = GitHubRepositoryBinding.model_validate(binding_document)
                repository = DeliveryRepositorySnapshot(
                    binding_id=f"GITHUB_REPOSITORY:{project_id}",
                    repository_id=value.repository_id,
                    owner=value.repository_owner,
                    name=value.repository_name,
                    full_name=value.repository_full_name,
                    html_url=value.repository_html_url,
                    visibility=value.visibility,
                    default_branch=value.default_branch,
                    is_empty=value.is_empty,
                )
        except (ValidationError, RuntimeError):
            # Delivery is optional at pre-code approval.  Invalid live delivery
            # state is deliberately not copied into a trusted run snapshot.
            connection = None
            repository = None
        requires_delivery = ImplementationOutputCode.GIT_SUMMARY in selected_outputs
        return DeliverySnapshot(
            policy_version=DELIVERY_POLICY_VERSION,
            configured=connection is not None or repository is not None,
            delivery_ready=repository is not None,
            required_before_delivery_execution=requires_delivery,
            connection=connection,
            repository=repository,
        )

    def _find_idempotent(self, project_id, key, current_user):
        try:
            for run in self._standalone.list_runs(project_id, current_user):
                if run.input_snapshot.get("snapshot_kind") != IMPLEMENTATION_RUN_SNAPSHOT_KIND:
                    continue
                approval = run.input_snapshot.get("approval")
                if isinstance(approval, dict) and approval.get("idempotency_key") == key:
                    return run
        except (ValidationError, ValueError, RuntimeError) as exc:
            raise ImplementationRunStorageError(
                "Implementation run history is unavailable"
            ) from exc
        return None

    @staticmethod
    def _assert_replay_matches(run, request):
        snapshot = ImplementationRunInputSnapshot.model_validate(run.input_snapshot)
        expected = (
            snapshot.project_specification_id,
            snapshot.readiness_id,
            snapshot.readiness_fingerprint,
            snapshot.selected_outputs_digest,
            snapshot.stack_adaptation_decision.fingerprint
            if snapshot.stack_adaptation_decision
            else None,
            ([] if snapshot.approval.readiness_continuation_decision_id
             else sorted(snapshot.approval.acknowledged_warning_codes)),
        )
        received = (
            request.expected_project_specification_id,
            request.expected_readiness_id,
            request.expected_readiness_fingerprint,
            request.expected_selected_outputs_digest,
            request.expected_stack_adaptation_fingerprint,
            sorted(request.acknowledged_warning_codes),
        )
        if expected != received:
            raise ImplementationRunApprovalError(
                "IDEMPOTENCY_KEY_REUSED",
                "The idempotency key was already used for a different approval",
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
        return sorted(refs)

    @staticmethod
    def _snapshot(run: AgentRun) -> ImplementationRunInputSnapshot:
        return ImplementationRunInputSnapshot.model_validate(run.input_snapshot)

    @classmethod
    def _response(cls, run):
        snapshot = cls._snapshot(run)
        return ImplementationRunResponse(
            run_id=run.run_id,
            agent_project_id=run.agent_project_id,
            agent_type=run.agent_type,
            run_status=snapshot.run_status,
            created_at=run.created_at,
            project_specification_id=snapshot.project_specification_id,
            project_specification_source_set_digest=snapshot.project_specification_source_set_digest,
            project_specification_decision_digest=snapshot.project_specification_decision_digest,
            readiness_id=snapshot.readiness_id,
            readiness_policy_version=snapshot.readiness_policy_version,
            readiness_status=snapshot.readiness_status,
            readiness_fingerprint=snapshot.readiness_fingerprint,
            selected_outputs=snapshot.selected_outputs,
            selected_outputs_digest=snapshot.selected_outputs_digest,
            implementation_stack=snapshot.implementation_stack,
            stack_adaptation_decision=snapshot.stack_adaptation_decision,
            approval_id=snapshot.approval.approval_id,
            approval_fingerprint=snapshot.approval.approval_fingerprint,
            delivery_snapshot=snapshot.delivery_snapshot,
            traceability_root_refs=snapshot.traceability_root_refs,
            schema_version=snapshot.schema_version,
            approved_input=snapshot,
        )

    @classmethod
    def _list_item(cls, run):
        snapshot = cls._snapshot(run)
        return ImplementationRunListItem(
            run_id=run.run_id,
            run_status=snapshot.run_status,
            created_at=run.created_at,
            readiness_status=snapshot.readiness_status,
            readiness_id=snapshot.readiness_id,
            readiness_fingerprint=snapshot.readiness_fingerprint,
            selected_outputs=snapshot.selected_outputs,
            approval_id=snapshot.approval.approval_id,
            delivery_configured=snapshot.delivery_snapshot.configured,
        )
