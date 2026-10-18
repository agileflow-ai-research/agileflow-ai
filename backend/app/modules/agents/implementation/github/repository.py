from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database.collections import (
    GITHUB_CONNECTIONS,
    GITHUB_REPOSITORY_BINDINGS,
)
from app.database.mongodb import get_database
from app.modules.agents.implementation.contracts.schemas import (
    GitHubConnection,
    GitHubRepositoryBinding,
)


class GitHubConnectionRepositoryError(RuntimeError):
    pass


class GitHubRepositoryBindingRepositoryError(RuntimeError):
    pass


class GitHubRepositoryBindingConflictError(
    GitHubRepositoryBindingRepositoryError
):
    pass


def _public(document: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in document.items() if key != "_id"}
    for key, value in result.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            result[key] = value.replace(tzinfo=timezone.utc)
    return result


class GitHubConnectionRepository:
    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[GITHUB_CONNECTIONS]

    def find_by_owner(self, owner_id: str) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {"owner_id": owner_id, "provider": "GITHUB"},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise GitHubConnectionRepositoryError(
                "Could not retrieve GitHub connection"
            ) from exc
        return _public(document) if document is not None else None

    def upsert(self, connection: GitHubConnection) -> dict[str, Any]:
        document = connection.model_dump(mode="python")
        try:
            persisted = self._collection.find_one_and_update(
                {"owner_id": connection.owner_id, "provider": "GITHUB"},
                {"$set": document},
                upsert=True,
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise GitHubConnectionRepositoryError(
                "Could not persist GitHub connection"
            ) from exc
        return _public(persisted or document)


class GitHubRepositoryBindingRepository:
    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[GITHUB_REPOSITORY_BINDINGS]

    def find_by_project(
        self, agent_project_id: str, owner_id: str
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {"agent_project_id": agent_project_id, "owner_id": owner_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise GitHubRepositoryBindingRepositoryError(
                "Could not retrieve GitHub repository binding"
            ) from exc
        return _public(document) if document is not None else None

    def create(self, binding: GitHubRepositoryBinding) -> dict[str, Any]:
        document = binding.model_dump(mode="python")
        document["_id"] = f"GITHUB_REPOSITORY:{binding.agent_project_id}"
        try:
            self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise GitHubRepositoryBindingConflictError(
                "Agent project already has a GitHub repository binding"
            ) from exc
        except PyMongoError as exc:
            raise GitHubRepositoryBindingRepositoryError(
                "Could not persist GitHub repository binding"
            ) from exc
        return _public(document)
