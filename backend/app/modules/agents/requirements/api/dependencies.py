from functools import lru_cache
from concurrent.futures import Executor
from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.modules.agents.requirements.infrastructure.storage import RequirementSourceStorage
from app.modules.agents.requirements.inputs.upload.service import RequirementSourceService
from app.modules.agents.requirements.processing.audio.providers.base import (
    SpeechToTextProvider,
)
from app.modules.agents.requirements.processing.audio.providers.faster_whisper import (
    FasterWhisperProvider,
    UnconfiguredSpeechToTextProvider,
)
from app.modules.agents.requirements.processing.audio.service import (
    AudioProcessingService,
)
from app.modules.agents.requirements.processing.facade import (
    RequirementProcessingService,
)
from app.modules.agents.requirements.processing.preparation.chunker import (
    DeterministicChunker,
    SentenceSegmenter,
    build_chunker_configuration,
)
from app.modules.agents.requirements.processing.preparation.service import (
    EvidencePreparationService,
)
from app.modules.agents.requirements.processing.service import DocumentProcessingService
from app.modules.agents.requirements.processing.video.providers.base import (
    VideoAudioExtractor,
)
from app.modules.agents.requirements.processing.video.providers.ffmpeg import (
    FFmpegAudioExtractor,
)
from app.modules.agents.requirements.processing.video.service import (
    VideoProcessingService,
)
from app.modules.agents.requirements.workflow.service import RequirementWorkflowService
from app.modules.agents.requirements.workflow.orchestration.n2_service import (
    RequirementN2OrchestrationService,
)
from app.modules.agents.requirements.workflow.orchestration.progression import (
    N2CompletionProgression,
)
from app.modules.agents.requirements.workflow.executor import AGENT1_N2_EXECUTOR
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import StandaloneService


def get_requirement_source_storage() -> RequirementSourceStorage:
    return RequirementSourceStorage(settings.agent1_source_root)


def get_requirement_workflow_storage() -> RequirementWorkflowStorage:
    return RequirementWorkflowStorage(settings.agent1_source_root)


def get_requirement_n4_orchestration_service():
    from app.modules.agents.requirements.quality.dependencies import build_n4_orchestration_service
    return build_n4_orchestration_service(settings.agent1_source_root)


def get_quality_result_service(
    standalone_service: Annotated[StandaloneService, Depends(get_standalone_service)],
    workflow_storage: Annotated[RequirementWorkflowStorage, Depends(get_requirement_workflow_storage)],
):
    from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore
    from app.modules.agents.requirements.quality.api import QualityResultService
    from app.modules.agents.requirements.quality.storage import QualityStorage
    return QualityResultService(
        standalone_service, workflow_storage,
        QualityStorage(JsonArtifactStore(settings.agent1_source_root)),
    )


def get_agent1_n2_executor() -> Executor:
    return AGENT1_N2_EXECUTOR


def get_workflow_progression() -> N2CompletionProgression:
    from app.modules.agents.requirements.discovery.dependencies import (
        build_workflow_progression,
    )

    return build_workflow_progression(settings.agent1_source_root)


def get_requirement_n3_orchestration_service():
    from app.modules.agents.requirements.discovery.dependencies import (
        build_n3_orchestration_service,
    )

    return build_n3_orchestration_service(settings.agent1_source_root)


def get_discovery_result_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    workflow_storage: Annotated[
        RequirementWorkflowStorage, Depends(get_requirement_workflow_storage)
    ],
):
    from app.modules.agents.requirements.discovery.dependencies import (
        build_discovery_storage,
    )
    from app.modules.agents.requirements.discovery.service import DiscoveryResultService

    return DiscoveryResultService(
        standalone_service,
        workflow_storage,
        build_discovery_storage(settings.agent1_source_root),
    )


def get_requirement_workflow_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    source_storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
    workflow_storage: Annotated[
        RequirementWorkflowStorage, Depends(get_requirement_workflow_storage)
    ],
) -> RequirementWorkflowService:
    return RequirementWorkflowService(
        standalone_service, source_storage, workflow_storage
    )


def get_requirement_source_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
) -> RequirementSourceService:
    return RequirementSourceService(standalone_service, storage)


def get_document_processing_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
) -> DocumentProcessingService:
    return DocumentProcessingService(standalone_service, storage)


@lru_cache(maxsize=1)
def get_speech_to_text_provider() -> SpeechToTextProvider:
    if settings.transcription_provider.strip().lower() != "faster_whisper":
        return UnconfiguredSpeechToTextProvider(settings.transcription_provider)
    return FasterWhisperProvider(
        model_name=settings.faster_whisper_model,
        device=settings.faster_whisper_device,
        compute_type=settings.faster_whisper_compute_type,
        language=settings.faster_whisper_language,
    )


def get_audio_processing_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
    provider: Annotated[
        SpeechToTextProvider, Depends(get_speech_to_text_provider)
    ],
) -> AudioProcessingService:
    return AudioProcessingService(standalone_service, storage, provider)


@lru_cache(maxsize=1)
def get_video_audio_extractor() -> VideoAudioExtractor:
    return FFmpegAudioExtractor(
        executable=settings.video_ffmpeg_path,
        timeout_seconds=settings.video_ffmpeg_timeout_seconds,
    )


def get_video_processing_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
    extractor: Annotated[
        VideoAudioExtractor, Depends(get_video_audio_extractor)
    ],
    provider: Annotated[
        SpeechToTextProvider, Depends(get_speech_to_text_provider)
    ],
) -> VideoProcessingService:
    return VideoProcessingService(standalone_service, storage, extractor, provider)


def get_requirement_processing_service(
    documents: Annotated[
        DocumentProcessingService, Depends(get_document_processing_service)
    ],
    audio: Annotated[
        AudioProcessingService, Depends(get_audio_processing_service)
    ],
    video: Annotated[
        VideoProcessingService, Depends(get_video_processing_service)
    ],
) -> RequirementProcessingService:
    return RequirementProcessingService(documents, audio, video)


@lru_cache(maxsize=1)
def get_sentence_segmenter() -> SentenceSegmenter:
    return SentenceSegmenter()


def get_evidence_preparation_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
    processing: Annotated[
        RequirementProcessingService, Depends(get_requirement_processing_service)
    ],
    segmenter: Annotated[SentenceSegmenter, Depends(get_sentence_segmenter)],
) -> EvidencePreparationService:
    configuration = build_chunker_configuration(
        target_chars=settings.agent1_chunk_target_chars,
        max_chars=settings.agent1_chunk_max_chars,
        overlap_sentences=settings.agent1_chunk_overlap_sentences,
        segmenter=segmenter,
    )
    return EvidencePreparationService(
        standalone_service,
        storage,
        processing,
        DeterministicChunker(configuration, segmenter),
    )


def get_requirement_n2_orchestration_service(
    standalone_service: Annotated[
        StandaloneService, Depends(get_standalone_service)
    ],
    source_storage: Annotated[
        RequirementSourceStorage, Depends(get_requirement_source_storage)
    ],
    workflow_storage: Annotated[
        RequirementWorkflowStorage, Depends(get_requirement_workflow_storage)
    ],
    workflow_service: Annotated[
        RequirementWorkflowService, Depends(get_requirement_workflow_service)
    ],
    processing_service: Annotated[
        RequirementProcessingService, Depends(get_requirement_processing_service)
    ],
    preparation_service: Annotated[
        EvidencePreparationService, Depends(get_evidence_preparation_service)
    ],
    executor: Annotated[Executor, Depends(get_agent1_n2_executor)],
    progression: Annotated[
        N2CompletionProgression, Depends(get_workflow_progression)
    ],
) -> RequirementN2OrchestrationService:
    return RequirementN2OrchestrationService(
        standalone_service,
        source_storage,
        workflow_storage,
        workflow_service,
        processing_service,
        preparation_service,
        executor=executor,
        progression=progression,
    )

