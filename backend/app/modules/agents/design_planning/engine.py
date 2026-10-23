import json
from dataclasses import dataclass
from typing import Any

from pydantic import ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import ModelStructuredOutputError, StructuredModelProvider
from app.modules.agents.design_planning.assignment import build_assignments
from app.modules.agents.design_planning.planning import enhance_sprints
from app.modules.agents.design_planning.schemas import Agent2InputContext, DesignPlanningOutputCode, OUTPUT_MODELS
from app.modules.agents.design_planning.validation import (
    ValidationFinding,
    _collect_nonblank,
    _collect_sources,
    _validate_plan,
    collect_consistency_findings,
)


MAX_CORRECTION_ATTEMPTS = 2

STAGE_1_CODES = (
    DesignPlanningOutputCode.PRODUCT_BACKLOG,
    DesignPlanningOutputCode.EPICS,
    DesignPlanningOutputCode.FEATURES,
)
STAGE_2_CODES = (
    DesignPlanningOutputCode.USER_STORIES,
    DesignPlanningOutputCode.TASKS,
)
STAGE_3_CODES = (
    DesignPlanningOutputCode.SPRINT_PLAN,
)
DESIGN_CODES = (
    DesignPlanningOutputCode.SYSTEM_ARCHITECTURE,
    DesignPlanningOutputCode.UML_DIAGRAMS,
    DesignPlanningOutputCode.DATABASE_SCHEMA,
    DesignPlanningOutputCode.API_SPECIFICATION,
    DesignPlanningOutputCode.WIREFRAMES,
    DesignPlanningOutputCode.UI_FLOW,
)


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
uses EPIC, FEATURE, STORY, TASK, and SPRINT identifiers with explicit hierarchy and dependencies.

Canonical Identifier Format Rules (MANDATORY):
- EPIC identifiers MUST use prefix EPIC- followed by 3+ digits: EPIC-001, EPIC-002, etc. (Never EPIC-1 or E-001).
- FEATURE identifiers MUST use prefix FEATURE- followed by 3+ digits: FEATURE-001, FEATURE-002, etc. (NEVER FEAT-001, FEAT-1, or F-001).
- USER STORY identifiers MUST use prefix STORY- followed by 3+ digits: STORY-001, STORY-002, etc. (Never STORY-1 or US-001).
- TASK identifiers MUST use prefix TASK- followed by 3+ digits: TASK-001, TASK-002, etc. (Never TASK-1 or T-001).
- SPRINT identifiers MUST use prefix SPRINT- followed by 3+ digits: SPRINT-001, SPRINT-002, etc. (Never SPRINT-1).
- In PRODUCT_BACKLOG: item_id MUST match the exact canonical work item identifier (e.g. EPIC-001, FEATURE-001). Never invent PB-001 or BACKLOG-001.

Sprint and assignment values are estimates and heuristic recommendations, not mathematical optimization or guarantees.
Use generic numbered team slots unless a name appears in team_composition.

JIRA_PLAN is Jira-compatible export data only. Set synchronization to NOT_PERFORMED. Never claim remote Jira
creation or synchronization. Never generate AGP/RUN ownership or lifecycle metadata. Return strict JSON with
exactly the requested top-level keys."""


def _make_schema_strict(node: Any) -> None:
    if isinstance(node, dict):
        node.pop("default", None)
        node.pop("pattern", None)
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


def _compact_stage1_context(outputs: dict[str, Any]) -> str:
    lines = ["Validated Planning Foundation from Stage 1:"]
    epics = outputs.get("EPICS") or []
    if epics:
        lines.append("Epics:")
        for epic in epics:
            lines.append(f"  - {epic['id']}: {epic['title']} (Priority: {epic.get('priority', 'MEDIUM')})")
    features = outputs.get("FEATURES") or []
    if features:
        lines.append("Features:")
        for feat in features:
            lines.append(f"  - {feat['id']} (Epic: {feat.get('epic_id', '')}): {feat['title']}")
    return "\n".join(lines)


def _compact_stage2_context(context: Agent2InputContext, outputs: dict[str, Any]) -> str:
    lines = ["Validated Work Items from earlier stages:"]
    stories = outputs.get("USER_STORIES") or []
    if stories:
        lines.append("User Stories:")
        for story in stories:
            lines.append(
                f"  - {story['id']} (Epic: {story.get('epic_id', '')}, Feature: {story.get('feature_id', '')}): "
                f"{story['goal']} ({story.get('estimate_points', 0)} pts)"
            )
    tasks = outputs.get("TASKS") or []
    if tasks:
        lines.append("Tasks:")
        for task in tasks:
            deps = ", ".join(task.get("depends_on", [])) or "None"
            lines.append(
                f"  - {task['id']} (Story: {task.get('story_id', '')}): {task['title']} "
                f"({task.get('estimate_points', 0)} pts, Depends on: [{deps}])"
            )
    lines.append("Sprint Planning Parameters:")
    if context.planning_mode:
        lines.append(f"  - Planning Mode: {context.planning_mode}")
    if context.sprint_duration:
        lines.append(f"  - Sprint Duration: {context.sprint_duration} days")
    if context.project_start_date:
        lines.append(f"  - Project Start Date: {context.project_start_date}")
    if context.expected_project_duration:
        lines.append(f"  - Expected Project Duration: {context.expected_project_duration}")
    if context.development_team_count:
        lines.append(f"  - Development Team Count: {context.development_team_count}")
    return "\n".join(lines)


def _build_deterministic_jira_plan(validated: dict[str, Any]) -> dict[str, Any] | None:
    epics = validated.get("EPICS")
    stories = validated.get("USER_STORIES")
    tasks = validated.get("TASKS")
    if not (epics and stories and tasks):
        return None
    sprints = validated.get("SPRINT_PLAN", [])
    assignments = validated.get("TASK_ASSIGNMENT") or []
    priorities = [
        {"item_id": item["id"], "priority": item["priority"]}
        for item in epics
    ] + [
        {"item_id": item["id"], "priority": item["priority"]}
        for item in stories
    ]
    return {
        "epics": epics,
        "stories": stories,
        "tasks": tasks,
        "sprints": sprints,
        "assignments": assignments,
        "priorities": priorities,
        "synchronization": "NOT_PERFORMED",
    }


def _should_stage_planning(selected: list[DesignPlanningOutputCode]) -> bool:
    selected_set = set(selected)
    has_s1 = bool(selected_set.intersection(STAGE_1_CODES))
    has_downstream = bool(
        selected_set.intersection(STAGE_2_CODES)
        or selected_set.intersection(STAGE_3_CODES)
        or DesignPlanningOutputCode.JIRA_PLAN in selected_set
    )
    return has_s1 and has_downstream


def _format_actionable_findings(findings: list[ValidationFinding]) -> str:
    lines = ["Specific Validation Errors to Correct:"]
    for f in findings:
        lines.append(f"- Field: {f.path}")
        lines.append(f"  Issue: {f.message}")
        path_lower = f.path.lower()
        msg_lower = f.message.lower()
        if "feature" in path_lower and ("id" in path_lower or "pattern" in msg_lower):
            lines.append("  Requirement: FEATURE IDs must strictly match format FEATURE-### (e.g. FEATURE-001, FEATURE-002). Never use FEAT-001, FEAT-1, or F-001.")
        elif "epic" in path_lower and ("id" in path_lower or "pattern" in msg_lower):
            lines.append("  Requirement: EPIC IDs must strictly match format EPIC-### (e.g. EPIC-001, EPIC-002). Never use EPIC-1 or E-001.")
        elif "story" in path_lower and ("id" in path_lower or "pattern" in msg_lower):
            lines.append("  Requirement: STORY IDs must strictly match format STORY-### (e.g. STORY-001, STORY-002). Never use STORY-1 or US-001.")
        elif "task" in path_lower and ("id" in path_lower or "pattern" in msg_lower):
            lines.append("  Requirement: TASK IDs must strictly match format TASK-### (e.g. TASK-001, TASK-002). Never use TASK-1 or T-001.")
        elif "sprint" in path_lower and ("id" in path_lower or "pattern" in msg_lower):
            lines.append("  Requirement: SPRINT IDs must strictly match format SPRINT-### (e.g. SPRINT-001, SPRINT-002). Never use SPRINT-1.")
        elif "backlog" in path_lower and ("item_id" in path_lower or "reference" in msg_lower):
            lines.append("  Requirement: In PRODUCT_BACKLOG, item_id must match the exact canonical work item identifier (e.g. EPIC-001, FEATURE-001). Do not invent PB-001 or BACKLOG-001.")
    return "\n".join(lines)


class Agent2Engine:
    def __init__(self, provider: StructuredModelProvider) -> None:
        self._provider = provider

    def execute(self, context: Agent2InputContext, selected_outputs: list[DesignPlanningOutputCode]) -> dict[str, Any]:
        return self.execute_with_metadata(context, selected_outputs).outputs

    def execute_with_metadata(
        self, context: Agent2InputContext, selected_outputs: list[DesignPlanningOutputCode]
    ) -> Agent2Execution:
        if _should_stage_planning(selected_outputs):
            return self._execute_staged(context, selected_outputs)
        return self._execute_single_stage(context, selected_outputs)

    def _execute_single_stage(
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

    def _execute_staged(
        self, context: Agent2InputContext, selected_outputs: list[DesignPlanningOutputCode]
    ) -> Agent2Execution:
        selected_set = set(selected_outputs)
        validated_all: dict[str, Any] = {}
        total_corrections = 0

        # Stage 0 (Design outputs if selected)
        design_codes = [c for c in DESIGN_CODES if c in selected_set]
        if design_codes:
            v, _, att = self._execute_stage(context, design_codes, validated_all)
            validated_all.update(v)
            total_corrections += att

        # Stage 1: PRODUCT_BACKLOG + EPICS + FEATURES
        s1_codes = [c for c in STAGE_1_CODES if c in selected_set]
        if s1_codes:
            v, _, att = self._execute_stage(context, s1_codes, validated_all)
            validated_all.update(v)
            total_corrections += att

        # Stage 2: USER_STORIES + TASKS
        s2_codes = [c for c in STAGE_2_CODES if c in selected_set]
        if s2_codes:
            compact_s1 = _compact_stage1_context(validated_all)
            v, _, att = self._execute_stage(context, s2_codes, validated_all, compact_context=compact_s1)
            validated_all.update(v)
            total_corrections += att

        # Stage 3: SPRINT_PLAN
        s3_codes = [c for c in STAGE_3_CODES if c in selected_set]
        if s3_codes:
            compact_s2 = _compact_stage2_context(context, validated_all)
            v, _, att = self._execute_stage(context, s3_codes, validated_all, compact_context=compact_s2)
            validated_all.update(v)
            total_corrections += att

        # Optional TASK_ASSIGNMENT (if selected directly and not generated)
        if DesignPlanningOutputCode.TASK_ASSIGNMENT in selected_set and "TASK_ASSIGNMENT" not in validated_all:
            if context.development_team_count and validated_all.get("TASKS"):
                validated_all["TASK_ASSIGNMENT"] = build_assignments(
                    context, validated_all["TASKS"], validated_all.get("SPRINT_PLAN") or []
                )
            else:
                v, _, att = self._execute_stage(context, [DesignPlanningOutputCode.TASK_ASSIGNMENT], validated_all)
                validated_all.update(v)
                total_corrections += att

        # JIRA_PLAN
        if DesignPlanningOutputCode.JIRA_PLAN in selected_set:
            jira_plan = _build_deterministic_jira_plan(validated_all)
            if jira_plan is not None:
                validated_all["JIRA_PLAN"] = jira_plan
            else:
                v, _, att = self._execute_stage(context, [DesignPlanningOutputCode.JIRA_PLAN], validated_all)
                validated_all.update(v)
                total_corrections += att

        # Apply planning heuristics across outputs
        self._apply_planning_heuristics(context, validated_all)

        # Full cross-artifact validation on the merged result
        final_findings = collect_consistency_findings(context, validated_all)
        if any(item.severity == "ERROR" for item in final_findings):
            raise StructuredOutputInvalidError(
                "Merged output failed final cross-artifact validation", final_findings
            )

        # Authoritative filter: return ONLY selected outputs
        selected_values = {code.value for code in selected_outputs}
        final_outputs = {k: v for k, v in validated_all.items() if k in selected_values}

        return Agent2Execution(final_outputs, final_findings, total_corrections)

    def _execute_stage(
        self,
        context: Agent2InputContext,
        stage_codes: list[DesignPlanningOutputCode],
        prior_validated: dict[str, Any],
        compact_context: str | None = None,
    ) -> tuple[dict[str, Any], list[ValidationFinding], int]:
        schema = selected_schema(stage_codes)
        previous_response: dict[str, Any] | None = None
        findings: list[ValidationFinding] = []
        for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
            prompt = (
                self._build_stage_prompt(context, stage_codes, compact_context)
                if attempt == 0
                else self._build_stage_correction_prompt(
                    context, stage_codes, previous_response, findings, attempt, compact_context
                )
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
                    f"Stage {[c.value for c in stage_codes]} remained invalid structured JSON after 2 correction attempts",
                    findings,
                )
            previous_response = raw
            validated, findings = self._validate_schema(raw, stage_codes)
            if validated is not None:
                combined_for_heuristics = {**prior_validated, **validated}
                self._apply_planning_heuristics(context, combined_for_heuristics)
                for k in validated:
                    if k in combined_for_heuristics:
                        validated[k] = combined_for_heuristics[k]
                stage_findings = self._validate_stage_consistency(context, validated, prior_validated)
                findings.extend(stage_findings)
            if validated is not None and not any(item.severity == "ERROR" for item in findings):
                return validated, findings, attempt
            if attempt == MAX_CORRECTION_ATTEMPTS:
                raise StructuredOutputInvalidError(
                    f"Stage {[c.value for c in stage_codes]} remained invalid after 2 correction attempts", findings
                )
        raise StructuredOutputInvalidError(f"Stage {[c.value for c in stage_codes]} validation failed", findings)

    @staticmethod
    def _validate_stage_consistency(
        context: Agent2InputContext,
        stage_outputs: dict[str, Any],
        prior_outputs: dict[str, Any],
    ) -> list[ValidationFinding]:
        combined = {**prior_outputs, **stage_outputs}
        findings: list[ValidationFinding] = []
        _collect_nonblank(stage_outputs, "$", findings)
        _collect_sources(context, stage_outputs, findings)

        backlog = stage_outputs.get("PRODUCT_BACKLOG")
        if backlog:
            known = {item["id"] for code in ("EPICS", "FEATURES", "USER_STORIES", "TASKS") for item in combined.get(code, [])}
            if known:
                for index, item in enumerate(backlog):
                    if item.get("item_type") in ("EPIC", "FEATURE"):
                        if item["item_id"] not in known or (item["parent_id"] and item["parent_id"] not in known):
                            findings.append(ValidationFinding(
                                "BACKLOG_REFERENCE_INVALID", "Backlog item or parent reference is invalid",
                                f"PRODUCT_BACKLOG[{index}]",
                            ))

        if "FEATURES" in stage_outputs and "EPICS" in combined:
            epic_ids = {item["id"] for item in combined["EPICS"]}
            for index, feature in enumerate(stage_outputs["FEATURES"]):
                if feature["epic_id"] not in epic_ids:
                    findings.append(ValidationFinding(
                        "FEATURE_EPIC_REFERENCE_INVALID", "Feature references an unknown epic",
                        f"features[{index}].epic_id",
                    ))

        if "USER_STORIES" in stage_outputs or "TASKS" in stage_outputs:
            _validate_plan(
                context,
                combined.get("EPICS"),
                combined.get("FEATURES"),
                combined.get("USER_STORIES"),
                combined.get("TASKS"),
                None,
                None,
                None,
                "",
                findings,
            )

        if "SPRINT_PLAN" in stage_outputs:
            _validate_plan(
                context,
                None,
                None,
                combined.get("USER_STORIES"),
                combined.get("TASKS"),
                stage_outputs.get("SPRINT_PLAN"),
                None,
                None,
                "",
                findings,
            )

        return findings

    @staticmethod
    def _build_prompt(context: Agent2InputContext, selected: list[DesignPlanningOutputCode]) -> str:
        return (
            "Requested outputs: " + ", ".join(code.value for code in selected)
            + "\nNormalized Agent 2 context:\n"
            + json.dumps(context.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
        )


    @staticmethod
    def _build_stage_prompt(
        context: Agent2InputContext,
        selected: list[DesignPlanningOutputCode],
        compact_context: str | None = None,
    ) -> str:
        prompt = (
            "Requested outputs: " + ", ".join(code.value for code in selected)
            + "\nNormalized Agent 2 context:\n"
            + json.dumps(context.model_dump(mode="json", exclude_none=True), ensure_ascii=False, indent=2)
            + "\n\nCanonical Identifier Format Rules (MANDATORY):\n"
            "- EPIC IDs: EPIC-001, EPIC-002, ... (prefix EPIC-, 3+ digits. Never EPIC-1 or E-001).\n"
            "- FEATURE IDs: FEATURE-001, FEATURE-002, ... (prefix FEATURE-, 3+ digits. NEVER FEAT-001, FEAT-1, or F-001).\n"
            "- USER STORY IDs: STORY-001, STORY-002, ... (prefix STORY-, 3+ digits. Never STORY-1 or US-001).\n"
            "- TASK IDs: TASK-001, TASK-002, ... (prefix TASK-, 3+ digits. Never TASK-1 or T-001).\n"
            "- SPRINT IDs: SPRINT-001, SPRINT-002, ... (prefix SPRINT-, 3+ digits. Never SPRINT-1).\n"
            "- In PRODUCT_BACKLOG: item_id MUST match the exact canonical work item identifier (e.g. EPIC-001, FEATURE-001). Never use PB-001 or BACKLOG-001."
        )
        if compact_context:
            prompt += f"\n\nDependency Context:\n{compact_context}"
        return prompt

    @staticmethod
    def _build_correction_prompt(
        context: Agent2InputContext,
        selected: list[DesignPlanningOutputCode],
        previous_response: dict[str, Any] | None,
        findings: list[ValidationFinding],
        attempt: int,
    ) -> str:
        actionable_advice = _format_actionable_findings(findings)
        return (
            f"Correction attempt {attempt} of {MAX_CORRECTION_ATTEMPTS}. Regenerate the complete selected "
            "object, correct every finding, and do not add unselected outputs.\n\n"
            + actionable_advice + "\n\nValidation findings JSON:\n"
            + json.dumps([item.as_dict() for item in findings], ensure_ascii=False, indent=2)
            + "\n\nPrevious response:\n" + json.dumps(previous_response, ensure_ascii=False, indent=2)
            + "\n\n" + Agent2Engine._build_prompt(context, selected)
        )

    @staticmethod
    def _build_stage_correction_prompt(
        context: Agent2InputContext,
        selected: list[DesignPlanningOutputCode],
        previous_response: dict[str, Any] | None,
        findings: list[ValidationFinding],
        attempt: int,
        compact_context: str | None = None,
    ) -> str:
        actionable_advice = _format_actionable_findings(findings)
        return (
            f"Correction attempt {attempt} of {MAX_CORRECTION_ATTEMPTS}. Regenerate the complete requested stage "
            "object, correct every finding, and do not add unselected outputs.\n\n"
            + actionable_advice + "\n\nValidation findings JSON:\n"
            + json.dumps([item.as_dict() for item in findings], ensure_ascii=False, indent=2)
            + "\n\nPrevious response:\n" + json.dumps(previous_response, ensure_ascii=False, indent=2)
            + "\n\n" + Agent2Engine._build_stage_prompt(context, selected, compact_context)
        )

    @staticmethod
    def _validate_schema(
        raw: dict[str, Any], requested: list[DesignPlanningOutputCode]
    ) -> tuple[dict[str, Any] | None, list[ValidationFinding]]:
        expected = {code.value for code in requested}
        if set(raw) != expected:
            if expected.issubset(set(raw)):
                raw = {k: raw[k] for k in expected}
            else:
                return None, [ValidationFinding(
                    "OUTPUT_SELECTION_MISMATCH", "Generated keys do not match selected outputs", "$"
                )]
        validated: dict[str, Any] = {}
        findings: list[ValidationFinding] = []
        for code in requested:
            try:
                value = TypeAdapter(OUTPUT_MODELS[code]).validate_python(raw[code.value])
                if isinstance(value, list):
                    if not value:
                        findings.append(ValidationFinding(
                            "OUTPUT_EMPTY", f"{code.value} must not be empty", code.value
                        ))
                    else:
                        validated[code.value] = [item.model_dump(mode="json") for item in value]
                else:
                    validated[code.value] = value.model_dump(mode="json")
            except ValidationError as exc:
                for error in exc.errors():
                    loc_parts = [code.value] + [str(part) for part in error.get("loc", ())]
                    field_path = ".".join(loc_parts)
                    err_type = error.get("type", "validation_error")
                    msg = error.get("msg", "Validation error")
                    findings.append(ValidationFinding(
                        "SCHEMA_VALIDATION_FAILED",
                        f"{code.value} validation error ({err_type}): {msg}",
                        field_path,
                    ))
            except (KeyError, TypeError) as exc:
                findings.append(ValidationFinding(
                    "SCHEMA_VALIDATION_FAILED",
                    f"{code.value} data structure error: {type(exc).__name__}",
                    code.value,
                ))
        if findings:
            return None, findings
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
            if outputs.get("TASK_ASSIGNMENT"):
                jira["assignments"] = outputs["TASK_ASSIGNMENT"]
            elif context.development_team_count:
                jira["assignments"] = build_assignments(context, jira["tasks"], jira["sprints"])
            else:
                jira["assignments"] = []
