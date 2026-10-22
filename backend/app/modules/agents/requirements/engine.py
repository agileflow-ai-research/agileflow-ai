import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import (
    ModelStructuredOutputError,
    StructuredModelProvider,
)
from app.modules.agents.requirements.schemas import (
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


@dataclass(frozen=True)
class Agent1Execution:
    outputs: dict[str, Any]
    clarification_recommended: bool


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
JSON conforming to the supplied schema, with exactly the requested top-level output keys.

Identifier rules: use FR-001, NFR-001, US-001, AC-001, PER-001, QF-001, and CQ-001 style identifiers.
Never use AGP-, RUN-, PRJ-, USR-, APP-, or EVT- identifiers. Every source_refs value must be an input
source ID. When requirements and user stories are requested together, populate each story's
requirement_refs with generated FR/NFR IDs. Acceptance criteria related_ids must reference generated
FR/NFR/US IDs when those artifacts are requested together; otherwise link to the relevant source ID.
Quality findings and clarification questions may reference only supplied sources or generated artifacts.
Do not repeat equivalent items. Optional unknown values must be null rather than invented."""


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
        return self.execute_with_metadata(context, selected_outputs).outputs

    def execute_with_metadata(
        self,
        context: Agent1InputContext,
        selected_outputs: list[RequirementOutputCode],
    ) -> Agent1Execution:
        requested = list(selected_outputs)
        requested_keys = {code.value for code in requested}
        duplicates = find_exact_duplicates(context)

        try:
            raw = self._provider.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=self._build_user_prompt(context, requested, duplicates),
                json_schema=_selected_schema(requested),
            )
        except ModelStructuredOutputError as exc:
            raise StructuredOutputInvalidError(
                "Model response was not valid structured JSON"
            ) from exc
        if not requested_keys.issubset(raw):
            raise StructuredOutputInvalidError(
                "Model output did not contain every requested output"
            )
        clarification_key = RequirementOutputCode.CLARIFICATION_QUESTIONS.value
        unselected_clarifications = (
            raw.get(clarification_key, [])
            if clarification_key not in requested_keys
            else []
        )
        raw = {key: value for key, value in raw.items() if key in requested_keys}

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
        self._validate_unique_artifacts(validated)
        self._merge_deterministic_findings(validated, duplicates)
        self._merge_required_clarifications(validated, duplicates)
        if not set(validated).issubset(requested_keys):
            raise StructuredOutputInvalidError(
                "Final output contained an unselected artifact"
            )
        clarification_recommended = bool(
            unselected_clarifications
            or duplicates
            or any(
                finding.get("suggested_clarification")
                for finding in validated.get(
                    RequirementOutputCode.QUALITY_FINDINGS.value, []
                )
            )
        )
        return Agent1Execution(validated, clarification_recommended)

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
        requirement_refs = {
            item["id"]
            for code in (
                RequirementOutputCode.FUNCTIONAL_REQUIREMENTS.value,
                RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS.value,
            )
            for item in outputs.get(code, [])
        }
        story_refs = {
            item["id"]
            for item in outputs.get(RequirementOutputCode.USER_STORIES.value, [])
        }
        criterion_refs = {
            item["id"]
            for item in outputs.get(
                RequirementOutputCode.ACCEPTANCE_CRITERIA.value, []
            )
        }
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
        stories = outputs.get(RequirementOutputCode.USER_STORIES.value, [])
        for item in stories:
            linked = set(item["requirement_refs"])
            if not linked.issubset(requirement_refs):
                raise StructuredOutputInvalidError(
                    "USER_STORIES contains an invalid requirement reference"
                )
            if requirement_refs and not linked:
                raise StructuredOutputInvalidError(
                    "USER_STORIES must link to generated requirements"
                )

        criteria_allowed = valid_source_refs | requirement_refs | story_refs
        for item in outputs.get(
            RequirementOutputCode.ACCEPTANCE_CRITERIA.value, []
        ):
            linked = set(item["related_ids"])
            if not linked.issubset(criteria_allowed):
                raise StructuredOutputInvalidError(
                    "ACCEPTANCE_CRITERIA contains an invalid reference"
                )
            if (requirement_refs or story_refs) and not linked.intersection(
                requirement_refs | story_refs
            ):
                raise StructuredOutputInvalidError(
                    "ACCEPTANCE_CRITERIA must link to a generated requirement or story"
                )

        evidence_refs = (
            valid_source_refs | requirement_refs | story_refs | criterion_refs
        )
        for code, field in (
            (RequirementOutputCode.QUALITY_FINDINGS.value, "affected_refs"),
            (RequirementOutputCode.CLARIFICATION_QUESTIONS.value, "related_refs"),
        ):
            for item in outputs.get(code, []):
                if not set(item[field]).issubset(evidence_refs):
                    raise StructuredOutputInvalidError(
                        f"{code} contains an invalid reference"
                    )

    @staticmethod
    def _validate_nonblank_strings(value: Any) -> None:
        if isinstance(value, str) and not value.strip():
            raise StructuredOutputInvalidError(
                "Model output contains an empty mandatory string"
            )
        if isinstance(value, str) and re.search(
            r"\b(?:AGP|RUN|USR|PRJ|APP|EVT)-\d{3,}\b", value
        ):
            raise StructuredOutputInvalidError(
                "Model output contains backend-owned system metadata"
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
        findings = outputs.get(RequirementOutputCode.QUALITY_FINDINGS.value)
        if findings is None:
            return
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

    @staticmethod
    def _validate_unique_artifacts(outputs: dict[str, Any]) -> None:
        identifiers: list[str] = []
        requirement_statements: list[str] = []
        for code, value in outputs.items():
            if not isinstance(value, list):
                continue
            identifiers.extend(
                item["id"] for item in value if isinstance(item, dict) and "id" in item
            )
            if code in {
                RequirementOutputCode.FUNCTIONAL_REQUIREMENTS.value,
                RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS.value,
            }:
                requirement_statements.extend(
                    _canonical_statement(item["statement"]) for item in value
                )
        if len(identifiers) != len(set(identifiers)):
            raise StructuredOutputInvalidError(
                "Model output contains duplicate artifact identifiers"
            )
        if len(requirement_statements) != len(set(requirement_statements)):
            raise StructuredOutputInvalidError(
                "Model output contains duplicate requirement statements"
            )

    @staticmethod
    def _merge_required_clarifications(
        outputs: dict[str, Any],
        duplicates: list[str],
    ) -> None:
        questions = outputs.get(
            RequirementOutputCode.CLARIFICATION_QUESTIONS.value
        )
        if questions is None:
            return

        candidates: list[tuple[str, str, list[str], str]] = []
        for index, statement in enumerate(duplicates, start=1):
            candidates.append(
                (
                    f"CQ-DUP-{index:03d}",
                    "Is the repeated requirement intentional, or should it be consolidated?",
                    ["TEXT-001"],
                    f"The statement appears more than once: {statement}",
                )
            )
        for finding in outputs.get(
            RequirementOutputCode.QUALITY_FINDINGS.value, []
        ):
            suggestion = finding.get("suggested_clarification")
            if suggestion:
                candidates.append(
                    (
                        f"CQ-QF-{finding['id'].removeprefix('QF-')}",
                        suggestion,
                        finding["affected_refs"],
                        finding["explanation"],
                    )
                )
        if not candidates:
            return

        existing = {
            _canonical_statement(question["question"]) for question in questions
        }
        existing_ids = {question["id"] for question in questions}
        for identifier, question, refs, reason in candidates:
            if (
                identifier not in existing_ids
                and _canonical_statement(question) not in existing
            ):
                questions.append(
                    {
                        "id": identifier,
                        "question": question,
                        "reason": reason,
                        "related_refs": refs,
                    }
                )
                existing_ids.add(identifier)
                existing.add(_canonical_statement(question))
