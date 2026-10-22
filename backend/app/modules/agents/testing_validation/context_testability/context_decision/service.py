"""
N4.4 Context Decision service (CD1): consolidates persisted TR1, TB1, and FB1.

N4.4 does NOT reassess requirements. It reads the three persisted N4 manifests,
checks that they belong to the current confirmed selection and workflow boundary,
and writes one consolidated context-decision.json.

Pipeline position: N3 completed -> N4.1 TR1 -> N4.2 TB1 -> N4.3 FB1 -> N4.4 CD1.
The service has no dependency on the TR1, TB1, or FB1 build/evaluate services,
so it cannot silently rerun or reinterpret earlier N4 decisions.
"""

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
    """
    Produces the N4.4 CD1 context decision for the current selection.

    Only persisted artifacts are read. TR1, TB1, and FB1 are never recomputed here.
    """

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
        """
        Build or reuse the CD1 context decision.

        Gates (all before any consolidation):
          - the confirmed selected outputs are current (digest and revision match);
          - the workflow is at the N4 boundary (N4 NOT_STARTED, CONTEXT_TESTABILITY current);
          - TR1, TB1, and FB1 are persisted, and each one's schema, engine, and
            policy versions match, and each one references the current confirmation,
            selection, and upstream fingerprints.
        Stale or missing evidence raises Agent4ContextDecisionGateError. That is a
        precondition failure, not a BLOCKED context decision, so no decision is saved.

        Cache: reused when the input fingerprint and the upstream result fingerprints
        match. The evaluation timestamp is excluded from every identity.
        """
        # This ownership/type/archive check is read-only. N4.4 deliberately has
        # no dependency on any TR1/TB1/FB1 build or evaluate service.
        self._workflow_service.get(project_id, user)
        with CONTEXT_DECISION_LOCK:
            record = self._workflows.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            self._validate_workflow(record)
            confirmation = record.n1_confirmation
            # N4.4 intentionally reads persisted upstream manifests instead of invoking
            # TR1/TB1/FB1 evaluators. This guarantees consolidation cannot silently rerun or
            # reinterpret earlier N4 decisions.
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
            # The input fingerprint binds the decision to the exact selection and
            # to the TR1/TB1/FB1 fingerprints it consumed.
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

            # Deterministic consolidation only. CD1 is pure over the persisted inputs.
            # The engine's ContextDecisionInputError is an input contradiction (for
            # example, FB1 NOT_READY without TB1 NOT_READY), so it is raised as a gate error.
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
        """
        Confirm the N4 boundary. N1-N3 must be COMPLETED, N4 must be NOT_STARTED
        and current, and N5/N6 must still be LOCKED. This keeps CD1 from running
        after N4 has already advanced or after the selection changed.
        """
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
        statuses = tuple(item.status for item in record.nodes)
        if (
            statuses[:3] != (Agent4WorkflowNodeStatus.COMPLETED,) * 3
            or statuses[3] not in {
                Agent4WorkflowNodeStatus.NOT_STARTED,
                Agent4WorkflowNodeStatus.RUNNING,
            }
            or statuses[4:] != (Agent4WorkflowNodeStatus.LOCKED,) * 2
            or record.current_node_id is not Agent4TestGenerationNodeId.CONTEXT_TESTABILITY
            or record.pipeline_status is not Agent4PipelineStatus.RUNNING
        ):
            raise Agent4ContextDecisionGateError("N4.4 requires the current N4 workflow boundary")

    @staticmethod
    def _validate_upstream(project_id, record, confirmation, graph, graph_fp,
                           testability, testability_fp, feasibility):
        """
        Provenance check. Each upstream manifest must reference the same project,
        confirmation, selection revision and digest, and fingerprints. It also
        requires one TB1 and one FB1 assessment per selected output, and every
        finding reference must resolve to a persisted finding.
        """
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
        """
        Reuse check for a stored CD1 result. Verifies the input fingerprint,
        the upstream fingerprints, and that every stored origin/assessment reference
        still points at a persisted TB1/FB1 item. The check does not rebuild anything.
        """
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
