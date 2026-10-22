from datetime import datetime, timezone
from threading import RLock

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.intelligence.effective.service import (
    effective_manifest_fingerprint,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N2ExecutionStatus,
    Agent4N3ExecutionStatus,
    Agent4N3SourceStatus,
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)

from .canonicalization import fingerprint
from .constants import (
    LEXICAL_POLICY_VERSION,
    TRACEABILITY_ENGINE_VERSION,
    TRACEABILITY_SCHEMA_VERSION,
)
from .engine import build_traceability_components
from .schemas import Agent4TraceabilityManifest, TraceabilityCounts


TRACEABILITY_LOCK = RLock()


class Agent4TraceabilityGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class Agent4TraceabilityService:
    def __init__(self, workflow_service, workflow_storage, source_storage,
                 chunk_storage, effective_storage, semantic_storage,
                 traceability_storage, *, clock=utc_now):
        self._workflow_service = workflow_service
        self._workflows = workflow_storage
        self._sources = source_storage
        self._chunks = chunk_storage
        self._effective = effective_storage
        self._semantic = semantic_storage
        self._storage = traceability_storage
        self._clock = clock

    def build(self, project_id, user, *, force=False):
        # Reuse the existing owner/lifecycle/type/stage trust boundary.
        self._workflow_service.get(project_id, user)
        with TRACEABILITY_LOCK:
            record = self._workflows.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            self._require_completed_n3(record)
            sources = self._sources.list_for_project(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            self._require_confirmed_sources(record, sources)
            chunks, effective, semantic, evidence = self._load_evidence(
                record, sources, user.user_id
            )
            input_identity = fingerprint({
                "schema": TRACEABILITY_SCHEMA_VERSION,
                "engine": TRACEABILITY_ENGINE_VERSION,
                "lexical": LEXICAL_POLICY_VERSION,
                "confirmation_id": record.n1_confirmation.confirmation_id,
                "n2_execution_id": record.current_n2_execution_id,
                "n3_execution_id": record.current_n3_execution_id,
                "evidence": evidence,
            })
            components = build_traceability_components(
                project_id=project_id, sources=sources, chunk_sets=chunks,
                effective_manifests=effective, semantic_manifests=semantic,
            )
            candidate = Agent4TraceabilityManifest(
                schema_version=TRACEABILITY_SCHEMA_VERSION,
                engine_version=TRACEABILITY_ENGINE_VERSION,
                lexical_policy_version=LEXICAL_POLICY_VERSION,
                agent_project_id=project_id,
                confirmation_id=record.n1_confirmation.confirmation_id,
                n2_execution_id=record.current_n2_execution_id,
                n3_execution_id=record.current_n3_execution_id,
                input_fingerprint=input_identity,
                evidence_fingerprints=evidence,
                nodes=components.nodes,
                links=components.links,
                unresolved_references=components.unresolved,
                ambiguities=components.ambiguities,
                counts=TraceabilityCounts(
                    node_count=len(components.nodes), link_count=len(components.links),
                    unresolved_count=len(components.unresolved),
                    ambiguous_count=len(components.ambiguities),
                ),
                built_at=self._clock(),
            )
            cached = self._storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            if not force and self._cache_matches(cached, candidate):
                return cached
            self._storage.save(candidate, owner_user_id=user.user_id)
            return candidate

    @staticmethod
    def _require_completed_n3(record):
        if record is None or record.n1_confirmation is None:
            raise Agent4TraceabilityGateError("Confirmed Agent 4 evidence is required")
        node = {item.node_id: item.status for item in record.nodes}
        n2 = next((item for item in record.n2_executions if item.execution_id == record.current_n2_execution_id), None)
        n3 = next((item for item in record.n3_executions if item.execution_id == record.current_n3_execution_id), None)
        valid = (
            n2 is not None and n2.status is Agent4N2ExecutionStatus.COMPLETED
            and n3 is not None and n3.status is Agent4N3ExecutionStatus.COMPLETED
            and node.get(Agent4TestGenerationNodeId.INPUT_OUTPUT_SETUP) is Agent4WorkflowNodeStatus.COMPLETED
            and node.get(Agent4TestGenerationNodeId.INPUT_PREPARATION) is Agent4WorkflowNodeStatus.COMPLETED
            and node.get(Agent4TestGenerationNodeId.TESTING_INTELLIGENCE) is Agent4WorkflowNodeStatus.COMPLETED
            and node.get(Agent4TestGenerationNodeId.TESTING_FACT_EXTRACTION) is Agent4WorkflowNodeStatus.COMPLETED
            and node.get(Agent4TestGenerationNodeId.CONTEXT_TESTABILITY) in {
                Agent4WorkflowNodeStatus.NOT_STARTED,
                Agent4WorkflowNodeStatus.RUNNING,
            }
            and node.get(Agent4TestGenerationNodeId.TEST_PLANNING_REVIEW) is Agent4WorkflowNodeStatus.LOCKED
            and node.get(Agent4TestGenerationNodeId.TEST_GENERATION_RESULTS) is Agent4WorkflowNodeStatus.LOCKED
            and record.current_node_id is Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            and record.pipeline_status is Agent4PipelineStatus.RUNNING
        )
        if not valid:
            raise Agent4TraceabilityGateError(
                "Current completed Testing Intelligence evidence is required"
            )
        if any(item.status not in {Agent4N3SourceStatus.COMPLETE, Agent4N3SourceStatus.PENDING_ANALYSIS} for item in n3.sources):
            raise Agent4TraceabilityGateError("Testing Intelligence source evidence is incomplete")

    @staticmethod
    def _require_confirmed_sources(record, sources):
        ids = sorted(item.source_id for item in sources)
        if ids != record.n1_confirmation.source_ids:
            raise Agent4TraceabilityGateError("Confirmed source evidence changed")

    def _load_evidence(self, record, sources, owner_id):
        chunks, effective, semantic, evidence = {}, {}, {}, {}
        for source in sorted(sources, key=lambda item: item.source_id):
            evidence[f"source:{source.source_id}"] = fingerprint(
                source.model_dump(mode="json", exclude={"created_at"})
            )
            if source.source_type is TestGenerationInputSourceType.IMAGE:
                continue
            chunk_set = self._chunks.load(
                agent_project_id=record.agent_project_id,
                owner_user_id=owner_id, source_id=source.source_id,
            )
            effective_manifest = self._effective.load(
                agent_project_id=record.agent_project_id,
                owner_user_id=owner_id, source_id=source.source_id,
            )
            semantic_manifest = self._semantic.load(
                agent_project_id=record.agent_project_id,
                owner_user_id=owner_id, source_id=source.source_id,
            )
            if not chunk_set or not effective_manifest or not semantic_manifest:
                raise Agent4TraceabilityGateError("Current N3 evidence is unavailable")
            effective_fp = effective_manifest_fingerprint(effective_manifest)
            if (
                effective_manifest.chunk_ids != chunk_set.chunk_ids
                or semantic_manifest.chunk_ids != chunk_set.chunk_ids
                or semantic_manifest.chunk_set_fingerprint != chunk_set.chunk_set_fingerprint
                or semantic_manifest.effective_manifest_fingerprint != effective_fp
            ):
                raise Agent4TraceabilityGateError("Current N3 evidence is stale")
            effective_by_chunk = {item.chunk.chunk_id: item for item in effective_manifest.results}
            if any(
                result.effective_result_id != effective_by_chunk[result.chunk.chunk_id].effective_result_id
                for result in semantic_manifest.results
            ):
                raise Agent4TraceabilityGateError("Semantic facts do not use current effective classification")
            chunks[source.source_id] = chunk_set
            effective[source.source_id] = effective_manifest
            semantic[source.source_id] = semantic_manifest
            evidence[f"chunks:{source.source_id}"] = chunk_set.chunk_set_fingerprint
            evidence[f"effective:{source.source_id}"] = effective_fp
            evidence[f"semantic:{source.source_id}"] = self._semantic_fingerprint(semantic_manifest)
        return chunks, effective, semantic, dict(sorted(evidence.items()))

    @staticmethod
    def _semantic_fingerprint(manifest):
        payload = manifest.model_dump(mode="json", exclude={"processed_at"})
        for result in payload.get("results", []):
            result.pop("processed_at", None)
            generation = result.get("generation", {})
            generation.pop("generation_duration_ms", None)
        return fingerprint(payload)

    @staticmethod
    def _cache_matches(cached, candidate):
        if cached is None or cached.input_fingerprint != candidate.input_fingerprint:
            return False
        return cached.model_dump(exclude={"built_at"}) == candidate.model_dump(exclude={"built_at"})
