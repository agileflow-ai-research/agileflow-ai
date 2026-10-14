# Agent 2 — Project Management and Design Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Agent type: `DESIGN_PLANNING`

Run mode: `DEFAULT`
Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Standalone Purpose

Agent 2 — Project Management and Design Agent generates software design and Agile planning artifacts from manually supplied requirements/specifications. It does not require Agent 1 to have executed; the user directly supplies usable specification context.

## 2. Required Basic and Specification Inputs

Required basic inputs:

```text
project_name
domain
```

At least one usable specification source is required from:

```text
requirements
SRS
user_stories
acceptance_criteria
```

The presence of a field without usable content does not satisfy this rule.

## 3. Optional Technical and Design Inputs

```text
technical_constraints
preferred_technology_stack
deployment_preference
database_preference
ui_ux_constraints
architecture_notes
```

These constrain rather than replace the supplied functional/specification context. Missing preferences may lead to explicit assumptions or clarification/warning output; they must not be misrepresented as user decisions.

## 4. Team and Planning Inputs

Planning fields:

```text
development_team_count
sprint_duration
expected_project_duration
```

Optional team detail:

```text
developer_roles
developer_skills
team_composition
```

### Conditional rules

- `development_team_count` is required when `selected_outputs` includes a planning output that requires capacity/allocation, including `SPRINT_PLAN`, `TASK_ASSIGNMENT`, or `JIRA_PLAN`.
- `sprint_duration` is required when `SPRINT_PLAN` is selected. It must also be required whenever another requested planning output is represented as sprint-based and cannot be produced honestly without sprint duration.
- `expected_project_duration` may remain optional when a useful plan can be generated without a fixed end date.
- Team count, roles, skills, composition, duration, and dependencies must be treated as constraints only when supplied and valid.

The engine must not invent named developers or claim resource optimization unsupported by its implemented method.

## 5. Selectable Output Codes

The allowed Agent 2 `selected_outputs` values are exactly:

```text
SYSTEM_ARCHITECTURE
UML_DIAGRAMS
DATABASE_SCHEMA
API_SPECIFICATION
WIREFRAMES
UI_FLOW
PRODUCT_BACKLOG
EPICS
FEATURES
USER_STORIES
TASKS
SPRINT_PLAN
TASK_ASSIGNMENT
JIRA_PLAN
```

The selection must be non-empty and all conditional planning inputs must be validated before execution.

## 6. Output Expectations

### Design outputs

- `SYSTEM_ARCHITECTURE`: components, responsibilities, boundaries, interactions, constraints, and assumptions at a level justified by the inputs.
- `UML_DIAGRAMS`: requested/applicable UML representations with readable structure and source relationships.
- `DATABASE_SCHEMA`: entities/collections, key fields, relationships, and constraints appropriate to the selected data technology or explicitly technology-neutral.
- `API_SPECIFICATION`: endpoint/operation contracts, inputs, outputs, errors, and authentication assumptions appropriate to the context.
- `WIREFRAMES`: low- or suitable-fidelity screen structures and interaction intent, not a claim of implemented UI.
- `UI_FLOW`: user navigation/task flows tied to relevant roles, stories, or requirements.

### Planning outputs

- `PRODUCT_BACKLOG`: prioritized structured backlog derived from supplied needs.
- `EPICS`: grouped outcome-oriented bodies of work.
- `FEATURES`: user/business capabilities decomposed from the specification.
- `USER_STORIES`: actor/goal/benefit stories suitable for planning.
- `TASKS`: implementable work items with dependencies or source links where supported.
- `SPRINT_PLAN`: sprint-organized work considering supplied duration, team capacity information, dependencies, and priorities.
- `TASK_ASSIGNMENT`: allocation recommendations considering supplied team count, roles, skills, sprint duration, and dependencies.
- `JIRA_PLAN`: the Jira-compatible structured planning representation defined below.

Outputs should preserve standalone-context relationships among requirements/specifications, designs, and plan items without forcing integrated `TraceabilityLink` persistence.

## 7. `JIRA_PLAN` Definition

For Progress Presentation 1, `JIRA_PLAN` means a structured Jira-compatible planning output, including as applicable:

```text
epics
stories
tasks
sprints
assignments
priorities
```

It does not require or imply live Jira Cloud synchronization, Jira credentials, remote issue creation, or two-way updates. Real Jira API integration is a later optional integration feature.

## 8. Task Assignment Boundary

Task allocation should consider, where supplied:

- team count;
- developer roles;
- developer skills;
- sprint duration; and
- dependencies.

The result must identify important assumptions and must not claim mathematical optimization, guaranteed delivery, or skill matching beyond what the implemented method can demonstrate.

## 9. Validation and Normalization

Before engine execution, Agent 2 must:

1. require `project_name` and `domain`;
2. require at least one usable specification source;
3. validate exact Agent 2 output codes;
4. enforce planning conditional requirements;
5. normalize specifications, technical preferences, UI constraints, and team data into an Agent 2 context; and
6. preserve that serializable state in `input_snapshot`.

## 10. Results, Errors, Isolation, and Reuse

Agent 2 returns selected structured outputs in the common `AgentRunResult.outputs`. Applicable errors include `INPUT_VALIDATION_FAILED`, `MODEL_EXECUTION_FAILED`, `STRUCTURED_OUTPUT_INVALID`, `TOOL_EXECUTION_FAILED`, and `INTERNAL_ERROR`.

The manual-input adapter and future integrated Shared Knowledge Base adapter use the same Agent 2 engine. Standalone execution does not require Agent 1, create H2 Approval, write automatically to the integrated Shared Knowledge Base, or advance the Central SDLC Orchestrator.
