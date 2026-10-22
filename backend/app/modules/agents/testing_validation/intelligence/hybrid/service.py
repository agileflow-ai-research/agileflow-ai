import hashlib
import json
from datetime import datetime, timezone
from threading import RLock

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.intelligence.rules.catalog import (
    AGENT4_RULE_CATALOG_FINGERPRINT,
    AGENT4_RULES_VERSION,
)
from app.modules.agents.testing_validation.intelligence.rules.service import (
    Agent4RuleClassificationService,
)
from app.modules.agents.testing_validation.intelligence.rules.storage import Agent4RuleStorage
from app.modules.agents.testing_validation.intelligence.zero_shot import constants as zc
from app.modules.agents.testing_validation.intelligence.zero_shot.classifier import (
    inference_configuration_fingerprint,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.service import (
    Agent4ZeroShotService,
)
from app.modules.agents.testing_validation.intelligence.zero_shot.storage import (
    Agent4ZeroShotStorage,
)
from app.modules.agents.testing_validation.preparation.chunking.storage import Agent4ChunkStorage
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

from .engine import decide_hybrid_for_chunk
from .policy import H1_POLICY, HYBRID_POLICY_FINGERPRINT
from .schemas import HybridPolicyMetadata, TestingHybridManifest, build_review_summaries
from .storage import Agent4HybridStorage


HYBRID_CLASSIFICATION_LOCK = RLock()


class Agent4HybridClassificationGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def manifest_fingerprint(manifest) -> str:
    canonical = json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Agent4HybridClassificationService:
    def __init__(self, standalone_service: StandaloneService,
                 workflow_storage: Agent4WorkflowStorage,
                 chunk_storage: Agent4ChunkStorage,
                 rule_storage: Agent4RuleStorage,
                 zero_shot_storage: Agent4ZeroShotStorage,
                 storage: Agent4HybridStorage, *, clock=utc_now):
        self._standalone = standalone_service
        self._workflows = workflow_storage
        self._chunks = chunk_storage
        self._rules = rule_storage
        self._zero_shot = zero_shot_storage
        self._storage = storage
        self._clock = clock

    def build(self, agent_project_id: str, source_id: str,
              current_user: UserPublicResponse, *, force=False):
        with AGENT4_WORKFLOW_STATE_LOCK, HYBRID_CLASSIFICATION_LOCK:
            chunks, rules, model = self._resolve(
                agent_project_id, source_id, current_user
            )
            rule_fingerprint = manifest_fingerprint(rules)
            model_fingerprint = manifest_fingerprint(model)
            if not force:
                cached = self._storage.load(
                    agent_project_id=agent_project_id,
                    owner_user_id=current_user.user_id,
                    source_id=source_id,
                )
                if self._cache_is_current(
                    cached, chunks, rules, model, rule_fingerprint, model_fingerprint
                ):
                    return cached
            now = self._clock()
            results = [
                decide_hybrid_for_chunk(rule, zero, processed_at=now)
                for rule, zero in zip(rules.results, model.results, strict=True)
            ]
            chunk_summaries, summary = build_review_summaries(results)
            manifest = TestingHybridManifest(
                taxonomy_version="T1",
                hybrid_policy_version=H1_POLICY.version,
                hybrid_policy_fingerprint=HYBRID_POLICY_FINGERPRINT,
                policy=HybridPolicyMetadata(
                    semantics=H1_POLICY.semantics,
                    rule_model_support_threshold=H1_POLICY.rule_model_support_threshold,
                    rule_model_conflict_threshold=H1_POLICY.rule_model_conflict_threshold,
                    model_only_review_threshold=H1_POLICY.model_only_review_threshold,
                    decision_rules_version=H1_POLICY.decision_rules_version,
                    non_testable_policy=H1_POLICY.non_testable_policy,
                ),
                rules_version=rules.rules_version,
                rule_catalog_fingerprint=rules.rule_catalog_fingerprint,
                rule_manifest_fingerprint=rule_fingerprint,
                zero_shot_version=model.zero_shot_version,
                zero_shot_config_fingerprint=model.configuration_fingerprint,
                zero_shot_manifest_fingerprint=model_fingerprint,
                model_id=model.model_id,
                model_revision=model.model_revision,
                agent_project_id=agent_project_id,
                source_id=source_id,
                chunk_set_fingerprint=chunks.chunk_set_fingerprint,
                chunk_ids=chunks.chunk_ids,
                results=results,
                chunk_summaries=chunk_summaries,
                summary=summary,
                processed_at=now,
            )
            self._storage.save(manifest, owner_user_id=current_user.user_id)
            return manifest

    def _resolve(self, project_id, source_id, user):
        project = self._standalone.require_active_project(user.user_id, project_id)
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise Agent4HybridClassificationGateError(
                "Agent project must have agent_type TESTING_VALIDATION"
            )
        if project.agent_stage is not AgentStage.TEST_GENERATION:
            raise Agent4HybridClassificationGateError(
                "Agent project must have agent_stage TEST_GENERATION"
            )
        workflow = self._workflows.load(
            agent_project_id=project_id, owner_user_id=user.user_id
        )
        confirmation = workflow.n1_confirmation if workflow else None
        if workflow is None or confirmation is None or source_id not in confirmation.source_ids:
            raise Agent4HybridClassificationGateError(
                "Source is not present in the confirmed setup"
            )
        n2 = next(node for node in workflow.nodes
                  if node.node_id is Agent4TestGenerationNodeId.INPUT_PREPARATION)
        execution = next((item for item in workflow.n2_executions
                          if item.execution_id == workflow.current_n2_execution_id), None)
        if (n2.status is not Agent4WorkflowNodeStatus.COMPLETED
                or execution is None
                or execution.status is not Agent4N2ExecutionStatus.COMPLETED):
            raise Agent4HybridClassificationGateError(
                "Input Preparation must complete before hybrid classification"
            )
        chunks = self._chunks.load(
            agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id
        )
        rules = self._rules.load(
            agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id
        )
        model = self._zero_shot.load(
            agent_project_id=project_id, owner_user_id=user.user_id, source_id=source_id
        )
        if chunks is None:
            raise Agent4HybridClassificationGateError("Current prepared chunks are unavailable")
        if rules is None:
            raise Agent4HybridClassificationGateError("Current rule classification is required")
        if model is None:
            raise Agent4HybridClassificationGateError("Current zero-shot classification is required")
        if not Agent4RuleClassificationService._cache_is_current(rules, chunks):
            raise Agent4HybridClassificationGateError("Rule classification is stale")
        if not Agent4ZeroShotService._cache_is_current(model, chunks):
            raise Agent4HybridClassificationGateError("Zero-shot classification is stale")
        if (
            rules.agent_project_id != model.agent_project_id
            or rules.source_id != model.source_id
            or rules.chunk_set_fingerprint != model.chunk_set_fingerprint
            or rules.chunk_ids != model.chunk_ids
        ):
            raise Agent4HybridClassificationGateError(
                "Rule and zero-shot manifests do not describe identical evidence"
            )
        return chunks, rules, model

    @staticmethod
    def _cache_is_current(cached, chunks, rules, model, rule_fingerprint, model_fingerprint):
        if cached is None:
            return False
        return (
            cached.hybrid_policy_version == H1_POLICY.version
            and cached.hybrid_policy_fingerprint == HYBRID_POLICY_FINGERPRINT
            and cached.policy.rule_model_support_threshold == H1_POLICY.rule_model_support_threshold
            and cached.policy.rule_model_conflict_threshold == H1_POLICY.rule_model_conflict_threshold
            and cached.policy.model_only_review_threshold == H1_POLICY.model_only_review_threshold
            and cached.rules_version == AGENT4_RULES_VERSION
            and cached.rule_catalog_fingerprint == AGENT4_RULE_CATALOG_FINGERPRINT
            and cached.rule_manifest_fingerprint == rule_fingerprint
            and cached.zero_shot_version == zc.ZERO_SHOT_STAGE_VERSION
            and cached.zero_shot_config_fingerprint == inference_configuration_fingerprint()
            and cached.zero_shot_manifest_fingerprint == model_fingerprint
            and cached.chunk_set_fingerprint == chunks.chunk_set_fingerprint
            and cached.chunk_ids == chunks.chunk_ids
            and len(cached.results) == len(chunks.chunks)
            and all(len(result.decisions) == 15 for result in cached.results)
        )
