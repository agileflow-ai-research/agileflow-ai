from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)

from .constants import (
    ConflictAction,
    ConflictStatus,
    ConsolidationSourceKind,
    ConsolidationStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSourceRef(StrictModel):
    source_id: str
    source_kind: ConsolidationSourceKind
    label: str
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    declared_artifact_type: str | None = None
    final_artifact_id: str | None = None
    canonical_artifact_id: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    field_provenance: list[dict[str, Any]] = Field(default_factory=list)


class ConsolidationInput(StrictModel):
    source: ProjectSourceRef
    artifact_type: ArtifactDetectionLabel
    data: dict[str, Any]
    source_artifact_id: str


class ProjectSpecificationItem(StrictModel):
    project_item_id: str = Field(pattern=r"^PSI-[0-9A-F]{24}$")
    artifact_type: ArtifactDetectionLabel
    identity_key: str
    data: dict[str, Any]
    supporting_sources: list[ProjectSourceRef]
    source_artifact_ids: list[str]


class ConflictCandidate(StrictModel):
    candidate_id: str = Field(pattern=r"^PCC-[0-9A-F]{24}$")
    label: str
    value: Any
    project_item_ids: list[str]
    supporting_sources: list[ProjectSourceRef]


class ProjectConflict(StrictModel):
    conflict_id: str = Field(pattern=r"^PCF-[0-9A-F]{24}$")
    conflict_type: str
    artifact_type: ArtifactDetectionLabel
    candidates: list[ConflictCandidate] = Field(min_length=2)
    status: ConflictStatus = ConflictStatus.PENDING
    allowed_actions: list[ConflictAction]
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: ConflictAction | None = None
    selected_candidate_id: str | None = None
    reviewer_owner_id: str | None = None
    decided_at: datetime | None = None


class ConflictDecisionRequest(StrictModel):
    expected_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: ConflictAction
    candidate_id: str | None = None

    @model_validator(mode="after")
    def candidate_matches_action(self):
        requires = self.action in {
            ConflictAction.SELECT_CANDIDATE,
            ConflictAction.EXCLUDE_CANDIDATE,
        }
        if requires != (self.candidate_id is not None):
            raise ValueError(
                "candidate_id is required only for candidate-specific actions"
            )
        return self


class ConsolidationIssue(StrictModel):
    source_id: str
    error_code: str
    message: str


class ProjectConsolidationRecord(StrictModel):
    agent_project_id: str
    owner_user_id: str
    status: ConsolidationStatus
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_refs: list[ProjectSourceRef]
    items: list[ProjectSpecificationItem]
    conflicts: list[ProjectConflict]
    issues: list[ConsolidationIssue]
    deduplicated_item_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ProjectConsolidationStatusResponse(StrictModel):
    agent_project_id: str
    status: ConsolidationStatus
    source_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    pending_conflict_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    source_set_digest: str | None = None
    issues: list[ConsolidationIssue] = Field(default_factory=list)
    updated_at: datetime | None = None


class ProjectRelationship(StrictModel):
    from_item_id: str
    to_item_id: str
    relationship_type: str


class TrustedProjectSpecification(StrictModel):
    project_specification_id: str = Field(pattern=r"^TPS-[0-9A-F]{24}$")
    agent_project_id: str
    status: ConsolidationStatus
    categories: dict[ArtifactDetectionLabel, list[ProjectSpecificationItem]]
    relationships: list[ProjectRelationship]
    source_artifact_refs: list[str]
    conflict_decisions: list[ProjectConflict]
    traceability: dict[str, list[ProjectSourceRef]]
    source_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str
    created_at: datetime
