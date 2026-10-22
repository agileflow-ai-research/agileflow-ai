from concurrent.futures import Executor
from datetime import datetime, timezone
from threading import Lock, RLock

from app.modules.agents.implementation.contracts.enums import (
    ImplementationInputSourceType,
)
from app.modules.agents.implementation.contracts.schemas import (
    UploadedFileMetadata,
)
from app.modules.agents.implementation.infrastructure.storage import (
    ImplementationUploadStorage,
)
from app.modules.agents.implementation.inputs.extraction.schemas import (
    ExtractionStatus,
)
from app.modules.agents.implementation.inputs.extraction.service import (
    DocumentExtractionService,
)
from app.modules.agents.implementation.inputs.upload.service import (
    require_implementation_project,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.schemas import (
    ZeroShotStatus,
)
from app.modules.agents.implementation.preparation.classification.zero_shot.service import (
    ZeroShotDetectionService,
)
from app.modules.agents.implementation.preparation.human_review.service import (
    HumanReviewService,
)
from app.modules.agents.implementation.preparation.hybrid.service import (
    HybridDetectionService,
)
from app.modules.agents.implementation.preparation.schemas import ChunkingStatus
from app.modules.agents.implementation.preparation.service import (
    RuleDetectionService,
    SemanticChunkingService,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from .constants import (
    IMAGE_ANALYSIS_NOT_IMPLEMENTED,
    PreparationStage,
    ProjectPreparationStatus,
    SourcePreparationStatus,
)
from .executor import AGENT3_PREPARATION_EXECUTOR
from .schemas import (
    PersistedPreparationSource,
    PreparationSourceError,
    PreparationSourceStatus,
    ProjectPreparationRecord,
    ProjectPreparationStartRequest,
    ProjectPreparationStatusResponse,
)
from .status import derive_project_status, public_status
from .storage import ProjectPreparationStorage, ProjectPreparationStorageError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


_PREPARATION_EXECUTOR = AGENT3_PREPARATION_EXECUTOR


class ProjectPreparationService:
    """Sequential, resumable orchestration over trusted file services."""

    _running_lock = Lock()
    _state_lock = RLock()
    _running_projects: set[str] = set()

    def __init__(
        self,
        standalone_service: StandaloneService,
        upload_storage: ImplementationUploadStorage,
        state_storage: ProjectPreparationStorage,
        extraction_service: DocumentExtractionService,
        chunking_service: SemanticChunkingService,
        rule_service: RuleDetectionService,
        zero_shot_service: ZeroShotDetectionService,
        hybrid_service: HybridDetectionService,
        human_review_service: HumanReviewService,
        *,
        executor: Executor = _PREPARATION_EXECUTOR,
        clock=utc_now,
    ) -> None:
        self._standalone = standalone_service
        self._uploads = upload_storage
        self._states = state_storage
        self._extraction = extraction_service
        self._chunks = chunking_service
        self._rules = rule_service
        self._zero_shot = zero_shot_service
        self._hybrid = hybrid_service
        self._human_review = human_review_service
        self._executor = executor
        self._clock = clock

    def start(
        self,
        agent_project_id: str,
        request: ProjectPreparationStartRequest,
        current_user: UserPublicResponse,
    ) -> ProjectPreparationStatusResponse:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        with self._running_lock:
            already_running = project.agent_project_id in self._running_projects
        if already_running:
            return self.get_status(agent_project_id, current_user)

        uploads = self._uploads.list_for_project(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )
        with self._state_lock:
            previous_record = self._states.load(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
            )
        now = self._clock()
        sources = self._initial_sources(
            uploads,
            request,
            previous_sources=(
                previous_record.sources if previous_record is not None else []
            ),
        )
        documents = [
            source
            for source in sources
            if source.source_kind is ImplementationInputSourceType.DOCUMENT
        ]
        if documents:
            documents[0].status = SourcePreparationStatus.EXTRACTING
            documents[0].current_stage = PreparationStage.EXTRACTION
        record = ProjectPreparationRecord(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
            status=derive_project_status(sources),
            sources=sources,
            started_at=now,
            updated_at=now,
        )
        if documents:
            with self._running_lock:
                if project.agent_project_id in self._running_projects:
                    already_running = True
                else:
                    already_running = False
                    self._running_projects.add(project.agent_project_id)
            if already_running:
                return self.get_status(agent_project_id, current_user)
        try:
            self._save(record)
        except ProjectPreparationStorageError:
            if documents:
                with self._running_lock:
                    self._running_projects.discard(project.agent_project_id)
            raise
        if not documents:
            return public_status(record)
        try:
            self._executor.submit(self._run, record, current_user)
        except RuntimeError:
            with self._running_lock:
                self._running_projects.discard(project.agent_project_id)
            for source in documents:
                source.status = SourcePreparationStatus.FAILED
                source.error = PreparationSourceError(
                    error_code="PREPARATION_EXECUTOR_UNAVAILABLE",
                    message="Project input analysis could not be started.",
                )
            self._save(record)
        return public_status(record)

    def get_status(
        self,
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> ProjectPreparationStatusResponse:
        project = require_implementation_project(
            self._standalone, agent_project_id, current_user
        )
        uploads = self._uploads.list_for_project(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )
        with self._state_lock:
            record = self._states.load(
                agent_project_id=project.agent_project_id,
                owner_user_id=current_user.user_id,
            )
        if record is None:
            sources = self._initial_sources(
                uploads, ProjectPreparationStartRequest()
            )
            public_sources = [
                PreparationSourceStatus.model_validate(
                    source.model_dump(exclude={"text_content"})
                )
                for source in sources
            ]
            return ProjectPreparationStatusResponse(
                agent_project_id=project.agent_project_id,
                status=ProjectPreparationStatus.NOT_STARTED,
                source_count=len(public_sources),
                eligible_source_count=sum(
                    source.source_kind
                    is not ImplementationInputSourceType.IMAGE
                    for source in public_sources
                ),
                processed_source_count=0,
                completed_source_count=0,
                active_source_count=0,
                failed_source_count=0,
                sources=public_sources,
                requires_human_review=False,
                human_review_source_count=0,
            )

        with self._state_lock:
            with self._running_lock:
                is_running = project.agent_project_id in self._running_projects
            if not is_running and record.status is ProjectPreparationStatus.RUNNING:
                for source in record.sources:
                    if source.status in {
                        SourcePreparationStatus.QUEUED,
                        SourcePreparationStatus.EXTRACTING,
                        SourcePreparationStatus.CHUNKING,
                        SourcePreparationStatus.CLASSIFYING_RULES,
                        SourcePreparationStatus.CLASSIFYING_MODEL,
                        SourcePreparationStatus.BUILDING_HYBRID,
                    }:
                        source.status = SourcePreparationStatus.FAILED
                        source.error = PreparationSourceError(
                            error_code="PREPARATION_INTERRUPTED",
                            message=(
                                "Project input analysis was interrupted and "
                                "can be resumed safely."
                            ),
                        )
            record.sources = self._reconcile_sources(
                record.sources, uploads, project.agent_project_id, current_user
            )
            record.status = derive_project_status(record.sources)
            record.updated_at = self._clock()
            self._states.save(record)
            return public_status(record)

    @staticmethod
    def _initial_sources(
        uploads: list[UploadedFileMetadata],
        request: ProjectPreparationStartRequest,
        previous_sources: list[PersistedPreparationSource] | None = None,
    ) -> list[PersistedPreparationSource]:
        previous_text = {
            source.source_id: source
            for source in previous_sources or []
            if source.source_kind is ImplementationInputSourceType.TEXT
        }
        current_text_ids = {item.input_id for item in request.text_inputs}
        sources: list[PersistedPreparationSource] = [
            source.model_copy(deep=True)
            for source_id, source in previous_text.items()
            if source_id not in current_text_ids
        ]
        for item in request.text_inputs:
            sources.append(
                PersistedPreparationSource(
                    source_id=item.input_id,
                    source_kind=ImplementationInputSourceType.TEXT,
                    artifact_type=item.artifact_type,
                    label=item.label,
                    filename=None,
                    status=SourcePreparationStatus.READY,
                    current_stage=PreparationStage.TEXT_NORMALIZATION,
                    text_content=item.content,
                )
            )
        for upload in uploads:
            is_image = (
                upload.source_type is ImplementationInputSourceType.IMAGE
            )
            sources.append(
                PersistedPreparationSource(
                    source_id=upload.upload_id,
                    source_kind=upload.source_type,
                    artifact_type=upload.artifact_type,
                    label=upload.label,
                    filename=upload.original_filename,
                    status=(
                        SourcePreparationStatus.SKIPPED
                        if is_image
                        else SourcePreparationStatus.QUEUED
                    ),
                    error=(
                        PreparationSourceError(
                            error_code=IMAGE_ANALYSIS_NOT_IMPLEMENTED,
                            message=(
                                "Image analysis is not implemented; the "
                                "source remains pending analysis."
                            ),
                        )
                        if is_image
                        else None
                    ),
                )
            )
        return sources

    def _run(
        self,
        record: ProjectPreparationRecord,
        current_user: UserPublicResponse,
    ) -> None:
        try:
            for source in record.sources:
                if (
                    source.source_kind
                    is not ImplementationInputSourceType.DOCUMENT
                ):
                    continue
                self._prepare_document(record, source, current_user)
            self._save(record)
        finally:
            with self._running_lock:
                self._running_projects.discard(record.agent_project_id)

    def _prepare_document(
        self,
        record: ProjectPreparationRecord,
        source: PersistedPreparationSource,
        current_user: UserPublicResponse,
    ) -> None:
        try:
            self._advance(
                record,
                source,
                SourcePreparationStatus.EXTRACTING,
                PreparationStage.EXTRACTION,
            )
            extraction = self._extraction.extract(
                record.agent_project_id, source.source_id, current_user
            )
            if extraction.status is ExtractionStatus.FAILED:
                self._fail_source(
                    record,
                    source,
                    "EXTRACTION_FAILED",
                    "The document could not be extracted.",
                )
                return

            self._advance(
                record,
                source,
                SourcePreparationStatus.CHUNKING,
                PreparationStage.CHUNKING,
            )
            chunks = self._chunks.build(
                record.agent_project_id, source.source_id, current_user
            )
            if chunks.status is ChunkingStatus.FAILED:
                self._fail_source(
                    record,
                    source,
                    "CHUNKING_FAILED",
                    "No usable semantic chunks could be prepared.",
                )
                return

            self._advance(
                record,
                source,
                SourcePreparationStatus.CLASSIFYING_RULES,
                PreparationStage.RULE_CLASSIFICATION,
            )
            self._rules.build(
                record.agent_project_id, source.source_id, current_user
            )

            self._advance(
                record,
                source,
                SourcePreparationStatus.CLASSIFYING_MODEL,
                PreparationStage.MODEL_CLASSIFICATION,
            )
            model = self._zero_shot.build(
                record.agent_project_id, source.source_id, current_user
            )
            if model.status is ZeroShotStatus.FAILED:
                self._fail_source(
                    record,
                    source,
                    "MODEL_CLASSIFICATION_FAILED",
                    "The local classification model produced no usable result.",
                )
                return

            self._advance(
                record,
                source,
                SourcePreparationStatus.BUILDING_HYBRID,
                PreparationStage.HYBRID,
            )
            self._hybrid.build(
                record.agent_project_id, source.source_id, current_user
            )
            review = self._human_review.get_state(
                record.agent_project_id, source.source_id, current_user
            )
            if review.review.review_status.value == "COMPLETE":
                source.status = SourcePreparationStatus.READY
            else:
                source.status = SourcePreparationStatus.WAITING_FOR_HUMAN
            source.current_stage = PreparationStage.HUMAN_REVIEW
            source.error = None
            self._save(record)
        except Exception:
            self._fail_source(
                record,
                source,
                "SOURCE_PREPARATION_FAILED",
                "This source could not be prepared at its current stage.",
            )

    def _advance(
        self,
        record: ProjectPreparationRecord,
        source: PersistedPreparationSource,
        status: SourcePreparationStatus,
        stage: PreparationStage,
    ) -> None:
        source.status = status
        source.current_stage = stage
        source.error = None
        self._save(record)

    def _fail_source(
        self,
        record: ProjectPreparationRecord,
        source: PersistedPreparationSource,
        code: str,
        message: str,
    ) -> None:
        source.status = SourcePreparationStatus.FAILED
        source.error = PreparationSourceError(
            error_code=code, message=message
        )
        self._save(record)

    def _save(self, record: ProjectPreparationRecord) -> None:
        with self._state_lock:
            record.status = derive_project_status(record.sources)
            record.updated_at = self._clock()
            self._states.save(record)

    def _reconcile_sources(
        self,
        previous: list[PersistedPreparationSource],
        uploads: list[UploadedFileMetadata],
        agent_project_id: str,
        current_user: UserPublicResponse,
    ) -> list[PersistedPreparationSource]:
        existing = {source.source_id: source for source in previous}
        reconciled = [
            source
            for source in previous
            if source.source_kind is ImplementationInputSourceType.TEXT
        ]
        for upload in uploads:
            source = existing.get(upload.upload_id)
            if source is None:
                source = self._initial_sources(
                    [upload], ProjectPreparationStartRequest()
                )[0]
            else:
                source.artifact_type = upload.artifact_type
                source.label = upload.label
                source.filename = upload.original_filename
            if (
                source.source_kind is ImplementationInputSourceType.DOCUMENT
                and source.status
                in {
                    SourcePreparationStatus.READY,
                    SourcePreparationStatus.WAITING_FOR_HUMAN,
                }
            ):
                try:
                    review = self._human_review.get_state(
                        agent_project_id, source.source_id, current_user
                    )
                    source.status = (
                        SourcePreparationStatus.READY
                        if review.review.review_status.value == "COMPLETE"
                        else SourcePreparationStatus.WAITING_FOR_HUMAN
                    )
                    source.current_stage = PreparationStage.HUMAN_REVIEW
                except Exception:
                    pass
            reconciled.append(source)
        return reconciled
