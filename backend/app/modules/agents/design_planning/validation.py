"""Deterministic cross-artifact and structural validation for Agent 2."""

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.agents.design_planning.assignment import supplied_member_names
from app.modules.agents.design_planning.schemas import Agent2InputContext


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str
    path: str
    severity: Literal["ERROR", "WARNING"] = "ERROR"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path, "severity": self.severity}


def collect_consistency_findings(
    context: Agent2InputContext, outputs: dict[str, Any]
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    _collect_nonblank(outputs, "$", findings)
    _collect_sources(context, outputs, findings)
    _collect_design(outputs, findings)
    _collect_planning(context, outputs, findings)
    _collect_diagrams(outputs, findings)
    return findings


def _collect_nonblank(value: Any, path: str, findings: list[ValidationFinding]) -> None:
    if isinstance(value, str) and not value.strip():
        findings.append(ValidationFinding("BLANK_GENERATED_TEXT", "Generated text is blank", path))
    elif isinstance(value, dict):
        for key, nested in value.items():
            _collect_nonblank(nested, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _collect_nonblank(nested, f"{path}[{index}]", findings)


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


def _collect_design(outputs: dict[str, Any], findings: list[ValidationFinding]) -> None:
    architecture = outputs.get("SYSTEM_ARCHITECTURE")
    component_ids: set[str] = set()
    if architecture:
        component_ids = {item["id"] for item in architecture["components"]}
        _duplicate_ids(architecture["components"], "SYSTEM_ARCHITECTURE.components", findings)
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
        _duplicate_ids(database["entities"], "DATABASE_SCHEMA.entities", findings)
        for entity_index, entity in enumerate(database["entities"]):
            for relation_index, relation in enumerate(entity["relationships"]):
                if relation["target_entity_id"] not in entity_ids:
                    findings.append(ValidationFinding(
                        "DATABASE_ENTITY_REFERENCE_INVALID", "Relationship targets an unknown entity",
                        f"DATABASE_SCHEMA.entities[{entity_index}].relationships[{relation_index}]",
                    ))
    api = outputs.get("API_SPECIFICATION")
    if api:
        _duplicate_ids(api["operations"], "API_SPECIFICATION.operations", findings)
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
        _duplicate_ids(wireframes["screens"], "WIREFRAMES.screens", findings)
    ui_flow = outputs.get("UI_FLOW")
    if ui_flow:
        _duplicate_ids(ui_flow["flows"], "UI_FLOW.flows", findings)
        if wireframes:
            for index, flow in enumerate(ui_flow["flows"]):
                if not flow["screen_refs"] or set(flow["screen_refs"]) - screen_ids:
                    findings.append(ValidationFinding(
                        "UI_FLOW_SCREEN_REFERENCE_INVALID", "UI flow must reference valid screens",
                        f"UI_FLOW.flows[{index}].screen_refs",
                    ))


def _collect_planning(
    context: Agent2InputContext, outputs: dict[str, Any], findings: list[ValidationFinding]
) -> None:
    _validate_plan(
        context, outputs.get("EPICS"), outputs.get("FEATURES"), outputs.get("USER_STORIES"),
        outputs.get("TASKS"), outputs.get("SPRINT_PLAN"), outputs.get("TASK_ASSIGNMENT"),
        None, "", findings,
    )
    jira = outputs.get("JIRA_PLAN")
    if jira:
        _validate_plan(
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
            _duplicate_ids(items, f"{path}{key}", findings)
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
    supplied_names = supplied_member_names(context)
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


def _duplicate_ids(items: list[dict[str, Any]], path: str, findings: list[ValidationFinding]) -> None:
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        findings.append(ValidationFinding("DUPLICATE_ARTIFACT_ID", "Artifact IDs must be unique", path))
