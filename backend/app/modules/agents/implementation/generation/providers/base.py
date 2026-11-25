from typing import Protocol

from ..schemas import (
    CodeGenerationErrorCode,
    ProviderGenerationRequest,
    ProviderGenerationResponse,
)


class CodeGenerationError(RuntimeError):
    """Safe, stable failure raised by local code-generation boundaries."""

    def __init__(self, code: CodeGenerationErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class CodeGenerationProvider(Protocol):
    """Narrow provider boundary for one server-selected planned file."""

    def generate_file(
        self, request: ProviderGenerationRequest
    ) -> ProviderGenerationResponse: ...

