from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock, RLock

from app.modules.agents.implementation.contracts.enums import (
    ImplementationInputSourceType,
)
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
)
from app.modules.agents.implementation.inputs.upload.service import (
    require_implementation_project,
)
from app.modules.agents.implementation.preparation.canonical.schemas import (
    CanonicalStatus,
)
from app.modules.agents.implementation.preparation.canonical.service import (
    CanonicalArtifactService,
)
from app.modules.agents.implementation.preparation.human_review.schemas import (
    DocumentReviewStatus,
)
from app.modules.agents.implementation.preparation.human_review.service import (
    HumanReviewService,
)
from app.modules.agents.implementation.preparation.orchestration.executor import (
    AGENT3_PREPARATION_EXECUTOR,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.preparation.semantic_extraction.artifact_service import (
    SemanticArtifactService,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    SemanticArtifactRunStatus,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from .constants import (
    ProjectSpecificationStatus,
    SemanticReviewStatus,
    SourceSpecificationStatus,
)
from .review_service import SemanticReviewService
from .schemas import (
    ProjectSpecificationRecord,
    ProjectSpecificationStatusResponse,
    SpecificationSourceError,
    SpecificationSourceState,
)
from .storage import (
    ProjectSpecificationStorage,
    ProjectSpecificationStorageError,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ACTIVE = {
    SourceSpecificationStatus.BUILDING_CANONICAL,
    SourceSpecificationStatus.BUILDING_SEMANTIC,
}


def derive_specification_status(sources):
    applicable = [
        source for source in sources
        if source.status is not SourceSpecificationStatus.SKIPPED
    ]
    if any(source.status in ACTIVE for source in applicable):
        return ProjectSpecificationStatus.PREPARING_SPECIFICATION
    failed = sum(
        source.status is SourceSpecificationStatus.FAILED
        for source in applicable
    )
    usable = sum(
        source.status in {
            SourceSpecificationStatus.READY,
            SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW,
            SourceSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW,
        }
        for source in applicable
    )
    if failed and usable:
        return ProjectSpecificationStatus.PARTIAL_FAILURE
    if applicable and failed == len(applicable):
        return ProjectSpecificationStatus.FAILED
    if any(
        source.status is SourceSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW
        for source in applicable
    ):
        return ProjectSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW
    if any(
        source.status is SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
        for source in applicable
    ):
        return ProjectSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
    if applicable and all(
        source.status is SourceSpecificationStatus.READY
        for source in applicable
    ):
        return ProjectSpecificationStatus.SPECIFICATION_READY
    return ProjectSpecificationStatus.NOT_STARTED


def public_status(record):
    applicable = [
        source for source in record.sources
        if source.status is not SourceSpecificationStatus.SKIPPED
    ]
    return ProjectSpecificationStatusResponse(
        agent_project_id=record.agent_project_id,
        status=record.status,
        source_count=len(record.sources),
        applicable_source_count=len(applicable),
        ready_source_count=sum(
            source.status is SourceSpecificationStatus.READY
            for source in applicable
        ),
        waiting_artifact_review_count=sum(
            source.status is SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
            for source in applicable
        ),
        waiting_semantic_review_count=sum(
            source.status is SourceSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW
            for source in applicable
        ),
        failed_source_count=sum(
            source.status is SourceSpecificationStatus.FAILED
            for source in applicable
        ),
        pending_semantic_decision_count=sum(
            source.pending_semantic_decision_count for source in applicable
        ),
        sources=record.sources,
        started_at=record.started_at,
        updated_at=record.updated_at,
    )


class ProjectSpecificationService:
    _running_lock = Lock()
    _state_lock = RLock()
    _running_projects: set[str] = set()

    def __init__(
        self,
        standalone_service: StandaloneService,
        upload_storage: ImplementationUploadStorage,
        state_storage: ProjectSpecificationStorage,
        human_review_service: HumanReviewService,
        canonical_service: CanonicalArtifactService,
        semantic_service: SemanticArtifactService,
        semantic_review_service: SemanticReviewService,
        *,
        executor: Executor = AGENT3_PREPARATION_EXECUTOR,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._uploads = upload_storage
        self._states = state_storage
        self._human_review = human_review_service
        self._canonical = canonical_service
        self._semantic = semantic_service
        self._semantic_review = semantic_review_service
        self._executor = executor
        self._clock = clock

    def start(self, agent_project_id, current_user):
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        with self._running_lock:
            if project.agent_project_id in self._running_projects:
                return self.get_status(agent_project_id, current_user)
        uploads = self._uploads.list_for_project(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
        )
        previous = self._states.load(agent_project_id, current_user.user_id)
        old = {
            source.source_id: source for source in previous.sources
        } if previous else {}
        sources = []
        ready_to_process = []
        for upload in uploads:
            if upload.source_type is ImplementationInputSourceType.IMAGE:
                sources.append(SpecificationSourceState(
                    source_id=upload.upload_id,
                    filename=upload.original_filename,
                    status=SourceSpecificationStatus.SKIPPED,
                    error=SpecificationSourceError(
                        error_code="IMAGE_ANALYSIS_NOT_IMPLEMENTED",
                        message="Image specification preparation is not implemented.",
                    ),
                ))
                continue
            prior = old.get(upload.upload_id)
            try:
                review = self._human_review.get_state(
                    agent_project_id, upload.upload_id, current_user
                )
                complete = (
                    review.review.review_status
                    is DocumentReviewStatus.COMPLETE
                )
            except Exception:
                complete = False
            if not complete:
                sources.append(SpecificationSourceState(
                    source_id=upload.upload_id,
                    filename=upload.original_filename,
                    status=SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW,
                ))
                continue
            source = SpecificationSourceState(
                source_id=upload.upload_id,
                filename=upload.original_filename,
                status=SourceSpecificationStatus.BUILDING_CANONICAL,
                pending_semantic_decision_count=(
                    prior.pending_semantic_decision_count if prior else 0
                ),
            )
            sources.append(source)
            ready_to_process.append(source)
        now = self._clock()
        record = ProjectSpecificationRecord(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
            status=derive_specification_status(sources),
            sources=sources,
            started_at=previous.started_at if previous else now,
            updated_at=now,
        )
        if ready_to_process:
            with self._running_lock:
                if agent_project_id in self._running_projects:
                    return self.get_status(agent_project_id, current_user)
                self._running_projects.add(agent_project_id)
        try:
            self._save(record)
        except ProjectSpecificationStorageError:
            with self._running_lock:
                self._running_projects.discard(agent_project_id)
            raise
        if not ready_to_process:
            return public_status(record)
        try:
            self._executor.submit(
                self._run, record, ready_to_process, current_user
            )
        except RuntimeError:
            with self._running_lock:
                self._running_projects.discard(agent_project_id)
            for source in ready_to_process:
                self._fail(source, "SPECIFICATION_EXECUTOR_UNAVAILABLE",
                           "Specification preparation could not be started.")
            self._save(record)
        return public_status(record)

    def get_status(self, agent_project_id, current_user):
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        uploads = self._uploads.list_for_project(
            agent_project_id=agent_project_id,
            owner_user_id=current_user.user_id,
        )
        with self._state_lock:
            record = self._states.load(agent_project_id, current_user.user_id)
            if record is None:
                sources = [SpecificationSourceState(
                    source_id=upload.upload_id,
                    filename=upload.original_filename,
                    status=(
                        SourceSpecificationStatus.SKIPPED
                        if upload.source_type is ImplementationInputSourceType.IMAGE
                        else SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
                    ),
                ) for upload in uploads]
                return ProjectSpecificationStatusResponse(
                    agent_project_id=project.agent_project_id,
                    status=ProjectSpecificationStatus.NOT_STARTED,
                    source_count=len(sources),
                    applicable_source_count=sum(
                        source.status is not SourceSpecificationStatus.SKIPPED
                        for source in sources
                    ),
                    ready_source_count=0,
                    waiting_artifact_review_count=0,
                    waiting_semantic_review_count=0,
                    failed_source_count=0,
                    pending_semantic_decision_count=0,
                    sources=sources,
                )
            current_ids = {upload.upload_id for upload in uploads}
            record.sources = [
                source for source in record.sources
                if source.source_id in current_ids
            ]
            known_ids = {source.source_id for source in record.sources}
            for upload in uploads:
                if upload.upload_id in known_ids:
                    continue
                record.sources.append(SpecificationSourceState(
                    source_id=upload.upload_id,
                    filename=upload.original_filename,
                    status=(
                        SourceSpecificationStatus.SKIPPED
                        if upload.source_type
                        is ImplementationInputSourceType.IMAGE
                        else SourceSpecificationStatus.WAITING_FOR_ARTIFACT_REVIEW
                    ),
                    error=(
                        SpecificationSourceError(
                            error_code="IMAGE_ANALYSIS_NOT_IMPLEMENTED",
                            message=(
                                "Image specification preparation is not "
                                "implemented."
                            ),
                        )
                        if upload.source_type
                        is ImplementationInputSourceType.IMAGE
                        else None
                    ),
                ))
            with self._running_lock:
                running = agent_project_id in self._running_projects
            if (
                not running
                and record.status
                is ProjectSpecificationStatus.PREPARING_SPECIFICATION
            ):
                for source in record.sources:
                    if source.status in ACTIVE:
                        self._fail(
                            source,
                            "SPECIFICATION_PREPARATION_INTERRUPTED",
                            "Specification preparation was interrupted and can be resumed safely.",
                        )
            record.status = derive_specification_status(record.sources)
            record.updated_at = self._clock()
            self._states.save(record)
            return public_status(record)

    def _run(self, record, sources, current_user):
        try:
            for source in sources:
                self._prepare_source(record, source, current_user)
            self._save(record)
        finally:
            with self._running_lock:
                self._running_projects.discard(record.agent_project_id)

    def _prepare_source(self, record, source, current_user):
        try:
            source.status = SourceSpecificationStatus.BUILDING_CANONICAL
            source.error = None
            self._save(record)
            canonical = self._canonical.build(
                record.agent_project_id, source.source_id, current_user
            )
            semantic_targets = [
                artifact for artifact in canonical.artifacts
                if artifact.status in {
                    CanonicalStatus.PARTIAL,
                    CanonicalStatus.UNRESOLVED,
                }
                and artifact.artifact_type
                is not ArtifactDetectionLabel.OTHER_CONTEXT
            ]
            if not semantic_targets:
                final = self._semantic_review.build_deterministic_final(
                    canonical, current_user
                )
                source.status = SourceSpecificationStatus.READY
                source.final_artifact_count = len(final.artifacts)
                source.pending_semantic_decision_count = 0
                self._save(record)
                return
            source.status = SourceSpecificationStatus.BUILDING_SEMANTIC
            self._save(record)
            semantic = self._semantic.build(
                record.agent_project_id, source.source_id, current_user
            )
            semantic_failed = any(
                item.status in {
                    SemanticArtifactRunStatus.MODEL_ERROR,
                    SemanticArtifactRunStatus.MODEL_OUTPUT_INVALID,
                }
                for item in semantic.results
            )
            if semantic_failed:
                self._fail(
                    source,
                    "SEMANTIC_ARTIFACT_PREPARATION_FAILED",
                    "Some semantic artifacts could not be prepared.",
                )
                self._save(record)
                return
            review = self._semantic_review.prepare(
                record.agent_project_id, source.source_id, current_user
            )
            pending = sum(item.decision is None for item in review.items)
            source.pending_semantic_decision_count = pending
            if review.status is SemanticReviewStatus.PENDING:
                source.status = (
                    SourceSpecificationStatus.WAITING_FOR_SEMANTIC_REVIEW
                )
            else:
                final = self._semantic_review.get_final(
                    record.agent_project_id, source.source_id, current_user
                )
                source.status = SourceSpecificationStatus.READY
                source.final_artifact_count = len(final.artifacts)
                source.error = None
            self._save(record)
        except Exception:
            self._fail(
                source,
                "SOURCE_SPECIFICATION_PREPARATION_FAILED",
                "This source specification could not be prepared.",
            )
            self._save(record)

    @staticmethod
    def _fail(source, code, message):
        source.status = SourceSpecificationStatus.FAILED
        source.error = SpecificationSourceError(
            error_code=code,
            message=message,
        )

    def _save(self, record):
        with self._state_lock:
            record.status = derive_specification_status(record.sources)
            record.updated_at = self._clock()
            self._states.save(record)
