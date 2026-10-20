from functools import lru_cache
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
from app.modules.agents.requirements.processing.service import DocumentProcessingService
from app.modules.standalone.router import get_standalone_service
from app.modules.standalone.service import StandaloneService


def get_requirement_source_storage() -> RequirementSourceStorage:
    return RequirementSourceStorage(settings.agent1_source_root)


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


def get_requirement_processing_service(
    documents: Annotated[
        DocumentProcessingService, Depends(get_document_processing_service)
    ],
    audio: Annotated[
        AudioProcessingService, Depends(get_audio_processing_service)
    ],
) -> RequirementProcessingService:
    return RequirementProcessingService(documents, audio)

