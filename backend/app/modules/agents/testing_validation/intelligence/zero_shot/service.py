from datetime import datetime, timezone
from threading import RLock

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.intelligence.taxonomy import (
    AGENT4_TESTING_TAXONOMY_VERSION,
    AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionStatus, Agent4TestGenerationNodeId, Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK, Agent4WorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from . import constants
from .classifier import Agent4ZeroShotClassifier, inference_configuration_fingerprint
from .schemas import TestingZeroShotManifest
from .storage import Agent4ZeroShotStorage


ZERO_SHOT_LOCK = RLock()


class Agent4ZeroShotGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class Agent4ZeroShotService:
    def __init__(self, standalone_service: StandaloneService,
                 workflow_storage: Agent4WorkflowStorage,
                 chunk_storage: Agent4ChunkStorage,
                 storage: Agent4ZeroShotStorage,
                 classifier: Agent4ZeroShotClassifier, *, clock=utc_now):
        self._standalone = standalone_service
        self._workflows = workflow_storage
        self._chunks = chunk_storage
        self._storage = storage
        self._classifier = classifier
        self._clock = clock

    def build(self, agent_project_id: str, source_id: str,
              current_user: UserPublicResponse, *, force=False):
        with AGENT4_WORKFLOW_STATE_LOCK, ZERO_SHOT_LOCK:
            project = self._standalone.require_active_project(
                current_user.user_id, agent_project_id
            )
            if project.agent_type is not AgentType.TESTING_VALIDATION:
                raise Agent4ZeroShotGateError(
                    "Agent project must have agent_type TESTING_VALIDATION"
                )
            if project.agent_stage is not AgentStage.TEST_GENERATION:
                raise Agent4ZeroShotGateError(
                    "Agent project must have agent_stage TEST_GENERATION"
                )
            workflow = self._workflows.load(
                agent_project_id=agent_project_id, owner_user_id=current_user.user_id
            )
            confirmation = workflow.n1_confirmation if workflow else None
            if workflow is None or confirmation is None:
                raise Agent4ZeroShotGateError("Confirmed Test Generation evidence is required")
            n2 = next(node for node in workflow.nodes
                      if node.node_id is Agent4TestGenerationNodeId.INPUT_PREPARATION)
            execution = next((item for item in workflow.n2_executions
                              if item.execution_id == workflow.current_n2_execution_id), None)
            if (n2.status is not Agent4WorkflowNodeStatus.COMPLETED
                    or execution is None
                    or execution.status is not Agent4N2ExecutionStatus.COMPLETED):
                raise Agent4ZeroShotGateError(
                    "Input Preparation must complete before zero-shot classification"
                )
            if source_id not in confirmation.source_ids:
                raise Agent4ZeroShotGateError("Source is not present in the confirmed setup")
            chunks = self._chunks.load(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id, source_id=source_id,
            )
            if chunks is None:
                raise Agent4ZeroShotGateError("Current prepared chunks are unavailable")
            if not force:
                cached = self._storage.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=current_user.user_id, source_id=source_id,
                )
                if self._cache_is_current(cached, chunks):
                    return cached
            now = self._clock()
            device, results = self._classifier.classify(
                chunks, confirmed_source_ids=frozenset(confirmation.source_ids),
                processed_at=now,
            )
            manifest = TestingZeroShotManifest(
                taxonomy_version=AGENT4_TESTING_TAXONOMY_VERSION,
                label_description_version=AGENT4_ZERO_SHOT_LABEL_DESCRIPTION_VERSION,
                hypothesis_template_version=constants.HYPOTHESIS_TEMPLATE_VERSION,
                hypothesis_template=constants.HYPOTHESIS_TEMPLATE,
                configuration_fingerprint=inference_configuration_fingerprint(),
                model_id=constants.MODEL_ID, model_revision=constants.MODEL_REVISION,
                task=constants.MODEL_TASK, multi_label=True, device=device,
                batch_size=constants.INFERENCE_BATCH_SIZE,
                truncation_strategy=constants.TRUNCATION_STRATEGY,
                agent_project_id=agent_project_id, source_id=source_id,
                chunk_set_fingerprint=chunks.chunk_set_fingerprint,
                chunk_ids=chunks.chunk_ids, results=results, processed_at=now,
            )
            self._storage.save(manifest, owner_user_id=current_user.user_id)
            return manifest

    @staticmethod
    def _cache_is_current(cached, chunks):
        if cached is None:
            return False
        if (cached.zero_shot_version != constants.ZERO_SHOT_STAGE_VERSION
                or cached.configuration_fingerprint != inference_configuration_fingerprint()
                or cached.model_id != constants.MODEL_ID
                or cached.model_revision != constants.MODEL_REVISION
                or cached.chunk_set_fingerprint != chunks.chunk_set_fingerprint
                or cached.chunk_ids != chunks.chunk_ids
                or len(cached.results) != len(chunks.chunks)):
            return False
        return all(
            result.chunk.chunk_id == chunk.chunk_id
            and result.chunk.text_sha256 == chunk.text_sha256
            and result.chunk.normalization_fingerprint == chunk.normalization_fingerprint
            for result, chunk in zip(cached.results, chunks.chunks, strict=True)
        )
