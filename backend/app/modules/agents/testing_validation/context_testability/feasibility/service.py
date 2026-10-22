"""
N4.3 Feasibility service (FB1) for the selected outputs.

Orchestration layer. It loads the TR1 graph and the TB1 result, extracts
technical evidence from the graph, evaluates executable feasibility per output,
and persists feasibility.json. It does not execute any generated or existing
test, and it does not probe the host environment.
"""

from datetime import datetime, timezone
from threading import RLock

from app.modules.agents.testing_validation.context_testability.testability.constants import (
    OUTPUT_POLICY_VERSION,
    TESTABILITY_ENGINE_VERSION,
    TESTABILITY_SCHEMA_VERSION,
)
from app.modules.agents.testing_validation.context_testability.testability.service import (
    traceability_manifest_fingerprint,
)
from app.modules.agents.testing_validation.context_testability.traceability.canonicalization import (
    fingerprint,
)

from .constants import (
    FEASIBILITY_ENGINE_VERSION,
    FEASIBILITY_POLICY_VERSION,
    FEASIBILITY_SCHEMA_VERSION,
    TECHNOLOGY_CATALOG_VERSION,
)
from .engine import evaluate_feasibility
from .extractor import build_technical_evidence_inventory
from .schemas import (
    Agent4FeasibilityResult,
    FeasibilityFindingSeverity,
)


FEASIBILITY_LOCK = RLock()


class Agent4FeasibilityGateError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc)


def testability_result_fingerprint(result):
    return fingerprint(result.model_dump(mode="json", exclude={"evaluated_at"}))


class Agent4FeasibilityService:
    """
    Produces the N4.3 FB1 result for the current selection.

    Depends on the TR1 build and the TB1 evaluate. It requires TB1 to match the
    current confirmation and TR1 fingerprint before FB1 runs.
    """

    def __init__(self, workflow_service, workflow_storage, traceability_service,
                 testability_service, feasibility_storage, *, clock=utc_now):
        self._workflow_service = workflow_service
        self._workflows = workflow_storage
        self._traceability = traceability_service
        self._testability = testability_service
        self._storage = feasibility_storage
        self._clock = clock

    def evaluate(self, project_id, user, *, force=False):
        """
        Build or reuse FB1. The input fingerprint covers the selection, the TR1
        fingerprint, the TB1 result, the technology catalog version, and the
        technical evidence fingerprint. A cache hit requires an identical fingerprint
        and content (ignoring evaluated_at).
        """
        self._workflow_service.get(project_id, user)
        with FEASIBILITY_LOCK:
            record = self._workflows.load(
                agent_project_id=project_id, owner_user_id=user.user_id
            )
            graph = self._traceability.build(project_id, user)
            testability = self._testability.evaluate(project_id, user)
            confirmation = record.n1_confirmation if record else None
            if confirmation is None or not confirmation.selected_outputs:
                raise Agent4FeasibilityGateError("Confirmed selected outputs are required")
            graph_fp = traceability_manifest_fingerprint(graph)
            if (
                testability.schema_version != TESTABILITY_SCHEMA_VERSION
                or testability.engine_version != TESTABILITY_ENGINE_VERSION
                or testability.output_policy_version != OUTPUT_POLICY_VERSION
                or testability.agent_project_id != project_id
                or testability.confirmation_id != confirmation.confirmation_id
                or testability.selection_revision != confirmation.selection_revision
                or testability.selected_outputs_digest != confirmation.selection_digest
                or testability.confirmed_selected_outputs != confirmation.selected_outputs
                or testability.traceability_manifest_fingerprint != graph_fp
            ):
                raise Agent4FeasibilityGateError("Current TB1 testability evidence is required")

            technical = build_technical_evidence_inventory(graph)
            testability_fp = testability_result_fingerprint(testability)
            input_fingerprint = fingerprint({
                "schema": FEASIBILITY_SCHEMA_VERSION,
                "engine": FEASIBILITY_ENGINE_VERSION,
                "policy": FEASIBILITY_POLICY_VERSION,
                "technology_catalog": TECHNOLOGY_CATALOG_VERSION,
                "confirmation_id": confirmation.confirmation_id,
                "selection_revision": confirmation.selection_revision,
                "selection_digest": confirmation.selection_digest,
                "selected_outputs": [item.value for item in confirmation.selected_outputs],
                "traceability_manifest_fingerprint": graph_fp,
                "testability_input_fingerprint": testability.input_fingerprint,
                "testability_result_fingerprint": testability_fp,
                "technical_evidence_fingerprint": technical.fingerprint,
            })
            assessments, findings, overall = evaluate_feasibility(
                confirmation.selected_outputs, testability.output_assessments,
                technical, input_fingerprint=input_fingerprint,
            )
            candidate = Agent4FeasibilityResult(
                schema_version=FEASIBILITY_SCHEMA_VERSION,
                engine_version=FEASIBILITY_ENGINE_VERSION,
                policy_version=FEASIBILITY_POLICY_VERSION,
                technology_catalog_version=TECHNOLOGY_CATALOG_VERSION,
                agent_project_id=project_id,
                confirmation_id=confirmation.confirmation_id,
                selection_revision=confirmation.selection_revision,
                selected_outputs_digest=confirmation.selection_digest,
                selected_outputs=confirmation.selected_outputs,
                traceability_manifest_fingerprint=graph_fp,
                testability_input_fingerprint=testability.input_fingerprint,
                testability_result_fingerprint=testability_fp,
                technical_evidence_fingerprint=technical.fingerprint,
                technical_evidence_inventory=list(technical.items),
                output_assessments=assessments,
                overall_feasibility=overall,
                blocking_executable_finding_count=sum(
                    item.severity is FeasibilityFindingSeverity.BLOCKING_EXECUTABLE
                    for item in findings
                ),
                warning_count=sum(
                    item.severity is FeasibilityFindingSeverity.WARNING
                    for item in findings
                ),
                findings=findings,
                input_fingerprint=input_fingerprint,
                evaluated_at=self._clock(),
            )
            cached = self._storage.load(
                agent_project_id=project_id, owner_user_id=user.user_id
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
