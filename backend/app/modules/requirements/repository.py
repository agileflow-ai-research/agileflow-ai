from typing import Any

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.database.collections import CLIENT_INPUTS, PROJECTS
from app.database.mongodb import get_database
from app.modules.requirements.schemas import ClientInputResponse


class ClientInputRepositoryError(RuntimeError):
    """Raised when ClientInput persistence cannot be completed."""


class ClientInputRepository:
    """Persistence operations for project-owned ClientInput records."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._projects = configured_database[PROJECTS]
        self._client_inputs = configured_database[CLIENT_INPUTS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def project_exists(self, project_id: str) -> bool:
        try:
            return (
                self._projects.find_one(
                    {"project_id": project_id},
                    {"_id": 1},
                )
                is not None
            )
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not verify project"
            ) from exc

    def create_client_input(
        self,
        client_input: ClientInputResponse,
    ) -> dict[str, Any]:
        document = client_input.model_dump(mode="python")
        try:
            self._client_inputs.insert_one(document.copy())
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not create client input"
            ) from exc
        return self._public_document(document)

    def list_client_inputs(self, project_id: str) -> list[dict[str, Any]]:
        try:
            documents = self._client_inputs.find(
                {"project_id": project_id},
                {"_id": 0},
            )
            return [self._public_document(document) for document in documents]
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not list client inputs"
            ) from exc

    def has_client_input(self, project_id: str) -> bool:
        try:
            return (
                self._client_inputs.find_one(
                    {"project_id": project_id},
                    {"_id": 1},
                )
                is not None
            )
        except PyMongoError as exc:
            raise ClientInputRepositoryError(
                "Could not check client input"
            ) from exc
