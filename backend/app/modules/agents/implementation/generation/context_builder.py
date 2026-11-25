import hashlib
import json
from collections.abc import Mapping
from pathlib import PurePosixPath

from .planner import GenerationPlanValidator, GenerationPlanningError
from .providers.base import CodeGenerationError
from .schemas import (
    ApprovedGenerationContext,
    CodeGenerationErrorCode as ErrorCode,
    FileContentType,
    FileDependencyContext,
    FileGenerationContext,
    FileTrustedSpecificationItem,
    GeneratedCandidateStatus,
    GeneratedContentCandidate,
    GenerationPlan,
    GenerationPlanStatus,
    PlannedFileEntry,
)


_MISSING_INFORMATION_CONSTRAINTS = (
    "Report every essential missing fact; do not invent APIs, fields, imports, "
    "exports, or business behavior.",
    "If an essential fact is missing, return it in missing_information and do "
    "not present the content as complete.",
    "Bounded assumptions may cover formatting only and cannot create domain "
    "behavior or dependencies.",
)


class FileGenerationContextBuilder:
    """Selects only approved evidence for one deterministic planned file."""

    def build(
        self,
        approved_context: ApprovedGenerationContext,
        plan: GenerationPlan,
        planned_file: PlannedFileEntry,
        dependency_candidates: Mapping[str, GeneratedContentCandidate] | None = None,
    ) -> FileGenerationContext:
        if not isinstance(approved_context, ApprovedGenerationContext):
            self._fail(ErrorCode.INVALID_GENERATION_PLAN, "Approved context is invalid")
        try:
            GenerationPlanValidator.validate_plan(plan, approved_context)
        except GenerationPlanningError as exc:
            raise CodeGenerationError(
                ErrorCode.INVALID_GENERATION_PLAN,
                "The generation plan is invalid",
            ) from exc
        if plan.status is GenerationPlanStatus.BLOCKED:
            self._fail(
                ErrorCode.INVALID_GENERATION_PLAN,
                "A blocked generation plan cannot be used for inference",
            )
        plan_file = next(
            (
                item
                for item in plan.planned_files
                if item.planned_file_id == planned_file.planned_file_id
            ),
            None,
        )
        if plan_file is None or plan_file != planned_file:
            self._fail(
                ErrorCode.INVALID_GENERATION_PLAN,
                "The requested file is not the approved planned file",
            )
        if not set(planned_file.output_codes).issubset(approved_context.selected_outputs):
            self._fail(
                ErrorCode.INVALID_GENERATION_PLAN,
                "The requested file contains unauthorized outputs",
            )

        specification_items = {
            item.project_item_id: item
            for items in approved_context.trusted_project_specification.categories.values()
            for item in items
        }
        trusted_items = tuple(
            FileTrustedSpecificationItem(
                project_item_id=item_id,
                artifact_type=specification_items[item_id].artifact_type.value,
                identity_key=specification_items[item_id].identity_key,
                trusted_data_json=json.dumps(
                    specification_items[item_id].data,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
                source_artifact_ids=tuple(
                    sorted(set(specification_items[item_id].source_artifact_ids))
                ),
            )
            for item_id in planned_file.supporting_specification_item_ids
        )

        candidates = dependency_candidates or {}
        planned_by_id = {item.planned_file_id: item for item in plan.planned_files}
        dependencies = tuple(
            self._dependency_context(
                dependency_id,
                planned_by_id[dependency_id],
                candidates.get(dependency_id),
                approved_context,
                plan,
            )
            for dependency_id in planned_file.dependency_file_ids
        )
        return FileGenerationContext(
            agent_project_id=approved_context.agent_project_id,
            run_id=approved_context.run_id,
            generation_plan_id=plan.identity.generation_plan_id,
            plan_fingerprint=plan.plan_fingerprint,
            source_snapshot_fingerprint=plan.source_snapshot_fingerprint,
            planned_file_id=planned_file.planned_file_id,
            relative_output_path=planned_file.relative_output_path,
            responsibility=planned_file.responsibility,
            content_type=_content_type(planned_file.relative_output_path.root),
            authorized_output_codes=planned_file.output_codes,
            effective_stack=approved_context.effective_implementation_stack,
            trusted_specification_items=trusted_items,
            dependencies=dependencies,
            missing_information_constraints=_MISSING_INFORMATION_CONSTRAINTS,
            traceability_root_refs=(
                approved_context.traceability_root_refs
                if trusted_items
                else ()
            ),
        )

    def _dependency_context(
        self,
        dependency_id,
        planned_dependency,
        candidate,
        approved_context,
        plan,
    ) -> FileDependencyContext:
        if candidate is None:
            self._fail(
                ErrorCode.MISSING_DEPENDENCY_CONTEXT,
                "A required generated dependency is unavailable",
            )
        if (
            candidate.validation_status is not GeneratedCandidateStatus.VALIDATED
            or candidate.agent_project_id != approved_context.agent_project_id
            or candidate.run_id != approved_context.run_id
            or candidate.generation_plan_id != plan.identity.generation_plan_id
            or candidate.plan_fingerprint != plan.plan_fingerprint
            or candidate.source_snapshot_fingerprint
            != plan.source_snapshot_fingerprint
            or candidate.planned_file_id != dependency_id
            or candidate.relative_output_path != planned_dependency.relative_output_path
            or not candidate.generated_content
            or not candidate.content_sha256
            or hashlib.sha256(candidate.generated_content.encode("utf-8")).hexdigest()
            != candidate.content_sha256
        ):
            self._fail(
                ErrorCode.MISSING_DEPENDENCY_CONTEXT,
                "A required generated dependency failed validation",
            )
        return FileDependencyContext(
            planned_file_id=dependency_id,
            relative_output_path=planned_dependency.relative_output_path,
            responsibility=planned_dependency.responsibility,
            validated_content=candidate.generated_content,
            content_sha256=candidate.content_sha256,
        )

    @staticmethod
    def _fail(code: ErrorCode, message: str):
        raise CodeGenerationError(code, message)


def _content_type(relative_path: str) -> FileContentType:
    path = PurePosixPath(relative_path)
    if path.name == ".env.example":
        return FileContentType.ENV
    return {
        ".js": FileContentType.JAVASCRIPT,
        ".jsx": FileContentType.JSX,
        ".json": FileContentType.JSON,
        ".sql": FileContentType.SQL,
        ".html": FileContentType.HTML,
        ".css": FileContentType.CSS,
        ".md": FileContentType.MARKDOWN,
        ".yml": FileContentType.YAML,
        ".yaml": FileContentType.YAML,
        ".gitignore": FileContentType.TEXT,
    }.get(path.suffix.lower(), FileContentType.TEXT)

