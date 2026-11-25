from dataclasses import dataclass, replace
from enum import StrEnum
import re
import unicodedata

from pydantic import ValidationError

from app.modules.agents.implementation.contracts.enums import (
    ImplementationOutputCode,
)
from app.modules.agents.implementation.infrastructure.digests import (
    stable_json_sha256,
)
from app.modules.agents.implementation.preparation.readiness.trusted.constants import (
    EFFECTIVE_STACK,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)

from .file_catalog import GIT_SUMMARY_RESPONSIBILITY, STRUCTURAL_FILE_RULES
from .schemas import (
    ApprovedGenerationContext,
    GenerationPlan,
    GenerationPlanIdentity,
    GenerationPlanningFinding,
    GenerationPlanStatus,
    GenerationStatus,
    GenerationTraceabilityCoverage,
    PlannedFileCategory,
    PlannedFileEntry,
    PlannedNonFileDeliverable,
    PlanningEvidenceKind,
    PlanningFindingSeverity,
    RelativeOutputPath,
)


GENERATION_PLAN_POLICY_VERSION = "GEN-R1.2-1"


class GenerationPlanningErrorCode(StrEnum):
    INVALID_CONTEXT = "INVALID_CONTEXT"
    UNSUPPORTED_EFFECTIVE_STACK = "UNSUPPORTED_EFFECTIVE_STACK"
    UNAUTHORIZED_OUTPUT = "UNAUTHORIZED_OUTPUT"
    UNSAFE_OUTPUT_PATH = "UNSAFE_OUTPUT_PATH"
    DUPLICATE_FILE_ID = "DUPLICATE_FILE_ID"
    DUPLICATE_OUTPUT_PATH = "DUPLICATE_OUTPUT_PATH"
    CASE_INSENSITIVE_PATH_COLLISION = "CASE_INSENSITIVE_PATH_COLLISION"
    FILE_DIRECTORY_NAMESPACE_COLLISION = "FILE_DIRECTORY_NAMESPACE_COLLISION"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    SELF_DEPENDENCY = "SELF_DEPENDENCY"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    UNKNOWN_TRACEABILITY_REFERENCE = "UNKNOWN_TRACEABILITY_REFERENCE"
    MISSING_OUTPUT_COVERAGE = "MISSING_OUTPUT_COVERAGE"
    INVALID_GENERATION_ORDER = "INVALID_GENERATION_ORDER"
    INVALID_PLAN_COVERAGE = "INVALID_PLAN_COVERAGE"
    INVALID_PLAN_STATE = "INVALID_PLAN_STATE"
    INVALID_PLAN_IDENTITY = "INVALID_PLAN_IDENTITY"
    INVALID_PLAN_FINGERPRINT = "INVALID_PLAN_FINGERPRINT"


class GenerationPlanningError(ValueError):
    def __init__(self, code: GenerationPlanningErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class _FileDraft:
    relative_path: str
    responsibility: str
    output_codes: tuple[ImplementationOutputCode, ...]
    dependency_paths: tuple[str, ...]
    supporting_specification_item_ids: tuple[str, ...]
    file_category: PlannedFileCategory
    evidence_kind: PlanningEvidenceKind


class GenerationPlanValidator:
    """Validates file graphs and complete deterministic generation plans."""

    @classmethod
    def validate_files(
        cls,
        files: tuple[PlannedFileEntry, ...],
        approved_outputs: tuple[ImplementationOutputCode, ...],
        specification_item_ids: set[str],
    ) -> tuple[str, ...]:
        approved = set(approved_outputs)
        identities = [item.planned_file_id for item in files]
        if len(identities) != len(set(identities)):
            cls._fail(
                GenerationPlanningErrorCode.DUPLICATE_FILE_ID,
                "The generation plan contains duplicate file identities",
            )

        paths = [item.relative_output_path.root for item in files]
        if len(paths) != len(set(paths)):
            cls._fail(
                GenerationPlanningErrorCode.DUPLICATE_OUTPUT_PATH,
                "The generation plan contains duplicate output paths",
            )
        folded = [path.casefold() for path in paths]
        if len(folded) != len(set(folded)):
            cls._fail(
                GenerationPlanningErrorCode.CASE_INSENSITIVE_PATH_COLLISION,
                "The generation plan contains case-insensitive path collisions",
            )
        cls._validate_namespace(paths)

        by_id = {item.planned_file_id: item for item in files}
        for item in files:
            if not set(item.output_codes).issubset(approved):
                cls._fail(
                    GenerationPlanningErrorCode.UNAUTHORIZED_OUTPUT,
                    "A planned file references an unapproved output",
                )
            if item.planned_file_id in item.dependency_file_ids:
                cls._fail(
                    GenerationPlanningErrorCode.SELF_DEPENDENCY,
                    "A planned file cannot depend on itself",
                )
            if not set(item.dependency_file_ids).issubset(by_id):
                cls._fail(
                    GenerationPlanningErrorCode.MISSING_DEPENDENCY,
                    "A planned file references a missing dependency",
                )
            if not set(item.supporting_specification_item_ids).issubset(
                specification_item_ids
            ):
                cls._fail(
                    GenerationPlanningErrorCode.UNKNOWN_TRACEABILITY_REFERENCE,
                    "A planned file references unknown specification evidence",
                )
        return cls._topological_order(by_id)

    @classmethod
    def validate_plan(
        cls,
        plan: GenerationPlan,
        context: ApprovedGenerationContext,
    ) -> None:
        if plan.approved_output_codes != context.selected_outputs:
            cls._fail(
                GenerationPlanningErrorCode.UNAUTHORIZED_OUTPUT,
                "The generation plan outputs do not match the approved context",
            )
        if plan.effective_stack != context.effective_implementation_stack:
            cls._fail(
                GenerationPlanningErrorCode.UNSUPPORTED_EFFECTIVE_STACK,
                "The generation plan stack does not match the approved context",
            )
        specification_ids = _specification_items(context)
        order = cls.validate_files(
            plan.planned_files,
            plan.approved_output_codes,
            set(specification_ids),
        )
        if plan.generation_order != order or any(
            item.generation_order != order.index(item.planned_file_id) + 1
            for item in plan.planned_files
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_GENERATION_ORDER,
                "The generation order does not respect file dependencies",
            )
        if any(
            item.status is not GenerationStatus.NOT_STARTED
            for item in (*plan.planned_files, *plan.non_file_deliverables)
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_STATE,
                "A generation plan cannot claim that planned work has started",
            )
        if any(
            item.planned_file_id
            != _planned_file_id(plan.identity.generation_plan_id, item)
            for item in plan.planned_files
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_IDENTITY,
                "A planned file identity is inconsistent",
            )
        if any(
            item.output_code not in plan.approved_output_codes
            for item in plan.non_file_deliverables
        ) or any(
            finding.output_code is not None
            and finding.output_code not in plan.approved_output_codes
            for finding in plan.validation_findings
        ):
            cls._fail(
                GenerationPlanningErrorCode.UNAUTHORIZED_OUTPUT,
                "Plan metadata references an unapproved output",
            )
        if len({item.deliverable_id for item in plan.non_file_deliverables}) != len(
            plan.non_file_deliverables
        ) or any(
            item.deliverable_id
            != _non_file_deliverable_id(
                plan.identity.generation_plan_id, item.output_code
            )
            for item in plan.non_file_deliverables
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_IDENTITY,
                "A non-file deliverable identity is inconsistent",
            )
        represented = {
            output for item in plan.planned_files for output in item.output_codes
        } | {item.output_code for item in plan.non_file_deliverables}
        if represented != set(plan.approved_output_codes):
            cls._fail(
                GenerationPlanningErrorCode.MISSING_OUTPUT_COVERAGE,
                "The generation plan does not represent every approved output",
            )
        expected_coverage = DeterministicGenerationPlanner._coverage(
            context,
            plan.planned_files,
            plan.non_file_deliverables,
            plan.validation_findings,
        )
        expected_status = DeterministicGenerationPlanner._status(
            plan.validation_findings
        )
        if (
            plan.traceability_coverage != expected_coverage
            or plan.status is not expected_status
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_COVERAGE,
                "The generation plan coverage or status is inconsistent",
            )
        expected_source = _source_snapshot_fingerprint(context)
        expected_identity = _plan_identity(
            context, plan.plan_policy_version, expected_source
        )
        if (
            plan.source_snapshot_fingerprint != expected_source
            or plan.identity != expected_identity
        ):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_IDENTITY,
                "The generation plan identity is inconsistent",
            )
        if plan.plan_fingerprint != _plan_fingerprint(plan):
            cls._fail(
                GenerationPlanningErrorCode.INVALID_PLAN_FINGERPRINT,
                "The generation plan fingerprint is inconsistent",
            )

    @staticmethod
    def _validate_namespace(paths: list[str]) -> None:
        parts = {path: tuple(path.casefold().split("/")) for path in paths}
        for left, left_parts in parts.items():
            for right, right_parts in parts.items():
                if left == right:
                    continue
                shorter = min(len(left_parts), len(right_parts))
                if left_parts[:shorter] == right_parts[:shorter]:
                    GenerationPlanValidator._fail(
                        GenerationPlanningErrorCode.FILE_DIRECTORY_NAMESPACE_COLLISION,
                        "A planned file collides with a planned directory namespace",
                    )

    @classmethod
    def _topological_order(cls, by_id: dict[str, PlannedFileEntry]) -> tuple[str, ...]:
        remaining = {key: set(value.dependency_file_ids) for key, value in by_id.items()}
        result = []
        while remaining:
            available = sorted(
                (key for key, dependencies in remaining.items() if not dependencies),
                key=lambda key: by_id[key].relative_output_path.root.casefold(),
            )
            if not available:
                cls._fail(
                    GenerationPlanningErrorCode.DEPENDENCY_CYCLE,
                    "The planned file dependency graph contains a cycle",
                )
            for key in available:
                result.append(key)
                remaining.pop(key)
            for dependencies in remaining.values():
                dependencies.difference_update(available)
        return tuple(result)

    @staticmethod
    def _fail(code, message):
        raise GenerationPlanningError(code, message)


class DeterministicGenerationPlanner:
    """Builds a validated plan without model calls, persistence, or file I/O."""

    def __init__(self, policy_version: str = GENERATION_PLAN_POLICY_VERSION) -> None:
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,50}", policy_version):
            raise ValueError("Invalid generation planning policy version")
        self.policy_version = policy_version

    def plan(self, context: ApprovedGenerationContext) -> GenerationPlan:
        if not isinstance(context, ApprovedGenerationContext):
            raise GenerationPlanningError(
                GenerationPlanningErrorCode.INVALID_CONTEXT,
                "A validated approved generation context is required",
            )
        if context.effective_implementation_stack.model_dump() != EFFECTIVE_STACK:
            raise GenerationPlanningError(
                GenerationPlanningErrorCode.UNSUPPORTED_EFFECTIVE_STACK,
                "The approved effective stack is not supported by this planning policy",
            )

        source_fingerprint = _source_snapshot_fingerprint(context)
        identity = _plan_identity(context, self.policy_version, source_fingerprint)
        drafts, findings = self._drafts(context)
        entries = self._entries(drafts, identity.generation_plan_id)
        specification_ids = set(_specification_items(context))
        order = GenerationPlanValidator.validate_files(
            entries, context.selected_outputs, specification_ids
        )
        positions = {file_id: index + 1 for index, file_id in enumerate(order)}
        entries = tuple(
            item.model_copy(
                update={"generation_order": positions[item.planned_file_id]}
            )
            for item in entries
        )
        non_files = self._non_file_deliverables(context, identity.generation_plan_id)
        coverage = self._coverage(context, entries, non_files, findings)
        status = self._status(findings)
        plan = GenerationPlan(
            identity=identity,
            plan_policy_version=self.policy_version,
            approved_output_codes=context.selected_outputs,
            effective_stack=context.effective_implementation_stack,
            planned_files=entries,
            non_file_deliverables=non_files,
            generation_order=order,
            traceability_coverage=coverage,
            validation_findings=findings,
            source_snapshot_fingerprint=source_fingerprint,
            plan_fingerprint="0" * 64,
            status=status,
        )
        plan = plan.model_copy(update={"plan_fingerprint": _plan_fingerprint(plan)})
        GenerationPlanValidator.validate_plan(plan, context)
        return plan

    def _drafts(self, context):
        selected = set(context.selected_outputs)
        drafts = []
        for rule in STRUCTURAL_FILE_RULES:
            outputs = tuple(
                sorted(selected & rule.output_triggers, key=lambda item: item.value)
            )
            if not outputs:
                continue
            drafts.append(
                _FileDraft(
                    relative_path=rule.relative_path,
                    responsibility=rule.responsibility,
                    output_codes=outputs,
                    dependency_paths=rule.dependency_paths,
                    supporting_specification_item_ids=(),
                    file_category=rule.file_category,
                    evidence_kind=PlanningEvidenceKind.STRUCTURAL,
                )
            )

        api_drafts = self._api_drafts(context, selected)
        page_drafts = self._page_drafts(context, selected)
        drafts.extend(api_drafts)
        drafts.extend(page_drafts)
        drafts = self._add_dynamic_dependencies(drafts, api_drafts, page_drafts)
        drafts = self._attach_database_evidence(context, drafts)
        findings = self._findings(context, api_drafts, page_drafts)
        return tuple(sorted(drafts, key=lambda item: item.relative_path.casefold())), findings

    @staticmethod
    def _api_drafts(context, selected):
        outputs = tuple(
            item
            for item in (
                ImplementationOutputCode.BACKEND_CODE,
                ImplementationOutputCode.API_IMPLEMENTATION,
            )
            if item in selected
        )
        if not outputs:
            return []
        grouped = {}
        for item in _category_items(context, ArtifactDetectionLabel.API_SPECIFICATION):
            resource = _api_resource(item.data.get("path"))
            if resource:
                grouped.setdefault(resource, []).append(item.project_item_id)
        return [
            _FileDraft(
                relative_path=f"backend/src/routes/{resource}.routes.js",
                responsibility=(
                    f"Implement only the verified REST endpoints for resource "
                    f"'{resource}'."
                ),
                output_codes=outputs,
                dependency_paths=("backend/package.json",),
                supporting_specification_item_ids=tuple(sorted(set(refs))),
                file_category=PlannedFileCategory.API,
                evidence_kind=PlanningEvidenceKind.TRUSTED_SPECIFICATION,
            )
            for resource, refs in sorted(grouped.items())
        ]

    @staticmethod
    def _page_drafts(context, selected):
        if ImplementationOutputCode.FRONTEND_CODE not in selected:
            return []
        grouped = {}
        for item in _category_items(context, ArtifactDetectionLabel.UI_FLOW):
            name = item.data.get("name")
            slug = _safe_slug(name) if isinstance(name, str) else None
            if slug:
                grouped.setdefault(slug, []).append(item.project_item_id)
        return [
            _FileDraft(
                relative_path=f"frontend/src/pages/{slug}-page.jsx",
                responsibility=f"Represent only the verified '{slug}' UI flow.",
                output_codes=(ImplementationOutputCode.FRONTEND_CODE,),
                dependency_paths=("frontend/package.json",),
                supporting_specification_item_ids=tuple(sorted(set(refs))),
                file_category=PlannedFileCategory.FRONTEND,
                evidence_kind=PlanningEvidenceKind.TRUSTED_SPECIFICATION,
            )
            for slug, refs in sorted(grouped.items())
        ]

    @staticmethod
    def _add_dynamic_dependencies(drafts, api_drafts, page_drafts):
        paths = {item.relative_path for item in drafts}
        result = []
        for item in drafts:
            dependencies = list(item.dependency_paths)
            if item.relative_path == "backend/src/app.js":
                dependencies.extend(draft.relative_path for draft in api_drafts)
            elif item.relative_path == "frontend/src/App.jsx":
                dependencies.extend(draft.relative_path for draft in page_drafts)
            elif item.relative_path == "docker-compose.yml":
                dependencies.extend(
                    path
                    for path in (
                        "frontend/package.json",
                        "backend/package.json",
                        "database/schema.sql",
                    )
                    if path in paths
                )
            result.append(
                replace(
                    item,
                    dependency_paths=tuple(
                        sorted(set(dependencies), key=str.casefold)
                    ),
                )
            )
        return result

    @staticmethod
    def _attach_database_evidence(context, drafts):
        database_ids = tuple(
            sorted(
                item.project_item_id
                for item in _category_items(
                    context, ArtifactDetectionLabel.DATABASE_SCHEMA
                )
                if item.data.get("name")
            )
        )
        result = []
        for item in drafts:
            if item.relative_path == "database/schema.sql" and database_ids:
                entities = sorted(
                    {
                        str(spec_item.data["name"])
                        for spec_item in _category_items(
                            context, ArtifactDetectionLabel.DATABASE_SCHEMA
                        )
                        if spec_item.data.get("name")
                    },
                    key=str.casefold,
                )
                item = replace(
                    item,
                    responsibility=(
                        "Define only the verified MySQL entities: "
                        + ", ".join(entities)
                        + "."
                    ),
                    supporting_specification_item_ids=database_ids,
                    evidence_kind=PlanningEvidenceKind.TRUSTED_SPECIFICATION,
                )
            result.append(item)
        return result

    @staticmethod
    def _findings(context, api_drafts, page_drafts):
        selected = set(context.selected_outputs)
        findings = []
        if (
            ImplementationOutputCode.API_IMPLEMENTATION in selected
            and not api_drafts
        ):
            findings.append(
                _finding(
                    "API_DETAIL_REQUIRED",
                    PlanningFindingSeverity.BLOCKER,
                    "No trusted API path can support an API route plan.",
                    ImplementationOutputCode.API_IMPLEMENTATION,
                )
            )
        if (
            ImplementationOutputCode.DATABASE_IMPLEMENTATION in selected
            and not any(
                item.data.get("name")
                for item in _category_items(
                    context, ArtifactDetectionLabel.DATABASE_SCHEMA
                )
            )
        ):
            findings.append(
                _finding(
                    "DATABASE_DETAIL_REQUIRED",
                    PlanningFindingSeverity.BLOCKER,
                    "No trusted database entity can support the SQL schema plan.",
                    ImplementationOutputCode.DATABASE_IMPLEMENTATION,
                )
            )
        if ImplementationOutputCode.FRONTEND_CODE in selected and not page_drafts:
            findings.append(
                _finding(
                    "NAMED_UI_FLOW_NOT_AVAILABLE",
                    PlanningFindingSeverity.WARNING,
                    "No named trusted UI flow is available for a domain page plan.",
                    ImplementationOutputCode.FRONTEND_CODE,
                )
            )
        if (
            ImplementationOutputCode.BACKEND_CODE in selected
            and not api_drafts
        ):
            findings.append(
                _finding(
                    "BACKEND_DOMAIN_MODULE_NOT_DERIVED",
                    PlanningFindingSeverity.WARNING,
                    "No explicit trusted API path is available for a backend domain module.",
                    ImplementationOutputCode.BACKEND_CODE,
                )
            )
        if (
            ImplementationOutputCode.CONTAINER_CONFIGURATION in selected
            and not selected.intersection(
                {
                    ImplementationOutputCode.FRONTEND_CODE,
                    ImplementationOutputCode.BACKEND_CODE,
                    ImplementationOutputCode.DATABASE_IMPLEMENTATION,
                    ImplementationOutputCode.API_IMPLEMENTATION,
                }
            )
        ):
            findings.append(
                _finding(
                    "CONTAINER_TARGETS_NOT_SELECTED",
                    PlanningFindingSeverity.WARNING,
                    "Container configuration has no selected implementation target.",
                    ImplementationOutputCode.CONTAINER_CONFIGURATION,
                )
            )
        return tuple(sorted(findings, key=lambda item: item.code))

    @staticmethod
    def _entries(drafts, plan_id):
        ids_by_path = {
            draft.relative_path: _planned_file_id(plan_id, draft)
            for draft in drafts
        }
        entries = []
        for draft in drafts:
            try:
                path = RelativeOutputPath(draft.relative_path)
            except ValidationError as exc:
                raise GenerationPlanningError(
                    GenerationPlanningErrorCode.UNSAFE_OUTPUT_PATH,
                    "The planning policy produced an unsafe output path",
                ) from exc
            missing_paths = set(draft.dependency_paths).difference(ids_by_path)
            if missing_paths:
                raise GenerationPlanningError(
                    GenerationPlanningErrorCode.MISSING_DEPENDENCY,
                    "The planning policy produced a missing file dependency",
                )
            entries.append(
                PlannedFileEntry(
                    planned_file_id=ids_by_path[draft.relative_path],
                    relative_output_path=path,
                    responsibility=draft.responsibility,
                    output_codes=draft.output_codes,
                    dependency_file_ids=tuple(
                        ids_by_path[path] for path in draft.dependency_paths
                    ),
                    supporting_specification_item_ids=(
                        draft.supporting_specification_item_ids
                    ),
                    file_category=draft.file_category,
                    evidence_kind=draft.evidence_kind,
                    generation_order=1,
                    status=GenerationStatus.NOT_STARTED,
                )
            )
        return tuple(entries)

    @staticmethod
    def _non_file_deliverables(context, plan_id):
        if ImplementationOutputCode.GIT_SUMMARY not in context.selected_outputs:
            return ()
        return (
            PlannedNonFileDeliverable(
                deliverable_id=_non_file_deliverable_id(
                    plan_id, ImplementationOutputCode.GIT_SUMMARY
                ),
                output_code=ImplementationOutputCode.GIT_SUMMARY,
                responsibility=GIT_SUMMARY_RESPONSIBILITY,
            ),
        )

    @staticmethod
    def _coverage(context, files, non_files, findings):
        all_ids = set(_specification_items(context))
        referenced = {
            ref for item in files for ref in item.supporting_specification_item_ids
        }
        represented = {
            output for item in files for output in item.output_codes
        } | {item.output_code for item in non_files}
        return GenerationTraceabilityCoverage(
            approved_outputs=context.selected_outputs,
            represented_outputs=tuple(
                item for item in context.selected_outputs if item in represented
            ),
            referenced_specification_item_ids=tuple(sorted(referenced)),
            unmapped_specification_item_ids=tuple(sorted(all_ids - referenced)),
            structural_file_ids=tuple(
                item.planned_file_id
                for item in files
                if item.evidence_kind is PlanningEvidenceKind.STRUCTURAL
            ),
            domain_file_ids=tuple(
                item.planned_file_id
                for item in files
                if item.evidence_kind is PlanningEvidenceKind.TRUSTED_SPECIFICATION
            ),
            planning_blocker_codes=tuple(
                item.code
                for item in findings
                if item.severity is PlanningFindingSeverity.BLOCKER
            ),
            planning_warning_codes=tuple(
                item.code
                for item in findings
                if item.severity is PlanningFindingSeverity.WARNING
            ),
        )

    @staticmethod
    def _status(findings):
        if any(item.severity is PlanningFindingSeverity.BLOCKER for item in findings):
            return GenerationPlanStatus.BLOCKED
        if findings:
            return GenerationPlanStatus.READY_WITH_WARNINGS
        return GenerationPlanStatus.READY


def _category_items(context, category):
    return tuple(context.trusted_project_specification.categories.get(category, ()))


def _specification_items(context):
    return {
        item.project_item_id: item
        for items in context.trusted_project_specification.categories.values()
        for item in items
    }


def _safe_slug(value):
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return slug[:80].rstrip("-") or None


def _api_resource(path):
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    segments = [
        _safe_slug(segment)
        for segment in path.split("/")
        if segment and not segment.startswith(("{", ":"))
    ]
    segments = [
        segment
        for segment in segments
        if segment and segment != "api" and not re.fullmatch(r"v\d+", segment)
    ]
    return segments[0] if segments else None


def _finding(code, severity, message, output):
    return GenerationPlanningFinding(
        code=code, severity=severity, message=message, output_code=output
    )


def _planned_file_id(plan_id, item):
    relative_path = (
        item.relative_output_path.root
        if isinstance(item, PlannedFileEntry)
        else item.relative_path
    )
    return "GPF-" + stable_json_sha256(
        {
            "plan_id": plan_id,
            "path": relative_path,
            "responsibility": item.responsibility,
            "outputs": [output.value for output in item.output_codes],
            "references": item.supporting_specification_item_ids,
            "category": item.file_category,
            "evidence_kind": item.evidence_kind,
        }
    )[:32]


def _non_file_deliverable_id(plan_id, output_code):
    return "GPD-" + stable_json_sha256([plan_id, output_code])[:32]


def _source_snapshot_fingerprint(context):
    specification = context.trusted_project_specification
    return stable_json_sha256(
        {
            "run_id": context.run_id,
            "project_id": context.agent_project_id,
            "snapshot_schema_version": context.snapshot_schema_version,
            "project_specification_id": specification.project_specification_id,
            "source_set_digest": context.project_specification_source_set_digest,
            "decision_digest": context.project_specification_decision_digest,
            "readiness_fingerprint": context.readiness_fingerprint,
            "selected_outputs_digest": context.selected_outputs_digest,
            "approval_fingerprint": context.approval_fingerprint,
            "effective_stack": context.effective_implementation_stack.model_dump(),
            "stack_adaptation_fingerprint": (
                context.stack_adaptation_decision.fingerprint
                if context.stack_adaptation_decision
                else None
            ),
        }
    )


def _plan_identity(context, policy_version, source_fingerprint):
    return GenerationPlanIdentity(
        generation_plan_id="GPL-"
        + stable_json_sha256([policy_version, source_fingerprint])[:32],
        agent_project_id=context.agent_project_id,
        run_id=context.run_id,
    )


def _plan_fingerprint(plan):
    return stable_json_sha256(
        plan.model_dump(mode="json", exclude={"plan_fingerprint"})
    )
