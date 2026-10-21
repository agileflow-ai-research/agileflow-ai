import hashlib
import json
from datetime import datetime, timezone
from threading import RLock

from app.modules.agents.testing_validation.preparation.chunking import constants
from app.modules.agents.testing_validation.preparation.chunking.chunker import (
    build_chunks,
)
from app.modules.agents.testing_validation.preparation.chunking.schemas import (
    TestingChunkMetrics,
    TestingChunkSet,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import (
    Agent4ChunkStorage,
)
from app.modules.agents.testing_validation.preparation.normalization.schemas import (
    NormalizedTestingArtifact,
)
from app.modules.agents.testing_validation.preparation.normalization.service import (
    Agent4NormalizationService,
)
from app.modules.agents.testing_validation.workflow.storage import (
    AGENT4_WORKFLOW_STATE_LOCK,
)
from app.modules.auth.schemas import UserPublicResponse


CHUNKING_LOCK = RLock()


class Agent4ChunkingNotApplicableError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Agent4ChunkingService:
    def __init__(
        self,
        normalization_service: Agent4NormalizationService,
        storage: Agent4ChunkStorage,
        *,
        clock=utc_now,
    ) -> None:
        self._normalization = normalization_service
        self._storage = storage
        self._clock = clock

    def build(
        self,
        agent_project_id: str,
        source_id: str,
        current_user: UserPublicResponse,
        *,
        force: bool = False,
    ) -> TestingChunkSet:
        with AGENT4_WORKFLOW_STATE_LOCK, CHUNKING_LOCK:
            artifact = self._normalization.get_existing(
                agent_project_id, source_id, current_user
            )
            if not artifact.textual_context_usable:
                raise Agent4ChunkingNotApplicableError(
                    "The normalized artifact has no usable textual context"
                )
            expected = self._build(artifact)
            if not force:
                cached = self._storage.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(cached, expected):
                    return cached
            self._storage.save(expected, owner_user_id=current_user.user_id)
            return expected

    def _build(self, artifact: NormalizedTestingArtifact) -> TestingChunkSet:
        policy_fingerprint = self._policy_fingerprint()
        input_payload = {
            "normalized_artifact_id": artifact.normalized_artifact_id,
            "normalization_fingerprint": artifact.input_fingerprint,
            "chunk_schema_version": constants.CHUNK_SCHEMA_VERSION,
            "chunker_version": constants.CHUNKER_VERSION,
            "policy_version": constants.CHUNK_POLICY_VERSION,
            "policy_fingerprint": policy_fingerprint,
        }
        input_fingerprint = self._digest(input_payload)
        chunks = build_chunks(artifact, policy_fingerprint=policy_fingerprint)
        if not chunks:
            raise Agent4ChunkingNotApplicableError(
                "The normalized artifact contains no chunkable text"
            )
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        token_counts = [chunk.token_count for chunk in chunks]
        chunk_set_fingerprint = self._digest(
            {
                "input_fingerprint": input_fingerprint,
                "chunk_ids": chunk_ids,
            }
        )
        return TestingChunkSet(
            schema_version=constants.CHUNK_SCHEMA_VERSION,
            chunker_version=constants.CHUNKER_VERSION,
            policy_version=constants.CHUNK_POLICY_VERSION,
            policy_fingerprint=policy_fingerprint,
            input_fingerprint=input_fingerprint,
            chunk_set_fingerprint=chunk_set_fingerprint,
            agent_project_id=artifact.agent_project_id,
            source_id=artifact.source_id,
            normalized_artifact_id=artifact.normalized_artifact_id,
            normalization_fingerprint=artifact.input_fingerprint,
            source_evidence_sha256=artifact.source_evidence_sha256,
            chunk_ids=chunk_ids,
            chunks=chunks,
            metrics=TestingChunkMetrics(
                chunk_count=len(chunks),
                total_tokens=sum(token_counts),
                min_chunk_tokens=min(token_counts),
                max_chunk_tokens=max(token_counts),
            ),
            created_at=self._clock(),
        )

    @staticmethod
    def _policy_fingerprint() -> str:
        return Agent4ChunkingService._digest(
            {
                "policy_version": constants.CHUNK_POLICY_VERSION,
                "target_tokens": constants.TARGET_CHUNK_TOKENS,
                "maximum_tokens": constants.MAX_CHUNK_TOKENS,
                "overlap_tokens": constants.OVERLAP_TOKENS,
                "maximum_chunks": constants.MAX_CHUNKS_PER_ARTIFACT,
                "tokenizer": "DETERMINISTIC_LEXICAL_V1",
            }
        )

    @staticmethod
    def _cache_is_current(cached, expected):
        if cached is None:
            return False
        return cached.model_copy(update={"created_at": expected.created_at}) == expected

    @staticmethod
    def _digest(payload) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
