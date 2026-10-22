import json

from . import constants
from .schemas import SemanticFactType


def build_semantic_prompt(chunk_text, accepted_labels, *, correction_feedback=None):
    labels = [label.value for label in accepted_labels]
    example_label = labels[0] if labels else "FUNCTIONAL_BEHAVIOR"
    correction = (
        "PREVIOUS_OUTPUT_REJECTED=" + correction_feedback
        + "\nReturn a new corrected JSON object. Do not repeat the rejected shape."
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
        "Each fact may contain only FACT_FIELDS listed below. Omit every unused optional field.",
        "fact_type must be one value from FACT_TYPES; it is not a testing label.",
        "related_labels must be a non-empty array containing only ACCEPTED_TESTING_LABELS.",
        "Use only the supplied source text. Omit uncertain or inferred facts.",
        "Every fact requires an exact verbatim evidence_quote from the source text.",
        "The evidence_quote must directly contain every structured semantic value in that fact.",
        "Use exact offsets when a quote repeats; never guess an occurrence.",
        "related_labels must contain only accepted labels supplied below.",
        "Do not invent values, endpoints, status codes, constraints, examples, or domain rules.",
        "Do not generate tests, steps, assertions, edge cases, or boundary test values.",
        "Do not resolve classification disagreements and do not include confidence scores.",
        'If no fully valid grounded fact exists, return exactly {"facts":[]}.',
        "FACT_TYPES=" + json.dumps(
            [item.value for item in SemanticFactType], separators=(",", ":")
        ),
        "FACT_FIELDS=" + fields,
        "ACCEPTED_TESTING_LABELS=" + json.dumps(labels, separators=(",", ":")),
        "VALID_EXAMPLE_SOURCE=The customer can cancel a booking.",
        "VALID_EXAMPLE_OUTPUT=" + json.dumps({"facts": [{
            "fact_type": "ACTOR_ACTION",
            "related_labels": [example_label],
            "evidence_quote": "The customer can cancel a booking.",
            "actor": "customer",
            "action": "cancel",
            "target": "booking",
        }]}, separators=(",", ":")),
        "The example demonstrates shape only. For the real output, use only the supplied source text and accepted labels.",
        correction,
        "SOURCE_TEXT_BEGIN",
        chunk_text,
        "SOURCE_TEXT_END",
    ))
