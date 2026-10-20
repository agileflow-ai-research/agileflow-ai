from collections.abc import Callable
from datetime import datetime, timezone

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.workflow.constants import (
    OUTPUT_SELECTION_CONTRACT_VERSION,
    REQUIREMENTS_WORKFLOW_SCHEMA_VERSION,
    REQUIREMENTS_WORKFLOW_VERSION,
    SOURCE_SET_CONTRACT_VERSION,
)
from app.modules.agents.requirements.workflow.contracts.n1 import (
    RequirementN1Confirmation,
    RequirementOutputCode,
)
from app.modules.agents.requirements.workflow.contracts.record import (
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.contracts.responses import (
    RequirementWorkflowResponse,
)
from app.modules.agents.requirements.workflow.projection import (
    build_workflow_response,
    confirmation_is_current,
)
from app.modules.agents.requirements.workflow.storage import (
    WORKFLOW_STATE_LOCK,
    RequirementWorkflowStorage,
    RequirementWorkflowStorageError,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class RequirementWorkflowGateError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(payload: dict[str, object]) -> str:
    return stable_json_sha256(payload)


def canonical_outputs(
    outputs: list[RequirementOutputCode],
) -> list[RequirementOutputCode]:
    return sorted(outputs, key=lambda item: item.value)


def selection_digest(outputs: list[RequirementOutputCode]) -> str:
    return _digest(
        {
            "contract_version": OUTPUT_SELECTION_CONTRACT_VERSION,
            "selected_outputs": [item.value for item in canonical_outputs(outputs)],
        }
    )


def source_set_digest(sources) -> str:
    entries = sorted(
        (
            {
                "source_id": source.source_id,
                "source_type": source.source_type.value,
                "sha256": source.sha256,
            }
            for source in sources
        ),
        key=lambda item: (item["source_id"], item["source_type"], item["sha256"]),
    )
    return _digest(
        {"contract_version": SOURCE_SET_CONTRACT_VERSION, "sources": entries}
    )


class RequirementWorkflowService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        source_storage: RequirementSourceStorage,
        workflow_storage: RequirementWorkflowStorage,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._sources = source_storage
        self._workflow = workflow_storage
        self._clock = clock

    def get(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            project = require_requirements_project(
                self._standalone, agent_project_id, current_user
            )
            record, sources = self._load_current(project.agent_project_id, current_user)
            return build_workflow_response(record, len(sources))

    def update_outputs(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
        outputs: list[RequirementOutputCode],
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            project = require_requirements_project(
                self._standalone, agent_project_id, current_user
            )
            record, sources = self._load_current(project.agent_project_id, current_user)
            next_outputs = canonical_outputs(outputs)
            if next_outputs != record.selected_outputs:
                record = record.model_copy(
                    update={
                        "selected_outputs": next_outputs,
                        "selection_revision": record.selection_revision + 1,
                        "selection_digest": selection_digest(next_outputs),
                        "updated_at": self._clock(),
                    }
                )
                self._workflow.save(record)
            return build_workflow_response(record, len(sources))

    def continue_n1(
        self, agent_project_id: str, current_user: UserPublicResponse
    ) -> RequirementWorkflowResponse:
        with WORKFLOW_STATE_LOCK:
            project = require_requirements_project(
                self._standalone, agent_project_id, current_user
            )
            record, sources = self._load_current(project.agent_project_id, current_user)
            if not sources:
                raise RequirementWorkflowGateError(
                    "Add at least one valid requirement source before continuing"
                )
            if not record.selected_outputs:
                raise RequirementWorkflowGateError(
                    "Select at least one requested output before continuing"
                )
            confirmation = record.n1_confirmation
            if not confirmation_is_current(record):
                now = self._clock()
                record = record.model_copy(
                    update={
                        "n1_confirmation": RequirementN1Confirmation(
                            source_set_digest=record.source_set_digest,
                            selection_digest=record.selection_digest,
                            confirmed_at=now,
                        ),
                        "updated_at": now,
                    }
                )
                self._workflow.save(record)
            elif confirmation is None:  # pragma: no cover - defensive invariant
                raise RequirementWorkflowGateError("N1 confirmation is unavailable")
            return build_workflow_response(record, len(sources))

    def _load_current(self, agent_project_id: str, current_user: UserPublicResponse):
        sources = self._sources.list_for_project(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
        )
        current_source_digest = source_set_digest(sources)
        record = self._workflow.load(
            agent_project_id=agent_project_id, owner_user_id=current_user.user_id
        )
        if record is None:
            now = self._clock()
            record = RequirementWorkflowRecord(
                schema_version=REQUIREMENTS_WORKFLOW_SCHEMA_VERSION,
                workflow_version=REQUIREMENTS_WORKFLOW_VERSION,
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
                selected_outputs=[],
                selection_revision=0,
                selection_digest=selection_digest([]),
                source_set_digest=current_source_digest,
                created_at=now,
                updated_at=now,
            )
            self._workflow.save(record)
        elif record.schema_version == "1" and record.workflow_version == "W1":
            record = record.model_copy(
                update={
                    "schema_version": REQUIREMENTS_WORKFLOW_SCHEMA_VERSION,
                    "workflow_version": REQUIREMENTS_WORKFLOW_VERSION,
                    "updated_at": self._clock(),
                }
            )
            self._workflow.save(record)
        else:
            if (
                record.schema_version != REQUIREMENTS_WORKFLOW_SCHEMA_VERSION
                or record.workflow_version != REQUIREMENTS_WORKFLOW_VERSION
                or record.selected_outputs != canonical_outputs(record.selected_outputs)
                or record.selection_digest != selection_digest(record.selected_outputs)
            ):
                raise RequirementWorkflowStorageError(
                    "Requirement workflow record is inconsistent"
                )
        if record.source_set_digest != current_source_digest:
            record = record.model_copy(
                update={
                    "source_set_digest": current_source_digest,
                    "updated_at": self._clock(),
                }
            )
            self._workflow.save(record)
        return record, sources
