import hashlib
import json
from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.agents.implementation.preparation.canonical.schemas import (
    ApiEndpointItem, ApiSpecificationData, CanonicalArtifact,
    CanonicalSourceRef, CanonicalStatus, DatabaseSchemaData,
    FunctionalRequirementsData, OtherContextData, OtherContextItem,
    TechnologyStackData, UserStoriesData, UserStoryItem,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.preparation.semantic_extraction import constants
from app.modules.agents.implementation.preparation.semantic_extraction.evidence import (
    validate_evidence,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    EvidenceSpan, SemanticExtractionProposal, SemanticExtractionRequest,
)
from app.modules.agents.implementation.preparation.semantic_extraction.service import (
    SemanticExtractionContractError, SemanticExtractionService,
)


CHUNK_ID = "CHK-0123456789ABCDEF0123"
UPLOAD_ID = "A3UP-0123456789abcdef0123456789abcdef"


class FakeSemanticExtractor:
    def __init__(self, proposal):
        self.proposal = proposal
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        return self.proposal


def span(quote, start=None, end=None, chunk_id=CHUNK_ID):
    return {
        "chunk_id": chunk_id, "quote": quote,
        "start_char": start, "end_char": end,
    }


def source_ref(text):
    return CanonicalSourceRef(
        upload_id=UPLOAD_ID, chunk_id=CHUNK_ID,
        text_hash=hashlib.sha256(text.encode()).hexdigest(),
        original_filename="spec.md", line_start=1, line_end=1,
    )


def artifact(text, label=ArtifactDetectionLabel.API_SPECIFICATION,
             status=CanonicalStatus.PARTIAL, data=None):
    ref = source_ref(text)
    if data is None:
        data = ApiSpecificationData(endpoints=[ApiEndpointItem(
            method="POST", path="/api/bookings", description=None,
            request_fields=[], response_statuses=[], source_refs=[ref],
        )])
    return CanonicalArtifact(
        artifact_id="CA-0123456789ABCDEF01234567",
        artifact_type=label, status=status, data=data,
        source_refs=[ref], unresolved_items=[],
        canonical_schema_version="1", extractor_version="1",
        created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
    )


def request(text, label=ArtifactDetectionLabel.API_SPECIFICATION,
            status=CanonicalStatus.PARTIAL, data=None, verified_labels=None):
    canonical = artifact(text, label, status, data)
    return SemanticExtractionRequest(
        project_id="AGP-003", upload_id=UPLOAD_ID, chunk_id=CHUNK_ID,
        chunk_text_hash=canonical.source_refs[0].text_hash,
        artifact_type=label, verified_labels=verified_labels or [label],
        source_text=text, deterministic_artifact=canonical,
        unresolved_items=[], target_schema_version="1",
        semantic_contract_version="1",
    )


def api_proposal(text, **endpoint):
    return {
        "artifact_type": "API_SPECIFICATION",
        "endpoints": [{
            "id": None, "method": endpoint.get("method"),
            "path": endpoint.get("path"),
            "description": endpoint.get("description"),
            "request_fields": endpoint.get("request_fields", []),
            "response_statuses": endpoint.get("response_statuses", []),
            "evidence": [span(text)],
        }],
    }


def test_exact_evidence_and_omitted_offsets_are_grounded():
    source = "Customers can cancel bookings."
    result = validate_evidence(
        EvidenceSpan(**span(source)), trusted_chunk_id=CHUNK_ID,
        trusted_source_text=source,
    )
    assert result.valid
    assert (result.evidence.start_char, result.evidence.end_char) == (0, len(source))


@pytest.mark.parametrize(("evidence", "source", "reason"), [
    (span("missing"), "source", "EVIDENCE_QUOTE_NOT_FOUND"),
    (span("source", chunk_id="CHK-AAAAAAAAAAAAAAAAAAAA"), "source", "WRONG_EVIDENCE_CHUNK"),
    (span("source", 1, 7), "source", "EVIDENCE_OFFSET_MISMATCH"),
    (span("repeat"), "repeat and repeat", "AMBIGUOUS_EVIDENCE_QUOTE"),
    (span("outside", 0, 7), "short", "EVIDENCE_OFFSET_MISMATCH"),
])
def test_invalid_evidence_is_rejected(evidence, source, reason):
    result = validate_evidence(
        EvidenceSpan(**evidence), trusted_chunk_id=CHUNK_ID,
        trusted_source_text=source,
    )
    assert not result.valid
    assert result.reason == reason


def test_exact_offsets_and_crlf_normalization():
    source = "Header\r\nCustomers can cancel."
    quote = "Customers can cancel."
    start = len("Header\n")
    result = validate_evidence(
        EvidenceSpan(**span(quote, start, start + len(quote))),
        trusted_chunk_id=CHUNK_ID, trusted_source_text=source,
    )
    assert result.valid


def test_empty_and_oversized_evidence_are_schema_rejected():
    with pytest.raises(ValidationError):
        EvidenceSpan(**span(""))
    with pytest.raises(ValidationError):
        EvidenceSpan(**span("x" * (constants.MAX_EVIDENCE_QUOTE_CHARACTERS + 1)))


@pytest.mark.parametrize(("field", "value"), [
    ("path", "/api/invented"),
    ("method", "DELETE"),
])
def test_invented_api_facts_are_rejected(field, value):
    text = "Create a booking using name and email."
    proposal = api_proposal(text, **{field: value})
    result = SemanticExtractionService().run(request(text), FakeSemanticExtractor(proposal))
    assert result.validation.proposal_status == "REJECTED"
    assert result.validation.rejections[0].code == "UNSUPPORTED_BY_SOURCE"
    assert value not in str(result.merged_artifact.data)


def test_invented_database_type_is_rejected():
    text = "Store customer email."
    data = DatabaseSchemaData(entities=[])
    proposal = {
        "artifact_type": "DATABASE_SCHEMA",
        "entities": [{"name": "customer", "evidence": [span(text)], "fields": [{
            "name": "email", "type": "VARCHAR(255)", "nullable": None,
            "primary_key": None, "foreign_key": None, "evidence": [span(text)],
        }]}],
    }
    result = SemanticExtractionService().run(
        request(text, ArtifactDetectionLabel.DATABASE_SCHEMA,
                CanonicalStatus.UNRESOLVED, data),
        FakeSemanticExtractor(proposal),
    )
    rejected = {item.proposed_value for item in result.validation.rejections}
    assert "VARCHAR(255)" in rejected
    assert "VARCHAR(255)" not in str(result.merged_artifact.data)


def test_invented_performance_target_is_rejected():
    text = "The system should be fast."
    proposal = {
        "artifact_type": "NON_FUNCTIONAL_REQUIREMENTS",
        "requirements": [{
            "id": None, "statement": text, "category": "PERFORMANCE",
            "measurable_target": "below 2 seconds", "evidence": [span(text)],
        }],
    }
    from app.modules.agents.implementation.preparation.canonical.schemas import NonFunctionalRequirementsData
    result = SemanticExtractionService().run(
        request(text, ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS,
                CanonicalStatus.UNRESOLVED, NonFunctionalRequirementsData(requirements=[])),
        FakeSemanticExtractor(proposal),
    )
    assert "below 2 seconds" in {item.proposed_value for item in result.validation.rejections}
    assert any(item.field_path.endswith("category") for item in result.merged_artifact.field_provenance)


def test_grounded_requirement_runs_through_fake_adapter_without_mutating_deterministic():
    text = "Customers can cancel existing bookings."
    data = FunctionalRequirementsData(requirements=[])
    req = request(text, ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
                  CanonicalStatus.UNRESOLVED, data)
    original = req.deterministic_artifact.model_dump(mode="json")
    fake = FakeSemanticExtractor({
        "artifact_type": "FUNCTIONAL_REQUIREMENTS",
        "requirements": [{"id": None, "statement": text, "evidence": [span(text)]}],
    })
    result = SemanticExtractionService().run(req, fake)
    assert result.validation.proposal_status == "GROUNDED"
    assert result.merged_artifact.data["requirements"][0]["statement"] == text
    assert result.merged_artifact.field_provenance[-1].origin == "SEMANTIC"
    assert req.deterministic_artifact.model_dump(mode="json") == original
    assert fake.requests == [req]


def test_api_request_field_is_added_but_same_deterministic_values_keep_origin():
    text = "POST /api/bookings accepts the name field."
    proposal = api_proposal(
        text, method="POST", path="/api/bookings", request_fields=["name"],
    )
    result = SemanticExtractionService().run(request(text), FakeSemanticExtractor(proposal))
    endpoint = result.merged_artifact.data["endpoints"][0]
    assert endpoint["request_fields"] == ["name"]
    origins = {item.field_path: item.origin for item in result.merged_artifact.field_provenance}
    assert origins["endpoints[0].method"] == "DETERMINISTIC"
    assert origins["endpoints[0].request_fields[0]"] == "SEMANTIC"


def test_semantic_value_fills_a_missing_deterministic_scalar():
    text = "As a guest, I want booking. The benefit is save time."
    ref = source_ref(text)
    data = UserStoriesData(stories=[UserStoryItem(
        id=None, role="guest", goal="booking", benefit=None,
        raw_statement="As a guest, I want booking.", source_refs=[ref],
    )])
    proposal = {
        "artifact_type": "USER_STORIES", "stories": [{
            "id": None, "role": "guest", "goal": "booking",
            "benefit": "save time",
            "raw_statement": "As a guest, I want booking.",
            "evidence": [span(text)],
        }],
    }
    result = SemanticExtractionService().run(
        request(text, ArtifactDetectionLabel.USER_STORIES,
                CanonicalStatus.PARTIAL, data),
        FakeSemanticExtractor(proposal),
    )
    assert result.merged_artifact.data["stories"][0]["benefit"] == "save time"
    provenance = next(item for item in result.merged_artifact.field_provenance
                      if item.field_path == "stories[0].benefit")
    assert provenance.origin == "SEMANTIC"


def test_source_backed_technology_and_natural_language_ui_steps_are_accepted():
    technology_text = "The frontend uses React."
    technology_data = TechnologyStackData(
        frontend=[], styling=[], backend=[], database=[], languages=[],
        api_styles=[], other=[], source_refs=[source_ref(technology_text)],
    )
    technology_result = SemanticExtractionService().run(
        request(technology_text, ArtifactDetectionLabel.TECHNOLOGY_STACK,
                CanonicalStatus.PARTIAL, technology_data),
        FakeSemanticExtractor({
            "artifact_type": "TECHNOLOGY_STACK",
            "stack": {"frontend": ["React"], "styling": [], "backend": [],
                      "database": [], "languages": [], "api_styles": [], "other": [],
                      "evidence": [span(technology_text)]},
        }),
    )
    assert technology_result.merged_artifact.data["frontend"] == ["React"]

    from app.modules.agents.implementation.preparation.canonical.schemas import UiFlowData
    ui_text = "The user opens Home and then selects Booking Form."
    ui_result = SemanticExtractionService().run(
        request(ui_text, ArtifactDetectionLabel.UI_FLOW,
                CanonicalStatus.UNRESOLVED, UiFlowData(flows=[])),
        FakeSemanticExtractor({
            "artifact_type": "UI_FLOW", "flows": [{"name": None,
            "evidence": [span(ui_text)], "steps": [
                {"order": 1, "screen_or_action": "Home", "evidence": [span(ui_text)]},
                {"order": 2, "screen_or_action": "Booking Form", "evidence": [span(ui_text)]},
            ]}],
        }),
    )
    assert [step["screen_or_action"] for step in ui_result.merged_artifact.data["flows"][0]["steps"]] == ["Home", "Booking Form"]


def test_semantic_conflict_does_not_overwrite_deterministic_value():
    text = "POST /api/bookings is current. PUT /api/bookings is proposed."
    result = SemanticExtractionService().run(
        request(text), FakeSemanticExtractor(api_proposal(
            text, method="PUT", path="/api/bookings",
        )),
    )
    assert result.validation.proposal_status == "HUMAN_REVIEW_REQUIRED"
    assert result.merged_artifact.status == "HUMAN_REVIEW_REQUIRED"
    assert result.merged_artifact.data["endpoints"][0]["method"] == "POST"
    conflict = result.validation.conflicts[0]
    assert conflict.code == "SEMANTIC_DETERMINISTIC_CONFLICT"
    assert (conflict.deterministic_value, conflict.semantic_value) == ("POST", "PUT")


def test_multiple_grounded_semantic_values_require_review():
    text = "POST /api/bookings or PUT /api/bookings may be used."
    proposal = {"artifact_type": "API_SPECIFICATION", "endpoints": [
        api_proposal(text, method="POST", path="/api/bookings")["endpoints"][0],
        api_proposal(text, method="PUT", path="/api/bookings")["endpoints"][0],
    ]}
    result = SemanticExtractionService().run(request(text), FakeSemanticExtractor(proposal))
    assert result.validation.proposal_status == "HUMAN_REVIEW_REQUIRED"
    assert any(item.code == "CONFLICTING_SEMANTIC_FACTS" for item in result.validation.conflicts)


@pytest.mark.parametrize("proposal", [
    {"artifact_type": "FUNCTIONAL_REQUIREMENTS", "requirements": [{"id": None, "statement": "Requirement", "evidence": [span("Requirement")]}]},
    {"artifact_type": "NON_FUNCTIONAL_REQUIREMENTS", "requirements": [{"id": None, "statement": "Security", "category": "SECURITY", "measurable_target": None, "evidence": [span("Security")]}]},
    {"artifact_type": "USER_STORIES", "stories": [{"id": None, "role": "guest", "goal": "book", "benefit": None, "raw_statement": "guest book", "evidence": [span("guest book")]}]},
    {"artifact_type": "ACCEPTANCE_CRITERIA", "criteria": [{"id": None, "statement": "booking succeeds", "given": None, "when": None, "then": None, "evidence": [span("booking succeeds")]}]},
    {"artifact_type": "API_SPECIFICATION", "endpoints": [{"id": None, "method": None, "path": None, "description": "booking API", "request_fields": [], "response_statuses": [], "evidence": [span("booking API")]}]},
    {"artifact_type": "DATABASE_SCHEMA", "entities": [{"name": "booking", "fields": [], "evidence": [span("booking")]}]},
    {"artifact_type": "SYSTEM_ARCHITECTURE", "components": [{"name": "API", "type": None, "evidence": [span("API")]}], "relationships": [], "raw_architecture_statements": []},
    {"artifact_type": "UI_FLOW", "flows": [{"name": None, "steps": [{"order": 1, "screen_or_action": "Home", "evidence": [span("Home")]}], "evidence": [span("Home")]}]},
    {"artifact_type": "TECHNOLOGY_STACK", "stack": {"frontend": ["React"], "styling": [], "backend": [], "database": [], "languages": [], "api_styles": [], "other": [], "evidence": [span("React")]}},
    {"artifact_type": "TECHNICAL_CONSTRAINTS", "constraints": [{"id": None, "statement": "must use Python", "constraint_type": None, "evidence": [span("must use Python")]}]},
    {"artifact_type": "IMPLEMENTATION_TASKS", "tasks": [{"id": None, "title": "Build API", "description": None, "evidence": [span("Build API")]}]},
    {"artifact_type": "TEST_CASES", "test_cases": [{"id": None, "description": "create booking", "preconditions": [], "steps": [], "expected_result": None, "evidence": [span("create booking")]}]},
])
def test_all_artifact_specific_proposal_schemas_are_strictly_validated(proposal):
    validated = TypeAdapter(SemanticExtractionProposal).validate_json(json.dumps(proposal))
    assert validated.artifact_type.value == proposal["artifact_type"]


def test_unknown_fields_and_wrong_nested_values_are_rejected():
    proposal = api_proposal("POST /api/bookings", method="POST", path="/api/bookings")
    proposal["unexpected"] = True
    with pytest.raises(ValidationError):
        TypeAdapter(SemanticExtractionProposal).validate_json(json.dumps(proposal))
    malformed = api_proposal("POST /api/bookings", method="POST", path="/api/bookings")
    malformed["endpoints"][0]["response_statuses"] = ["201"]
    with pytest.raises(ValidationError):
        TypeAdapter(SemanticExtractionProposal).validate_json(json.dumps(malformed))


def test_complete_other_context_and_wrong_verified_type_are_ineligible():
    text = "POST /api/bookings"
    proposal = api_proposal(text, method="POST", path="/api/bookings")
    service = SemanticExtractionService()
    with pytest.raises(SemanticExtractionContractError, match="COMPLETE_ARTIFACT_NOT_ELIGIBLE"):
        service.run(request(text, status=CanonicalStatus.COMPLETE), FakeSemanticExtractor(proposal))

    context_data = OtherContextData(context_items=[OtherContextItem(
        text="Background", source_refs=[source_ref("Background")]
    )])
    context_request = request(
        "Background", ArtifactDetectionLabel.OTHER_CONTEXT,
        CanonicalStatus.UNRESOLVED, context_data,
    )
    with pytest.raises(SemanticExtractionContractError, match="OTHER_CONTEXT_NOT_ELIGIBLE"):
        service.run(context_request, FakeSemanticExtractor({}))

    wrong = request(text, verified_labels=[ArtifactDetectionLabel.DATABASE_SCHEMA])
    with pytest.raises(SemanticExtractionContractError, match="ARTIFACT_TYPE_NOT_HUMAN_VERIFIED"):
        service.run(wrong, FakeSemanticExtractor(proposal))


def test_partial_and_unresolved_artifacts_are_eligible():
    text = "POST /api/bookings"
    proposal = api_proposal(text, method="POST", path="/api/bookings")
    for status in (CanonicalStatus.PARTIAL, CanonicalStatus.UNRESOLVED):
        result = SemanticExtractionService().run(
            request(text, status=status), FakeSemanticExtractor(proposal)
        )
        assert result.deterministic_status is status


def test_wrong_proposal_type_malformed_result_and_oversized_result_are_rejected():
    text = "POST /api/bookings"
    service = SemanticExtractionService()
    wrong_type = {"artifact_type": "FUNCTIONAL_REQUIREMENTS", "requirements": []}
    with pytest.raises(SemanticExtractionContractError, match="WRONG_ARTIFACT_TYPE"):
        service.run(request(text), FakeSemanticExtractor(wrong_type))
    with pytest.raises(SemanticExtractionContractError, match="MALFORMED_SEMANTIC_PROPOSAL"):
        service.run(request(text), FakeSemanticExtractor({"bad": object()}))
    oversized = api_proposal(text, description="x" * (constants.MAX_PROPOSAL_SERIALIZED_BYTES + 1))
    with pytest.raises(SemanticExtractionContractError, match="SEMANTIC_PROPOSAL_TOO_LARGE"):
        service.run(request(text), FakeSemanticExtractor(oversized))


def test_total_item_limit_and_trusted_source_hash_are_enforced():
    text = "POST /api/bookings"
    too_many = {
        "artifact_type": "SYSTEM_ARCHITECTURE",
        "components": [
            {"name": "API", "type": None, "evidence": [span(text)]}
            for _ in range(constants.MAX_SEMANTIC_ITEMS_PER_ARTIFACT)
        ],
        "relationships": [],
        "raw_architecture_statements": [
            {"statement": text, "evidence": [span(text)]}
        ],
    }
    from app.modules.agents.implementation.preparation.canonical.schemas import SystemArchitectureData
    architecture_request = request(
        text, ArtifactDetectionLabel.SYSTEM_ARCHITECTURE,
        CanonicalStatus.UNRESOLVED,
        SystemArchitectureData(components=[], relationships=[], raw_architecture_statements=[]),
    )
    with pytest.raises(SemanticExtractionContractError, match="TOO_MANY_SEMANTIC_ITEMS"):
        SemanticExtractionService().run(
            architecture_request, FakeSemanticExtractor(too_many)
        )

    stale = request(text).model_copy(update={"source_text": text + " changed"})
    with pytest.raises(SemanticExtractionContractError, match="STALE_TRUSTED_SOURCE"):
        SemanticExtractionService().run(
            stale, FakeSemanticExtractor(api_proposal(text, method="POST", path="/api/bookings"))
        )
