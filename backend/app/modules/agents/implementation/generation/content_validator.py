import hashlib
import json

from .providers.base import CodeGenerationError
from .schemas import (
    CodeGenerationErrorCode as ErrorCode,
    ContentValidationFinding,
    FileContentType,
    FileGenerationContext,
    GeneratedCandidateStatus,
    ModelFileResponse,
    SyntaxValidationStatus,
)


class ValidatedGeneratedContent:
    def __init__(
        self,
        *,
        status: GeneratedCandidateStatus,
        content: str | None,
        content_sha256: str | None,
        syntax_status: SyntaxValidationStatus,
        findings: tuple[ContentValidationFinding, ...],
        safe_failure_code: ErrorCode | None,
    ) -> None:
        self.status = status
        self.content = content
        self.content_sha256 = content_sha256
        self.syntax_status = syntax_status
        self.findings = findings
        self.safe_failure_code = safe_failure_code


class GeneratedContentValidator:
    """Performs bounded deterministic validation without executing content."""

    def __init__(self, *, max_content_chars: int) -> None:
        self.max_content_chars = max_content_chars

    def validate(
        self,
        context: FileGenerationContext,
        response: ModelFileResponse,
    ) -> ValidatedGeneratedContent:
        if response.missing_information:
            return ValidatedGeneratedContent(
                status=GeneratedCandidateStatus.MISSING_INFORMATION,
                content=None,
                content_sha256=None,
                syntax_status=SyntaxValidationStatus.UNAVAILABLE,
                findings=(
                    ContentValidationFinding(
                        code="MANDATORY_INFORMATION_MISSING",
                        message="The model reported missing mandatory generation information",
                    ),
                ),
                safe_failure_code=ErrorCode.MISSING_REQUIRED_INFORMATION,
            )
        content = response.content
        if not content.strip():
            self._fail(ErrorCode.EMPTY_GENERATION, "Generated content is empty")
        if len(content) > self.max_content_chars:
            self._fail(
                ErrorCode.UNSUPPORTED_CONTENT,
                "Generated content exceeds the configured size limit",
            )
        if "\x00" in content or "\ufffd" in content:
            self._fail(
                ErrorCode.UNSAFE_GENERATED_CONTENT,
                "Generated content contains unsupported text",
            )
        if any(ord(character) < 32 and character not in "\n\r\t" for character in content):
            self._fail(
                ErrorCode.UNSAFE_GENERATED_CONTENT,
                "Generated content contains control characters",
            )
        try:
            encoded = content.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise CodeGenerationError(
                ErrorCode.UNSUPPORTED_CONTENT,
                "Generated content is not valid UTF-8 text",
            ) from exc

        syntax_status, findings = self._syntax_validation(context, content)
        if syntax_status is SyntaxValidationStatus.INVALID:
            self._fail(
                ErrorCode.UNSUPPORTED_CONTENT,
                "Generated content failed available syntax validation",
            )
        return ValidatedGeneratedContent(
            status=GeneratedCandidateStatus.VALIDATED,
            content=content,
            content_sha256=hashlib.sha256(encoded).hexdigest(),
            syntax_status=syntax_status,
            findings=findings,
            safe_failure_code=None,
        )

    @staticmethod
    def _syntax_validation(context, content):
        if context.content_type is FileContentType.JSON:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                return (
                    SyntaxValidationStatus.INVALID,
                    (
                        ContentValidationFinding(
                            code="INVALID_JSON_CONTENT",
                            message="Generated JSON content is not syntactically valid",
                        ),
                    ),
                )
            if not isinstance(parsed, (dict, list)):
                return (
                    SyntaxValidationStatus.INVALID,
                    (
                        ContentValidationFinding(
                            code="UNSUPPORTED_JSON_ROOT",
                            message="Generated JSON must use an object or array root",
                        ),
                    ),
                )
            return SyntaxValidationStatus.VALID, ()
        return (
            SyntaxValidationStatus.UNAVAILABLE,
            (
                ContentValidationFinding(
                    code="SYNTAX_VALIDATION_UNAVAILABLE",
                    message=(
                        "No approved non-executing syntax parser is available for "
                        f"{context.content_type.value} content"
                    ),
                ),
            ),
        )

    @staticmethod
    def _fail(code: ErrorCode, message: str):
        raise CodeGenerationError(code, message)

