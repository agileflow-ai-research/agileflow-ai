from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone

from pydantic import JsonValue, ValidationError

from app.common.id_generator import generate_id, validate_id
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.repository import (
    AgentProjectRepository,
    AgentRunRepository,
    StandaloneRepositoryError,
)
from app.modules.standalone.schemas import (
    ALLOWED_RUN_MODES,
    AgentProject,
    AgentProjectCreateRequest,
    AgentProjectStatus,
    AgentProjectUpdateRequest,
    AgentRun,
    AgentRunMessage,
    AgentRunMode,
    AgentRunStatus,
    AgentType,
)


class AgentProjectNotFoundError(LookupError):
    """Raised for missing and foreign standalone projects alike."""


class AgentRunNotFoundError(LookupError):
    """Raised for missing, foreign, and wrong-project runs alike."""


class ArchivedAgentProjectError(ValueError):
    """Raised when a future execution targets an archived project."""


class InvalidAgentRunModeError(ValueError):
    """Raised when a run mode is incompatible with the project's agent."""


class AgentRunTransitionError(ValueError):
    """Raised when a run lifecycle transition is not allowed."""

    def __init__(
        self,
        current_status: AgentRunStatus,
        target_status: AgentRunStatus,
    ) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot transition agent run from {current_status.value} "
            f"to {target_status.value}"
        )


class StandaloneServiceError(RuntimeError):
    """Raised when standalone persistence cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StandaloneService:
    """Shared owner isolation, project lifecycle, and run lifecycle rules."""

    def __init__(
        self,
        project_repository: AgentProjectRepository,
        run_repository: AgentRunRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._project_repository = project_repository
        self._run_repository = run_repository
        self._clock = clock

    def create_project(
        self,
        request: AgentProjectCreateRequest,
        current_user: UserPublicResponse,
    ) -> AgentProject:
        try:
            now = self._clock()
            project = AgentProject(
                agent_project_id=generate_id(
                    "AGP",
                    self._project_repository.next_project_sequence(),
                ),
                owner_user_id=current_user.user_id,
                agent_type=request.agent_type,
                name=request.name,
                description=request.description,
                domain=request.domain,
                status=AgentProjectStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            document = self._project_repository.create_project(project)
            return AgentProject.model_validate(document)
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError(
                "Agent project creation failed"
            ) from exc

    def list_projects(
        self,
        current_user: UserPublicResponse,
        *,
        agent_type: AgentType | None = None,
        status: AgentProjectStatus | None = None,
    ) -> list[AgentProject]:
        try:
            return [
                AgentProject.model_validate(document)
                for document in self._project_repository.list_projects(
                    current_user.user_id,
                    agent_type=agent_type,
                    status=status,
                )
            ]
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError(
                "Agent project listing failed"
            ) from exc

    def get_project(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> AgentProject:
        return self._get_owned_project(
            agent_project_id,
            current_user.user_id,
        )

    def update_project(
        self,
        agent_project_id: str,
        request: AgentProjectUpdateRequest,
        current_user: UserPublicResponse,
    ) -> AgentProject:
        self._get_owned_project(agent_project_id, current_user.user_id)
        updates = request.model_dump(exclude_unset=True, mode="python")
        updates["updated_at"] = self._clock()
        try:
            document = self._project_repository.update_project(
                agent_project_id,
                current_user.user_id,
                updates,
            )
            if document is None:
                raise AgentProjectNotFoundError(agent_project_id)
            return AgentProject.model_validate(document)
        except AgentProjectNotFoundError:
            raise
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError(
                "Agent project update failed"
            ) from exc

    def require_active_project(
        self,
        owner_user_id: str,
        agent_project_id: str,
    ) -> AgentProject:
        project = self._get_owned_project(agent_project_id, owner_user_id)
        if project.status is AgentProjectStatus.ARCHIVED:
            raise ArchivedAgentProjectError(agent_project_id)
        return project

    def create_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_mode: AgentRunMode,
        selected_outputs: list[str],
        input_snapshot: dict[str, JsonValue],
    ) -> AgentRun:
        project = self.require_active_project(
            owner_user_id,
            agent_project_id,
        )
        if run_mode not in ALLOWED_RUN_MODES[project.agent_type]:
            raise InvalidAgentRunModeError(
                f"{run_mode.value} is not valid for {project.agent_type.value}"
            )
        if not selected_outputs:
            raise ValueError("selected_outputs must contain at least one value")

        try:
            now = self._clock()
            run = AgentRun(
                run_id=generate_id(
                    "RUN",
                    self._run_repository.next_run_sequence(),
                ),
                agent_project_id=project.agent_project_id,
                owner_user_id=project.owner_user_id,
                agent_type=project.agent_type,
                run_mode=run_mode,
                selected_outputs=deepcopy(selected_outputs),
                input_snapshot=deepcopy(input_snapshot),
                status=AgentRunStatus.QUEUED,
                output_manifest={},
                warnings=[],
                errors=[],
                created_at=now,
                started_at=None,
                completed_at=None,
            )
            document = self._run_repository.create_run(run)
            return AgentRun.model_validate(document)
        except ValidationError as exc:
            raise ValueError("Invalid agent run input") from exc
        except StandaloneRepositoryError as exc:
            raise StandaloneServiceError("Agent run creation failed") from exc

    def list_runs(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> list[AgentRun]:
        self._get_owned_project(agent_project_id, current_user.user_id)
        try:
            return [
                AgentRun.model_validate(document)
                for document in self._run_repository.list_runs(
                    current_user.user_id,
                    agent_project_id,
                )
            ]
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError("Agent run listing failed") from exc

    def get_run(
        self,
        agent_project_id: str,
        run_id: str,
        current_user: UserPublicResponse,
    ) -> AgentRun:
        self._get_owned_project(agent_project_id, current_user.user_id)
        return self._get_owned_run(
            current_user.user_id,
            agent_project_id,
            run_id,
        )

    def mark_run_running(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
    ) -> AgentRun:
        run = self._get_owned_run(owner_user_id, agent_project_id, run_id)
        self._require_transition(run, AgentRunStatus.RUNNING)
        return self._update_run_state(
            run,
            AgentRunStatus.RUNNING,
            {
                "status": AgentRunStatus.RUNNING,
                "started_at": self._clock(),
                "completed_at": None,
            },
        )

    def complete_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
        output_manifest: dict[str, JsonValue],
        warnings: list[AgentRunMessage] | None = None,
    ) -> AgentRun:
        run = self._get_owned_run(owner_user_id, agent_project_id, run_id)
        self._require_transition(run, AgentRunStatus.COMPLETED)
        return self._update_run_state(
            run,
            AgentRunStatus.COMPLETED,
            {
                "status": AgentRunStatus.COMPLETED,
                "completed_at": self._clock(),
                "output_manifest": deepcopy(output_manifest),
                "warnings": [
                    warning.model_dump(mode="python")
                    for warning in (warnings or [])
                ],
                "errors": [],
            },
        )

    def fail_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
        errors: list[AgentRunMessage],
        *,
        output_manifest: dict[str, JsonValue] | None = None,
        warnings: list[AgentRunMessage] | None = None,
    ) -> AgentRun:
        if not errors:
            raise ValueError("Failed agent runs require at least one error")
        run = self._get_owned_run(owner_user_id, agent_project_id, run_id)
        self._require_transition(run, AgentRunStatus.FAILED)
        return self._update_run_state(
            run,
            AgentRunStatus.FAILED,
            {
                "status": AgentRunStatus.FAILED,
                "completed_at": self._clock(),
                "output_manifest": deepcopy(output_manifest or {}),
                "warnings": [
                    warning.model_dump(mode="python")
                    for warning in (warnings or [])
                ],
                "errors": [
                    error.model_dump(mode="python") for error in errors
                ],
            },
        )

    def _get_owned_project(
        self,
        agent_project_id: str,
        owner_user_id: str,
    ) -> AgentProject:
        validate_id(agent_project_id, "AGP")
        validate_id(owner_user_id, "USR")
        try:
            document = self._project_repository.get_project(
                agent_project_id,
                owner_user_id,
            )
            if document is None:
                raise AgentProjectNotFoundError(agent_project_id)
            return AgentProject.model_validate(document)
        except AgentProjectNotFoundError:
            raise
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError(
                "Agent project retrieval failed"
            ) from exc

    def _get_owned_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
    ) -> AgentRun:
        validate_id(owner_user_id, "USR")
        validate_id(agent_project_id, "AGP")
        validate_id(run_id, "RUN")
        try:
            document = self._run_repository.get_run(
                owner_user_id,
                agent_project_id,
                run_id,
            )
            if document is None:
                raise AgentRunNotFoundError(run_id)
            return AgentRun.model_validate(document)
        except AgentRunNotFoundError:
            raise
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError("Agent run retrieval failed") from exc

    @staticmethod
    def _require_transition(
        run: AgentRun,
        target_status: AgentRunStatus,
    ) -> None:
        allowed_target = {
            AgentRunStatus.QUEUED: AgentRunStatus.RUNNING,
            AgentRunStatus.RUNNING: {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
            },
        }.get(run.status)
        is_allowed = (
            target_status == allowed_target
            if isinstance(allowed_target, AgentRunStatus)
            else target_status in (allowed_target or set())
        )
        if not is_allowed:
            raise AgentRunTransitionError(run.status, target_status)

    def _update_run_state(
        self,
        run: AgentRun,
        target_status: AgentRunStatus,
        updates: dict[str, object],
    ) -> AgentRun:
        candidate_data = run.model_dump(mode="python")
        candidate_data.update(deepcopy(updates))
        try:
            candidate = AgentRun.model_validate(candidate_data)
        except ValidationError as exc:
            raise ValueError("Invalid agent run lifecycle data") from exc
        candidate_document = candidate.model_dump(mode="python")
        validated_updates = {
            key: candidate_document[key] for key in updates
        }
        try:
            document = self._run_repository.update_run_state(
                run.owner_user_id,
                run.agent_project_id,
                run.run_id,
                run.status,
                validated_updates,
            )
            if document is None:
                raise AgentRunTransitionError(run.status, target_status)
            return AgentRun.model_validate(document)
        except AgentRunTransitionError:
            raise
        except (StandaloneRepositoryError, ValidationError) as exc:
            raise StandaloneServiceError(
                "Agent run lifecycle update failed"
            ) from exc
