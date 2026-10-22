from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse
from app.modules.agents.requirements.contracts.errors import WrongAgentProjectTypeError
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
)


def requirement_error(
    status_code: int, message: str, field: str, detail: str
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def requirement_project_error(exc: Exception, action: str) -> JSONResponse:
    if isinstance(exc, AgentProjectNotFoundError):
        return requirement_error(
            404,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    if isinstance(exc, ArchivedAgentProjectError):
        return requirement_error(
            409,
            "Agent project is archived",
            "agent_project_id",
            f"Reactivate the agent project before {action}",
        )
    if isinstance(exc, WrongAgentProjectTypeError):
        return requirement_error(
            422, "Wrong agent project type", "agent_project_id", str(exc)
        )
    raise TypeError("Unsupported project error")
