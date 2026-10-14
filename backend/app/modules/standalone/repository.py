from datetime import datetime, timezone
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.database.collections import AGENT_PROJECTS, AGENT_RUNS
from app.database.mongodb import get_database
from app.modules.standalone.schemas import (
    AgentProject,
    AgentProjectStatus,
    AgentRun,
    AgentRunStatus,
    AgentType,
)


class StandaloneRepositoryError(RuntimeError):
    """Raised when standalone persistence cannot be completed."""


def _public_document(document: dict[str, Any]) -> dict[str, Any]:
    public_document = {
        key: value for key, value in document.items() if key != "_id"
    }
    for key, value in public_document.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            public_document[key] = value.replace(tzinfo=timezone.utc)
    return public_document


class AgentProjectRepository:
    """MongoDB persistence for owner-scoped standalone agent projects."""

    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[AGENT_PROJECTS]

    def next_project_sequence(self) -> int:
        try:
            largest_sequence = 0
            for document in self._collection.find(
                {},
                {"agent_project_id": 1, "_id": 0},
            ):
                agent_project_id = document.get("agent_project_id")
                if not isinstance(agent_project_id, str):
                    continue
                try:
                    validate_id(agent_project_id, "AGP")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(agent_project_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not allocate an agent project ID"
            ) from exc

    def create_project(self, project: AgentProject) -> dict[str, Any]:
        document = project.model_dump(mode="python")
        try:
            self._collection.insert_one(document.copy())
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not create agent project"
            ) from exc
        return _public_document(document)

    def list_projects(
        self,
        owner_user_id: str,
        *,
        agent_type: AgentType | None = None,
        status: AgentProjectStatus | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"owner_user_id": owner_user_id}
        if agent_type is not None:
            query["agent_type"] = agent_type.value
        if status is not None:
            query["status"] = status.value
        try:
            documents = self._collection.find(query, {"_id": 0}).sort(
                [("created_at", -1), ("agent_project_id", -1)]
            )
            return [_public_document(document) for document in documents]
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not list agent projects"
            ) from exc

    def get_project(
        self,
        agent_project_id: str,
        owner_user_id: str,
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {
                    "agent_project_id": agent_project_id,
                    "owner_user_id": owner_user_id,
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not get agent project"
            ) from exc
        return _public_document(document) if document is not None else None

    def update_project(
        self,
        agent_project_id: str,
        owner_user_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one_and_update(
                {
                    "agent_project_id": agent_project_id,
                    "owner_user_id": owner_user_id,
                },
                {"$set": updates},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not update agent project"
            ) from exc
        return _public_document(document) if document is not None else None


class AgentRunRepository:
    """MongoDB persistence for immutable requests and run-state updates."""

    def __init__(
        self,
        database: Database[dict[str, Any]] | None = None,
    ) -> None:
        configured_database = database if database is not None else get_database()
        self._collection = configured_database[AGENT_RUNS]

    def next_run_sequence(self) -> int:
        try:
            largest_sequence = 0
            for document in self._collection.find(
                {},
                {"run_id": 1, "_id": 0},
            ):
                run_id = document.get("run_id")
                if not isinstance(run_id, str):
                    continue
                try:
                    validate_id(run_id, "RUN")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(run_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not allocate an agent run ID"
            ) from exc

    def create_run(self, run: AgentRun) -> dict[str, Any]:
        document = run.model_dump(mode="python")
        try:
            self._collection.insert_one(document.copy())
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not create agent run"
            ) from exc
        return _public_document(document)

    def list_runs(
        self,
        owner_user_id: str,
        agent_project_id: str,
    ) -> list[dict[str, Any]]:
        try:
            documents = self._collection.find(
                {
                    "owner_user_id": owner_user_id,
                    "agent_project_id": agent_project_id,
                },
                {"_id": 0},
            ).sort([("created_at", -1), ("run_id", -1)])
            return [_public_document(document) for document in documents]
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not list agent runs"
            ) from exc

    def get_run(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one(
                {
                    "owner_user_id": owner_user_id,
                    "agent_project_id": agent_project_id,
                    "run_id": run_id,
                },
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not get agent run"
            ) from exc
        return _public_document(document) if document is not None else None

    def update_run_state(
        self,
        owner_user_id: str,
        agent_project_id: str,
        run_id: str,
        expected_status: AgentRunStatus,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            document = self._collection.find_one_and_update(
                {
                    "owner_user_id": owner_user_id,
                    "agent_project_id": agent_project_id,
                    "run_id": run_id,
                    "status": expected_status.value,
                },
                {"$set": updates},
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as exc:
            raise StandaloneRepositoryError(
                "Could not update agent run"
            ) from exc
        return _public_document(document) if document is not None else None
