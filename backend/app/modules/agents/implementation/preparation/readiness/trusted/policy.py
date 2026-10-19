import hashlib
import json

from app.modules.agents.implementation.preparation.readiness.schemas import (
    FindingSeverity,
    HumanResolutionDecision,
)

from .constants import EFFECTIVE_STACK, OUTPUT_POLICY
from .schemas import TrustedReadinessFinding


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        .encode("utf-8")
    ).hexdigest()


def finding(code, severity, title, message, *, outputs=(), categories=(),
            item_ids=(), resolution_action=None, provided=None,
            supported=None, identity=None):
    finding_id = "TRF-" + digest({
        "code": code, "outputs": sorted(str(item) for item in outputs),
        "categories": sorted(str(item) for item in categories),
        "items": sorted(item_ids), "identity": identity,
    })[:16]
    return TrustedReadinessFinding(
        finding_id=finding_id, issue_code=code, severity=severity,
        title=title, message=message,
        related_selected_outputs=list(outputs),
        related_artifact_categories=list(categories),
        related_project_item_ids=sorted(set(item_ids)),
        resolution_action=resolution_action,
        provided_value=provided, supported_value=supported,
    )


def evaluate_output_policy(selected_outputs, categories):
    findings = []
    for output in selected_outputs:
        rules = OUTPUT_POLICY[output]
        for alternatives in rules["required"]:
            if not any(categories.get(category) for category in alternatives):
                label = " or ".join(item.value.replace("_", " ").lower()
                                    for item in alternatives)
                code = (
                    "DATABASE_SCHEMA_REQUIRED"
                    if len(alternatives) == 1 and alternatives[0].value == "DATABASE_SCHEMA"
                    else "API_SPECIFICATION_REQUIRED"
                    if len(alternatives) == 1 and alternatives[0].value == "API_SPECIFICATION"
                    else f"{output.value}_IMPLEMENTATION_CONTEXT_REQUIRED"
                )
                findings.append(finding(
                    code, FindingSeverity.ERROR,
                    f"{label.title()} required",
                    f"{output.value.replace('_', ' ').title()} requires trusted {label}.",
                    outputs=[output], categories=alternatives,
                ))
        strictly_required = {group[0] for group in rules["required"] if len(group) == 1}
        for category in rules["recommended"]:
            if category not in strictly_required and not categories.get(category):
                findings.append(finding(
                    f"{output.value}_{category.value}_RECOMMENDED",
                    FindingSeverity.WARNING,
                    f"{category.value.replace('_', ' ').title()} recommended",
                    f"Agent 3 can proceed with {output.value.replace('_', ' ').lower()}, but trusted {category.value.replace('_', ' ').lower()} would improve the result.",
                    outputs=[output], categories=[category],
                ))
    return findings


def evaluate_stack(technology_items):
    from app.modules.agents.implementation.preparation.readiness.stack_detector import classify_stack_value

    findings = []
    for item in technology_items:
        category = str(item.data.get("category", ""))
        value = str(item.data.get("value", "")).strip()
        normalized = {"languages": "language", "api_styles": "api_style"}.get(category, category)
        if normalized not in EFFECTIVE_STACK or not value:
            continue
        _, supported = classify_stack_value(normalized, value)
        if supported is False:
            findings.append(finding(
                "UNSUPPORTED_IMPLEMENTATION_STACK", FindingSeverity.ERROR,
                "Unsupported implementation stack",
                "The trusted specification requests technology outside the frozen Agent 3 PP1 implementation stack.",
                categories=[item.artifact_type], item_ids=[item.project_item_id],
                resolution_action=HumanResolutionDecision.ADAPT_TO_SUPPORTED_STACK,
                provided=value, supported=EFFECTIVE_STACK[normalized],
                identity=[normalized, value, item.project_item_id],
            ))
    return findings
