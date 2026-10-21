import json

from . import constants
from .schemas import SemanticFactType


def build_semantic_prompt(chunk_text, accepted_labels, *, correction_feedback=None):
    labels = [label.value for label in accepted_labels]
    correction = (
        "CORRECTION_REQUIRED=" + correction_feedback
        if correction_feedback else "FIRST_ATTEMPT"
    )
    fields = (
        "fact_type, related_labels, evidence_quote, evidence_start, evidence_end, "
        "actor, role, action, target, field_name, operator, value, minimum, maximum, "
        "unit, allowed_values, disallowed_values, api_method, api_endpoint, http_status, "
        "precondition, postcondition, expected_outcome, security_mechanism, "
        "performance_metric, reliability_condition, persistence_behavior"
    )
    return "\n".join((
        f"SEMANTIC_PROMPT_VERSION={constants.SEMANTIC_PROMPT_VERSION}",
        "You extract concrete testing facts explicitly stated in trusted source text.",
        "Return exactly one JSON object and nothing else. No Markdown or commentary.",
        'The object shape is {"facts":[...]} and no other top-level keys are allowed.',
        "Use only the supplied source text. Omit uncertain or inferred facts.",
        "Every fact requires an exact verbatim evidence_quote from the source text.",
        "The evidence_quote must directly contain every structured semantic value in that fact.",
        "Use exact offsets when a quote repeats; never guess an occurrence.",
        "related_labels must contain only accepted labels supplied below.",
        "Do not invent values, endpoints, status codes, constraints, examples, or domain rules.",
        "Do not generate tests, steps, assertions, edge cases, or boundary test values.",
        "Do not resolve classification disagreements and do not include confidence scores.",
        "FACT_TYPES=" + json.dumps(
            [item.value for item in SemanticFactType], separators=(",", ":")
        ),
        "FACT_FIELDS=" + fields,
        "ACCEPTED_TESTING_LABELS=" + json.dumps(labels, separators=(",", ":")),
        correction,
        "SOURCE_TEXT_BEGIN",
        chunk_text,
        "SOURCE_TEXT_END",
    ))
