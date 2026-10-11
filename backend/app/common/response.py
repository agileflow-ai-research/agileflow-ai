from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.common.status import WorkflowStage


DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    message: str


class ApiResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    data: DataT | None = None
    errors: list[ErrorDetail] = Field(default_factory=list)
    workflow_stage: WorkflowStage | None = None
    next_action: str | None = None


class SuccessResponse(ApiResponse[DataT], Generic[DataT]):
    success: Literal[True] = True


class ErrorResponse(ApiResponse[None]):
    success: Literal[False] = False
    data: None = None
