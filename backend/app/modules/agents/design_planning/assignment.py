"""Deterministic Agent 2 task-assignment heuristics."""

import re
from typing import Any

from app.modules.agents.design_planning.planning import dependency_order
from app.modules.agents.design_planning.schemas import Agent2InputContext


def build_assignments(
    context: Agent2InputContext, tasks: list[dict[str, Any]], sprints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates = assignment_candidates(context)
    workloads = {candidate["name"]: 0 for candidate in candidates}
    sprint_by_task = {
        ref: sprint["id"] for sprint in sprints for ref in sprint["item_refs"] if ref.startswith("TASK-")
    }
    result: list[dict[str, Any]] = []
    for task in dependency_order(tasks):
        required = {skill.casefold() for skill in task["required_skills"]}
        desired = desired_role(task)
        minimum_workload = min(workloads.values())
        choices = []
        for position, candidate in enumerate(candidates):
            matches = sorted(skill for skill in candidate["skills"] if any(
                skill.casefold() in needed or needed in skill.casefold() for needed in required
            ))
            role_match = desired in candidate["role"].casefold()
            score = (round(60 * len(matches) / len(required)) if required else 0) + (30 if role_match else 0)
            score += 10 if workloads[candidate["name"]] == minimum_workload else 0
            choices.append((score, -workloads[candidate["name"]], -position, candidate, matches, role_match))
        score, _, _, chosen, matches, role_match = max(choices, key=lambda item: item[:3])
        before = workloads[chosen["name"]]
        reasons = [f"Lowest-current-workload consideration: {before} points before assignment."]
        if role_match:
            reasons.append(f"Role matches inferred {desired} task type.")
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


def assignment_candidates(context: Agent2InputContext) -> list[dict[str, Any]]:
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
                    "skills": split_terms(skill_text), "detailed": True,
                })
    count = context.development_team_count or max(1, len(candidates))
    candidates = candidates[:count]
    roles = split_terms(context.developer_roles)
    skills = split_terms(context.developer_skills)
    while len(candidates) < count:
        index = len(candidates)
        candidates.append({
            "name": f"Team member {index + 1}",
            "role": roles[index % len(roles)] if roles else "Developer",
            "skills": [skill for skill_index, skill in enumerate(skills) if skill_index % count == index],
            "detailed": bool(roles or skills),
        })
    return candidates


def split_terms(value: str | None) -> list[str]:
    return [part.strip() for part in re.split(r"[,\n]+", value or "") if part.strip()]


def supplied_member_names(context: Agent2InputContext) -> set[str]:
    return {item["name"] for item in assignment_candidates(context) if not item["name"].startswith("Team member ")}


def desired_role(task: dict[str, Any]) -> str:
    text = " ".join([task["title"], task["description"], *task["required_skills"]]).casefold()
    for role, terms in (
        ("qa", ("test", "qa", "quality")), ("frontend", ("ui", "ux", "frontend", "react")),
        ("devops", ("deploy", "devops", "cloud", "infrastructure")),
        ("backend", ("api", "database", "backend", "python", "java")),
    ):
        if any(term in text for term in terms):
            return role
    return "developer"
