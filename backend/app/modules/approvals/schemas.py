from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.status import ApprovalDecision


class ApprovalCreateRequest(BaseModel):
    """Only the reviewer-controlled fields accepted by an approval route."""

    model_config = ConfigDict(extra="forbid")

    reviewer_name: str | None = None
    reviewer_role: str | None = None
    decision: ApprovalDecision
    comment: str
    artifact_version: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_reviewer(self) -> "ApprovalCreateRequest":
        if self.reviewer_name is None and self.reviewer_role is None:
            raise ValueError("reviewer_name or reviewer_role is required")
        return self
