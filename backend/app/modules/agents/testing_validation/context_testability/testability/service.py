from datetime import datetime, timezone
from threading import RLock

from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.constants import (
    TRACEABILITY_ENGINE_VERSION,
    TRACEABILITY_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.workflow.digests import (
    output_selection_digest,
)

from .constants import (
    OUTPUT_POLICY_VERSION,
    TESTABILITY_ENGINE_VERSION,
    TESTABILITY_SCHEMA_VERSION,
)
from .engine import build_evidence_inventory, evaluate_testability
from .schemas import Agent4TestabilityResult, TestabilityFindingSeverity


TESTABILITY_LOCK = RLock()


class Agent4TestabilityGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def traceability_manifest_fingerprint(graph):
    return fingerprint(graph.model_dump(mode="json", exclude={"built_at"}))


class Agent4TestabilityService:
    def __init__(self, workflow_service, workflow_storage, traceability_service,
                 testability_storage, *, clock=utc_now):
        self._workflow_service = workflow_service
        self._workflows = workflow_storage
        self._traceability = traceability_service
        self._storage = testability_storage
        self._clock = clock

    def evaluate(self, project_id, user, *, force=False):
        # Owner, project type/stage, archive state, and N1-N4 lifecycle are
        # enforced by the workflow and TR1 services. No client evidence enters here.
        self._workflow_service.get(project_id, user)
        with TESTABILITY_LOCK:
            record = self._workflows.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            graph = self._traceability.build(project_id, user)
            confirmation = record.n1_confirmation if record else None
            if confirmation is None or not confirmation.selected_outputs:
                raise Agent4TestabilityGateError("Confirmed selected outputs are required")
            expected_digest = output_selection_digest(confirmation.selected_outputs)
            if (
                confirmation.selection_digest != expected_digest
                or confirmation.selection_revision != record.selection_revision
                or confirmation.selected_outputs != record.selected_outputs
            ):
                raise Agent4TestabilityGateError("Confirmed selected outputs are stale")
            if (
                graph.schema_version != TRACEABILITY_SCHEMA_VERSION
                or graph.engine_version != TRACEABILITY_ENGINE_VERSION
                or graph.agent_project_id != project_id
                or graph.confirmation_id != confirmation.confirmation_id
                or graph.n2_execution_id != record.current_n2_execution_id
                or graph.n3_execution_id != record.current_n3_execution_id
            ):
                raise Agent4TestabilityGateError("Current TR1 traceability evidence is required")

            graph_fingerprint = traceability_manifest_fingerprint(graph)
            input_fingerprint = fingerprint({
                "schema": TESTABILITY_SCHEMA_VERSION,
                "engine": TESTABILITY_ENGINE_VERSION,
                "policy": OUTPUT_POLICY_VERSION,
                "confirmation_id": confirmation.confirmation_id,
                "selection_revision": confirmation.selection_revision,
                "selection_digest": confirmation.selection_digest,
                "selected_outputs": [item.value for item in confirmation.selected_outputs],
                "traceability_input_fingerprint": graph.input_fingerprint,
                "traceability_manifest_fingerprint": graph_fingerprint,
            })
            cached = self._storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            inventory = build_evidence_inventory(graph)
            assessments, findings, overall = evaluate_testability(
                confirmation.selected_outputs, inventory, graph,
                graph_fingerprint=graph_fingerprint,
            )
            candidate = Agent4TestabilityResult(
                schema_version=TESTABILITY_SCHEMA_VERSION,
                engine_version=TESTABILITY_ENGINE_VERSION,
                output_policy_version=OUTPUT_POLICY_VERSION,
                agent_project_id=project_id,
                confirmation_id=confirmation.confirmation_id,
                selection_revision=confirmation.selection_revision,
                selected_outputs_digest=confirmation.selection_digest,
                confirmed_selected_outputs=confirmation.selected_outputs,
                traceability_input_fingerprint=graph.input_fingerprint,
                traceability_manifest_fingerprint=graph_fingerprint,
                traceability_finding_ids=sorted(
                    [item.unresolved_id for item in graph.unresolved_references]
                    + [item.ambiguity_id for item in graph.ambiguities]
                ),
                evidence_inventory=list(inventory.items),
                output_assessments=assessments,
                overall_status=overall,
                blocking_finding_count=sum(
                    item.severity is TestabilityFindingSeverity.BLOCKING
                    for item in findings
                ),
                warning_count=sum(
                    item.severity is TestabilityFindingSeverity.WARNING
                    for item in findings
                ),
                findings=findings,
                input_fingerprint=input_fingerprint,
                evaluated_at=self._clock(),
            )
            if not force and self._cache_matches(cached, candidate):
                return cached
            self._storage.save(candidate, owner_user_id=user.user_id)
            return candidate

    @staticmethod
    def _cache_matches(cached, candidate):
        if cached is None or cached.input_fingerprint != candidate.input_fingerprint:
            return False
        return cached.model_dump(exclude={"evaluated_at"}) == candidate.model_dump(
            exclude={"evaluated_at"}
        )
