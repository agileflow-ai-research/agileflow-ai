from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

from app.common.status import AgentStage, AgentType
from app.modules.agents.testing_validation.details.service import (
    Agent4DetailService,
    Agent4DetailSourceNotFoundError,
)
from app.modules.standalone.service import AgentProjectNotFoundError


NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)
PROJECT_ID = "AGP-404"
OWNER_ID = "USR-owner"
SOURCE_ID = "A4SRC-" + "a" * 32
CHUNK_ID = "A4CHK-" + "b" * 32


def enum(value):
    class EnumValue(str):
        @property
        def value(self):
            return str(self)
    return EnumValue(value)


class OwnedStandalone:
    def __init__(self):
        self.calls = []

    def require_active_project(self, owner_user_id, agent_project_id):
        self.calls.append((owner_user_id, agent_project_id))
        if owner_user_id != OWNER_ID:
            raise AgentProjectNotFoundError(agent_project_id)
        return NS(agent_type=AgentType.TESTING_VALIDATION, agent_stage=AgentStage.TEST_GENERATION)


class WorkflowStorage:
    def __init__(self, record):
        self.record = record
        self.loads = []
        self.save_calls = 0

    def load(self, **kwargs):
        self.loads.append(kwargs)
        if kwargs["owner_user_id"] != OWNER_ID:
            raise AssertionError("owner was not propagated")
        return self.record

    def save(self, _record):
        self.save_calls += 1
        raise AssertionError("detail reads must never save workflow state")


class SourceStorage:
    def __init__(self, sources):
        self.sources = sources

    def list_for_project(self, **kwargs):
        assert kwargs == {"agent_project_id": PROJECT_ID, "owner_user_id": OWNER_ID}
        return self.sources


class PerSourceStorage:
    def __init__(self, value=None):
        self.value = value
        self.calls = []

    def load(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["agent_project_id"] == PROJECT_ID
        assert kwargs["owner_user_id"] == OWNER_ID
        assert kwargs["source_id"] == SOURCE_ID
        return self.value


class ProjectStorage:
    def __init__(self, value=None):
        self.value = value
        self.calls = []

    def load(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs == {"agent_project_id": PROJECT_ID, "owner_user_id": OWNER_ID}
        return self.value


def source():
    return NS(
        source_id=SOURCE_ID, label="Functional Requirements",
        original_filename=None, artifact_type=enum("FUNCTIONAL_REQUIREMENTS"),
    )


def chunk(sequence=1, text="Only administrators may delete bookings."):
    return NS(
        chunk_id=CHUNK_ID, sequence=sequence, text=text,
        heading_path=["Authorization"], structure_type="PARAGRAPH", token_count=7,
    )


def build_service(*, chunks=None, rules=None, hybrid=None, effective=None,
                  semantic=None, traceability=None, testability=None,
                  feasibility=None, decision=None, review_history=None):
    workflow = NS(
        n1_confirmation=NS(source_ids=[SOURCE_ID]),
        n3_review_history=review_history or [],
    )
    workflow_storage = WorkflowStorage(workflow)
    service = Agent4DetailService(
        OwnedStandalone(), workflow_storage, SourceStorage([source()]),
        PerSourceStorage(chunks), PerSourceStorage(rules),
        PerSourceStorage(NS(forbidden="unused model output")),
        PerSourceStorage(hybrid), PerSourceStorage(effective),
        PerSourceStorage(semantic), ProjectStorage(traceability),
        ProjectStorage(testability), ProjectStorage(feasibility),
        ProjectStorage(decision),
    )
    return service, workflow_storage


def user(user_id=OWNER_ID):
    return NS(user_id=user_id)


def test_prepared_sections_are_ordered_paginated_and_owner_scoped():
    first = chunk()
    second = NS(**{**first.__dict__, "chunk_id": "A4CHK-" + "c" * 32, "sequence": 2, "text": "Second persisted section"})
    service, workflow = build_service(chunks=NS(chunks=[first, second]))

    result = service.prepared_sections(PROJECT_ID, user(), source_id=None, offset=1, limit=1)

    assert result.total == 2 and result.has_more is False
    assert result.items[0].sequence == 2
    assert result.items[0].source_id == SOURCE_ID
    assert result.items[0].text == "Second persisted section"
    serialized = result.model_dump_json().lower()
    assert "storage_path" not in serialized and "filesystem" not in serialized
    assert workflow.save_calls == 0


def test_prepared_sections_handle_missing_manifest_and_unknown_source():
    service, _ = build_service(chunks=None)
    assert service.prepared_sections(PROJECT_ID, user(), source_id=None, offset=0, limit=5).items == []
    with pytest.raises(Agent4DetailSourceNotFoundError):
        service.prepared_sections(PROJECT_ID, user(), source_id="A4SRC-" + "f" * 32, offset=0, limit=5)


def test_classification_projects_persisted_evidence_and_effective_decision():
    decision = NS(
        label=enum("AUTHORIZATION"), rule_detected=True, model_score=0.82,
        evidence_state=enum("AGREEMENT"), status=enum("ACCEPTED"),
        reason_codes=["RULE_AND_MODEL_AGREE"], explanation="Both methods supported this concern.",
    )
    hybrid_result = NS(chunk=NS(chunk_id=CHUNK_ID), decisions=[decision])
    evidence = NS(label=decision.label, quote="Only administrators may delete bookings.")
    rule_result = NS(chunk=NS(chunk_id=CHUNK_ID), rule_evidence=[evidence])
    effective_decision = NS(
        label=decision.label, status=enum("ACCEPTED"),
        origin=enum("H1_AUTO_ACCEPTED"), review_id=None,
    )
    effective_result = NS(chunk=NS(chunk_id=CHUNK_ID), decisions=[effective_decision])
    service, _ = build_service(
        chunks=NS(chunks=[chunk()]), rules=NS(results=[rule_result]),
        hybrid=NS(results=[hybrid_result]), effective=NS(results=[effective_result]),
    )

    result = service.classifications(PROJECT_ID, user(), source_id=None, offset=0, limit=5)

    item = result.items[0]
    assert item.label == "AUTHORIZATION"
    assert item.evidence_quote == "Only administrators may delete bookings."
    assert item.hybrid_decision == "ACCEPTED"
    assert item.effective_decision == "ACCEPTED"
    assert item.effective_origin == "H1_AUTO_ACCEPTED"


def test_review_audit_projects_human_note_and_effective_result_without_mutation():
    review = NS(
        review_id="A4N3R-" + "d" * 32, reviewed_at=NOW,
        resolutions=[NS(
            source_id=SOURCE_ID, chunk_id=CHUNK_ID, label="AUTHORIZATION",
            decision=enum("ACCEPT"), note="Confirmed against the requirement.",
        )],
    )
    effective_decision = NS(
        label=enum("AUTHORIZATION"), status=enum("ACCEPTED"),
    )
    effective = NS(results=[NS(chunk=NS(chunk_id=CHUNK_ID), decisions=[effective_decision])])
    service, workflow = build_service(
        chunks=NS(chunks=[chunk()]), effective=effective, review_history=[review],
    )

    result = service.review_decisions(PROJECT_ID, user(), offset=0, limit=5)

    assert result.items[0].human_decision == "ACCEPT"
    assert result.items[0].note == "Confirmed against the requirement."
    assert result.items[0].effective_decision == "ACCEPTED"
    assert workflow.save_calls == 0


def test_testing_facts_return_only_persisted_grounded_facts_and_exact_quote():
    fact = NS(
        fact_id="A4FACT-" + "e" * 32, fact_type=enum("AUTHORIZATION_RULE"),
        related_labels=[enum("AUTHORIZATION")],
        evidence_quote="Only administrators may delete bookings.",
    )
    fact.model_dump = lambda mode: {
        "fact_id": fact.fact_id, "fact_type": "AUTHORIZATION_RULE",
        "related_labels": ["AUTHORIZATION"], "evidence_quote": fact.evidence_quote,
        "evidence_start": 0, "evidence_end": 41,
        "actor": "administrators", "action": "delete", "target": "bookings",
    }
    semantic = NS(results=[NS(chunk=NS(chunk_id=CHUNK_ID, sequence=1), facts=[fact])])
    service, _ = build_service(semantic=semantic)

    result = service.testing_facts(PROJECT_ID, user(), source_id=None, offset=0, limit=5)

    item = result.items[0]
    assert item.fact_type == "AUTHORIZATION_RULE"
    assert item.evidence_quote == fact.evidence_quote
    assert item.structured_values == {"actor": "administrators", "action": "delete", "target": "bookings"}


def test_testing_facts_handle_empty_or_incomplete_persisted_result_without_model_call():
    semantic = NS(results=[NS(chunk=NS(chunk_id=CHUNK_ID, sequence=1), facts=[])])
    service, _ = build_service(semantic=semantic)
    assert service.testing_facts(PROJECT_ID, user(), source_id=None, offset=0, limit=5).items == []


def test_context_details_project_tr1_tb1_fb1_and_cd1_without_recomputation():
    left = NS(node_id="left", display_value="FR-001", node_kind=enum("FUNCTIONAL_REQUIREMENT"))
    right = NS(node_id="right", display_value="POST /bookings", node_kind=enum("API_ENDPOINT"))
    links = [NS(
        traceability_link_id=f"link-{index}", source_node_id="left", target_node_id="right",
        relation_type=enum("USES_ENDPOINT"), explanation="Explicit endpoint evidence.",
        strength=enum("EXACT"),
    ) for index in range(6)]
    traceability = NS(nodes=[left, right], links=links)
    requirement = NS(requirement_id="API_BEHAVIOR", description="API behavior is present", satisfied=True, observed_count=2)
    output = enum("API_TESTS")
    testability = NS(
        overall_status=enum("READY"),
        output_assessments=[NS(output_code=output, mandatory_requirements=[requirement], supporting_requirements=[])],
    )
    profile = NS(language="Python", test_framework="pytest")
    profile.model_dump = lambda mode: {"language": "Python", "test_framework": "pytest"}
    feasibility = NS(
        overall_feasibility=enum("EXECUTABLE_POSSIBLE"),
        output_assessments=[NS(output_code=output, generation_profile=profile)],
    )
    blocker_id = "finding-blocker"
    warning_id = "finding-warning"
    output_profile = NS(
        output_code=output, testability_status=enum("READY"),
        feasibility_status=enum("EXECUTABLE_POSSIBLE"),
        recommended_representation=enum("EXECUTABLE_CODE"),
        decision=enum("PROCEED_WITH_WARNINGS"), planning_allowed=True,
        blocking_finding_ids=[blocker_id], warning_finding_ids=[warning_id],
        evidence_node_ids=["left", "right"], evidence_link_ids=["link-0"],
        semantic_fact_ids=["fact"],
    )
    decision = NS(
        overall_decision=enum("PROCEED_WITH_WARNINGS"), output_profiles=[output_profile],
        consolidated_findings=[
            NS(consolidated_finding_id=blocker_id, display_message="Missing negative case."),
            NS(consolidated_finding_id=warning_id, display_message="Authentication failures are incomplete."),
        ],
    )
    service, workflow = build_service(
        traceability=traceability, testability=testability,
        feasibility=feasibility, decision=decision,
    )

    result = service.context_details(PROJECT_ID, user(), offset=0, limit=5)

    assert result.traceability_total == 6 and result.traceability_has_more is True
    assert len(result.connections) == 5
    assert result.connections[0].source_value == "FR-001"
    assert result.outputs[0].mandatory_requirements[0].description == "API behavior is present"
    assert result.outputs[0].generation_profile["test_framework"] == "pytest"
    assert result.outputs[0].warnings == ["Authentication failures are incomplete."]
    assert workflow.save_calls == 0


def test_owner_isolation_stops_before_any_artifact_load():
    service, workflow = build_service(chunks=NS(chunks=[chunk()]))
    with pytest.raises(AgentProjectNotFoundError):
        service.prepared_sections(PROJECT_ID, user("USR-other"), source_id=None, offset=0, limit=5)
    assert workflow.loads == []
