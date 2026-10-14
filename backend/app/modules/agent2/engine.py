import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, create_model

from app.common.model_provider import ModelStructuredOutputError, StructuredModelProvider
from app.modules.agent2.schemas import Agent2InputContext, DesignPlanningOutputCode, OUTPUT_MODELS


MAX_CORRECTION_ATTEMPTS = 2


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str
    path: str
    severity: Literal["ERROR", "WARNING"] = "ERROR"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path, "severity": self.severity}


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
                findings.extend(self._collect_consistency_findings(context, validated))
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
    def _collect_consistency_findings(
        context: Agent2InputContext, outputs: dict[str, Any]
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        Agent2Engine._collect_nonblank(outputs, "$", findings)
        Agent2Engine._collect_sources(context, outputs, findings)
        Agent2Engine._collect_design(outputs, findings)
        Agent2Engine._collect_planning(context, outputs, findings)
        Agent2Engine._collect_diagrams(outputs, findings)
        return findings

    @staticmethod
    def _collect_nonblank(value: Any, path: str, findings: list[ValidationFinding]) -> None:
        if isinstance(value, str) and not value.strip():
            findings.append(ValidationFinding("BLANK_GENERATED_TEXT", "Generated text is blank", path))
        elif isinstance(value, dict):
            for key, nested in value.items():
                Agent2Engine._collect_nonblank(nested, f"{path}.{key}", findings)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                Agent2Engine._collect_nonblank(nested, f"{path}[{index}]", findings)

    @staticmethod
    def _collect_sources(
        context: Agent2InputContext, outputs: dict[str, Any], findings: list[ValidationFinding]
    ) -> None:
        allowed = {source.source_id for source in context.specification_sources}

        def visit(value: Any, path: str) -> None:
            if isinstance(value, dict):
                refs = value.get("source_refs")
                invalid = sorted(set(refs or []) - allowed)
                if invalid:
                    findings.append(ValidationFinding(
                        "SOURCE_REFERENCE_INVALID", f"Unknown source reference(s): {', '.join(invalid)}",
                        f"{path}.source_refs",
                    ))
                for key, nested in value.items():
                    visit(nested, f"{path}.{key}")
            elif isinstance(value, list):
                for index, nested in enumerate(value):
                    visit(nested, f"{path}[{index}]")
        visit(outputs, "$")

    @staticmethod
    def _collect_design(outputs: dict[str, Any], findings: list[ValidationFinding]) -> None:
        architecture = outputs.get("SYSTEM_ARCHITECTURE")
        component_ids: set[str] = set()
        if architecture:
            component_ids = {item["id"] for item in architecture["components"]}
            Agent2Engine._duplicate_ids(architecture["components"], "SYSTEM_ARCHITECTURE.components", findings)
            for index, component in enumerate(architecture["components"]):
                invalid = set(component["dependencies"]) - component_ids
                if component["id"] in component["dependencies"]:
                    invalid.add(component["id"])
                if invalid:
                    findings.append(ValidationFinding(
                        "ARCHITECTURE_COMPONENT_REFERENCE_INVALID", "Unknown or self component dependency",
                        f"SYSTEM_ARCHITECTURE.components[{index}].dependencies",
                    ))
        database = outputs.get("DATABASE_SCHEMA")
        entity_ids: set[str] = set()
        if database:
            entity_ids = {item["id"] for item in database["entities"]}
            Agent2Engine._duplicate_ids(database["entities"], "DATABASE_SCHEMA.entities", findings)
            for entity_index, entity in enumerate(database["entities"]):
                for relation_index, relation in enumerate(entity["relationships"]):
                    if relation["target_entity_id"] not in entity_ids:
                        findings.append(ValidationFinding(
                            "DATABASE_ENTITY_REFERENCE_INVALID", "Relationship targets an unknown entity",
                            f"DATABASE_SCHEMA.entities[{entity_index}].relationships[{relation_index}]",
                        ))
        api = outputs.get("API_SPECIFICATION")
        if api:
            Agent2Engine._duplicate_ids(api["operations"], "API_SPECIFICATION.operations", findings)
            for index, operation in enumerate(api["operations"]):
                if architecture and (
                    not operation["component_refs"] or set(operation["component_refs"]) - component_ids
                ):
                    findings.append(ValidationFinding(
                        "API_ARCHITECTURE_REFERENCE_INVALID", "API operation must reference a valid component",
                        f"API_SPECIFICATION.operations[{index}].component_refs",
                    ))
                if database and set(operation["entity_refs"]) - entity_ids:
                    findings.append(ValidationFinding(
                        "API_DATABASE_REFERENCE_INVALID", "API operation references an unknown entity",
                        f"API_SPECIFICATION.operations[{index}].entity_refs",
                    ))
        wireframes = outputs.get("WIREFRAMES")
        screen_ids: set[str] = set()
        if wireframes:
            screen_ids = {item["id"] for item in wireframes["screens"]}
            Agent2Engine._duplicate_ids(wireframes["screens"], "WIREFRAMES.screens", findings)
        ui_flow = outputs.get("UI_FLOW")
        if ui_flow:
            Agent2Engine._duplicate_ids(ui_flow["flows"], "UI_FLOW.flows", findings)
            if wireframes:
                for index, flow in enumerate(ui_flow["flows"]):
                    if not flow["screen_refs"] or set(flow["screen_refs"]) - screen_ids:
                        findings.append(ValidationFinding(
                            "UI_FLOW_SCREEN_REFERENCE_INVALID", "UI flow must reference valid screens",
                            f"UI_FLOW.flows[{index}].screen_refs",
                        ))

    @staticmethod
    def _collect_planning(
        context: Agent2InputContext, outputs: dict[str, Any], findings: list[ValidationFinding]
    ) -> None:
        Agent2Engine._validate_plan(
            context, outputs.get("EPICS"), outputs.get("FEATURES"), outputs.get("USER_STORIES"),
            outputs.get("TASKS"), outputs.get("SPRINT_PLAN"), outputs.get("TASK_ASSIGNMENT"),
            None, "", findings,
        )
        jira = outputs.get("JIRA_PLAN")
        if jira:
            Agent2Engine._validate_plan(
                context, jira["epics"], None, jira["stories"], jira["tasks"], jira["sprints"],
                jira["assignments"], jira["priorities"], "JIRA_PLAN.", findings,
            )
            if jira["synchronization"] != "NOT_PERFORMED":
                findings.append(ValidationFinding(
                    "JIRA_SYNCHRONIZATION_INVALID", "Jira plan must remain unsynchronized",
                    "JIRA_PLAN.synchronization",
                ))
            for output_code, jira_key in (("EPICS", "epics"), ("USER_STORIES", "stories"), ("TASKS", "tasks")):
                if output_code in outputs and {item["id"] for item in outputs[output_code]} != {item["id"] for item in jira[jira_key]}:
                    findings.append(ValidationFinding(
                        "JIRA_ARTIFACT_MISMATCH", f"Jira {jira_key} IDs must match {output_code}",
                        f"JIRA_PLAN.{jira_key}",
                    ))
        backlog = outputs.get("PRODUCT_BACKLOG")
        if backlog:
            known = {item["id"] for code in ("EPICS", "FEATURES", "USER_STORIES", "TASKS") for item in outputs.get(code, [])}
            if known:
                for index, item in enumerate(backlog):
                    if item["item_id"] not in known or (item["parent_id"] and item["parent_id"] not in known):
                        findings.append(ValidationFinding(
                            "BACKLOG_REFERENCE_INVALID", "Backlog item or parent reference is invalid",
                            f"PRODUCT_BACKLOG[{index}]",
                        ))

    @staticmethod
    def _validate_plan(
        context: Agent2InputContext,
        epics: list[dict[str, Any]] | None,
        features: list[dict[str, Any]] | None,
        stories: list[dict[str, Any]] | None,
        tasks: list[dict[str, Any]] | None,
        sprints: list[dict[str, Any]] | None,
        assignments: list[dict[str, Any]] | None,
        priorities: list[dict[str, Any]] | None,
        path: str,
        findings: list[ValidationFinding],
    ) -> None:
        for key, items in {"epics": epics, "features": features, "stories": stories, "tasks": tasks, "sprints": sprints}.items():
            if items is not None:
                Agent2Engine._duplicate_ids(items, f"{path}{key}", findings)
        epic_ids = {item["id"] for item in epics or []}
        feature_ids = {item["id"] for item in features or []}
        story_ids = {item["id"] for item in stories or []}
        task_ids = {item["id"] for item in tasks or []}
        stories_by_id = {item["id"]: item for item in stories or []}
        sprint_ids = {item["id"] for item in sprints or []}
        if epics is not None and features is not None:
            for index, feature in enumerate(features):
                if feature["epic_id"] not in epic_ids:
                    findings.append(ValidationFinding(
                        "FEATURE_EPIC_REFERENCE_INVALID", "Feature references an unknown epic",
                        f"{path}features[{index}].epic_id",
                    ))
        for index, story in enumerate(stories or []):
            if epics is not None and story["epic_id"] not in epic_ids:
                findings.append(ValidationFinding(
                    "STORY_EPIC_REFERENCE_INVALID", "Story references an unknown epic",
                    f"{path}stories[{index}].epic_id",
                ))
            if features is not None and story["feature_id"] not in feature_ids:
                findings.append(ValidationFinding(
                    "STORY_FEATURE_REFERENCE_INVALID", "Story references an unknown feature",
                    f"{path}stories[{index}].feature_id",
                ))
        for index, task in enumerate(tasks or []):
            if stories is not None and task["story_id"] not in story_ids:
                findings.append(ValidationFinding(
                    "TASK_STORY_REFERENCE_INVALID", "Task references an unknown story",
                    f"{path}tasks[{index}].story_id",
                ))
            parent = stories_by_id.get(task["story_id"])
            if parent and (task["epic_id"], task["feature_id"]) != (parent["epic_id"], parent["feature_id"]):
                findings.append(ValidationFinding(
                    "TASK_HIERARCHY_CONFLICT", "Task hierarchy conflicts with its story", f"{path}tasks[{index}]"
                ))
            if any(dependency not in task_ids or dependency == task["id"] for dependency in task["depends_on"]):
                findings.append(ValidationFinding(
                    "TASK_DEPENDENCY_INVALID", "Task has an unknown or self dependency",
                    f"{path}tasks[{index}].depends_on",
                ))
        allowed_sprint_items = story_ids | task_ids
        item_sprint: dict[str, int] = {}
        for sprint_index, sprint in enumerate(sprints or []):
            if context.sprint_duration and sprint["duration_days"] != context.sprint_duration:
                findings.append(ValidationFinding(
                    "SPRINT_DURATION_MISMATCH", "Sprint duration differs from supplied duration",
                    f"{path}sprints[{sprint_index}].duration_days",
                ))
            if allowed_sprint_items and set(sprint["item_refs"]) - allowed_sprint_items:
                findings.append(ValidationFinding(
                    "SPRINT_ITEM_REFERENCE_INVALID", "Sprint references an unknown story/task",
                    f"{path}sprints[{sprint_index}].item_refs",
                ))
            for item_ref in sprint["item_refs"]:
                if item_ref in item_sprint:
                    findings.append(ValidationFinding(
                        "SPRINT_ITEM_DUPLICATED", "Work item appears in multiple sprints",
                        f"{path}sprints[{sprint_index}].item_refs",
                    ))
                item_sprint[item_ref] = sprint_index
        for task in tasks or []:
            for dependency in task["depends_on"]:
                if task["id"] in item_sprint and dependency in item_sprint and item_sprint[dependency] > item_sprint[task["id"]]:
                    findings.append(ValidationFinding(
                        "SPRINT_DEPENDENCY_ORDER_INVALID", "Task is scheduled before its dependency",
                        f"{path}sprints[{item_sprint[task['id']]}].item_refs",
                    ))
        assigned: set[str] = set()
        supplied_names = Agent2Engine._supplied_member_names(context)
        for index, assignment in enumerate(assignments or []):
            task_id = assignment["task_id"]
            if task_id in assigned:
                findings.append(ValidationFinding(
                    "TASK_ASSIGNED_MORE_THAN_ONCE", "Task is assigned more than once",
                    f"{path}assignments[{index}].task_id",
                ))
            assigned.add(task_id)
            if tasks is not None and task_id not in task_ids:
                findings.append(ValidationFinding(
                    "ASSIGNMENT_TASK_REFERENCE_INVALID", "Assignment references an unknown task",
                    f"{path}assignments[{index}].task_id",
                ))
            if assignment.get("sprint_id") and sprints is not None and assignment["sprint_id"] not in sprint_ids:
                findings.append(ValidationFinding(
                    "ASSIGNMENT_SPRINT_REFERENCE_INVALID", "Assignment references an unknown sprint",
                    f"{path}assignments[{index}].sprint_id",
                ))
            slot = assignment["team_slot"]
            if not re.fullmatch(r"Team member \d+", slot) and slot not in supplied_names:
                findings.append(ValidationFinding(
                    "ASSIGNEE_NOT_SUPPLIED", "Assignment invented an unsupplied developer",
                    f"{path}assignments[{index}].team_slot",
                ))
        if context.development_team_count and len({item["team_slot"] for item in assignments or []}) > context.development_team_count:
            findings.append(ValidationFinding(
                "ASSIGNMENT_TEAM_COUNT_EXCEEDED", "Assignments exceed team count", f"{path}assignments"
            ))
        valid_priority_refs = epic_ids | story_ids | task_ids
        for index, priority in enumerate(priorities or []):
            if priority["item_id"] not in valid_priority_refs:
                findings.append(ValidationFinding(
                    "JIRA_PRIORITY_REFERENCE_INVALID", "Priority references an unknown item",
                    f"{path}priorities[{index}].item_id",
                ))
        for sprint_index, sprint in enumerate(sprints or []):
            for warning in sprint.get("planning_warnings", []):
                findings.append(ValidationFinding(
                    "SPRINT_ESTIMATE_WARNING", warning,
                    f"{path}sprints[{sprint_index}].planning_warnings", "WARNING",
                ))

    @staticmethod
    def _collect_diagrams(outputs: dict[str, Any], findings: list[ValidationFinding]) -> None:
        for index, diagram in enumerate(outputs.get("UML_DIAGRAMS", {}).get("diagrams", [])):
            source = diagram["source"].strip()
            valid = (
                diagram["notation"] == "MERMAID"
                and re.match(r"^(?:flowchart|graph|sequenceDiagram|classDiagram|erDiagram|stateDiagram)", source)
            ) or (diagram["notation"] == "PLANTUML" and source.startswith("@startuml"))
            if not valid:
                findings.append(ValidationFinding(
                    "DIAGRAM_SOURCE_INVALID", "Diagram source does not match notation",
                    f"UML_DIAGRAMS.diagrams[{index}].source",
                ))

    @staticmethod
    def _duplicate_ids(items: list[dict[str, Any]], path: str, findings: list[ValidationFinding]) -> None:
        ids = [item["id"] for item in items]
        if len(ids) != len(set(ids)):
            findings.append(ValidationFinding("DUPLICATE_ARTIFACT_ID", "Artifact IDs must be unique", path))

    @staticmethod
    def _apply_planning_heuristics(context: Agent2InputContext, outputs: dict[str, Any]) -> None:
        Agent2Engine._enhance_sprints(
            context, outputs.get("SPRINT_PLAN"), outputs.get("TASKS"), outputs.get("USER_STORIES")
        )
        if outputs.get("TASK_ASSIGNMENT") is not None and outputs.get("TASKS") is not None:
            outputs["TASK_ASSIGNMENT"] = Agent2Engine._build_assignments(
                context, outputs["TASKS"], outputs.get("SPRINT_PLAN") or []
            )
        jira = outputs.get("JIRA_PLAN")
        if jira:
            Agent2Engine._enhance_sprints(context, jira["sprints"], jira["tasks"], jira["stories"])
            jira["assignments"] = Agent2Engine._build_assignments(context, jira["tasks"], jira["sprints"])

    @staticmethod
    def _enhance_sprints(
        context: Agent2InputContext,
        sprints: list[dict[str, Any]] | None,
        tasks: list[dict[str, Any]] | None,
        stories: list[dict[str, Any]] | None,
    ) -> None:
        if sprints is None:
            return
        estimates = {item["id"]: item["estimate_points"] for item in (stories or []) + (tasks or [])}
        story_priorities = {item["id"]: item["priority"] for item in stories or []}
        priority_by_ref = dict(story_priorities)
        priority_by_ref.update({
            task["id"]: story_priorities.get(task["story_id"], "MEDIUM") for task in tasks or []
        })
        priority_rank = {"HIGHEST": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "LOWEST": 4}
        task_by_id = {item["id"]: item for item in tasks or []}
        capacity = (
            context.development_team_count * context.sprint_duration
            if context.development_team_count and context.sprint_duration else None
        )
        expected_days = Agent2Engine._duration_days(context.expected_project_duration)
        feasible_sprints = expected_days // context.sprint_duration if expected_days and context.sprint_duration else None
        for index, sprint in enumerate(sprints):
            if context.sprint_duration:
                sprint["duration_days"] = context.sprint_duration
            if capacity:
                sprint["capacity_points"] = capacity
            known_refs = [ref for ref in sprint["item_refs"] if ref in estimates]
            planned = sum(estimates[ref] for ref in known_refs) if known_refs else sprint.get("planned_points", 0)
            sprint["planned_points"] = planned
            sprint["utilization_percent"] = round(planned / sprint["capacity_points"] * 100, 1)
            warnings: list[str] = []
            if not known_refs:
                warnings.append("Workload could not be recomputed because selected story/task estimates were unavailable.")
            if planned > sprint["capacity_points"]:
                warnings.append(f"Estimated workload exceeds capacity by {planned - sprint['capacity_points']} points.")
            if feasible_sprints is not None and index >= feasible_sprints:
                warnings.append("Sprint falls outside the supplied expected project duration estimate.")
            later_refs = {
                ref for later_sprint in sprints[index + 1:] for ref in later_sprint["item_refs"]
            }
            current_ranks = [priority_rank[priority_by_ref[ref]] for ref in sprint["item_refs"] if ref in priority_by_ref]
            later_ranks = [priority_rank[priority_by_ref[ref]] for ref in later_refs if ref in priority_by_ref]
            if current_ranks and later_ranks and min(later_ranks) < max(current_ranks):
                warnings.append("A higher-priority item is planned in a later sprint; review sequencing and dependencies.")
            dependency_notes = []
            for ref in sprint["item_refs"]:
                task = task_by_id.get(ref)
                if task and task["depends_on"]:
                    dependency_notes.append(f"{ref} depends on {', '.join(task['depends_on'])}.")
            sprint["dependency_notes"] = dependency_notes
            sprint["planning_warnings"] = warnings
            sprint["estimate_basis"] = (
                "Estimated capacity = team count × sprint duration days; planned workload is the sum of "
                "referenced generated point estimates."
            )
        total_work = sum(item["estimate_points"] for item in (tasks or stories or []))
        if sprints and feasible_sprints is not None and capacity and total_work > feasible_sprints * capacity:
            sprints[-1]["planning_warnings"].append(
                f"Estimated work ({total_work} points) exceeds duration-feasible capacity ({feasible_sprints * capacity} points)."
            )

    @staticmethod
    def _duration_days(value: str | None) -> int | None:
        if not value:
            return None
        match = re.search(r"(\d+(?:\.\d+)?)\s*(day|week|month)s?", value.casefold())
        if not match:
            return None
        return max(1, round(float(match.group(1)) * {"day": 1, "week": 7, "month": 30}[match.group(2)]))

    @staticmethod
    def _build_assignments(
        context: Agent2InputContext, tasks: list[dict[str, Any]], sprints: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        candidates = Agent2Engine._assignment_candidates(context)
        workloads = {candidate["name"]: 0 for candidate in candidates}
        sprint_by_task = {
            ref: sprint["id"] for sprint in sprints for ref in sprint["item_refs"] if ref.startswith("TASK-")
        }
        result: list[dict[str, Any]] = []
        for task in Agent2Engine._dependency_order(tasks):
            required = {skill.casefold() for skill in task["required_skills"]}
            desired_role = Agent2Engine._desired_role(task)
            minimum_workload = min(workloads.values())
            choices = []
            for position, candidate in enumerate(candidates):
                matches = sorted(skill for skill in candidate["skills"] if any(
                    skill.casefold() in needed or needed in skill.casefold() for needed in required
                ))
                role_match = desired_role in candidate["role"].casefold()
                score = (round(60 * len(matches) / len(required)) if required else 0) + (30 if role_match else 0)
                score += 10 if workloads[candidate["name"]] == minimum_workload else 0
                choices.append((score, -workloads[candidate["name"]], -position, candidate, matches, role_match))
            score, _, _, chosen, matches, role_match = max(choices, key=lambda item: item[:3])
            before = workloads[chosen["name"]]
            reasons = [f"Lowest-current-workload consideration: {before} points before assignment."]
            if role_match:
                reasons.append(f"Role matches inferred {desired_role} task type.")
            if matches:
                reasons.append(f"Matched supplied skills: {', '.join(matches)}.")
            if not chosen["detailed"]:
                reasons.append("No named developer details were supplied; this is a team-slot recommendation.")
            workloads[chosen["name"]] += task["estimate_points"]
            result.append({
                "task_id": task["id"], "team_slot": chosen["name"], "role": chosen["role"],
                "rationale": " ".join(reasons), "sprint_id": sprint_by_task.get(task["id"]),
                "matching_reasons": reasons, "role_match": role_match, "skill_matches": matches,
                "workload_points_before": before, "confidence_score": score,
            })
        return result

    @staticmethod
    def _assignment_candidates(context: Agent2InputContext) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if context.team_composition:
            for entry in re.split(r"[;\n]+", context.team_composition):
                if ":" not in entry:
                    continue
                name, details = (part.strip() for part in entry.split(":", 1))
                role, _, skill_text = details.partition("|")
                if name and role.strip():
                    candidates.append({
                        "name": name, "role": role.strip(),
                        "skills": Agent2Engine._split_terms(skill_text), "detailed": True,
                    })
        count = context.development_team_count or max(1, len(candidates))
        candidates = candidates[:count]
        roles = Agent2Engine._split_terms(context.developer_roles)
        skills = Agent2Engine._split_terms(context.developer_skills)
        while len(candidates) < count:
            index = len(candidates)
            candidates.append({
                "name": f"Team member {index + 1}",
                "role": roles[index % len(roles)] if roles else "Developer",
                "skills": [skill for skill_index, skill in enumerate(skills) if skill_index % count == index],
                "detailed": bool(roles or skills),
            })
        return candidates

    @staticmethod
    def _split_terms(value: str | None) -> list[str]:
        return [part.strip() for part in re.split(r"[,\n]+", value or "") if part.strip()]

    @staticmethod
    def _supplied_member_names(context: Agent2InputContext) -> set[str]:
        return {item["name"] for item in Agent2Engine._assignment_candidates(context) if not item["name"].startswith("Team member ")}

    @staticmethod
    def _desired_role(task: dict[str, Any]) -> str:
        text = " ".join([task["title"], task["description"], *task["required_skills"]]).casefold()
        for role, terms in (
            ("qa", ("test", "qa", "quality")), ("frontend", ("ui", "ux", "frontend", "react")),
            ("devops", ("deploy", "devops", "cloud", "infrastructure")),
            ("backend", ("api", "database", "backend", "python", "java")),
        ):
            if any(term in text for term in terms):
                return role
        return "developer"

    @staticmethod
    def _dependency_order(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        remaining = {task["id"]: task for task in tasks}
        ordered: list[dict[str, Any]] = []
        resolved: set[str] = set()
        while remaining:
            ready = [task for task in remaining.values() if set(task["depends_on"]).issubset(resolved)]
            task = sorted(ready or remaining.values(), key=lambda item: item["id"])[0]
            ordered.append(task)
            resolved.add(task["id"])
            remaining.pop(task["id"])
        return ordered
