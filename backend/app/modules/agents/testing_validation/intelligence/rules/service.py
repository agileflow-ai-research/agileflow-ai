from datetime import datetime, timezone
from threading import RLock

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
    Agent4WorkflowStorage,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.service import StandaloneService

from .catalog import AGENT4_RULE_CATALOG_FINGERPRINT, AGENT4_RULES_VERSION
from .matcher import classify_testing_chunk
from .schemas import TestingRuleClassificationManifest
from .storage import Agent4RuleStorage


RULE_CLASSIFICATION_LOCK = RLock()


class Agent4RuleClassificationGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class Agent4RuleClassificationService:
    def __init__(self, standalone_service: StandaloneService,
                 workflow_storage: Agent4WorkflowStorage,
                 chunk_storage: Agent4ChunkStorage,
                 storage: Agent4RuleStorage, *, clock=utc_now):
        self._standalone = standalone_service
        self._workflows = workflow_storage
        self._chunks = chunk_storage
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, source_id: str,
              current_user: UserPublicResponse, *, force: bool = False):
        with AGENT4_WORKFLOW_STATE_LOCK, RULE_CLASSIFICATION_LOCK:
            project = self._standalone.require_active_project(
                current_user.user_id, agent_project_id
            )
            if project.agent_type is not AgentType.TESTING_VALIDATION:
                raise Agent4RuleClassificationGateError(
                    "Agent project must have agent_type TESTING_VALIDATION"
                )
            if project.agent_stage is not AgentStage.TEST_GENERATION:
                raise Agent4RuleClassificationGateError(
                    "Agent project must have agent_stage TEST_GENERATION"
                )
            workflow = self._workflows.load(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
            )
            confirmation = workflow.n1_confirmation if workflow else None
            if workflow is None or confirmation is None:
                raise Agent4RuleClassificationGateError(
                    "Confirmed Test Generation evidence is required"
                )
            n2_node = next(
                node for node in workflow.nodes
                if node.node_id is Agent4TestGenerationNodeId.INPUT_PREPARATION
            )
            execution = next(
                (item for item in workflow.n2_executions
                 if item.execution_id == workflow.current_n2_execution_id), None
            )
            if (n2_node.status is not Agent4WorkflowNodeStatus.COMPLETED
                    or execution is None
                    or execution.status is not Agent4N2ExecutionStatus.COMPLETED):
                raise Agent4RuleClassificationGateError(
                    "Input Preparation must complete before rule classification"
                )
            if source_id not in confirmation.source_ids:
                raise Agent4RuleClassificationGateError(
                    "Source is not present in the confirmed setup"
                )
            chunks = self._chunks.load(
                agent_project_id=agent_project_id,
                owner_user_id=current_user.user_id,
                source_id=source_id,
            )
            if chunks is None:
                raise Agent4RuleClassificationGateError(
                    "Current prepared chunks are unavailable"
                )
            if not force:
                cached = self._storage.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(cached, chunks):
                    return cached
            now = self._clock()
            confirmed = frozenset(confirmation.source_ids)
            results = [
                classify_testing_chunk(
                    chunk, chunks, confirmed_source_ids=confirmed, processed_at=now
                ) for chunk in chunks.chunks
            ]
            manifest = TestingRuleClassificationManifest(
                taxonomy_version="T1",
                rules_version=AGENT4_RULES_VERSION,
                rule_catalog_fingerprint=AGENT4_RULE_CATALOG_FINGERPRINT,
                agent_project_id=agent_project_id,
                source_id=source_id,
                chunk_set_fingerprint=chunks.chunk_set_fingerprint,
                chunk_ids=chunks.chunk_ids,
                results=results,
                processed_at=now,
            )
            self._storage.save(manifest, owner_user_id=current_user.user_id)
            return manifest

    @staticmethod
    def _cache_is_current(cached, chunks):
        if cached is None:
            return False
        if (cached.taxonomy_version != "T1"
                or cached.rules_version != AGENT4_RULES_VERSION
                or cached.rule_catalog_fingerprint != AGENT4_RULE_CATALOG_FINGERPRINT
                or cached.chunk_set_fingerprint != chunks.chunk_set_fingerprint
                or cached.chunk_ids != chunks.chunk_ids
                or len(cached.results) != len(chunks.chunks)):
            return False
        return all(
            result.chunk.chunk_id == chunk.chunk_id
            and result.chunk.text_sha256 == chunk.text_sha256
            and result.chunk.normalization_fingerprint == chunk.normalization_fingerprint
            and result.chunk.chunk_set_fingerprint == chunks.chunk_set_fingerprint
            for result, chunk in zip(cached.results, chunks.chunks, strict=True)
        )
