from typing import Any

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.common.id_generator import validate_id
from app.common.status import ApprovalGate
from app.database.collections import APPROVALS, PROJECTS, WORKFLOW_EVENTS
from app.database.mongodb import get_database
from app.modules.orchestrator.event_ids import (
    next_event_sequence_from_collection,
)
from app.schemas.approval import Approval
from app.schemas.workflow import WorkflowEvent


class ApprovalRepositoryError(RuntimeError):
    """Raised when approval persistence cannot be completed."""


class EffectiveApprovalLookup:
    """Shared deterministic lookup for the newest project/gate decision."""

    def __init__(self, approvals_collection: Any) -> None:
        self._approvals = approvals_collection

    def get_effective_approval(
        self,
        project_id: str,
        gate_id: ApprovalGate,
    ) -> dict[str, Any] | None:
        try:
            documents = (
                self._approvals.find(
                    {
                        "project_id": project_id,
                        "gate_id": gate_id.value,
                    },
                    {"_id": 0},
                )
                .sort([("timestamp", -1), ("approval_id", -1)])
                .limit(1)
            )
            document = next(iter(documents), None)
        except PyMongoError as exc:
            raise ApprovalRepositoryError(
                "Could not get effective approval"
            ) from exc
        return (
            {key: value for key, value in document.items() if key != "_id"}
            if document is not None
            else None
        )


class ApprovalRepository:
    """Append-only Approval and approval-event persistence."""

    def __init__(self, database: Database[dict[str, Any]] | None = None) -> None:
        configured_database = database if database is not None else get_database()
        self._projects = configured_database[PROJECTS]
        self._approvals = configured_database[APPROVALS]
        self._workflow_events = configured_database[WORKFLOW_EVENTS]
        self._effective_approvals = EffectiveApprovalLookup(self._approvals)

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
            raise ApprovalRepositoryError("Could not get project") from exc
        return self._public_document(document) if document is not None else None

    def next_approval_sequence(self) -> int:
        """Return one greater than the largest valid persisted APP sequence."""
        try:
            largest_sequence = 0
            for document in self._approvals.find(
                {},
                {"approval_id": 1, "_id": 0},
            ):
                approval_id = document.get("approval_id")
                if not isinstance(approval_id, str):
                    continue
                try:
                    validate_id(approval_id, "APP")
                except ValueError:
                    continue
                largest_sequence = max(
                    largest_sequence,
                    int(approval_id.rsplit("-", maxsplit=1)[1]),
                )
            return largest_sequence + 1
        except PyMongoError as exc:
            raise ApprovalRepositoryError(
                "Could not allocate an approval ID"
            ) from exc

    def next_event_sequence(self) -> int:
        """Reuse the Orchestrator EVT allocation scanner."""
        try:
            return next_event_sequence_from_collection(self._workflow_events)
        except PyMongoError as exc:
            raise ApprovalRepositoryError(
                "Could not allocate a workflow event ID"
            ) from exc

    def create_approval_with_event(
        self,
        approval: Approval,
        event: WorkflowEvent,
    ) -> dict[str, Any]:
        """Append an Approval and then its audit event without hiding failures."""
        approval_document = approval.model_dump(mode="python")
        event_document = event.model_dump(mode="python")
        try:
            self._approvals.insert_one(approval_document.copy())
            self._workflow_events.insert_one(event_document.copy())
        except PyMongoError as exc:
            raise ApprovalRepositoryError(
                "Could not persist approval decision"
            ) from exc
        return self._public_document(approval_document)

    def get_effective_approval(
        self,
        project_id: str,
        gate_id: ApprovalGate,
    ) -> dict[str, Any] | None:
        """Return the newest append-only decision for one project and gate."""
        return self._effective_approvals.get_effective_approval(
            project_id,
            gate_id,
        )
