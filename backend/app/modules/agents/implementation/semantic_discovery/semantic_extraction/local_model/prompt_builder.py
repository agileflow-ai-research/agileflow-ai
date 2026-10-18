import json

from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
)

from ..schemas import SemanticExtractionRequest
from . import constants


_ARTIFACT_RULES = {
    ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: "Preserve requirement wording. Do not create IDs absent from the source.",
    ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: "Numeric targets and categories require direct source support.",
    ArtifactDetectionLabel.USER_STORIES: "Do not invent a role, goal, or benefit missing from the source.",
    ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: "Do not manufacture Given/When/Then fields.",
    ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: "Do not invent components, services, queues, caches, or relationships.",
    ArtifactDetectionLabel.DATABASE_SCHEMA: "Do not infer names, types, keys, nullability, uniqueness, or relationships. Every entity and every field requires its own evidence array. foreign_key is a source string or null, never a boolean.",
    ArtifactDetectionLabel.API_SPECIFICATION: "Do not invent HTTP methods, paths, fields, response codes, or schemas.",
    ArtifactDetectionLabel.UI_FLOW: "Include only screens and actions explicitly present in the source sequence.",
    ArtifactDetectionLabel.TECHNOLOGY_STACK: "Report source technologies only; never substitute a preferred stack.",
    ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: "Include only explicit source restrictions.",
    ArtifactDetectionLabel.IMPLEMENTATION_TASKS: "Do not derive tasks from requirements; structure only stated tasks.",
    ArtifactDetectionLabel.TEST_CASES: "Do not invent preconditions, steps, or expected results.",
}

_PROPOSAL_PREFIXES = {
    ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: '{"artifact_type":"FUNCTIONAL_REQUIREMENTS","requirements":',
    ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: '{"artifact_type":"NON_FUNCTIONAL_REQUIREMENTS","requirements":',
    ArtifactDetectionLabel.USER_STORIES: '{"artifact_type":"USER_STORIES","stories":',
    ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: '{"artifact_type":"ACCEPTANCE_CRITERIA","criteria":',
    ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: '{"artifact_type":"SYSTEM_ARCHITECTURE","components":',
    ArtifactDetectionLabel.DATABASE_SCHEMA: '{"artifact_type":"DATABASE_SCHEMA","entities":',
    ArtifactDetectionLabel.API_SPECIFICATION: '{"artifact_type":"API_SPECIFICATION","endpoints":',
    ArtifactDetectionLabel.UI_FLOW: '{"artifact_type":"UI_FLOW","flows":',
    ArtifactDetectionLabel.TECHNOLOGY_STACK: '{"artifact_type":"TECHNOLOGY_STACK","stack":',
    ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: '{"artifact_type":"TECHNICAL_CONSTRAINTS","constraints":',
    ArtifactDetectionLabel.IMPLEMENTATION_TASKS: '{"artifact_type":"IMPLEMENTATION_TASKS","tasks":',
    ArtifactDetectionLabel.TEST_CASES: '{"artifact_type":"TEST_CASES","test_cases":',
}


def build_proposal_prefix(artifact_type: ArtifactDetectionLabel) -> str:
    return _PROPOSAL_PREFIXES[artifact_type]


def _prompt_data_without_source_refs(value):
    if isinstance(value, dict):
        return {
            key: _prompt_data_without_source_refs(item)
            for key, item in value.items()
            if key != "source_refs"
        }
    if isinstance(value, list):
        return [_prompt_data_without_source_refs(item) for item in value]
    return value

_PROPOSAL_SHAPES = {
    ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS: '{"artifact_type":"FUNCTIONAL_REQUIREMENTS","requirements":[{"id":null,"statement":"...","evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS: '{"artifact_type":"NON_FUNCTIONAL_REQUIREMENTS","requirements":[{"id":null,"statement":"...","category":null,"measurable_target":null,"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.USER_STORIES: '{"artifact_type":"USER_STORIES","stories":[{"id":null,"role":null,"goal":null,"benefit":null,"raw_statement":"...","evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.ACCEPTANCE_CRITERIA: '{"artifact_type":"ACCEPTANCE_CRITERIA","criteria":[{"id":null,"statement":"...","given":null,"when":null,"then":null,"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.SYSTEM_ARCHITECTURE: '{"artifact_type":"SYSTEM_ARCHITECTURE","components":[],"relationships":[],"raw_architecture_statements":[]}',
    ArtifactDetectionLabel.DATABASE_SCHEMA: '{"artifact_type":"DATABASE_SCHEMA","entities":[{"name":"...","fields":[{"name":"...","type":null,"nullable":null,"primary_key":null,"foreign_key":null,"evidence":[EVIDENCE]}],"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.API_SPECIFICATION: '{"artifact_type":"API_SPECIFICATION","endpoints":[{"id":null,"method":null,"path":null,"description":null,"request_fields":[],"response_statuses":[],"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.UI_FLOW: '{"artifact_type":"UI_FLOW","flows":[{"name":null,"steps":[],"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.TECHNOLOGY_STACK: '{"artifact_type":"TECHNOLOGY_STACK","stack":{"frontend":[],"styling":[],"backend":[],"database":[],"languages":[],"api_styles":[],"other":[],"evidence":[EVIDENCE]}}',
    ArtifactDetectionLabel.TECHNICAL_CONSTRAINTS: '{"artifact_type":"TECHNICAL_CONSTRAINTS","constraints":[{"id":null,"statement":"...","constraint_type":null,"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.IMPLEMENTATION_TASKS: '{"artifact_type":"IMPLEMENTATION_TASKS","tasks":[{"id":null,"title":"...","description":null,"evidence":[EVIDENCE]}]}',
    ArtifactDetectionLabel.TEST_CASES: '{"artifact_type":"TEST_CASES","test_cases":[{"id":null,"description":null,"preconditions":[],"steps":[],"expected_result":null,"evidence":[EVIDENCE]}]}',
}


def build_prompt(request: SemanticExtractionRequest, *, correction: bool = False) -> str:
    correction_text = (
        "A previous attempt was invalid. Return only one schema-valid JSON object with no commentary."
        if correction else "Return exactly one JSON object and nothing else."
    )
    return "\n".join((
        f"SEMANTIC_PROMPT_VERSION={constants.SEMANTIC_PROMPT_VERSION}",
        "You are an information extraction component.",
        "Extract only information explicitly supported by SOURCE_TEXT.",
        "Do not design the software. Do not infer missing architecture.",
        "Do not invent APIs, database fields, numeric requirements, IDs, or expected results.",
        "Do not provide reasoning or chain-of-thought.",
        "The trusted proposal prefix already contains artifact_type and the required top-level data key. Continue its value and close that same object without repeating either key.",
        "DETERMINISTIC_ARTIFACT is read-only input. Never copy its envelope or add a data wrapper.",
        "Use only keys shown in REQUIRED_JSON_SHAPE. Every evidence value is a JSON array, even when it contains one entry.",
        "Preserve null exactly where a value is unsupported; never replace null with false or an invented value.",
        "Every proposed item and fact must include evidence.quote copied verbatim from SOURCE_TEXT.",
        "Use the supplied CHUNK_ID in every evidence entry. Omit offsets unless exact normalized offsets are known.",
        _ARTIFACT_RULES[request.artifact_type],
        correction_text,
        f"VERIFIED_ARTIFACT_TYPE={request.artifact_type.value}",
        f"CHUNK_ID={request.chunk_id}",
        "DETERMINISTIC_ARTIFACT_STATUS="
        + request.deterministic_artifact.status.value,
        "DETERMINISTIC_ARTIFACT_DATA=" + json.dumps(
            _prompt_data_without_source_refs(
                request.deterministic_artifact.data.model_dump(
                    mode="json", by_alias=True
                )
            ),
            separators=(",", ":"),
        ),
        "UNRESOLVED_ITEMS=" + json.dumps(
            [item.model_dump(mode="json") for item in request.unresolved_items],
            separators=(",", ":"),
        ),
        'EVIDENCE={"chunk_id":"' + request.chunk_id + '","quote":"exact source quote","start_char":null,"end_char":null}',
        "REQUIRED_JSON_SHAPE=" + _PROPOSAL_SHAPES[request.artifact_type],
        "SOURCE_TEXT_BEGIN",
        request.source_text,
        "SOURCE_TEXT_END",
    ))
