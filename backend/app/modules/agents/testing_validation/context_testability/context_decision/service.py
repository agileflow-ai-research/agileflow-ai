from datetime import datetime, timezone
from threading import RLock

from app.modules.agents.testing_validation.context_testability.feasibility.constants import (
    FEASIBILITY_ENGINE_VERSION,
    FEASIBILITY_POLICY_VERSION,
    FEASIBILITY_SCHEMA_VERSION,
    TECHNOLOGY_CATALOG_VERSION,
)
from app.modules.agents.testing_validation.context_testability.testability.constants import (
    OUTPUT_POLICY_VERSION,
    TESTABILITY_ENGINE_VERSION,
    TESTABILITY_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    deterministic_id,
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.constants import (
    LEXICAL_POLICY_VERSION,
    TRACEABILITY_ENGINE_VERSION,
    TRACEABILITY_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.context_testability.feasibility.schemas import (
    RepresentationRecommendation,
)
from app.modules.agents.testing_validation.workflow.digests import output_selection_digest
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4PipelineStatus,
    Agent4TestGenerationNodeId,
    Agent4WorkflowNodeStatus,
)

from .constants import (
    CONTEXT_DECISION_ENGINE_VERSION,
    CONTEXT_DECISION_POLICY_VERSION,
    CONTEXT_DECISION_SCHEMA_VERSION,
    ConsolidatedFindingSeverity,
)
from .engine import ContextDecisionInputError, consolidate_context_decision
from .schemas import Agent4ContextDecisionResult


CONTEXT_DECISION_LOCK = RLock()


class Agent4ContextDecisionGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def _result_fingerprint(result):
    return fingerprint(result.model_dump(mode="json", exclude={"evaluated_at"}))


def _traceability_fingerprint(result):
    return fingerprint(result.model_dump(mode="json", exclude={"built_at"}))


class Agent4ContextDecisionService:
    def __init__(self, workflow_service, workflow_storage, traceability_storage,
                 testability_storage, feasibility_storage, decision_storage,
                 *, clock=utc_now):
        self._workflow_service = workflow_service
        self._workflows = workflow_storage
        self._traceability = traceability_storage
        self._testability = testability_storage
        self._feasibility = feasibility_storage
        self._storage = decision_storage
        self._clock = clock

    def evaluate(self, project_id, user, *, force=False):
        # This ownership/type/archive check is read-only. N4.4 deliberately has
        # no dependency on any TR1/TB1/FB1 build or evaluate service.
        self._workflow_service.get(project_id, user)
        with CONTEXT_DECISION_LOCK:
            record = self._workflows.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            self._validate_workflow(record)
            confirmation = record.n1_confirmation
            graph = self._traceability.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            testability = self._testability.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            feasibility = self._feasibility.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            if graph is None or testability is None or feasibility is None:
                raise Agent4ContextDecisionGateError("Current persisted TR1, TB1, and FB1 artifacts are required")

            graph_fp = _traceability_fingerprint(graph)
            testability_fp = _result_fingerprint(testability)
            feasibility_fp = _result_fingerprint(feasibility)
            self._validate_upstream(
                project_id, record, confirmation, graph, graph_fp,
                testability, testability_fp, feasibility,
            )
            input_fp = fingerprint({
                "schema": CONTEXT_DECISION_SCHEMA_VERSION,
                "engine": CONTEXT_DECISION_ENGINE_VERSION,
                "policy": CONTEXT_DECISION_POLICY_VERSION,
                "confirmation_id": confirmation.confirmation_id,
                "selection_revision": confirmation.selection_revision,
                "selection_digest": confirmation.selection_digest,
                "selected_outputs": [item.value for item in confirmation.selected_outputs],
                "traceability_input_fingerprint": graph.input_fingerprint,
                "traceability_manifest_fingerprint": graph_fp,
                "testability_input_fingerprint": testability.input_fingerprint,
                "testability_result_fingerprint": testability_fp,
                "feasibility_input_fingerprint": feasibility.input_fingerprint,
                "feasibility_result_fingerprint": feasibility_fp,
            })
            cached = self._storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            if not force and self._cache_matches(
                cached, input_fp, graph_fp, testability_fp, feasibility_fp,
                testability, feasibility,
            ):
                return cached

            try:
                profiles, planning, findings, overall = consolidate_context_decision(
                    confirmation.selected_outputs, testability, feasibility
                )
            except ContextDecisionInputError as exc:
                raise Agent4ContextDecisionGateError(str(exc)) from exc
            candidate = Agent4ContextDecisionResult(
                schema_version=CONTEXT_DECISION_SCHEMA_VERSION,
                engine_version=CONTEXT_DECISION_ENGINE_VERSION,
                policy_version=CONTEXT_DECISION_POLICY_VERSION,
                agent_project_id=project_id,
                confirmation_id=confirmation.confirmation_id,
                selection_revision=confirmation.selection_revision,
                selected_outputs_digest=confirmation.selection_digest,
                selected_outputs=confirmation.selected_outputs,
                traceability_input_fingerprint=graph.input_fingerprint,
                traceability_manifest_fingerprint=graph_fp,
                testability_input_fingerprint=testability.input_fingerprint,
                testability_result_fingerprint=testability_fp,
                feasibility_input_fingerprint=feasibility.input_fingerprint,
                feasibility_result_fingerprint=feasibility_fp,
                output_profiles=profiles,
                planning_profiles=planning,
                overall_decision=overall,
                planning_allowed_output_count=sum(item.planning_allowed for item in profiles),
                blocked_output_count=sum(not item.planning_allowed for item in profiles),
                blocking_count=sum(
                    item.severity is ConsolidatedFindingSeverity.BLOCKING for item in findings
                ),
                executable_output_count=sum(
                    item.recommended_representation is RepresentationRecommendation.EXECUTABLE_CODE
                    for item in profiles
                ),
                specification_output_count=sum(
                    item.recommended_representation is RepresentationRecommendation.SPECIFICATION
                    for item in profiles
                ),
                structured_artifact_count=sum(
                    item.recommended_representation is RepresentationRecommendation.STRUCTURED_ARTIFACT
                    for item in profiles
                ),
                warning_count=sum(
                    item.severity is ConsolidatedFindingSeverity.WARNING for item in findings
                ),
                consolidated_findings=findings,
                input_fingerprint=input_fp,
                evaluated_at=self._clock(),
            )
            self._storage.save(candidate, owner_user_id=user.user_id)
            return candidate

    @staticmethod
    def _validate_workflow(record):
        if record is None or record.n1_confirmation is None:
            raise Agent4ContextDecisionGateError("Confirmed selected outputs are required")
        confirmation = record.n1_confirmation
        if (
            not confirmation.selected_outputs
            or confirmation.selection_digest != output_selection_digest(confirmation.selected_outputs)
            or confirmation.selection_revision != record.selection_revision
            or confirmation.selected_outputs != record.selected_outputs
        ):
            raise Agent4ContextDecisionGateError("Confirmed selected outputs are stale")
        expected = (
            Agent4WorkflowNodeStatus.COMPLETED,
            Agent4WorkflowNodeStatus.COMPLETED,
            Agent4WorkflowNodeStatus.COMPLETED,
            Agent4WorkflowNodeStatus.NOT_STARTED,
            Agent4WorkflowNodeStatus.LOCKED,
            Agent4WorkflowNodeStatus.LOCKED,
        )
        if (
            tuple(item.status for item in record.nodes) != expected
            or record.current_node_id is not Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            or record.pipeline_status is not Agent4PipelineStatus.RUNNING
        ):
            raise Agent4ContextDecisionGateError("N4.4 requires the current unstarted N4 workflow boundary")

    @staticmethod
    def _validate_upstream(project_id, record, confirmation, graph, graph_fp,
                           testability, testability_fp, feasibility):
        outputs = confirmation.selected_outputs
        if (
            graph.schema_version != TRACEABILITY_SCHEMA_VERSION
            or graph.engine_version != TRACEABILITY_ENGINE_VERSION
            or graph.lexical_policy_version != LEXICAL_POLICY_VERSION
            or graph.agent_project_id != project_id
            or graph.confirmation_id != confirmation.confirmation_id
            or graph.n2_execution_id != record.current_n2_execution_id
            or graph.n3_execution_id != record.current_n3_execution_id
        ):
            raise Agent4ContextDecisionGateError("Current persisted TR1 artifact is required")
        if (
            testability.schema_version != TESTABILITY_SCHEMA_VERSION
            or testability.engine_version != TESTABILITY_ENGINE_VERSION
            or testability.output_policy_version != OUTPUT_POLICY_VERSION
            or testability.agent_project_id != project_id
            or testability.confirmation_id != confirmation.confirmation_id
            or testability.selection_revision != confirmation.selection_revision
            or testability.selected_outputs_digest != confirmation.selection_digest
            or testability.confirmed_selected_outputs != outputs
            or testability.traceability_input_fingerprint != graph.input_fingerprint
            or testability.traceability_manifest_fingerprint != graph_fp
        ):
            raise Agent4ContextDecisionGateError("Current persisted TB1 artifact is required")
        if (
            feasibility.schema_version != FEASIBILITY_SCHEMA_VERSION
            or feasibility.engine_version != FEASIBILITY_ENGINE_VERSION
            or feasibility.policy_version != FEASIBILITY_POLICY_VERSION
            or feasibility.technology_catalog_version != TECHNOLOGY_CATALOG_VERSION
            or feasibility.agent_project_id != project_id
            or feasibility.confirmation_id != confirmation.confirmation_id
            or feasibility.selection_revision != confirmation.selection_revision
            or feasibility.selected_outputs_digest != confirmation.selection_digest
            or feasibility.selected_outputs != outputs
            or feasibility.traceability_manifest_fingerprint != graph_fp
            or feasibility.testability_input_fingerprint != testability.input_fingerprint
            or feasibility.testability_result_fingerprint != testability_fp
        ):
            raise Agent4ContextDecisionGateError("Current persisted FB1 artifact is required")
        if (
            len(testability.output_assessments) != len(outputs)
            or len(feasibility.output_assessments) != len(outputs)
            or [item.output_code for item in testability.output_assessments] != outputs
            or [item.output_code for item in feasibility.output_assessments] != outputs
        ):
            raise Agent4ContextDecisionGateError("Every selected output requires one current TB1 and FB1 assessment")
        tb_findings = {item.finding_id for item in testability.findings}
        fb_findings = {item.finding_id for item in feasibility.findings}
        if any(not set(item.finding_ids).issubset(tb_findings) for item in testability.output_assessments):
            raise Agent4ContextDecisionGateError("TB1 assessment finding reference does not resolve")
        if any(not set(item.finding_ids).issubset(fb_findings) for item in feasibility.output_assessments):
            raise Agent4ContextDecisionGateError("FB1 assessment finding reference does not resolve")

    @staticmethod
    def _cache_matches(cached, input_fp, graph_fp, testability_fp, feasibility_fp,
                       testability, feasibility):
        if (
            cached is None
            or cached.input_fingerprint != input_fp
            or cached.traceability_manifest_fingerprint != graph_fp
            or cached.testability_result_fingerprint != testability_fp
            or cached.feasibility_result_fingerprint != feasibility_fp
            or cached.selected_outputs != testability.confirmed_selected_outputs
        ):
            return False
        known = {
            item.finding_id for item in testability.findings
        } | {item.finding_id for item in feasibility.findings}
        tb_refs = {
            item.output_code: deterministic_id("A4TBA", item.model_dump(mode="json"))
            for item in testability.output_assessments
        }
        fb_refs = {
            item.output_code: deterministic_id("A4FBA", item.model_dump(mode="json"))
            for item in feasibility.output_assessments
        }
        return all(
            all(ref.origin_finding_id in known for ref in item.origin_references)
            for item in cached.consolidated_findings
        ) and all(
            item.testability_assessment_ref == tb_refs.get(item.output_code)
            and item.feasibility_assessment_ref == fb_refs.get(item.output_code)
            for item in cached.output_profiles
        )
