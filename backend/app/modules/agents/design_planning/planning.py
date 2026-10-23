"""Deterministic sprint and dependency planning helpers for Agent 2."""

import re
from datetime import datetime, timedelta
from typing import Any

from app.modules.agents.design_planning.schemas import Agent2InputContext


def enhance_sprints(
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
    expected_days = duration_days(context.expected_project_duration, context.project_start_date)
    feasible_sprints = expected_days // context.sprint_duration if expected_days and context.sprint_duration else None

    start_date_obj = None
    if context.project_start_date:
        try:
            start_date_obj = datetime.strptime(context.project_start_date.strip(), "%Y-%m-%d").date()
        except Exception:
            pass

    for index, sprint in enumerate(sprints):
        if context.sprint_duration:
            sprint["duration_days"] = context.sprint_duration
        if capacity:
            sprint["capacity_points"] = capacity
        else:
            sprint["capacity_points"] = None

        if start_date_obj and context.sprint_duration:
            s_start = start_date_obj + timedelta(days=index * context.sprint_duration)
            s_end = s_start + timedelta(days=context.sprint_duration)
            sprint["start_date"] = s_start.isoformat()
            sprint["end_date"] = s_end.isoformat()

        known_refs = [ref for ref in sprint["item_refs"] if ref in estimates]
        planned = sum(estimates[ref] for ref in known_refs) if known_refs else sprint.get("planned_points", 0)
        sprint["planned_points"] = planned

        if sprint.get("capacity_points"):
            sprint["utilization_percent"] = round(planned / sprint["capacity_points"] * 100, 1)
        else:
            sprint["utilization_percent"] = None

        warnings: list[str] = []
        if not known_refs:
            warnings.append("Workload could not be recomputed because selected story/task estimates were unavailable.")
        if capacity and planned > sprint["capacity_points"]:
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
        if capacity:
            sprint["estimate_basis"] = (
                "Estimated capacity = team count × sprint duration days; planned workload is the sum of "
                "referenced generated point estimates."
            )
        else:
            sprint["estimate_basis"] = (
                "Timeline-based sprint schedule organized across project timeline and sprint duration; "
                "planned workload is the sum of referenced generated point estimates."
            )
    total_work = sum(item["estimate_points"] for item in (tasks or stories or []))
    if sprints and feasible_sprints is not None and capacity and total_work > feasible_sprints * capacity:
        sprints[-1]["planning_warnings"].append(
            f"Estimated work ({total_work} points) exceeds duration-feasible capacity ({feasible_sprints * capacity} points)."
        )


def duration_days(value: str | None, start_date: str | None = None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(day|week|month)s?", value.casefold())
    if match:
        return max(1, round(float(match.group(1)) * {"day": 1, "week": 7, "month": 30}[match.group(2)]))
    if start_date:
        try:
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
            end_dt = datetime.strptime(value.strip(), "%Y-%m-%d").date()
            diff = (end_dt - start_dt).days
            if diff > 0:
                return diff
        except Exception:
            pass
    return None


def dependency_order(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
