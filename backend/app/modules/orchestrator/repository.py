from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.common.status import WorkflowStage
from app.database.collections import CLIENT_INPUTS, PROJECTS, WORKFLOW_EVENTS
from app.database.mongodb import get_database
from app.schemas.workflow import WorkflowEvent


class OrchestratorRepositoryError(RuntimeError):
    """Raised when workflow persistence cannot be completed."""


class OrchestratorRepository:
    """Persistence operations for workflow state and event history."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._projects = configured_database[PROJECTS]
        self._client_inputs = configured_database[CLIENT_INPUTS]
        self._workflow_events = configured_database[WORKFLOW_EVENTS]

    @staticmethod
    def _public_document(document: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in document.items() if key != "_id"}

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        try:
            document = self._projects.find_one(
                {"project_id": project_id},
                {"_id": 0},
            )
        except PyMongoError as exc:
            raise OrchestratorRepositoryError("Could not get project") from exc
        return self._public_document(document) if document is not None else None

    def next_event_sequence(self) -> int:
        """Return one greater than the largest valid persisted EVT sequence."""
        try:
            largest_sequence = 0
            for document in self._workflow_events.find(
                {},
                {"event_id": 1, "_id": 0},
            ):
                event_id = document.get("event_id")
                if not isinstance(event_id, str):
                    continue
                try:
                    validate_id(event_id, "EVT")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(event_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise OrchestratorRepositoryError(
                "Could not allocate a workflow event ID"
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
            raise OrchestratorRepositoryError(
                "Could not check workflow prerequisites"
            ) from exc

    def list_workflow_events(self, project_id: str) -> list[dict[str, Any]]:
        try:
            documents = self._workflow_events.find(
                {"project_id": project_id},
                {"_id": 0},
            ).sort([("created_at", 1), ("event_id", 1)])
            return [self._public_document(document) for document in documents]
        except PyMongoError as exc:
            raise OrchestratorRepositoryError(
                "Could not list workflow events"
            ) from exc

    def persist_stage_change(
        self,
        project_id: str,
        owner_user_id: str,
        stage_before: WorkflowStage,
        stage_after: WorkflowStage,
        updated_at: datetime,
        event: WorkflowEvent,
    ) -> dict[str, Any] | None:
        """Conditionally update the project, then append its workflow event."""
        try:
            project = self._projects.find_one_and_update(
                {
                    "project_id": project_id,
                    "owner_user_id": owner_user_id,
                    "current_stage": stage_before.value,
                },
                {
                    "$set": {
                        "current_stage": stage_after.value,
                        "updated_at": updated_at,
                    }
                },
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
            if project is None:
                return None

            self._workflow_events.insert_one(
                event.model_dump(mode="python")
            )
            return self._public_document(project)
        except PyMongoError as exc:
            raise OrchestratorRepositoryError(
                "Could not persist workflow transition"
            ) from exc
