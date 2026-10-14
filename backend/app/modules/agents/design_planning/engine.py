import json
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import ModelStructuredOutputError, StructuredModelProvider
from app.modules.agents.design_planning.assignment import build_assignments
from app.modules.agents.design_planning.planning import enhance_sprints
from app.modules.agents.design_planning.schemas import Agent2InputContext, DesignPlanningOutputCode, OUTPUT_MODELS
from app.modules.agents.design_planning.validation import ValidationFinding, collect_consistency_findings


MAX_CORRECTION_ATTEMPTS = 2


@dataclass(frozen=True)
class Agent2Execution:
    outputs: dict[str, Any]
    validation_findings: list[ValidationFinding]
    correction_attempts: int


class StructuredOutputInvalidError(ValueError):
    """Generated data did not satisfy the Agent 2 contract."""

    def __init__(self, message: str, findings: list[ValidationFinding] | None = None) -> None:
        super().__init__(message)
        self.findings = findings or []


SYSTEM_PROMPT = """You are Agent 2, the Project Management and Design Agent for AgileFlow AI.
Generate only the requested JSON outputs, grounded in normalized specification sources. Preserve source_refs
using supplied SPEC identifiers; these are generated source labels, not invented requirement IDs. Keep
assumptions explicit. UML output is Mermaid/PlantUML source, and WIREFRAMES are structured specifications.

Use machine-readable references: component dependencies use COMP IDs, database relationships target ENTITY
IDs, API references link to selected components/entities, and UI flow screen_refs link to WF IDs. Planning
uses EPIC, FEATURE, STORY, TASK, and SPRINT identifiers with explicit hierarchy and dependencies. Sprint and
assignment values are estimates and heuristic recommendations, not mathematical optimization or guarantees.
Use generic numbered team slots unless a name appears in team_composition.

JIRA_PLAN is Jira-compatible export data only. Set synchronization to NOT_PERFORMED. Never claim remote Jira
creation or synchronization. Never generate AGP/RUN ownership or lifecycle metadata. Return strict JSON with
exactly the requested top-level keys."""


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


def selected_schema(selected: list[DesignPlanningOutputCode]) -> dict[str, Any]:
    response_model = create_model(
        "Agent2SelectedOutputs", __config__=ConfigDict(extra="forbid"),
        **{code.value: (OUTPUT_MODELS[code], ...) for code in selected},
    )
    schema = response_model.model_json_schema()
    _make_schema_strict(schema)
    return schema


class Agent2Engine:
    def __init__(self, provider: StructuredModelProvider) -> None:
        self._provider = provider

    def execute(self, context: Agent2InputContext, selected_outputs: list[DesignPlanningOutputCode]) -> dict[str, Any]:
        return self.execute_with_metadata(context, selected_outputs).outputs

    def execute_with_metadata(
        self, context: Agent2InputContext, selected_outputs: list[DesignPlanningOutputCode]
    ) -> Agent2Execution:
        requested = list(selected_outputs)
        schema = selected_schema(requested)
        previous_response: dict[str, Any] | None = None
        findings: list[ValidationFinding] = []
        for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
            prompt = self._build_prompt(context, requested) if attempt == 0 else self._build_correction_prompt(
                context, requested, previous_response, findings, attempt
            )
            try:
                raw = self._provider.generate_structured(
                    system_prompt=SYSTEM_PROMPT, user_prompt=prompt, json_schema=schema
                )
            except ModelStructuredOutputError:
                findings = [ValidationFinding(
                    "STRUCTURED_JSON_INVALID", "Provider response was not valid structured JSON", "$"
                )]
                previous_response = None
                if attempt < MAX_CORRECTION_ATTEMPTS:
                    continue
                raise StructuredOutputInvalidError(
                    "Structured output remained invalid after 2 correction attempts", findings
                )
            previous_response = raw
            validated, findings = self._validate_schema(raw, requested)
            if validated is not None:
                self._apply_planning_heuristics(context, validated)
                findings.extend(collect_consistency_findings(context, validated))
            if validated is not None and not any(item.severity == "ERROR" for item in findings):
                return Agent2Execution(validated, findings, attempt)
            if attempt == MAX_CORRECTION_ATTEMPTS:
                raise StructuredOutputInvalidError(
                    "Structured output remained invalid after 2 correction attempts", findings
                )
        raise StructuredOutputInvalidError("Structured output validation failed", findings)

    @staticmethod
    def _build_prompt(context: Agent2InputContext, selected: list[DesignPlanningOutputCode]) -> str:
        return (
            "Requested outputs: " + ", ".join(code.value for code in selected)
            + "\nNormalized Agent 2 context:\n"
            + json.dumps(context.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _build_correction_prompt(
        context: Agent2InputContext,
        selected: list[DesignPlanningOutputCode],
        previous_response: dict[str, Any] | None,
        findings: list[ValidationFinding],
        attempt: int,
    ) -> str:
        return (
            f"Correction attempt {attempt} of {MAX_CORRECTION_ATTEMPTS}. Regenerate the complete selected "
            "object, correct every finding, and do not add unselected outputs.\nValidation findings:\n"
            + json.dumps([item.as_dict() for item in findings], ensure_ascii=False, indent=2)
            + "\nPrevious response:\n" + json.dumps(previous_response, ensure_ascii=False, indent=2)
            + "\n" + Agent2Engine._build_prompt(context, selected)
        )

    @staticmethod
    def _validate_schema(
        raw: dict[str, Any], requested: list[DesignPlanningOutputCode]
    ) -> tuple[dict[str, Any] | None, list[ValidationFinding]]:
        expected = {code.value for code in requested}
        if set(raw) != expected:
            return None, [ValidationFinding(
                "OUTPUT_SELECTION_MISMATCH", "Generated keys do not match selected outputs", "$"
            )]
        validated: dict[str, Any] = {}
        try:
            for code in requested:
                value = TypeAdapter(OUTPUT_MODELS[code]).validate_python(raw[code.value])
                if isinstance(value, list):
                    if not value:
                        return None, [ValidationFinding(
                            "OUTPUT_EMPTY", f"{code.value} must not be empty", code.value
                        )]
                    validated[code.value] = [item.model_dump(mode="json") for item in value]
                else:
                    validated[code.value] = value.model_dump(mode="json")
        except (ValidationError, KeyError, TypeError) as exc:
            path = "$"
            if isinstance(exc, ValidationError) and exc.errors():
                path = ".".join(str(part) for part in exc.errors()[0].get("loc", ())) or "$"
            return None, [ValidationFinding(
                "SCHEMA_VALIDATION_FAILED", "Generated output failed the Agent 2 structured schema", path
            )]
        return validated, []

    @staticmethod
    def _apply_planning_heuristics(context: Agent2InputContext, outputs: dict[str, Any]) -> None:
        enhance_sprints(
            context, outputs.get("SPRINT_PLAN"), outputs.get("TASKS"), outputs.get("USER_STORIES")
        )
        if outputs.get("TASK_ASSIGNMENT") is not None and outputs.get("TASKS") is not None:
            outputs["TASK_ASSIGNMENT"] = build_assignments(
                context, outputs["TASKS"], outputs.get("SPRINT_PLAN") or []
            )
        jira = outputs.get("JIRA_PLAN")
        if jira:
            enhance_sprints(context, jira["sprints"], jira["tasks"], jira["stories"])
            jira["assignments"] = build_assignments(context, jira["tasks"], jira["sprints"])
