from collections.abc import Mapping

from .content_validator import GeneratedContentValidator
from .context_builder import FileGenerationContextBuilder
from .prompt_builder import LocalFileGenerationPromptBuilder
from .providers.base import CodeGenerationError, CodeGenerationProvider
from .schemas import (
    ApprovedGenerationContext,
    CodeGenerationErrorCode as ErrorCode,
    DependencyFingerprint,
    GeneratedContentCandidate,
    GenerationPlan,
    PlannedFileEntry,
)


class LocalCodeGenerationService:
    """Orchestrates one in-memory file candidate without persistence or execution."""

    def __init__(
        self,
        provider: CodeGenerationProvider,
        *,
        context_tokens: int,
        max_output_tokens: int,
        max_content_chars: int,
        max_retries: int = 1,
    ) -> None:
        if max_retries not in {0, 1}:
            raise ValueError("Code generation supports at most one correction retry")
        self._provider = provider
        self._context_builder = FileGenerationContextBuilder()
        self._prompt_builder = LocalFileGenerationPromptBuilder(
            context_tokens=context_tokens,
            max_output_tokens=max_output_tokens,
        )
        self._content_validator = GeneratedContentValidator(
            max_content_chars=max_content_chars
        )
        self._max_retries = max_retries

    def generate_file(
        self,
        approved_context: ApprovedGenerationContext,
        plan: GenerationPlan,
        planned_file: PlannedFileEntry,
        dependency_candidates: Mapping[str, GeneratedContentCandidate] | None = None,
    ) -> GeneratedContentCandidate:
        file_context = self._context_builder.build(
            approved_context,
            plan,
            planned_file,
            dependency_candidates,
        )
        attempts = 0
        provider_response = None
        while attempts <= self._max_retries:
            request = self._prompt_builder.build(
                file_context,
                correction_retry=attempts > 0,
            )
            attempts += 1
            try:
                provider_response = self._provider.generate_file(request)
                break
            except CodeGenerationError as exc:
                if (
                    exc.code
                    not in {
                        ErrorCode.INVALID_MODEL_RESPONSE,
                        ErrorCode.INVALID_RESPONSE_SCHEMA,
                    }
                    or attempts > self._max_retries
                ):
                    raise
        if provider_response is None:
            raise CodeGenerationError(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "The local model did not return a usable response",
            )

        metadata = provider_response.metadata
        if (
            metadata.context_tokens != request.context_tokens
            or metadata.max_output_tokens != request.max_output_tokens
            or metadata.temperature != 0
            or metadata.keep_alive != "0"
        ):
            raise CodeGenerationError(
                ErrorCode.INVALID_MODEL_RESPONSE,
                "Local model runtime metadata did not match the approved request",
            )
        validation = self._content_validator.validate(
            file_context, provider_response.result
        )
        return GeneratedContentCandidate(
            agent_project_id=file_context.agent_project_id,
            run_id=file_context.run_id,
            generation_plan_id=file_context.generation_plan_id,
            plan_fingerprint=file_context.plan_fingerprint,
            source_snapshot_fingerprint=file_context.source_snapshot_fingerprint,
            planned_file_id=file_context.planned_file_id,
            relative_output_path=file_context.relative_output_path,
            authorized_output_codes=file_context.authorized_output_codes,
            relevant_specification_item_ids=tuple(
                item.project_item_id
                for item in file_context.trusted_specification_items
            ),
            dependency_fingerprints=tuple(
                DependencyFingerprint(
                    planned_file_id=item.planned_file_id,
                    content_sha256=item.content_sha256,
                )
                for item in file_context.dependencies
            ),
            provider_type=metadata.provider_type,
            requested_model=metadata.requested_model,
            resolved_model=metadata.resolved_model,
            model_digest=metadata.model_digest,
            model_source=metadata.model_source,
            model_license=metadata.model_license,
            quantization_level=metadata.quantization_level,
            parameter_size=metadata.parameter_size,
            ollama_version=metadata.ollama_version,
            prompt_template_version=request.prompt_template_version,
            generation_policy_version=request.generation_policy_version,
            context_tokens=metadata.context_tokens,
            max_output_tokens=metadata.max_output_tokens,
            temperature=metadata.temperature,
            keep_alive=metadata.keep_alive,
            generated_content=validation.content,
            content_sha256=validation.content_sha256,
            validation_status=validation.status,
            syntax_validation_status=validation.syntax_status,
            validation_findings=validation.findings,
            missing_information=provider_response.result.missing_information,
            bounded_assumptions=provider_response.result.bounded_assumptions,
            diagnostics=provider_response.result.diagnostics,
            attempts=attempts,
            inference_duration_ms=metadata.total_duration_ms,
            prompt_token_count=metadata.prompt_token_count,
            generated_token_count=metadata.generated_token_count,
            safe_failure_code=validation.safe_failure_code,
        )

