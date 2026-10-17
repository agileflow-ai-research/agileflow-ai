from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.model_provider import build_model_provider
from app.common.transcription_provider import (
    SpeechToTextProvider,
    build_transcription_provider,
)
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.agent1.engine import Agent1Engine
from app.modules.agent1.processing import (
    AudioProcessor,
    FFmpegAudioExtractor,
    SourceProcessorResolver,
    VideoProcessor,
)
from app.modules.agent1.repository import (
    RequirementSourceRepository,
    RequirementSourceRepositoryError,
)
from app.modules.agent1.schemas import (
    Agent1RunRequest,
    Agent1RunResult,
    RequirementSourceResponse,
    RequirementSourceType,
    SourceProcessingResult,
)
from app.modules.agent1.service import (
    Agent1Service,
    NoUsableSourceError,
    RequirementSourceProcessingService,
    RequirementSourceService,
    SourceNotFoundError,
    WrongAgentProjectTypeError,
)
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)


router = APIRouter(prefix="/agents/requirements", tags=["requirements-agent"])


def get_agent1_engine() -> Agent1Engine:
    return Agent1Engine(build_model_provider(settings))


def get_requirement_source_repository() -> RequirementSourceRepository:
    return RequirementSourceRepository()


def get_agent1_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    repository: Annotated[
        RequirementSourceRepository, Depends(get_requirement_source_repository)
    ],
    engine: Annotated[Agent1Engine, Depends(get_agent1_engine)],
) -> Agent1Service:
    return Agent1Service(standalone_service, repository, engine)


def get_requirement_source_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    repository: Annotated[
        RequirementSourceRepository, Depends(get_requirement_source_repository)
    ],
) -> RequirementSourceService:
    return RequirementSourceService(standalone_service, repository)


def get_speech_to_text_provider() -> SpeechToTextProvider:
    return build_transcription_provider(settings)


def get_requirement_source_processing_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    repository: Annotated[
        RequirementSourceRepository, Depends(get_requirement_source_repository)
    ],
    transcription_provider: Annotated[
        SpeechToTextProvider, Depends(get_speech_to_text_provider)
    ],
) -> RequirementSourceProcessingService:
    audio_processor = AudioProcessor(transcription_provider)
    resolver = SourceProcessorResolver(
        audio_processor=audio_processor,
        video_processor=VideoProcessor(
            FFmpegAudioExtractor(
                settings.ffmpeg_path, settings.video_processing_timeout_seconds
            ),
            audio_processor,
        ),
    )
    return RequirementSourceProcessingService(standalone_service, repository, resolver)


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(
        message=message,
        errors=[ErrorDetail(field=field, message=detail)],
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@router.post(
    "/{agent_project_id}/sources",
    response_model=SuccessResponse[list[RequirementSourceResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def upload_requirement_sources(
    agent_project_id: str,
    service: Annotated[
        RequirementSourceService, Depends(get_requirement_source_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    files: list[UploadFile] = File(default_factory=list),
    file: UploadFile | None = File(None),
    source_type: RequirementSourceType | None = Form(None),
) -> SuccessResponse[list[RequirementSourceResponse]] | JSONResponse:
    upload_files = list(files)
    if file is not None and file not in upload_files:
        upload_files.append(file)
    if not upload_files:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "files",
            "At least one file must be provided",
        )

    try:
        sources = await service.upload_sources(
            agent_project_id, current_user, upload_files, source_type
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
            "Reactivate the agent project before uploading sources",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except ValueError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "file",
            str(exc),
        )
    except RequirementSourceRepositoryError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Requirement source persistence failed",
            "database",
            "Source storage is unavailable",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project retrieval failed",
            "database",
            "Project storage is unavailable",
        )

    return SuccessResponse(
        message="Requirement sources uploaded successfully",
        data=sources,
    )


@router.get(
    "/{agent_project_id}/sources",
    response_model=SuccessResponse[list[RequirementSourceResponse]],
)
def list_requirement_sources(
    agent_project_id: str,
    service: Annotated[
        RequirementSourceService, Depends(get_requirement_source_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[RequirementSourceResponse]] | JSONResponse:
    try:
        sources = service.list_sources(agent_project_id, current_user)
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
            "Reactivate the agent project before listing sources",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except RequirementSourceRepositoryError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Requirement source retrieval failed",
            "database",
            "Source storage is unavailable",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project retrieval failed",
            "database",
            "Project storage is unavailable",
        )

    return SuccessResponse(
        message="Requirement sources retrieved successfully",
        data=sources,
    )


@router.post(
    "/{agent_project_id}/sources/process",
    response_model=SuccessResponse[list[SourceProcessingResult]],
)
def process_requirement_sources(
    agent_project_id: str,
    service: Annotated[
        RequirementSourceProcessingService,
        Depends(get_requirement_source_processing_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[SourceProcessingResult]] | JSONResponse:
    try:
        results = service.process_sources(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before processing sources")
    except WrongAgentProjectTypeError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Wrong agent project type", "agent_project_id", str(exc))
    except RequirementSourceRepositoryError:
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Requirement source processing failed", "database", "Source storage is unavailable")
    except StandaloneServiceError:
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Agent project retrieval failed", "database", "Project storage is unavailable")
    return SuccessResponse(message="Requirement sources processed", data=results)


@router.delete(
    "/{agent_project_id}/sources/{source_id}",
    response_model=SuccessResponse[None],
)
def delete_requirement_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        RequirementSourceService, Depends(get_requirement_source_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[None] | JSONResponse:
    try:
        service.delete_source(agent_project_id, source_id, current_user)
    except AgentProjectNotFoundError:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    except SourceNotFoundError:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Requirement source not found",
            "source_id",
            "Requirement source not found",
        )
    except ArchivedAgentProjectError:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project is archived",
            "agent_project_id",
            "Reactivate the agent project before deleting sources",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except RequirementSourceRepositoryError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Requirement source deletion failed",
            "database",
            "Source storage is unavailable",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent project retrieval failed",
            "database",
            "Project storage is unavailable",
        )

    return SuccessResponse(
        message="Requirement source deleted successfully",
        data=None,
    )


@router.post(
    "/{agent_project_id}/run",
    response_model=SuccessResponse[Agent1RunResult],
)
def run_requirements_agent(
    agent_project_id: str,
    request: Agent1RunRequest,
    service: Annotated[Agent1Service, Depends(get_agent1_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent1RunResult] | JSONResponse:
    try:
        result = service.run(agent_project_id, request, current_user)
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
            "Reactivate the agent project before running it",
        )
    except WrongAgentProjectTypeError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except NoUsableSourceError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No usable requirement sources",
            "sources",
            str(exc),
        )
    except ValueError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "agent_project_id",
            str(exc),
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Agent run persistence failed",
            "database",
            "Standalone run storage is unavailable",
        )
    return SuccessResponse(message="Requirements agent run finished", data=result)
