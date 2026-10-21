from datetime import datetime, timezone
from threading import RLock

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.intelligence.hybrid.service import (
    Agent4HybridClassificationService,
    manifest_fingerprint,
)
from app.modules.agents.testing_validation.intelligence.hybrid.storage import Agent4HybridStorage
from app.modules.agents.testing_validation.intelligence.rules.service import Agent4RuleClassificationService
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.zero_shot.service import Agent4ZeroShotService
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import Agent4ZeroShotStorage
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
from .eligibility import semantic_classification_context
from .extractor import (
    _fact_id, _ground, _result_id, disposition_result, extract_semantic_result,
    generation_configuration_fingerprint,
)
from .runtime import Agent4QwenRuntime
from .schemas import (
    SemanticEligibility, SemanticFactCandidate, SemanticGenerationPolicyMetadata,
    SemanticManifestMetrics, SemanticResultStatus, TestingSemanticManifest,
)
from .storage import Agent4SemanticStorage


SEMANTIC_FACT_LOCK = RLock()


class Agent4SemanticGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


class Agent4SemanticFactService:
    def __init__(self, standalone_service: StandaloneService,
                 workflow_storage: Agent4WorkflowStorage,
                 chunk_storage: Agent4ChunkStorage,
                 rule_storage: Agent4RuleStorage,
                 zero_shot_storage: Agent4ZeroShotStorage,
                 hybrid_storage: Agent4HybridStorage,
                 storage: Agent4SemanticStorage,
                 runtime=None, *, clock=utc_now):
        self._standalone = standalone_service
        self._workflows = workflow_storage
        self._chunks = chunk_storage
        self._rules = rule_storage
        self._zero = zero_shot_storage
        self._hybrid = hybrid_storage
        self._storage = storage
        self._runtime = runtime or Agent4QwenRuntime(
            local_files_only=constants.LOCAL_FILES_ONLY
        )
        self._clock = clock

    def build(self, project_id: str, source_id: str,
              user: UserPublicResponse, *, force=False):
        with AGENT4_WORKFLOW_STATE_LOCK, SEMANTIC_FACT_LOCK:
            chunks, rules, zero, hybrid = self._resolve(project_id, source_id, user)
            hybrid_fingerprint = manifest_fingerprint(hybrid)
            if not force:
                cached = self._storage.load(
                    agent_project_id=project_id, owner_user_id=user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(cached, chunks, hybrid, hybrid_fingerprint):
                    return cached
            now = self._clock()
            hybrid_by_id = {result.chunk.chunk_id: result for result in hybrid.results}
            results = []
            eligible = []
            waiting = []
            not_applicable = []
            for chunk in chunks.chunks:
                hybrid_result = hybrid_by_id[chunk.chunk_id]
                context = semantic_classification_context(hybrid_result)
                if context.eligibility is SemanticEligibility.ELIGIBLE:
                    eligible.append(chunk.chunk_id)
                    result = extract_semantic_result(
                        chunk=chunk, chunk_reference=hybrid_result.chunk,
                        hybrid_result=hybrid_result,
                        accepted_labels=context.accepted_labels,
                        runtime=self._runtime, processed_at=now,
                    )
                elif context.eligibility is SemanticEligibility.WAITING_FOR_CLASSIFICATION_REVIEW:
                    waiting.append(chunk.chunk_id)
                    result = disposition_result(
                        chunk_reference=hybrid_result.chunk,
                        hybrid_result=hybrid_result,
                        accepted_labels=context.accepted_labels,
                        status=SemanticResultStatus.WAITING_FOR_CLASSIFICATION_REVIEW,
                        processed_at=now,
                    )
                else:
                    not_applicable.append(chunk.chunk_id)
                    result = disposition_result(
                        chunk_reference=hybrid_result.chunk,
                        hybrid_result=hybrid_result,
                        accepted_labels=[], status=SemanticResultStatus.NOT_APPLICABLE,
                        processed_at=now,
                    )
                results.append(result)
            metrics = SemanticManifestMetrics(
                chunk_count=len(results), eligible_count=len(eligible),
                waiting_review_count=len(waiting),
                not_applicable_count=len(not_applicable),
                fact_count=sum(len(result.facts) for result in results),
                warning_count=sum(len(result.warnings) for result in results),
            )
            manifest = TestingSemanticManifest(
                semantic_stage_version=constants.SEMANTIC_STAGE_VERSION,
                prompt_version=constants.SEMANTIC_PROMPT_VERSION,
                grounding_version=constants.SEMANTIC_GROUNDING_VERSION,
                generation_policy_version=constants.SEMANTIC_GENERATION_POLICY_VERSION,
                model_id=constants.SEMANTIC_MODEL_ID,
                model_revision=constants.SEMANTIC_MODEL_REVISION,
                generation_configuration_fingerprint=generation_configuration_fingerprint(),
                generation_policy=SemanticGenerationPolicyMetadata(
                    do_sample=False,
                    max_input_tokens=constants.MAX_SEMANTIC_INPUT_TOKENS,
                    max_new_tokens=constants.MAX_SEMANTIC_NEW_TOKENS,
                    max_attempts=constants.MAX_SEMANTIC_ATTEMPTS,
                    local_files_only=True,
                ),
                agent_project_id=project_id, source_id=source_id,
                chunk_set_fingerprint=chunks.chunk_set_fingerprint,
                hybrid_manifest_fingerprint=hybrid_fingerprint,
                chunk_ids=chunks.chunk_ids, eligible_chunk_ids=eligible,
                waiting_review_chunk_ids=waiting,
                not_applicable_chunk_ids=not_applicable,
                results=results, metrics=metrics, processed_at=now,
            )
            self._storage.save(manifest, owner_user_id=user.user_id)
            return manifest

    def _resolve(self, project_id, source_id, user):
        project = self._standalone.require_active_project(user.user_id, project_id)
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise Agent4SemanticGateError("Agent project must have agent_type TESTING_VALIDATION")
        if project.agent_stage is not AgentStage.TEST_GENERATION:
            raise Agent4SemanticGateError("Agent project must have agent_stage TEST_GENERATION")
        workflow = self._workflows.load(agent_project_id=project_id, owner_user_id=user.user_id)
        confirmation = workflow.n1_confirmation if workflow else None
        if workflow is None or confirmation is None or source_id not in confirmation.source_ids:
            raise Agent4SemanticGateError("Source is not present in the confirmed setup")
        n2 = next(node for node in workflow.nodes
                  if node.node_id is Agent4TestGenerationNodeId.INPUT_PREPARATION)
        execution = next((item for item in workflow.n2_executions
                          if item.execution_id == workflow.current_n2_execution_id), None)
        if (n2.status is not Agent4WorkflowNodeStatus.COMPLETED or execution is None
                or execution.status is not Agent4N2ExecutionStatus.COMPLETED):
            raise Agent4SemanticGateError("Input Preparation must complete before semantic extraction")
        chunks = self._chunks.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id)
        rules = self._rules.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id)
        zero = self._zero.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id)
        hybrid = self._hybrid.load(agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id)
        if chunks is None or rules is None or zero is None or hybrid is None:
            raise Agent4SemanticGateError("Current hybrid classification evidence is required")
        if not Agent4RuleClassificationService._cache_is_current(rules, chunks):
            raise Agent4SemanticGateError("Rule classification is stale")
        if not Agent4ZeroShotService._cache_is_current(zero, chunks):
            raise Agent4SemanticGateError("Zero-shot classification is stale")
        if not Agent4HybridClassificationService._cache_is_current(
            hybrid, chunks, rules, zero,
            manifest_fingerprint(rules), manifest_fingerprint(zero),
        ):
            raise Agent4SemanticGateError("Hybrid classification is stale")
        return chunks, rules, zero, hybrid

    @staticmethod
    def _cache_is_current(cached, chunks, hybrid, hybrid_fingerprint):
        if cached is None or (
            cached.semantic_stage_version != constants.SEMANTIC_STAGE_VERSION
            or cached.prompt_version != constants.SEMANTIC_PROMPT_VERSION
            or cached.grounding_version != constants.SEMANTIC_GROUNDING_VERSION
            or cached.model_id != constants.SEMANTIC_MODEL_ID
            or cached.model_revision != constants.SEMANTIC_MODEL_REVISION
            or cached.generation_configuration_fingerprint != generation_configuration_fingerprint()
            or cached.chunk_set_fingerprint != chunks.chunk_set_fingerprint
            or cached.hybrid_manifest_fingerprint != hybrid_fingerprint
            or cached.chunk_ids != chunks.chunk_ids
            or len(cached.results) != len(chunks.chunks)
        ):
            return False
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks.chunks}
        hybrid_by_id = {result.chunk.chunk_id: result for result in hybrid.results}
        try:
            contexts = {
                chunk_id: semantic_classification_context(result)
                for chunk_id, result in hybrid_by_id.items()
            }
            if cached.eligible_chunk_ids != [
                chunk_id for chunk_id in chunks.chunk_ids
                if contexts[chunk_id].eligibility is SemanticEligibility.ELIGIBLE
            ]:
                return False
            if cached.waiting_review_chunk_ids != [
                chunk_id for chunk_id in chunks.chunk_ids
                if contexts[chunk_id].eligibility
                is SemanticEligibility.WAITING_FOR_CLASSIFICATION_REVIEW
            ]:
                return False
            if cached.not_applicable_chunk_ids != [
                chunk_id for chunk_id in chunks.chunk_ids
                if contexts[chunk_id].eligibility is SemanticEligibility.NOT_APPLICABLE
            ]:
                return False
            for result in cached.results:
                chunk = chunk_by_id[result.chunk.chunk_id]
                current = hybrid_by_id[result.chunk.chunk_id]
                context = contexts[result.chunk.chunk_id]
                if result.hybrid_result_id != current.result_id:
                    return False
                if result.accepted_labels != context.accepted_labels:
                    return False
                if result.semantic_result_id != _result_id(
                    result.chunk, current.result_id, context.accepted_labels
                ):
                    return False
                if context.eligibility is SemanticEligibility.ELIGIBLE:
                    if result.status not in {
                        SemanticResultStatus.SUCCESS,
                        SemanticResultStatus.SUCCESS_WITH_WARNINGS,
                        SemanticResultStatus.EMPTY,
                    }:
                        return False
                elif context.eligibility is SemanticEligibility.WAITING_FOR_CLASSIFICATION_REVIEW:
                    if result.status is not SemanticResultStatus.WAITING_FOR_CLASSIFICATION_REVIEW:
                        return False
                elif result.status is not SemanticResultStatus.NOT_APPLICABLE:
                    return False
                for fact in result.facts:
                    candidate = SemanticFactCandidate.model_validate(
                        fact.model_dump(exclude={"fact_id"})
                    )
                    grounded = _ground(candidate, chunk.text, context.accepted_labels)
                    if fact.fact_id != _fact_id(chunk.chunk_id, grounded):
                        return False
        except (KeyError, ValidationError, ValueError):
            return False
        return True
