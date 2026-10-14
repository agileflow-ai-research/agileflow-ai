# Standalone UI and API Contract

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Contract version: **v1.0 — frozen for Progress Presentation 1**

## 1. Scope

This document freezes the common standalone user journey, reusable frontend surface, and API paths. S1 implements the six common backend project/run operations below. S2 implements the shared pages and presentation components described below; the four specialist execution endpoints and specialist content remain unimplemented.

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
| `DownloadExportControls` | Future scope; S2 exposes no visible export control or export behavior. |

All common screens must account for loading, empty, error, access-denied/not-found, and archived states as relevant. Accessibility and responsive behavior follow the project frontend guide when implemented.

### S2 implementation status

The authenticated shared shell is implemented at:

- `/agents` â€” Agent Hub;
- `/agents/requirements`, `/agents/design-planning`, `/agents/implementation`, and `/agents/testing-validation` â€” type-filtered project lists;
- `/agents/{agentSlug}/new` â€” common project creation with `agent_type` derived from the route; and
- `/agent-projects/{agentProjectId}` â€” project overview, archive/reactivate action, run history, and on-demand run detail.

S2 also implements `AgentWorkspaceShell`, `AgentInputWizard`, `OutputSelector`, `RunReview`, `ProcessingState`, `ResultsWorkspace`, `RunHistory`, `RunDetail`, and a lightweight `ArtifactViewer`. The workspace slot is intentionally non-operational until the specialist phases. Agent 4 mode labels for `DEFAULT`, `TEST_GENERATION`, and `VALIDATION` are centralized for future specialist use; S2 does not add Agent 4 inputs or execution.

There is no specialist execution, file upload, generated output, simulated processing, or export/download behavior in S2. Project and run data shown on routed pages comes only from the implemented S1 APIs. The result and artifact components provide presentation/action slots only and do not claim that manifest metadata contains specialist result bodies.

## 5. Input and Output UI Rules

- Common basic project data is captured once and agent-specific required inputs follow the appropriate contract.
- The review step shows the selected `agent_type`, `run_mode`, input summary, and exact `selected_outputs` before execution.
- `OutputSelector` must not select unsupported codes or mix Agent 4 mode-specific output lists.
- Users are not forced to generate every available artifact.
- Mandatory technical evidence may appear in results even when it was not selectable. Agent 3's `BUILD_RESULT`, `EXECUTION_RESULT`, and `EXECUTION_LOGS` are the canonical example.
- Historical run views use that run's `input_snapshot` and selections, not the project's latest editable configuration.

## 6. Common Project and Run APIs

These `/api/v1` routes are implemented by S1:

| Method and path | Planned purpose |
|---|---|
| `POST /api/v1/agent-projects` | Create a standalone `AgentProject`. |
| `GET /api/v1/agent-projects` | List the authenticated user's standalone projects; filters/pagination remain for S1/S2. |
| `GET /api/v1/agent-projects/{agent_project_id}` | Retrieve one owned project. |
| `PATCH /api/v1/agent-projects/{agent_project_id}` | Update allowed current project metadata/configuration; immutable identity/type rules still apply. |
| `GET /api/v1/agent-projects/{agent_project_id}/runs` | Retrieve that owned project's run history. |
| `GET /api/v1/agent-projects/{agent_project_id}/runs/{run_id}` | Retrieve one matching historical run/result. |

No DELETE, dedicated archive/restore, upload, export, cancellation, or streaming endpoint is implemented. Archive/reactivate uses project PATCH with `status`; run creation and lifecycle changes remain internal service operations.

## 7. Planned Agent Execution APIs

| Agent | Method and path | Required mode |
|---|---|---|
| Agent 1 — Requirement Gathering and Analysis Agent | `POST /api/v1/agents/requirements/{agent_project_id}/run` | `DEFAULT` |
| Agent 2 — Project Management and Design Agent | `POST /api/v1/agents/design-planning/{agent_project_id}/run` | `DEFAULT` |
| Agent 3 — Implementation and Git Automation Agent | `POST /api/v1/agents/implementation/{agent_project_id}/run` | `DEFAULT` |
| Agent 4 — Testing, Validation and Security Agent | `POST /api/v1/agents/testing-validation/{agent_project_id}/run` | `TEST_GENERATION` or `VALIDATION` |

The future request conceptually supplies the agent/mode-specific inputs and `selected_outputs`. The server will validate them, record an input snapshot, create a `RUN-###`, and return or make available the common `AgentRunResult` envelope. S1 exposes none of these four specialist execution endpoints.

Common project and run lists are unpaginated in S1 and ordered newest-first. Project listing optionally filters by `agent_type` and `status`. Pagination and specialist execution transport remain later scalability/implementation decisions.

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

The common API family manages standalone `AGP-###` and `RUN-###` resources. It must not invoke H1–H5, create integrated Approval records, advance global Project stages, or automatically persist output into the integrated Shared Knowledge Base. A future explicit import/export workflow is outside this v1.0 contract.
