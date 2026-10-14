# Standalone UI and API Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Scope

This document freezes the planned common standalone user journey, reusable frontend surface, and API paths. It does not implement pages, components, routes, schemas, or services.

Agent-specific forms and result content plug into the shared shell. Members must not recreate the shell independently.

## 2. Common User Journey

```text
Agent Hub
  → Agent Project List
  → Create Agent Project
  → Basic Information
  → Required Inputs
  → Select Outputs
  → Review Configuration
  → Run Agent
  → Processing
  → Results Workspace
  → Run History
```

The flow supports first execution and repeated execution. After reviewing a result, a user can return to the current inputs, revise them, select outputs, and create another immutable run without overwriting earlier history.

## 3. Agent Hub

`AgentHubPage` presents exactly four specialist cards:

- Requirements Agent
- Design & Planning Agent
- Implementation Agent
- Testing & Validation Agent

Each card provides:

- **View Projects** — opens the authenticated user's list filtered to the matching `AgentType`.
- **Create Project** — begins creation with the matching `AgentType` fixed.

Agent 4's card remains one specialist agent. Its project/run flow must present `TEST_GENERATION` and `VALIDATION` as two explicit modes, not a single ambiguous process and not two research-agent cards.

## 4. Reusable Screens and Components

| Name | Shared responsibility |
|---|---|
| `AgentHubPage` | Displays four agent entry cards and routes to list/create actions. |
| `AgentProjectListPage` | Lists only the current user's projects, with type/status filtering and create/open actions. |
| `CreateAgentProjectPage` | Captures common project metadata and fixes the chosen `agent_type`. |
| `AgentProjectOverviewPage` | Shows project identity, current configuration summary, latest run, and history/run actions. |
| `AgentInputWizard` | Hosts agent-specific input steps, conditional validation, and mode selection where applicable. |
| `OutputSelector` | Presents only valid output codes for the project's agent and selected mode; records a non-empty selection. |
| `RunReview` | Summarizes normalized inputs/configuration, mode, and selected outputs before execution. |
| `ProcessingState` | Displays `QUEUED`/`RUNNING` progress and safe warnings/errors without inventing completion. |
| `ResultsWorkspace` | Provides the common result shell and delegates output rendering to agent-specific content. |
| `RunHistory` | Lists immutable runs and allows opening a historical snapshot/result. |
| `ArtifactViewer` | Renders structured text, diagrams, reports, code, or referenced artifacts as appropriate. |
| `DownloadExportControls` | Supports future copy/download/export operations according to output capability. |

All common screens must account for loading, empty, error, access-denied/not-found, and archived states as relevant. Accessibility and responsive behavior follow the project frontend guide when implemented.

## 5. Input and Output UI Rules

- Common basic project data is captured once and agent-specific required inputs follow the appropriate contract.
- The review step shows the selected `agent_type`, `run_mode`, input summary, and exact `selected_outputs` before execution.
- `OutputSelector` must not select unsupported codes or mix Agent 4 mode-specific output lists.
- Users are not forced to generate every available artifact.
- Mandatory technical evidence may appear in results even when it was not selectable. Agent 3's `BUILD_RESULT`, `EXECUTION_RESULT`, and `EXECUTION_LOGS` are the canonical example.
- Historical run views use that run's `input_snapshot` and selections, not the project's latest editable configuration.

## 6. Planned Common Project and Run APIs

These `/api/v1` routes are planned contracts only:

| Method and path | Planned purpose |
|---|---|
| `POST /api/v1/agent-projects` | Create a standalone `AgentProject`. |
| `GET /api/v1/agent-projects` | List the authenticated user's standalone projects; filters/pagination remain for S1/S2. |
| `GET /api/v1/agent-projects/{agent_project_id}` | Retrieve one owned project. |
| `PATCH /api/v1/agent-projects/{agent_project_id}` | Update allowed current project metadata/configuration; immutable identity/type rules still apply. |
| `GET /api/v1/agent-projects/{agent_project_id}/runs` | Retrieve that owned project's run history. |
| `GET /api/v1/agent-projects/{agent_project_id}/runs/{run_id}` | Retrieve one matching historical run/result. |

No DELETE/archive endpoint, restore endpoint, upload endpoint, export endpoint, cancellation endpoint, or streaming endpoint is frozen in S0.

## 7. Planned Agent Execution APIs

| Agent | Method and path | Required mode |
|---|---|---|
| Agent 1 — Requirement Gathering and Analysis Agent | `POST /api/v1/agents/requirements/{agent_project_id}/run` | `DEFAULT` |
| Agent 2 — Project Management and Design Agent | `POST /api/v1/agents/design-planning/{agent_project_id}/run` | `DEFAULT` |
| Agent 3 — Implementation and Git Automation Agent | `POST /api/v1/agents/implementation/{agent_project_id}/run` | `DEFAULT` |
| Agent 4 — Testing, Validation and Security Agent | `POST /api/v1/agents/testing-validation/{agent_project_id}/run` | `TEST_GENERATION` or `VALIDATION` |

The request conceptually supplies the agent/mode-specific inputs and `selected_outputs`. The server validates them, records an input snapshot, creates a `RUN-###`, and returns or makes available the common `AgentRunResult` envelope. Exact request bodies, synchronous/asynchronous transport, polling, and HTTP status/error envelope mappings remain S1/S2 decisions.

## 8. Authentication, Ownership, and Type Matching

Every route requires the existing authentication system.

Every project and run lookup must enforce owner isolation. A route must not reveal, mutate, execute, or export another user's project/run.

The `AgentProject.agent_type` must match the execution endpoint:

- `REQUIREMENTS` → requirements endpoint;
- `DESIGN_PLANNING` → design-planning endpoint;
- `IMPLEMENTATION` → implementation endpoint; and
- `TESTING_VALIDATION` → testing-validation endpoint.

A `DESIGN_PLANNING` project, for example, must be rejected by the Requirements Agent endpoint. Agent 4 must additionally validate that its mode and selected output codes belong together.

## 9. Processing and Result Behavior

The UI maps only the frozen `AgentRunStatus` values:

- `QUEUED` and `RUNNING` use `ProcessingState`;
- `COMPLETED` opens validated outputs in `ResultsWorkspace`; and
- `FAILED` opens the common result/error shell with structured `errors` and any safe retained evidence.

Warnings remain visible with the run. Errors do not disappear into a transient toast or server log. UI labels must not imply integrated approval, Orchestrator progression, or Shared Knowledge Base publication.

## 10. View, Copy, Download, and Export

The shared results shell should eventually support view, copy, and download/export where an artifact permits it. Candidate formats include JSON, Markdown, PDF, and ZIP. Agent 3 source should eventually support a project archive/workspace export.

S0 does not freeze which output supports which format, server-side export routes, bundle layout, generated filenames, or retention. UI controls must be capability-aware rather than promising unavailable formats.

## 11. Standalone Boundary

The planned API family manages standalone `AGP-###` and `RUN-###` resources. It must not invoke H1–H5, create integrated Approval records, advance global Project stages, or automatically persist output into the integrated Shared Knowledge Base. A future explicit import/export workflow is outside this v1.0 contract.
