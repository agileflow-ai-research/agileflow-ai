from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import ValidationError

from app.modules.auth.authorization import (
    ProjectAccessNotFoundError,
    authorize_project_access,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.requirements.repository import (
    ClientInputRepository,
    ClientInputRepositoryError,
)
from app.modules.requirements.schemas import (
    ClientInputCreateRequest,
    ClientInputResponse,
)


class ClientInputServiceError(RuntimeError):
    """Raised when a ClientInput operation cannot be completed safely."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClientInputService:
    """Project ownership rules for ClientInput persistence."""

    def __init__(
        self,
        repository: ClientInputRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def create_client_input(
        self,
        project_id: str,
        request: ClientInputCreateRequest,
        current_user: UserPublicResponse,
    ) -> ClientInputResponse:
        try:
            authorize_project_access(project_id, current_user, self._repository)

            client_input = ClientInputResponse(
                project_id=project_id,
                input_type=request.input_type,
                content=request.content,
                original_filename=request.original_filename,
                mime_type=request.mime_type,
                metadata=request.metadata,
                created_at=self._clock(),
            )
            document = self._repository.create_client_input(client_input)
            return ClientInputResponse.model_validate(document)
        except ProjectAccessNotFoundError:
            raise
        except (ClientInputRepositoryError, ValidationError) as exc:
            raise ClientInputServiceError(
                "Client input creation failed"
            ) from exc

    def list_client_inputs(
        self,
        project_id: str,
        current_user: UserPublicResponse,
    ) -> list[ClientInputResponse]:
        try:
            authorize_project_access(project_id, current_user, self._repository)

            return [
                ClientInputResponse.model_validate(document)
                for document in self._repository.list_client_inputs(project_id)
            ]
        except ProjectAccessNotFoundError:
            raise
        except (ClientInputRepositoryError, ValidationError) as exc:
            raise ClientInputServiceError(
                "Client input listing failed"
            ) from exc


ClientInputProjectNotFoundError = ProjectAccessNotFoundError
