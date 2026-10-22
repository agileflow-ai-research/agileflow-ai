import hashlib
import json
from datetime import datetime, timezone

from app.modules.agents.implementation.inputs.extraction.schemas import ExtractionStatus
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
    ExtractionNotFoundError,
)
from app.modules.agents.implementation.preparation.readiness.normalizer import (
    manifest_entry,
    normalize_document,
    normalize_text_input,
    text_manifest_entry,
)
from app.modules.agents.implementation.preparation.readiness.rules import (
    coverage,
    evaluate_rules,
    make_finding,
    upload_reference,
)
from app.modules.agents.implementation.preparation.readiness.schemas import (
    ArtifactManifestEntry,
    EffectivePrototypeStack,
    FindingSeverity,
    NormalizedArtifact,
    OutputReadiness,
    ReadinessEvaluationRequest,
    ReadinessEvaluationResult,
    ReadinessStatus,
    ReadinessSummary,
)
from app.modules.agents.implementation.preparation.readiness.stack_detector import detect_stack
from app.modules.agents.implementation.github.repository import (
    GitHubRepositoryBindingRepository,
)
from app.modules.agents.implementation.contracts.schemas import ImplementationInputSourceType
from app.modules.agents.implementation.inputs.upload.service import require_implementation_project
from app.modules.agents.implementation.infrastructure.storage import ImplementationUploadStorage
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService


class ReadinessResolutionError(ValueError):
    pass


class StaleReadinessResolutionError(ReadinessResolutionError):
    pass


class ReadinessUploadTypeError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImplementationReadinessService:
    def __init__(
        self,
        standalone_service: StandaloneService,
        storage: ImplementationUploadStorage,
        extraction_service: DocumentExtractionService,
        repository_bindings: GitHubRepositoryBindingRepository,
        *,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._storage = storage
        self._extractions = extraction_service
        self._repository_bindings = repository_bindings
        self._clock = clock

    def evaluate(
        self,
        agent_project_id: str,
        request: ReadinessEvaluationRequest,
        current_user: UserPublicResponse,
    ) -> ReadinessEvaluationResult:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        artifacts = [normalize_text_input(item) for item in request.text_inputs]
        manifest = [text_manifest_entry(item) for item in request.text_inputs]
        document_fingerprint: list[dict] = []
        extraction_findings_data: list[tuple] = []

        for upload_id in request.document_upload_ids:
            staged = self._storage.locate(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                upload_id=upload_id,
            )
            if staged.metadata.source_type is not ImplementationInputSourceType.DOCUMENT:
                raise ReadinessUploadTypeError(
                    f"Upload {upload_id} is not a DOCUMENT input"
                )
            try:
                extraction = self._extractions.get_existing(
                    project.agent_project_id, upload_id, current_user
                )
            except ExtractionNotFoundError:
                extraction = None
            status = extraction.status.value if extraction else "NOT_EXTRACTED"
            version = extraction.extractor_version if extraction else None
            document_fingerprint.append(
                {
                    "upload_id": upload_id,
                    "sha256": staged.metadata.sha256,
                    "status": status,
                    "extractor_version": version,
                }
            )
            if extraction is None:
                manifest.append(manifest_entry(staged.metadata, "NOT_EXTRACTED"))
                extraction_findings_data.append(
                    ("DOCUMENT_NOT_EXTRACTED", staged.metadata, None)
                )
            elif extraction.status is ExtractionStatus.FAILED:
                manifest.append(manifest_entry(staged.metadata, "FAILED"))
                extraction_findings_data.append(
                    ("DOCUMENT_EXTRACTION_FAILED", staged.metadata, extraction)
                )
            else:
                availability = (
                    "PARTIAL"
                    if extraction.status is ExtractionStatus.PARTIAL
                    else "AVAILABLE"
                )
                manifest.append(manifest_entry(staged.metadata, availability))
                artifacts.append(normalize_document(staged.metadata, extraction))
                if extraction.status is ExtractionStatus.PARTIAL:
                    extraction_findings_data.append(
                        ("DOCUMENT_EXTRACTION_PARTIAL", staged.metadata, extraction)
                    )

        images = []
        for upload_id in request.image_upload_ids:
            staged = self._storage.locate(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
                upload_id=upload_id,
            )
            if staged.metadata.source_type is not ImplementationInputSourceType.IMAGE:
                raise ReadinessUploadTypeError(
                    f"Upload {upload_id} is not an IMAGE input"
                )
            images.append(staged.metadata)
            manifest.append(manifest_entry(staged.metadata, "PENDING_ANALYSIS"))

        repository = None
        if any(item.value == "GIT_SUMMARY" for item in request.selected_outputs):
            repository = self._repository_bindings.find_by_project(
                project.agent_project_id, current_user.user_id
            )

        fingerprint = self._fingerprint(
            project.agent_project_id,
            request,
            document_fingerprint,
            images,
            repository,
        )
        if request.human_resolutions and request.input_fingerprint != fingerprint:
            raise StaleReadinessResolutionError(
                "Inputs changed; run readiness evaluation again before applying resolutions"
            )

        findings = self._extraction_findings(
            fingerprint, extraction_findings_data, request.selected_outputs
        )
        declarations = detect_stack(artifacts)
        findings.extend(evaluate_rules(
            fingerprint=fingerprint,
            artifacts=artifacts,
            images=images,
            selected_outputs=request.selected_outputs,
            repository_bound=repository is not None,
            declarations=declarations,
        ))
        findings = self._apply_resolutions(findings, request)

        unresolved_errors = [
            item for item in findings
            if item.severity is FindingSeverity.ERROR and not item.resolved
        ]
        unresolved_warnings = [
            item for item in findings
            if item.severity is FindingSeverity.WARNING and not item.resolved
        ]
        if unresolved_errors:
            status = ReadinessStatus.NOT_READY
        elif unresolved_warnings:
            status = ReadinessStatus.READY_WITH_WARNINGS
        else:
            status = ReadinessStatus.READY

        return ReadinessEvaluationResult(
            status=status,
            input_fingerprint=fingerprint,
            summary=ReadinessSummary(
                errors=len(unresolved_errors),
                warnings=len(unresolved_warnings),
                info=sum(
                    item.severity is FindingSeverity.INFO for item in findings
                ),
            ),
            coverage=coverage(artifacts, images),
            selected_outputs=request.selected_outputs,
            output_readiness=[
                OutputReadiness(
                    output=output,
                    ready=not any(
                        item.severity is FindingSeverity.ERROR
                        and not item.resolved
                        and (not item.affected_outputs or output in item.affected_outputs)
                        for item in findings
                    ),
                    findings=[
                        item.finding_id for item in findings
                        if not item.affected_outputs or output in item.affected_outputs
                    ],
                )
                for output in request.selected_outputs
            ],
            effective_stack=EffectivePrototypeStack(),
            artifact_manifest=manifest,
            findings=findings,
            human_resolutions=request.human_resolutions,
            evaluated_at=self._clock(),
        )

    @staticmethod
    def _fingerprint(
        project_id,
        request,
        documents,
        images,
        repository,
    ) -> str:
        payload = {
            "project_id": project_id,
            "selected_outputs": sorted(item.value for item in request.selected_outputs),
            "text_inputs": sorted(
                (
                    {
                        "input_id": item.input_id,
                        "artifact_type": item.artifact_type.value,
                        "label": item.label,
                        "content_sha256": hashlib.sha256(
                            item.content.encode("utf-8")
                        ).hexdigest(),
                    }
                    for item in request.text_inputs
                ),
                key=lambda item: item["input_id"],
            ),
            "documents": sorted(documents, key=lambda item: item["upload_id"]),
            "images": sorted(
                (
                    {
                        "upload_id": item.upload_id,
                        "sha256": item.sha256,
                    }
                    for item in images
                ),
                key=lambda item: item["upload_id"],
            ),
            "repository_id": repository.get("repository_id") if repository else None,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @staticmethod
    def _extraction_findings(fingerprint, entries, outputs):
        findings = []
        for code, metadata, extraction in entries:
            if code == "DOCUMENT_NOT_EXTRACTED":
                severity = FindingSeverity.ERROR
                title = "Document has not been extracted"
                message = "Run document extraction before using this upload for implementation readiness."
            elif code == "DOCUMENT_EXTRACTION_FAILED":
                severity = FindingSeverity.ERROR
                title = "Document extraction failed"
                message = "No sufficiently useful content was extracted from this document."
            else:
                severity = FindingSeverity.WARNING
                title = "Document extraction is partial"
                warning_count = len(extraction.warnings) if extraction else 0
                message = f"Useful content was extracted with {warning_count} extraction warning(s)."
            findings.append(make_finding(
                fingerprint, code, severity, title, message,
                affected_outputs=outputs,
                sources=[upload_reference(metadata)],
            ))
        return findings

    @staticmethod
    def _apply_resolutions(findings, request):
        by_id = {item.finding_id: item for item in findings}
        seen = set()
        for resolution in request.human_resolutions:
            if resolution.finding_id in seen:
                raise ReadinessResolutionError(
                    "A readiness finding cannot be resolved more than once"
                )
            seen.add(resolution.finding_id)
            finding = by_id.get(resolution.finding_id)
            if finding is None:
                raise ReadinessResolutionError(
                    "Human resolution refers to an unknown or stale finding"
                )
            if (
                not finding.requires_human_decision
                or resolution.decision not in finding.allowed_resolutions
            ):
                raise ReadinessResolutionError(
                    "Human resolution is not allowed for this finding"
                )
            finding.resolved = True
            finding.resolution = resolution
        return findings
