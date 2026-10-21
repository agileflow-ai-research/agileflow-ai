from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.common.model_provider import build_model_provider
from app.common.response import ErrorDetail, ErrorResponse, SuccessResponse
from app.core.config import settings
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import (
    AgentProjectNotFoundError,
    ArchivedAgentProjectError,
    StandaloneService,
    StandaloneServiceError,
)
from app.modules.agents.testing_validation.engine import Agent4Engine
from app.modules.agents.testing_validation.schemas import Agent4RunRequest, Agent4RunResult
from app.modules.agents.testing_validation.service import Agent4Service, WrongAgentProjectTypeError
from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputArtifactType,
    TestGenerationInputOriginAgent,
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceRecord,
    TestGenerationTextSourceCreate,
)
from app.modules.agents.testing_validation.sources.service import (
    Agent4SourceProjectIdError,
    Agent4SourceService,
)
from app.modules.agents.testing_validation.sources.storage import (
    Agent4SourceCapacityError,
    Agent4SourceNotFoundError,
    Agent4SourceStorage,
    Agent4SourceStorageError,
    Agent4SourceValidationError,
)
from app.modules.agents.testing_validation.preparation.extraction.service import (
    Agent4DocumentExtractionService,
)
from app.modules.agents.testing_validation.preparation.extraction.storage import (
    Agent4ExtractionStorage,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationService,
)
from app.modules.agents.testing_validation.preparation.normalization.storage import (
    Agent4NormalizationStorage,
)
from app.modules.agents.testing_validation.preparation.chunking.service import (
    Agent4ChunkingService,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.workflow.orchestration.service import (
    Agent4N2OrchestrationService,
)
from app.modules.agents.testing_validation.workflow.orchestration.n3_service import (
    Agent4N3OrchestrationService,
    Agent4N3ReviewError,
)
from app.modules.agents.testing_validation.workflow.orchestration.n4_service import (
    Agent4N4OrchestrationService,
    Agent4N4ReviewError,
)
from app.modules.agents.testing_validation.context_testability.traceability.service import Agent4TraceabilityService
from app.modules.agents.testing_validation.context_testability.traceability.storage import Agent4TraceabilityStorage
from app.modules.agents.testing_validation.context_testability.testability.service import Agent4TestabilityService
from app.modules.agents.testing_validation.context_testability.testability.storage import Agent4TestabilityStorage
from app.modules.agents.testing_validation.context_testability.feasibility.service import Agent4FeasibilityService
from app.modules.agents.testing_validation.context_testability.feasibility.storage import Agent4FeasibilityStorage
from app.modules.agents.testing_validation.context_testability.context_decision.service import Agent4ContextDecisionService
from app.modules.agents.testing_validation.context_testability.context_decision.storage import Agent4ContextDecisionStorage
from app.modules.agents.testing_validation.intelligence.rules.service import Agent4RuleClassificationService
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.zero_shot.service import Agent4ZeroShotService
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import Agent4ZeroShotStorage
from app.modules.agents.testing_validation.intelligence.zero_shot.classifier import Agent4ZeroShotClassifier
from app.modules.agents.testing_validation.intelligence.zero_shot.runtime import Agent4ZeroShotRuntime
from app.modules.agents.testing_validation.intelligence.hybrid.service import Agent4HybridClassificationService
from app.modules.agents.testing_validation.intelligence.hybrid.storage import Agent4HybridStorage
from app.modules.agents.testing_validation.intelligence.semantic.service import Agent4SemanticFactService
from app.modules.agents.testing_validation.intelligence.semantic.storage import Agent4SemanticStorage
from app.modules.agents.testing_validation.intelligence.effective.service import Agent4EffectiveClassificationService
from app.modules.agents.testing_validation.intelligence.effective.storage import Agent4EffectiveStorage
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3ReviewProjection,
    Agent4N3ReviewSubmission,
    Agent4N4ResultProjection,
    Agent4N4WarningAcknowledgementRequest,
    Agent4TestGenerationWorkflowResponse,
    TestGenerationOutputSelectionUpdate,
)
from app.modules.agents.testing_validation.workflow.service import (
    Agent4SetupConfirmedError,
    Agent4WorkflowService,
    Agent4WorkflowGateError,
    Agent4WorkflowStageError,
    WrongAgent4WorkflowProjectError,
)
from app.modules.agents.testing_validation.workflow.storage import (
    Agent4WorkflowStorage,
    Agent4WorkflowStorageError,
)


router = APIRouter(prefix="/agents/testing-validation", tags=["testing-validation-agent"])


def get_agent4_engine() -> Agent4Engine:
    return Agent4Engine(build_model_provider(settings))


def get_agent4_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    engine: Annotated[Agent4Engine, Depends(get_agent4_engine)],
) -> Agent4Service:
    return Agent4Service(standalone_service, engine)


def get_agent4_workflow_storage() -> Agent4WorkflowStorage:
    return Agent4WorkflowStorage(settings.agent4_storage_root)


def get_agent4_source_storage() -> Agent4SourceStorage:
    return Agent4SourceStorage(settings.agent4_storage_root)


def get_agent4_workflow_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    workflow_storage: Annotated[
        Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)
    ],
    source_storage: Annotated[
        Agent4SourceStorage, Depends(get_agent4_source_storage)
    ],
) -> Agent4WorkflowService:
    return Agent4WorkflowService(
        standalone_service, workflow_storage, source_storage
    )


def get_agent4_source_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    source_storage: Annotated[
        Agent4SourceStorage, Depends(get_agent4_source_storage)
    ],
    workflow_storage: Annotated[
        Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)
    ],
) -> Agent4SourceService:
    return Agent4SourceService(
        standalone_service, source_storage, workflow_storage
    )


def get_agent4_n4_orchestration_service(
    workflow_service: Annotated[Agent4WorkflowService, Depends(get_agent4_workflow_service)],
    workflow_storage: Annotated[Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)],
    source_storage: Annotated[Agent4SourceStorage, Depends(get_agent4_source_storage)],
) -> Agent4N4OrchestrationService:
    root = settings.agent4_storage_root
    traceability_storage = Agent4TraceabilityStorage(root)
    testability_storage = Agent4TestabilityStorage(root)
    feasibility_storage = Agent4FeasibilityStorage(root)
    decision_storage = Agent4ContextDecisionStorage(root)
    traceability = Agent4TraceabilityService(
        workflow_service, workflow_storage, source_storage,
        Agent4ChunkStorage(root), Agent4EffectiveStorage(root),
        Agent4SemanticStorage(root), traceability_storage,
    )
    testability = Agent4TestabilityService(
        workflow_service, workflow_storage, traceability, testability_storage,
    )
    feasibility = Agent4FeasibilityService(
        workflow_service, workflow_storage, traceability, testability,
        feasibility_storage,
    )
    decision = Agent4ContextDecisionService(
        workflow_service, workflow_storage, traceability_storage,
        testability_storage, feasibility_storage, decision_storage,
    )
    return Agent4N4OrchestrationService(
        workflow_service, workflow_storage, traceability, testability,
        feasibility, decision, traceability_storage, testability_storage,
        feasibility_storage, decision_storage,
    )


def get_agent4_n3_orchestration_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    workflow_service: Annotated[Agent4WorkflowService, Depends(get_agent4_workflow_service)],
    workflow_storage: Annotated[Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)],
    n4_service: Annotated[Agent4N4OrchestrationService, Depends(get_agent4_n4_orchestration_service)],
) -> Agent4N3OrchestrationService:
    root = settings.agent4_storage_root
    chunks = Agent4ChunkStorage(root)
    rules_storage = Agent4RuleStorage(root)
    zero_storage = Agent4ZeroShotStorage(root)
    hybrid_storage = Agent4HybridStorage(root)
    rules = Agent4RuleClassificationService(
        standalone_service, workflow_storage, chunks, rules_storage
    )
    zero = Agent4ZeroShotService(
        standalone_service, workflow_storage, chunks, zero_storage,
        Agent4ZeroShotClassifier(Agent4ZeroShotRuntime(local_files_only=True)),
    )
    hybrid = Agent4HybridClassificationService(
        standalone_service, workflow_storage, chunks, rules_storage,
        zero_storage, hybrid_storage,
    )
    semantic = Agent4SemanticFactService(
        standalone_service, workflow_storage, chunks, rules_storage,
        zero_storage, hybrid_storage, Agent4SemanticStorage(root),
    )
    effective = Agent4EffectiveClassificationService(Agent4EffectiveStorage(root))
    return Agent4N3OrchestrationService(
        workflow_service, workflow_storage, chunks, rules, zero, hybrid,
        semantic, effective, hybrid_storage, rules_storage, zero_storage,
        n4_handoff=n4_service.start_after_n3,
    )


def get_agent4_n2_orchestration_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    workflow_service: Annotated[
        Agent4WorkflowService, Depends(get_agent4_workflow_service)
    ],
    workflow_storage: Annotated[
        Agent4WorkflowStorage, Depends(get_agent4_workflow_storage)
    ],
    source_storage: Annotated[
        Agent4SourceStorage, Depends(get_agent4_source_storage)
    ],
    n3_service: Annotated[
        Agent4N3OrchestrationService, Depends(get_agent4_n3_orchestration_service)
    ],
) -> Agent4N2OrchestrationService:
    root = settings.agent4_storage_root
    extraction = Agent4DocumentExtractionService(
        standalone_service,
        source_storage,
        workflow_storage,
        Agent4ExtractionStorage(root),
    )
    normalization = Agent4NormalizationService(
        extraction, Agent4NormalizationStorage(root)
    )
    chunking = Agent4ChunkingService(normalization, Agent4ChunkStorage(root))
    return Agent4N2OrchestrationService(
        workflow_service,
        workflow_storage,
        source_storage,
        extraction,
        normalization,
        chunking,
        n3_handoff=n3_service.start_after_n2,
    )


def _error(status_code: int, message: str, field: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(message=message, errors=[ErrorDetail(field=field, message=detail)])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


@router.get(
    "/{agent_project_id}/test-generation/workflow",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def get_test_generation_workflow(
    agent_project_id: str,
    service: Annotated[
        Agent4N2OrchestrationService,
        Depends(get_agent4_n2_orchestration_service),
    ],
    n3_service: Annotated[
        Agent4N3OrchestrationService,
        Depends(get_agent4_n3_orchestration_service),
    ],
    n4_service: Annotated[
        Agent4N4OrchestrationService,
        Depends(get_agent4_n4_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        service.get(agent_project_id, current_user)
        n3_service.get(agent_project_id, current_user)
        workflow = n4_service.get(agent_project_id, current_user)
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
            "Reactivate the agent project before loading its workflow",
        )
    except WrongAgent4WorkflowProjectError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except Agent4WorkflowStageError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project stage is unavailable",
            "agent_stage",
            str(exc),
        )
    except Agent4WorkflowStorageError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow storage failed",
            "workflow",
            "The Agent 4 workflow could not be loaded",
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project storage failed",
            "database",
            "The Agent 4 project could not be loaded",
        )
    return SuccessResponse(
        message="Agent 4 Test Generation workflow retrieved", data=workflow
    )


@router.put(
    "/{agent_project_id}/test-generation/workflow/outputs",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def update_test_generation_outputs(
    agent_project_id: str,
    request: TestGenerationOutputSelectionUpdate,
    service: Annotated[
        Agent4WorkflowService, Depends(get_agent4_workflow_service)
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        workflow = service.update_outputs(
            agent_project_id, current_user, request.selected_outputs
        )
    except Agent4SetupConfirmedError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Input and output setup is frozen",
            "workflow",
            str(exc),
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
            "Reactivate the agent project before updating desired outputs",
        )
    except WrongAgent4WorkflowProjectError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except Agent4WorkflowStageError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project stage is unavailable",
            "agent_stage",
            str(exc),
        )
    except Agent4WorkflowStorageError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Workflow storage failed",
            "workflow",
            "The desired output selection could not be persisted",
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project storage failed",
            "database",
            "The Agent 4 project could not be loaded",
        )
    return SuccessResponse(
        message="Agent 4 desired outputs updated", data=workflow
    )


@router.post(
    "/{agent_project_id}/test-generation/workflow/n1/confirm",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def confirm_test_generation_n1(
    agent_project_id: str,
    service: Annotated[
        Agent4N2OrchestrationService,
        Depends(get_agent4_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        workflow = service.confirm_n1_and_start(agent_project_id, current_user)
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
            "Reactivate the agent project before confirming setup",
        )
    except WrongAgent4WorkflowProjectError as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    except Agent4WorkflowStageError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project stage is unavailable",
            "agent_stage",
            str(exc),
        )
    except (Agent4WorkflowGateError, Agent4SetupConfirmedError) as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Input and output setup cannot be confirmed",
            "workflow",
            str(exc),
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (Agent4WorkflowStorageError, Agent4SourceStorageError):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Setup storage failed",
            "workflow",
            "The input and output setup could not be confirmed",
        )
    except StandaloneServiceError:
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Project storage failed",
            "database",
            "The Agent 4 project could not be loaded",
        )
    return SuccessResponse(
        message="Agent 4 input and output setup confirmed", data=workflow
    )


@router.post(
    "/{agent_project_id}/test-generation/workflow/n3/start",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def start_test_generation_n3(
    agent_project_id: str,
    service: Annotated[Agent4N3OrchestrationService, Depends(get_agent4_n3_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.start(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before starting Testing Intelligence")
    except (WrongAgent4WorkflowProjectError, Agent4WorkflowStageError, Agent4WorkflowGateError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Testing Intelligence cannot be started", "workflow", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "agent_project_id", "Agent project ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Testing Intelligence unavailable", "workflow", "Testing Intelligence could not be started")
    return SuccessResponse(message="Agent 4 Testing Intelligence accepted", data=workflow)


@router.get(
    "/{agent_project_id}/test-generation/workflow/n3/review",
    response_model=SuccessResponse[Agent4N3ReviewProjection],
)
def get_test_generation_n3_review(
    agent_project_id: str,
    service: Annotated[Agent4N3OrchestrationService, Depends(get_agent4_n3_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        review = service.review_projection(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing classifications")
    except (Agent4N3ReviewError, Agent4WorkflowGateError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Classification review unavailable", "review", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "agent_project_id", "Agent project ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Classification review unavailable", "review", "Classification review could not be loaded")
    return SuccessResponse(message="Agent 4 classification review retrieved", data=review)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n3/review",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def submit_test_generation_n3_review(
    agent_project_id: str,
    request: Agent4N3ReviewSubmission,
    service: Annotated[Agent4N3OrchestrationService, Depends(get_agent4_n3_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.submit_review(agent_project_id, request, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before reviewing classifications")
    except Agent4N3ReviewError as exc:
        return _error(status.HTTP_409_CONFLICT, "Classification review rejected", "review", str(exc))
    except Agent4WorkflowGateError as exc:
        return _error(status.HTTP_409_CONFLICT, "Classification review unavailable", "workflow", str(exc))
    except ValueError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid classification review", "review", str(exc))
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Classification review unavailable", "review", "Classification review could not be saved")
    return SuccessResponse(message="Agent 4 classification review accepted", data=workflow)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n3/sources/{source_id}/retry",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def retry_test_generation_n3_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[Agent4N3OrchestrationService, Depends(get_agent4_n3_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.retry_source(agent_project_id, source_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the agent project before retrying Testing Intelligence")
    except (Agent4WorkflowGateError, Agent4N3ReviewError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Testing Intelligence source cannot be retried", "source_id", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "source_id", "The project or source ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Testing Intelligence unavailable", "workflow", "The source retry could not be started")
    return SuccessResponse(message="Agent 4 Testing Intelligence source retry accepted", data=workflow)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n4/start",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def start_test_generation_n4(
    agent_project_id: str,
    service: Annotated[Agent4N4OrchestrationService, Depends(get_agent4_n4_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.start(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the project before starting context analysis")
    except (WrongAgent4WorkflowProjectError, Agent4WorkflowStageError, Agent4WorkflowGateError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Context analysis cannot be started", "workflow", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "agent_project_id", "Agent project ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Context analysis unavailable", "workflow", "Context analysis could not be started")
    return SuccessResponse(message="Agent 4 Context & Testability accepted", data=workflow)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n4/retry",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def retry_test_generation_n4(
    agent_project_id: str,
    service: Annotated[Agent4N4OrchestrationService, Depends(get_agent4_n4_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.retry(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the project before retrying context analysis")
    except (Agent4WorkflowGateError, WrongAgent4WorkflowProjectError, Agent4WorkflowStageError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Context analysis cannot be retried", "workflow", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "agent_project_id", "Agent project ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Context analysis unavailable", "workflow", "Context analysis retry could not be started")
    return SuccessResponse(message="Agent 4 Context & Testability retry accepted", data=workflow)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n4/acknowledge-warnings",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def acknowledge_test_generation_n4_warnings(
    agent_project_id: str,
    request: Agent4N4WarningAcknowledgementRequest,
    service: Annotated[Agent4N4OrchestrationService, Depends(get_agent4_n4_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        workflow = service.acknowledge(agent_project_id, request, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the project before acknowledging warnings")
    except (Agent4N4ReviewError, Agent4WorkflowGateError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Warning acknowledgement rejected", "warning_snapshot_fingerprint", str(exc))
    except ValueError as exc:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid acknowledgement", "acknowledgement", str(exc))
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Warning acknowledgement unavailable", "workflow", "Warning acknowledgement could not be saved")
    return SuccessResponse(message="Agent 4 context warnings acknowledged", data=workflow)


@router.get(
    "/{agent_project_id}/test-generation/workflow/n4/result",
    response_model=SuccessResponse[Agent4N4ResultProjection],
)
def get_test_generation_n4_result(
    agent_project_id: str,
    service: Annotated[Agent4N4OrchestrationService, Depends(get_agent4_n4_orchestration_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
):
    try:
        result = service.result(agent_project_id, current_user)
    except AgentProjectNotFoundError:
        return _error(status.HTTP_404_NOT_FOUND, "Agent project not found", "agent_project_id", "Agent project not found")
    except ArchivedAgentProjectError:
        return _error(status.HTTP_409_CONFLICT, "Agent project is archived", "agent_project_id", "Reactivate the project before viewing context results")
    except (Agent4WorkflowGateError, WrongAgent4WorkflowProjectError, Agent4WorkflowStageError) as exc:
        return _error(status.HTTP_409_CONFLICT, "Context decision unavailable", "workflow", str(exc))
    except ValueError:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid request", "agent_project_id", "Agent project ID is invalid")
    except (Agent4WorkflowStorageError, StandaloneServiceError, RuntimeError):
        return _error(status.HTTP_503_SERVICE_UNAVAILABLE, "Context decision unavailable", "workflow", "Context decision could not be loaded")
    return SuccessResponse(message="Agent 4 context decision retrieved", data=result)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n2/start",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def start_test_generation_n2(
    agent_project_id: str,
    service: Annotated[
        Agent4N2OrchestrationService,
        Depends(get_agent4_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        workflow = service.start(agent_project_id, current_user)
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
            "Reactivate the agent project before starting preparation",
        )
    except (WrongAgent4WorkflowProjectError, Agent4WorkflowStageError) as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Input Preparation is unavailable",
            "workflow",
            str(exc),
        )
    except Agent4WorkflowGateError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Input Preparation cannot be started",
            "workflow",
            str(exc),
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (Agent4WorkflowStorageError, Agent4SourceStorageError):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Preparation storage failed",
            "workflow",
            "Input Preparation could not be started",
        )
    return SuccessResponse(message="Agent 4 Input Preparation accepted", data=workflow)


@router.post(
    "/{agent_project_id}/test-generation/workflow/n2/sources/{source_id}/retry",
    response_model=SuccessResponse[Agent4TestGenerationWorkflowResponse],
)
def retry_test_generation_n2_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[
        Agent4N2OrchestrationService,
        Depends(get_agent4_n2_orchestration_service),
    ],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4TestGenerationWorkflowResponse] | JSONResponse:
    try:
        workflow = service.retry_source(agent_project_id, source_id, current_user)
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
            "Reactivate the agent project before retrying preparation",
        )
    except (WrongAgent4WorkflowProjectError, Agent4WorkflowStageError) as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Input Preparation retry is unavailable",
            "workflow",
            str(exc),
        )
    except Agent4WorkflowGateError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Source cannot be retried",
            "source_id",
            str(exc),
        )
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid request",
            "source_id",
            "The project or source ID is invalid",
        )
    except (Agent4WorkflowStorageError, Agent4SourceStorageError):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Preparation storage failed",
            "workflow",
            "The source retry could not be started",
        )
    return SuccessResponse(message="Agent 4 source retry accepted", data=workflow)


def _source_project_error(exc: Exception, action: str) -> JSONResponse:
    if isinstance(exc, Agent4SetupConfirmedError):
        return _error(
            status.HTTP_409_CONFLICT,
            "Input and output setup is frozen",
            "workflow",
            str(exc),
        )
    if isinstance(exc, AgentProjectNotFoundError):
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Agent project not found",
            "agent_project_id",
            "Agent project not found",
        )
    if isinstance(exc, ArchivedAgentProjectError):
        return _error(
            status.HTTP_409_CONFLICT,
            "Agent project is archived",
            "agent_project_id",
            f"Reactivate the agent project before {action}",
        )
    if isinstance(exc, WrongAgent4WorkflowProjectError):
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Wrong agent project type",
            "agent_project_id",
            str(exc),
        )
    return _error(
        status.HTTP_409_CONFLICT,
        "Agent project stage is unavailable",
        "agent_stage",
        str(exc),
    )


@router.get(
    "/{agent_project_id}/test-generation/sources",
    response_model=SuccessResponse[list[TestGenerationSourceRecord]],
)
def list_test_generation_sources(
    agent_project_id: str,
    service: Annotated[Agent4SourceService, Depends(get_agent4_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[list[TestGenerationSourceRecord]] | JSONResponse:
    try:
        sources = service.list(agent_project_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgent4WorkflowProjectError,
        Agent4WorkflowStageError,
    ) as exc:
        return _source_project_error(exc, "listing sources")
    except ValueError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (
        StandaloneServiceError,
        Agent4SourceStorageError,
        Agent4WorkflowStorageError,
    ):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Source storage failed",
            "storage",
            "Agent 4 sources could not be listed",
        )
    return SuccessResponse(message="Agent 4 sources retrieved", data=sources)


@router.post(
    "/{agent_project_id}/test-generation/sources/text",
    response_model=SuccessResponse[TestGenerationSourceRecord],
    status_code=status.HTTP_201_CREATED,
)
def create_test_generation_text_source(
    agent_project_id: str,
    request: TestGenerationTextSourceCreate,
    service: Annotated[Agent4SourceService, Depends(get_agent4_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[TestGenerationSourceRecord] | JSONResponse:
    try:
        source = service.create_text(agent_project_id, request, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgent4WorkflowProjectError,
        Agent4WorkflowStageError,
        Agent4SetupConfirmedError,
    ) as exc:
        return _source_project_error(exc, "adding sources")
    except Agent4SourceCapacityError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Source capacity reached",
            "sources",
            str(exc),
        )
    except Agent4SourceProjectIdError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (
        StandaloneServiceError,
        Agent4SourceStorageError,
        Agent4WorkflowStorageError,
    ):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Source storage failed",
            "storage",
            "The Agent 4 source could not be stored",
        )
    return SuccessResponse(message="Agent 4 TEXT source created", data=source)


@router.post(
    "/{agent_project_id}/test-generation/sources/files",
    response_model=SuccessResponse[TestGenerationSourceRecord],
    status_code=status.HTTP_201_CREATED,
)
async def upload_test_generation_file_source(
    agent_project_id: str,
    artifact_type: Annotated[TestGenerationInputArtifactType, Form()],
    source_type: Annotated[TestGenerationInputSourceType, Form()],
    normally_supplied_by: Annotated[TestGenerationInputOriginAgent, Form()],
    file: Annotated[UploadFile, File()],
    service: Annotated[Agent4SourceService, Depends(get_agent4_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
    label: Annotated[str | None, Form(max_length=200)] = None,
) -> SuccessResponse[TestGenerationSourceRecord] | JSONResponse:
    try:
        source = await service.create_file(
            agent_project_id,
            artifact_type=artifact_type,
            source_type=source_type,
            normally_supplied_by=normally_supplied_by,
            label=label,
            upload=file,
            current_user=current_user,
        )
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgent4WorkflowProjectError,
        Agent4WorkflowStageError,
        Agent4SetupConfirmedError,
    ) as exc:
        return _source_project_error(exc, "uploading sources")
    except Agent4SourceCapacityError as exc:
        return _error(
            status.HTTP_409_CONFLICT,
            "Source capacity reached",
            "sources",
            str(exc),
        )
    except Agent4SourceProjectIdError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (ValueError, Agent4SourceValidationError) as exc:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Source validation failed",
            "file",
            str(exc),
        )
    except (
        StandaloneServiceError,
        Agent4SourceStorageError,
        Agent4WorkflowStorageError,
    ):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Source storage failed",
            "storage",
            "The Agent 4 source could not be stored",
        )
    finally:
        await file.close()
    return SuccessResponse(message="Agent 4 file source uploaded", data=source)


@router.delete(
    "/{agent_project_id}/test-generation/sources/{source_id}",
    response_model=SuccessResponse[dict[str, str]],
)
def delete_test_generation_source(
    agent_project_id: str,
    source_id: str,
    service: Annotated[Agent4SourceService, Depends(get_agent4_source_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[dict[str, str]] | JSONResponse:
    try:
        service.delete(agent_project_id, source_id, current_user)
    except (
        AgentProjectNotFoundError,
        ArchivedAgentProjectError,
        WrongAgent4WorkflowProjectError,
        Agent4WorkflowStageError,
        Agent4SetupConfirmedError,
    ) as exc:
        return _source_project_error(exc, "removing sources")
    except Agent4SourceNotFoundError:
        return _error(
            status.HTTP_404_NOT_FOUND,
            "Agent 4 source not found",
            "source_id",
            "Agent 4 source not found",
        )
    except Agent4SourceProjectIdError:
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Invalid agent project ID",
            "agent_project_id",
            "Agent project ID is invalid",
        )
    except (
        StandaloneServiceError,
        Agent4SourceStorageError,
        Agent4WorkflowStorageError,
    ):
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Source storage failed",
            "storage",
            "The Agent 4 source could not be removed",
        )
    return SuccessResponse(
        message="Agent 4 source removed", data={"source_id": source_id}
    )


@router.post("/{agent_project_id}/run", response_model=SuccessResponse[Agent4RunResult])
def run_testing_validation_agent(
    agent_project_id: str,
    request: Agent4RunRequest,
    service: Annotated[Agent4Service, Depends(get_agent4_service)],
    current_user: Annotated[UserPublicResponse, Depends(get_current_user)],
) -> SuccessResponse[Agent4RunResult] | JSONResponse:
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
    return SuccessResponse(message="Testing and validation agent run finished", data=result)
