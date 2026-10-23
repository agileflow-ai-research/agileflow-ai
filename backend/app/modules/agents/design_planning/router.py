from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.document_extractor import DocumentExtractorError, extract_document_text
from app.common.model_provider import build_model_provider
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.common.status import AgentType
from app.core.config import settings
from app.modules.agents.design_planning.engine import Agent2Engine
from app.modules.agents.design_planning.schemas import (
    Agent2RunRequest,
    Agent2RunResult,
    DocumentExtractionResult,
)
from app.modules.agents.design_planning.service import Agent2Service, WrongAgentProjectTypeError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(prefix="/agents/design-planning", tags=["design-planning-agent"])


def get_agent2_engine() -> Agent2Engine:
    return Agent2Engine(build_model_provider(settings))


def get_agent2_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    engine: Annotated[Agent2Engine, Depends(get_agent2_engine)],
) -> Agent2Service:
    return Agent2Service(standalone_service, engine)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@router.post("/{agent_project_id}/run", response_model=SuccessResponse[Agent2RunResult])
def run_design_planning_agent(
    agent_project_id: str,
    request: Agent2RunRequest,
    service: Annotated[Agent2Service, Depends(get_agent2_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent2RunResult] | JSONResponse:
    try:
        result = service.run(agent_project_id, request, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before running it")
    except WrongAgentProjectTypeError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wrong agent project type", "agent_project_id", str(exc))
    except ValueError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Validation failed", "agent_project_id", str(exc))
    except StandaloneServiceError:
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Agent run persistence failed", "database", "Standalone run storage is unavailable")
    return SuccessResponse(message="Design and planning agent run finished", data=result)


@router.post(
    "/{agent_project_id}/specification/extract",
    response_model=SuccessResponse[DocumentExtractionResult],
)
async def extract_specification_document(
    agent_project_id: str,
    file: Annotated[UploadFile, File(...)],
    source_type: Annotated[str, Form(...)],
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[DocumentExtractionResult] | JSONResponse:
    try:
        project = standalone_service.require_active_project(current_user.user_id, agent_project_id)
        if project.agent_type is not AgentType.DESIGN_PLANNING:
            return _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Wrong agent project type",
                "agent_project_id",
                "Agent project must have agent_type DESIGN_PLANNING",
            )
    except AgentProjectNotFoundError:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before extracting specifications",
        )

    valid_sources = {"REQUIREMENTS", "SRS", "USER_STORIES", "ACCEPTANCE_CRITERIA"}
    normalized_source = (source_type or "").strip().upper()
    if normalized_source not in valid_sources:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid specification source type",
            "source_type",
            f"source_type must be one of: {', '.join(sorted(valid_sources))}",
        )

    try:
        content = await file.read()
    except Exception as exc:
        return _error(
            status.HTTP_400_BAD_REQUEST,
            "Failed to read uploaded file",
            "file",
            str(exc),
        )

    try:
        extracted_text, detected_mime, char_count, sha256_hash = extract_document_text(
            content=content,
            filename=file.filename or "specification.txt",
            content_type=file.content_type,
        )
    except DocumentExtractorError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.message,
            "file",
            f"[{exc.code}] {exc.message}",
        )
    except Exception as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Document extraction failed unexpectedly",
            "file",
            f"[DOCUMENT_EXTRACTION_FAILED] {str(exc)}",
        )

    result = DocumentExtractionResult(
        source_type=normalized_source,
        original_filename=file.filename or "unknown",
        mime_type=detected_mime,
        size_bytes=len(content),
        sha256=sha256_hash,
        character_count=char_count,
        extracted_text=extracted_text,
        extraction_status="COMPLETED",
    )
    return SuccessResponse(message="Document text extracted successfully", data=result)
