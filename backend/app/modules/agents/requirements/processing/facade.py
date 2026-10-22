from app.modules.agents.requirements.processing.audio.service import (
    AudioProcessingService,
)
from app.modules.agents.requirements.processing.service import (
    DocumentProcessingService,
)
from app.modules.agents.requirements.processing.video.service import (
    VideoProcessingService,
)


class UnsupportedProcessingSourceError(ValueError):
    pass


class RequirementProcessingService:
    """Dispatches the shared processing API to the source-specific slice."""

    def __init__(
        self,
        documents: DocumentProcessingService,
        audio: AudioProcessingService,
        video: VideoProcessingService,
    ) -> None:
        self._documents = documents
        self._audio = audio
        self._video = video

    def process(self, agent_project_id, source_id, current_user, *, force=False):
        return self._service(source_id).process(
            agent_project_id, source_id, current_user, force=force
        )

    def get_status(self, agent_project_id, source_id, current_user):
        return self._service(source_id).get_status(
            agent_project_id, source_id, current_user
        )

    def get_result(self, agent_project_id, source_id, current_user):
        return self._service(source_id).get_result(
            agent_project_id, source_id, current_user
        )

    def _service(self, source_id: str):
        if source_id.startswith("DOC-"):
            return self._documents
        if source_id.startswith("AUD-"):
            return self._audio
        if source_id.startswith("VID-"):
            return self._video
        raise UnsupportedProcessingSourceError(
            "Processing is available for DOCUMENT, AUDIO, and VIDEO sources only"
        )
