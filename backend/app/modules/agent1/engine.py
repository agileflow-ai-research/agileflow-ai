import json
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import StructuredModelProvider
from app.modules.agent1.schemas import (
    AcceptanceCriterion,
    Agent1InputContext,
    ClarificationQuestion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Persona,
    QualityFinding,
    QualityFindingCategory,
    RequirementOutputCode,
    SRSArtifact,
    UserStory,
)


class StructuredOutputInvalidError(ValueError):
    """Model output did not conform to the selected Agent 1 contract."""


OUTPUT_MODELS: dict[RequirementOutputCode, type[BaseModel] | Any] = {
    RequirementOutputCode.FUNCTIONAL_REQUIREMENTS: list[FunctionalRequirement],
    RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS: list[NonFunctionalRequirement],
    RequirementOutputCode.USER_STORIES: list[UserStory],
    RequirementOutputCode.ACCEPTANCE_CRITERIA: list[AcceptanceCriterion],
    RequirementOutputCode.PERSONAS: list[Persona],
    RequirementOutputCode.QUALITY_FINDINGS: list[QualityFinding],
    RequirementOutputCode.CLARIFICATION_QUESTIONS: list[ClarificationQuestion],
    RequirementOutputCode.SRS: SRSArtifact,
}


SYSTEM_PROMPT = """You are the Requirement Gathering and Analysis Agent for AgileFlow AI.
Generate only domain requirements content grounded in the supplied sources. Never generate project IDs,
run IDs, owners, timestamps, lifecycle status, or claims unsupported by the input. Use source IDs for
traceability. Flag ambiguity, missing information, conflicts, semantic duplicates, and inconsistencies
with exactly the allowed quality categories. Keep assumptions and unresolved issues visible. Return only
JSON conforming to the supplied schema, with exactly the requested top-level output keys."""


def _selected_schema(selected: list[RequirementOutputCode]) -> dict[str, Any]:
    response_model = create_model(
        "Agent1SelectedOutputs",
        __config__=ConfigDict(extra="forbid"),
        **{code.value: (OUTPUT_MODELS[code], ...) for code in selected},
    )
    schema = response_model.model_json_schema()
    _make_schema_strict(schema)
    return schema


def _make_schema_strict(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["required"] = list(properties)
            node["additionalProperties"] = False
        for value in node.values():
            _make_schema_strict(value)
    elif isinstance(node, list):
        for value in node:
            _make_schema_strict(value)


def _canonical_statement(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def find_exact_duplicates(context: Agent1InputContext) -> list[str]:
    statements: list[str] = []
    for source in context.sources:
        statements.extend(
            part.strip(" \t-*\u2022")
            for part in re.split(r"[\r\n]+", source.content)
            if part.strip(" \t-*\u2022")
        )
    if context.existing_requirements:
        statements.extend(
            part.strip(" \t-*\u2022")
            for part in re.split(r"[\r\n]+", context.existing_requirements)
            if part.strip(" \t-*\u2022")
        )
    counts = Counter(_canonical_statement(statement) for statement in statements)
    return sorted(statement for statement, count in counts.items() if count > 1)


class Agent1Engine:
    def __init__(self, provider: StructuredModelProvider) -> None:
        self._provider = provider

    def execute(
        self,
        context: Agent1InputContext,
        selected_outputs: list[RequirementOutputCode],
    ) -> dict[str, Any]:
        requested = list(selected_outputs)
        duplicates = find_exact_duplicates(context)
        if (
            RequirementOutputCode.QUALITY_FINDINGS in requested
            and RequirementOutputCode.CLARIFICATION_QUESTIONS not in requested
        ):
            requested.append(RequirementOutputCode.CLARIFICATION_QUESTIONS)
        if duplicates and RequirementOutputCode.QUALITY_FINDINGS not in requested:
            requested.append(RequirementOutputCode.QUALITY_FINDINGS)
        if duplicates and RequirementOutputCode.CLARIFICATION_QUESTIONS not in requested:
            requested.append(RequirementOutputCode.CLARIFICATION_QUESTIONS)

        raw = self._provider.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=self._build_user_prompt(context, requested, duplicates),
            json_schema=_selected_schema(requested),
        )
        if set(raw) != {code.value for code in requested}:
            raise StructuredOutputInvalidError(
                "Model output keys did not match requested outputs"
            )

        validated: dict[str, Any] = {}
        try:
            for code in requested:
                value = TypeAdapter(OUTPUT_MODELS[code]).validate_python(raw[code.value])
                if (
                    isinstance(value, list)
                    and not value
                    and code
                    not in {
                        RequirementOutputCode.QUALITY_FINDINGS,
                        RequirementOutputCode.CLARIFICATION_QUESTIONS,
                    }
                ):
                    raise StructuredOutputInvalidError(
                        f"{code.value} must not be empty"
                    )
                if isinstance(value, BaseModel):
                    validated[code.value] = value.model_dump(mode="json")
                else:
                    validated[code.value] = [item.model_dump(mode="json") for item in value]
        except (ValidationError, KeyError, TypeError) as exc:
            raise StructuredOutputInvalidError(
                "Model output failed Agent 1 structured validation"
            ) from exc

        self._validate_nonblank_strings(validated)
        self._validate_references(context, validated)
        self._merge_deterministic_findings(validated, duplicates)
        return validated

    @staticmethod
    def _build_user_prompt(
        context: Agent1InputContext,
        selected: list[RequirementOutputCode],
        duplicates: list[str],
    ) -> str:
        payload = context.model_dump(mode="json", exclude_none=True)
        return (
            "Requested outputs: "
            + ", ".join(code.value for code in selected)
            + "\nDeterministic exact duplicates: "
            + json.dumps(duplicates)
            + "\nNormalized input context:\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _validate_references(
        context: Agent1InputContext,
        outputs: dict[str, Any],
    ) -> None:
        valid_source_refs = {source.source_id for source in context.sources}
        valid_item_refs = set(valid_source_refs)
        for value in outputs.values():
            if isinstance(value, list):
                valid_item_refs.update(
                    item["id"]
                    for item in value
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                )
        for code in (
            RequirementOutputCode.FUNCTIONAL_REQUIREMENTS.value,
            RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS.value,
            RequirementOutputCode.USER_STORIES.value,
        ):
            for item in outputs.get(code, []):
                if not set(item["source_refs"]).issubset(valid_source_refs):
                    raise StructuredOutputInvalidError(
                        f"{code} contains an invalid source reference"
                    )
        for code, field in (
            (RequirementOutputCode.ACCEPTANCE_CRITERIA.value, "related_ids"),
            (RequirementOutputCode.QUALITY_FINDINGS.value, "affected_refs"),
            (RequirementOutputCode.CLARIFICATION_QUESTIONS.value, "related_refs"),
        ):
            for item in outputs.get(code, []):
                if not set(item[field]).issubset(valid_item_refs):
                    raise StructuredOutputInvalidError(
                        f"{code} contains an invalid reference"
                    )

    @staticmethod
    def _validate_nonblank_strings(value: Any) -> None:
        if isinstance(value, str) and not value.strip():
            raise StructuredOutputInvalidError(
                "Model output contains an empty mandatory string"
            )
        if isinstance(value, dict):
            for nested in value.values():
                Agent1Engine._validate_nonblank_strings(nested)
        elif isinstance(value, list):
            for nested in value:
                Agent1Engine._validate_nonblank_strings(nested)

    @staticmethod
    def _merge_deterministic_findings(
        outputs: dict[str, Any],
        duplicates: list[str],
    ) -> None:
        if not duplicates:
            return
        findings = outputs.setdefault(RequirementOutputCode.QUALITY_FINDINGS.value, [])
        existing = {
            (item["category"], item["explanation"].casefold()) for item in findings
        }
        for index, statement in enumerate(duplicates, start=1):
            explanation = f"The exact statement appears more than once: {statement}"
            key = (QualityFindingCategory.DUPLICATE.value, explanation.casefold())
            if key not in existing:
                findings.append(
                    {
                        "id": f"QF-DUP-{index:03d}",
                        "category": QualityFindingCategory.DUPLICATE.value,
                        "affected_refs": ["TEXT-001"],
                        "explanation": explanation,
                        "suggested_clarification": "Confirm whether the repeated statement is intentional.",
                    }
                )
