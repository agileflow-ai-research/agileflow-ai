import hashlib
import json
from collections import defaultdict

from app.modules.agents.implementation.preparation.readiness.constants import (
    BEHAVIOR_ARTIFACTS,
    DESIGN_ARTIFACTS,
    EFFECTIVE_STACK,
    IMPLEMENTATION_ARTIFACTS,
    REQUIREMENTS_ARTIFACTS,
    TEST_ARTIFACTS,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
    HumanResolutionDecision,
    NormalizedArtifact,
    ReadinessFinding,
    SourceReference,
)
from app.modules.agents.implementation.preparation.readiness.stack_detector import (
    StackDeclaration,
)
from app.modules.agents.implementation.contracts.schemas import (
    ImplementationArtifactType as Artifact,
    ImplementationOutputCode as Output,
    UploadedFileMetadata,
)


EXECUTABLE_OUTPUTS = frozenset(
    {
        Output.FRONTEND_CODE,
        Output.BACKEND_CODE,
        Output.DATABASE_IMPLEMENTATION,
        Output.API_IMPLEMENTATION,
    }
)


def source_reference(artifact: NormalizedArtifact) -> SourceReference:
    return SourceReference(
        source_id=artifact.source_id,
        source_type=artifact.source_type,
        artifact_type=artifact.artifact_type,
        label=artifact.label,
        original_filename=artifact.provenance.original_filename,
    )


def upload_reference(metadata: UploadedFileMetadata) -> SourceReference:
    return SourceReference(
        source_id=metadata.upload_id,
        source_type=metadata.source_type,
        artifact_type=metadata.artifact_type,
        label=metadata.label,
        original_filename=metadata.original_filename,
    )


def make_finding(
    fingerprint: str,
    code: str,
    severity: FindingSeverity,
    title: str,
    message: str,
    *,
    affected_outputs: list[Output] | None = None,
    sources: list[SourceReference] | None = None,
    requires_human_decision: bool = False,
    category: str | None = None,
    provided_value: str | None = None,
    supported_value: str | None = None,
) -> ReadinessFinding:
    identity = {
        "fingerprint": fingerprint,
        "code": code,
        "outputs": sorted(item.value for item in (affected_outputs or [])),
        "sources": sorted(item.source_id for item in (sources or [])),
        "category": category,
        "provided": provided_value,
    }
    finding_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return ReadinessFinding(
        finding_id=f"RF-{finding_hash}",
        code=code,
        severity=severity,
        title=title,
        message=message,
        affected_outputs=affected_outputs or [],
        sources=sources or [],
        requires_human_decision=requires_human_decision,
        allowed_resolutions=(
            [HumanResolutionDecision.ADAPT_TO_SUPPORTED_STACK]
            if requires_human_decision
            else []
        ),
        category=category,
        provided_value=provided_value,
        supported_value=supported_value,
    )


def evaluate_rules(
    *,
    fingerprint: str,
    artifacts: list[NormalizedArtifact],
    images: list[UploadedFileMetadata],
    selected_outputs: list[Output],
    repository_bound: bool,
    declarations: list[StackDeclaration],
) -> list[ReadinessFinding]:
    findings: list[ReadinessFinding] = []
    artifact_types = {item.artifact_type for item in artifacts}
    outputs = set(selected_outputs)

    if not selected_outputs:
        findings.append(make_finding(
            fingerprint, "NO_OUTPUT_SELECTED", FindingSeverity.ERROR,
            "No implementation output selected",
            "Select at least one Agent 3 output before implementation can continue.",
        ))
    if not artifacts:
        findings.append(make_finding(
            fingerprint, "NO_IMPLEMENTATION_CONTEXT", FindingSeverity.ERROR,
            "No usable implementation context",
            "Add manual text or a successfully or partially extracted document. Images are not understood yet.",
            affected_outputs=selected_outputs,
        ))
    if not artifact_types & BEHAVIOR_ARTIFACTS:
        findings.append(make_finding(
            fingerprint, "IMPLEMENTATION_BEHAVIOR_MISSING", FindingSeverity.ERROR,
            "Implementation behavior is missing",
            "Provide an SRS, functional requirements, user stories, acceptance criteria, implementation tasks, or product backlog.",
            affected_outputs=selected_outputs,
        ))

    if Output.PROJECT_STRUCTURE in outputs and not artifact_types & {
        Artifact.TECHNOLOGY_STACK, Artifact.TECHNICAL_CONSTRAINTS
    }:
        findings.append(make_finding(
            fingerprint, "PROJECT_STRUCTURE_TECHNICAL_CONTEXT_LIMITED",
            FindingSeverity.WARNING, "Project structure technical context is limited",
            "No technology stack or technical constraints were supplied; frozen PP1 defaults will be used.",
            affected_outputs=[Output.PROJECT_STRUCTURE],
        ))

    frontend_required = {
        Artifact.SRS, Artifact.FUNCTIONAL_REQUIREMENTS,
        Artifact.USER_STORIES, Artifact.ACCEPTANCE_CRITERIA,
    }
    if Output.FRONTEND_CODE in outputs:
        if not artifact_types & frontend_required:
            findings.append(make_finding(
                fingerprint, "FRONTEND_IMPLEMENTATION_CONTEXT_REQUIRED",
                FindingSeverity.ERROR, "Frontend behavior context is required",
                "FRONTEND_CODE requires an SRS, functional requirements, user stories, or acceptance criteria.",
                affected_outputs=[Output.FRONTEND_CODE],
            ))
        if not artifact_types & {Artifact.UI_FLOW, Artifact.UI_WIREFRAMES}:
            findings.append(make_finding(
                fingerprint, "FRONTEND_UI_CONTEXT_LIMITED", FindingSeverity.WARNING,
                "Frontend UI context is limited",
                "No usable UI flow or interpreted UI wireframe is available.",
                affected_outputs=[Output.FRONTEND_CODE],
            ))

    backend_required = {
        Artifact.SRS, Artifact.FUNCTIONAL_REQUIREMENTS,
        Artifact.USER_STORIES, Artifact.API_SPECIFICATION,
    }
    if Output.BACKEND_CODE in outputs:
        if not artifact_types & backend_required:
            findings.append(make_finding(
                fingerprint, "BACKEND_IMPLEMENTATION_CONTEXT_REQUIRED",
                FindingSeverity.ERROR, "Backend behavior context is required",
                "BACKEND_CODE requires an SRS, functional requirements, user stories, or API specification.",
                affected_outputs=[Output.BACKEND_CODE],
            ))
        if Artifact.API_SPECIFICATION not in artifact_types:
            findings.append(make_finding(
                fingerprint, "BACKEND_API_CONTEXT_LIMITED", FindingSeverity.WARNING,
                "Backend API context is limited",
                "No API specification was supplied for BACKEND_CODE.",
                affected_outputs=[Output.BACKEND_CODE],
            ))

    if (
        Output.DATABASE_IMPLEMENTATION in outputs
        and Artifact.DATABASE_SCHEMA not in artifact_types
    ):
        findings.append(make_finding(
            fingerprint, "DATABASE_SCHEMA_REQUIRED", FindingSeverity.ERROR,
            "Database schema is required",
            "DATABASE_IMPLEMENTATION was selected but no usable database schema was supplied.",
            affected_outputs=[Output.DATABASE_IMPLEMENTATION],
        ))
    if (
        Output.API_IMPLEMENTATION in outputs
        and Artifact.API_SPECIFICATION not in artifact_types
    ):
        findings.append(make_finding(
            fingerprint, "API_SPECIFICATION_REQUIRED", FindingSeverity.ERROR,
            "API specification is required",
            "API_IMPLEMENTATION was selected but no usable API specification was supplied.",
            affected_outputs=[Output.API_IMPLEMENTATION],
        ))
    if Output.CONTAINER_CONFIGURATION in outputs and not artifact_types & {
        Artifact.TECHNICAL_CONSTRAINTS, Artifact.TECHNOLOGY_STACK
    }:
        findings.append(make_finding(
            fingerprint, "CONTAINER_CONTEXT_DEFAULTS_REQUIRED",
            FindingSeverity.WARNING, "Container defaults will be required",
            "No deployment, container, or technical constraints were supplied.",
            affected_outputs=[Output.CONTAINER_CONFIGURATION],
        ))
    if Output.GIT_SUMMARY in outputs and not repository_bound:
        findings.append(make_finding(
            fingerprint, "GITHUB_REPOSITORY_REQUIRED", FindingSeverity.ERROR,
            "GitHub repository is required",
            "GIT_SUMMARY requires a repository binding for this Agent 3 project. No commits are implied.",
            affected_outputs=[Output.GIT_SUMMARY],
        ))

    if outputs & EXECUTABLE_OUTPUTS and Artifact.ACCEPTANCE_CRITERIA not in artifact_types:
        findings.append(make_finding(
            fingerprint, "ACCEPTANCE_CRITERIA_MISSING", FindingSeverity.WARNING,
            "Acceptance criteria are missing",
            "Implementation can proceed, but expected behavior is less precisely verifiable.",
            affected_outputs=sorted(outputs & EXECUTABLE_OUTPUTS, key=lambda item: item.value),
        ))
    if not artifact_types & TEST_ARTIFACTS:
        findings.append(make_finding(
            fingerprint, "PRECODE_TEST_CONTEXT_MISSING", FindingSeverity.WARNING,
            "Pre-code test context is missing",
            "No pre-code test artifacts were supplied. They are recommended but optional in standalone PP1.",
            affected_outputs=selected_outputs,
        ))
    if outputs & EXECUTABLE_OUTPUTS and Artifact.NON_FUNCTIONAL_REQUIREMENTS not in artifact_types:
        findings.append(make_finding(
            fingerprint, "NON_FUNCTIONAL_CONTEXT_MISSING", FindingSeverity.INFO,
            "Non-functional context is missing",
            "No non-functional requirements were supplied.",
            affected_outputs=sorted(outputs & EXECUTABLE_OUTPUTS, key=lambda item: item.value),
        ))

    if images:
        image_sources = [upload_reference(item) for item in images]
        findings.append(make_finding(
            fingerprint, "VISUAL_CONTEXT_PENDING", FindingSeverity.INFO,
            "Visual context is pending",
            "Visual input is attached but has not yet been interpreted. Image understanding is a later Agent 3 input-preparation stage.",
            affected_outputs=selected_outputs,
            sources=image_sources,
        ))
        if Output.FRONTEND_CODE in outputs and any(
            item.artifact_type is Artifact.UI_WIREFRAMES for item in images
        ) and Artifact.UI_WIREFRAMES not in artifact_types:
            findings.append(make_finding(
                fingerprint, "UI_WIREFRAME_ANALYSIS_PENDING",
                FindingSeverity.WARNING, "UI wireframe analysis is pending",
                "A UI wireframe image is attached but cannot count as understood frontend context yet.",
                affected_outputs=[Output.FRONTEND_CODE],
                sources=[
                    upload_reference(item) for item in images
                    if item.artifact_type is Artifact.UI_WIREFRAMES
                ],
            ))

    findings.extend(_stack_findings(fingerprint, declarations, selected_outputs))
    if not declarations:
        findings.append(make_finding(
            fingerprint, "PROTOTYPE_STACK_DEFAULT_APPLIED", FindingSeverity.INFO,
            "Prototype stack defaults applied",
            "No explicit technology declaration was supplied; Agent 3 will use the frozen PP1 stack.",
            affected_outputs=selected_outputs,
        ))
    return findings


def _stack_findings(
    fingerprint: str,
    declarations: list[StackDeclaration],
    outputs: list[Output],
) -> list[ReadinessFinding]:
    findings: list[ReadinessFinding] = []
    for declaration in declarations:
        if declaration.supported is not False:
            continue
        findings.append(make_finding(
            fingerprint, "UNSUPPORTED_PROTOTYPE_TECHNOLOGY", FindingSeverity.ERROR,
            "Unsupported prototype technology",
            f"Provided {declaration.category}: {declaration.provided_value}. The PP1 target is {EFFECTIVE_STACK[declaration.category]}.",
            affected_outputs=outputs,
            sources=[source_reference(declaration.artifact)],
            requires_human_decision=True,
            category=declaration.category,
            provided_value=declaration.provided_value,
            supported_value=EFFECTIVE_STACK[declaration.category],
        ))

    grouped: dict[str, list[StackDeclaration]] = defaultdict(list)
    for declaration in declarations:
        if declaration.canonical_value is not None:
            grouped[declaration.category].append(declaration)
    for category, category_declarations in grouped.items():
        source_values = {
            item.artifact.source_id: item.canonical_value
            for item in category_declarations
        }
        values = set(source_values.values())
        if len(values) < 2 or len(source_values) < 2:
            continue
        provided = " vs ".join(
            f"{item.artifact.source_id}: {item.provided_value}"
            for item in category_declarations
        )
        findings.append(make_finding(
            fingerprint, "CROSS_SOURCE_TECHNOLOGY_CONFLICT", FindingSeverity.ERROR,
            "Cross-source technology conflict",
            f"Usable sources explicitly declare conflicting {category} technologies: {provided}.",
            affected_outputs=outputs,
            sources=[source_reference(item.artifact) for item in category_declarations],
            requires_human_decision=True,
            category=category,
            provided_value=provided,
            supported_value=EFFECTIVE_STACK[category],
        ))
    return findings


def coverage(artifacts: list[NormalizedArtifact], images: list[UploadedFileMetadata]):
    types = {item.artifact_type for item in artifacts}
    return {
        "requirements": bool(types & REQUIREMENTS_ARTIFACTS),
        "design": bool(types & DESIGN_ARTIFACTS),
        "implementation": bool(types & IMPLEMENTATION_ARTIFACTS),
        "tests": bool(types & TEST_ARTIFACTS),
        "visual_context_pending": bool(images),
    }
