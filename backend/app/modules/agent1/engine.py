import json
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import (
    ModelStructuredOutputError,
    StructuredModelProvider,
)
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
JSON conforming to the supplied schema, with exactly the requested top-level output keys.

Identifier rules: use FR-001, NFR-001, US-001, AC-001, PER-001, QF-001, and CQ-001 style identifiers.
Never use AGP-, RUN-, PRJ-, USR-, APP-, or EVT- identifiers. Every source_refs value must be an input
source ID. When requirements and user stories are requested together, populate each story's
requirement_refs with generated FR/NFR IDs. Acceptance criteria related_ids must reference generated
FR/NFR/US IDs when those artifacts are requested together; otherwise link to the relevant source ID.
Quality findings use issue, affected_requirement_refs, source_refs, and recommendation. Their affected
requirement references may contain only generated FR/NFR IDs, and their source references may contain
only supplied source IDs. Clarification questions use quality_finding_refs, requirement_refs, source_refs,
and optional LOW/MEDIUM/HIGH priority. Ask targeted questions about unresolved issues, never generic questions.
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
        requested = list(selected_outputs)
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

        first_source_id = context.sources[0].source_id if context.sources else "TEXT-001"
        self._merge_deterministic_findings(validated, duplicates, first_source_id)
        self._merge_required_clarifications(validated)
        self._validate_nonblank_strings(validated)
        self._validate_references(context, validated)
        self._validate_unique_artifacts(
            validated,
            allow_requirement_duplicates=(
                RequirementOutputCode.QUALITY_FINDINGS.value in validated
            ),
        )
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

        for item in outputs.get(RequirementOutputCode.QUALITY_FINDINGS.value, []):
            if not set(item["affected_requirement_refs"]).issubset(requirement_refs):
                raise StructuredOutputInvalidError(
                    "QUALITY_FINDINGS contains an invalid requirement reference"
                )
            if not set(item["source_refs"]).issubset(valid_source_refs):
                raise StructuredOutputInvalidError(
                    "QUALITY_FINDINGS contains an invalid source reference"
                )

        valid_quality_refs = {
            item["id"]
            for item in outputs.get(
                RequirementOutputCode.QUALITY_FINDINGS.value, []
            )
        }
        for item in outputs.get(
            RequirementOutputCode.CLARIFICATION_QUESTIONS.value, []
        ):
            if not set(item["quality_finding_refs"]).issubset(valid_quality_refs):
                raise StructuredOutputInvalidError(
                    "CLARIFICATION_QUESTIONS contains an invalid quality finding reference"
                )
            if not set(item["requirement_refs"]).issubset(requirement_refs):
                raise StructuredOutputInvalidError(
                    "CLARIFICATION_QUESTIONS contains an invalid requirement reference"
                )
            if not set(item["source_refs"]).issubset(valid_source_refs):
                raise StructuredOutputInvalidError(
                    "CLARIFICATION_QUESTIONS contains an invalid source reference"
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
        first_source_id: str = "TEXT-001",
    ) -> None:
        findings = outputs.get(RequirementOutputCode.QUALITY_FINDINGS.value)
        if findings is None:
            return
        candidates: list[dict[str, Any]] = []
        for statement in duplicates:
            candidates.append(
                {
                    "issue": (
                        "The exact source statement appears more than once: "
                        f"{statement}"
                    ),
                    "affected_requirement_refs": [],
                    "source_refs": [first_source_id],
                }
            )

        requirements = [
            item
            for code in (
                RequirementOutputCode.FUNCTIONAL_REQUIREMENTS.value,
                RequirementOutputCode.NON_FUNCTIONAL_REQUIREMENTS.value,
            )
            for item in outputs.get(code, [])
        ]
        by_statement: dict[str, list[dict[str, Any]]] = {}
        by_id: dict[str, list[dict[str, Any]]] = {}
        for requirement in requirements:
            by_statement.setdefault(
                _canonical_statement(requirement["statement"]), []
            ).append(requirement)
            by_id.setdefault(requirement["id"], []).append(requirement)
        for statement, matches in by_statement.items():
            if len(matches) > 1:
                candidates.append(
                    {
                        "issue": (
                            "Multiple requirements have the same statement: "
                            f"{statement}"
                        ),
                        "affected_requirement_refs": list(
                            dict.fromkeys(item["id"] for item in matches)
                        ),
                        "source_refs": list(
                            dict.fromkeys(
                                ref
                                for item in matches
                                for ref in item["source_refs"]
                            )
                        ),
                    }
                )
        for identifier, matches in by_id.items():
            if len(matches) > 1:
                candidates.append(
                    {
                        "issue": (
                            "The requirement identifier is used more than once: "
                            f"{identifier}"
                        ),
                        "affected_requirement_refs": [identifier],
                        "source_refs": list(
                            dict.fromkeys(
                                ref
                                for item in matches
                                for ref in item["source_refs"]
                            )
                        ),
                    }
                )

        existing_issues = {_canonical_statement(item["issue"]) for item in findings}
        used_ids = {item["id"] for item in findings}
        next_id = 1
        for candidate in candidates:
            if _canonical_statement(candidate["issue"]) in existing_issues:
                continue
            while f"QF-{next_id:03d}" in used_ids:
                next_id += 1
            finding = {
                "id": f"QF-{next_id:03d}",
                "category": QualityFindingCategory.DUPLICATE.value,
                **candidate,
                "recommendation": (
                    "Confirm whether the duplicate is intentional and consolidate "
                    "it if not."
                ),
            }
            findings.append(finding)
            used_ids.add(finding["id"])
            existing_issues.add(_canonical_statement(finding["issue"]))

    @staticmethod
    def _validate_unique_artifacts(
        outputs: dict[str, Any], *, allow_requirement_duplicates: bool = False
    ) -> None:
        identifiers: list[str] = []
        non_requirement_identifiers: list[str] = []
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
            else:
                non_requirement_identifiers.extend(
                    item["id"]
                    for item in value
                    if isinstance(item, dict) and "id" in item
                )
        checked_identifiers = (
            non_requirement_identifiers
            if allow_requirement_duplicates
            else identifiers
        )
        if len(checked_identifiers) != len(set(checked_identifiers)):
            raise StructuredOutputInvalidError(
                "Model output contains duplicate artifact identifiers"
            )
        if (
            len(requirement_statements) != len(set(requirement_statements))
            and not allow_requirement_duplicates
        ):
            raise StructuredOutputInvalidError(
                "Model output contains duplicate requirement statements"
            )

    @staticmethod
    def _merge_required_clarifications(
        outputs: dict[str, Any],
    ) -> None:
        questions = outputs.get(
            RequirementOutputCode.CLARIFICATION_QUESTIONS.value
        )
        supplemental = questions is None
        if supplemental:
            questions = []

        candidates: list[dict[str, Any]] = []
        for finding in outputs.get(
            RequirementOutputCode.QUALITY_FINDINGS.value, []
        ):
            suggestion = finding.get("recommendation")
            if suggestion:
                prompts = {
                    "AMBIGUITY": "What exact meaning should replace the ambiguous wording",
                    "MISSING_INFORMATION": "What missing business rule or detail should apply",
                    "CONFLICT": "Which conflicting rule should take precedence",
                    "DUPLICATE": "Should the identified duplicate be consolidated",
                    "INCONSISTENCY": "Which interpretation should be used consistently",
                }
                candidates.append(
                    {
                        "question": (
                            f"{prompts[finding['category']]} for {finding['id']}?"
                        ),
                        "reason": finding["issue"],
                        "quality_finding_refs": [finding["id"]],
                        "requirement_refs": finding["affected_requirement_refs"],
                        "source_refs": finding["source_refs"],
                        "priority": (
                            "HIGH"
                            if finding["category"] == "CONFLICT"
                            else "MEDIUM"
                        ),
                    }
                )
        if not candidates:
            return

        existing = {
            _canonical_statement(question["question"]) for question in questions
        }
        existing_ids = {question["id"] for question in questions}
        next_id = 1
        for candidate in candidates:
            if _canonical_statement(candidate["question"]) in existing:
                continue
            while f"CQ-{next_id:03d}" in existing_ids:
                next_id += 1
            question = {"id": f"CQ-{next_id:03d}", **candidate}
            questions.append(question)
            existing_ids.add(question["id"])
            existing.add(_canonical_statement(question["question"]))
        if supplemental and questions:
            outputs[RequirementOutputCode.CLARIFICATION_QUESTIONS.value] = questions
