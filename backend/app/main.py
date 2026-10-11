from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.common.response import ErrorDetail, ErrorResponse
from app.core.config import settings
from app.modules.auth.dependencies import (
    AuthenticationError,
    AuthenticationServiceError,
)
from app.modules.auth.router import router as auth_router
from app.modules.approvals.router import router as approvals_router
from app.modules.orchestrator.router import router as orchestrator_router
from app.modules.projects.router import router as projects_router
from app.modules.requirements.router import router as client_inputs_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(
    request: Request,
    exc: AuthenticationError,
) -> JSONResponse:
    del request, exc
    payload = ErrorResponse(
        message="Authentication failed",
        errors=[
            ErrorDetail(
                field="authorization",
                message="Authentication failed",
            )
        ],
    )
    return JSONResponse(
        status_code=401,
        content=payload.model_dump(mode="json"),
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(AuthenticationServiceError)
async def authentication_service_exception_handler(
    request: Request,
    exc: AuthenticationServiceError,
) -> JSONResponse:
    del request, exc
    payload = ErrorResponse(
        message="Authentication failed",
        errors=[
            ErrorDetail(
                field="authentication",
                message="Authentication service is unavailable",
            )
        ],
    )
    return JSONResponse(
        status_code=503,
        content=payload.model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request
    errors = []
    for error in exc.errors():
        location = [str(part) for part in error["loc"] if part != "body"]
        errors.append(
            ErrorDetail(
                field=".".join(location) or "request",
                message=error["msg"],
            )
        )
    payload = ErrorResponse(message="Validation failed", errors=errors)
    return JSONResponse(
        status_code=422,
        content=payload.model_dump(mode="json"),
    )


app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(projects_router, prefix=settings.api_v1_prefix)
app.include_router(orchestrator_router, prefix=settings.api_v1_prefix)
app.include_router(client_inputs_router, prefix=settings.api_v1_prefix)
app.include_router(approvals_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health_check():
    return {
        "success": True,
        "message": "AgileFlow AI backend is running",
        "data": {
            "status": "healthy"
        },
        "errors": [],
    }
