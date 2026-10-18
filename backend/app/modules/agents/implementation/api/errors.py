"""HTTP response helpers shared by Agent 3 route modules."""

from urllib.parse import urlencode
from fastapi.responses import JSONResponse, RedirectResponse
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings


def _error(
    status_code: int,
    message: str,
    field: str,
    detail: str,
) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(mode="json")
    )


def _frontend_callback_url(
    *,
    agent_project_id: str | None = None,
    connected: bool = False,
    reason: str | None = None,
) -> str:
    base = settings.frontend_base_url.rstrip("/")
    path = (
        f"/agent-projects/{agent_project_id}"
        if agent_project_id
        else "/agents/implementation"
    )
    query = {"github": "connected" if connected else "error"}
    if reason and not connected:
        query["reason"] = reason
    return f"{base}{path}?{urlencode(query)}"


