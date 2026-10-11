# AgileFlow AI Orchestrator Workflow

Project ID: **J26-SE-358**  
Primary authority: **File 12 — Orchestrator Workflow and Approval Rules**

This is the canonical complete workflow contract. Most of the workflow remains planned; the current repository implements only the limited Sprint 1 foundation described below.

## Current Implementation Status

- **Endpoint:** `POST /api/v1/projects/{project_id}/orchestrator/next-step`
- **Only implemented transition:** `PROJECT_CREATED` → `REQUIREMENTS_IN_PROGRESS`
- **Prerequisite:** at least one ClientInput must belong to the project.
- **Successful behavior:** update the project's `current_stage` and `updated_at`, then persist one `STAGE_CHANGED` WorkflowEvent.
- **Still planned:** H1-H5 handling, every later transition, approval-gate processing, failure routing, bounded retries, human-review escalation, and correction loops.

This foundation does not execute the Requirement Gathering and Analysis Agent and does not represent a complete Orchestrator implementation.

## Purpose and Boundaries

The **Central SDLC Orchestrator** coordinates the correct component at the correct time. It controls stage order, verifies prerequisites, enforces H1-H5, records state and events, routes failures, applies bounded retry policy, and keeps Shared Knowledge Base state consistent.

The Orchestrator must not perform requirement extraction, design generation, code generation, test execution, or security analysis. It must not overwrite approved artifacts, hide failures, skip gates, silently approve outputs, or let an individual agent advance the global workflow.

## Core Principles

1. **No automatic progression past approval gates.** H1-H5 require a recorded human decision.
2. **One active workflow stage.** A project has one main active stage at a time.
3. **Shared Knowledge Base as source of truth.** Agents read approved inputs and persist outputs through approved collections/schemas.
4. **Failures are routed, not hidden.** Requirement, design, build, test, security, and traceability problems become records and workflow events.
5. **Retries are bounded.** Counts and errors are retained; exhausted loops require human review.
6. **Traceability is mandatory.** Accepted artifacts link to the relevant requirements and downstream evidence.

## Human-in-the-Loop Sequence

```text
Client Input
  → Requirement Gathering and Analysis Agent
  → H1 Requirement Approval
  → Project Management and Design Agent
  → H2 Design and Planning Approval
  → Testing, Validation and Security Agent — Pre-Code Phase
  → H3 Pre-Code Test Approval
  → Implementation and Git Automation Agent
  → H4 Implementation Approval
  → Testing, Validation and Security Agent — Post-Code Phase
  → H5 Final Validation Approval
  → Final Reports / Traceability / Completion
```

The two testing phases belong to one Testing, Validation and Security Agent.

## Canonical Workflow Stages

| Order | WorkflowStage | Meaning | Main output |
|---:|---|---|---|
| 1 | `PROJECT_CREATED` | Project/client metadata exists | Project record and client input |
| 2 | `REQUIREMENTS_IN_PROGRESS` | Requirement Agent is processing input | Draft requirement package |
| 3 | `H1_WAITING_APPROVAL` | Human reviews requirements and quality evidence | H1 decision |
| 4 | `DESIGN_IN_PROGRESS` | Design Agent prepares planning/design artifacts | Backlog/design package |
| 5 | `H2_WAITING_APPROVAL` | Human reviews backlog, UML/API/DB/UI, and mappings | H2 decision |
| 6 | `TEST_PLANNING_IN_PROGRESS` | Testing Agent prepares pre-code tests and mappings | Test package |
| 7 | `H3_WAITING_APPROVAL` | Human reviews tests before implementation | H3 decision |
| 8 | `IMPLEMENTATION_IN_PROGRESS` | Implementation Agent creates modules/metadata/logs | Implementation package |
| 9 | `H4_WAITING_APPROVAL` | Human reviews implementation and execution evidence | H4 decision |
| 10 | `VALIDATION_IN_PROGRESS` | Testing Agent runs post-code validation/security work | Validation results |
| 11 | `H5_WAITING_APPROVAL` | Human reviews tests, bugs, security, and final evidence | H5 decision |
| 12 | `COMPLETED` | H5-approved outputs and traceability are final | Final report package |

Do not introduce alternative stage names. `ArtifactStatus`, `ApprovalDecision`, `ApprovalGate`, `EventType`, `ON_HOLD`, and `HUMAN_REVIEW_REQUIRED` are separate concepts, not workflow-stage aliases.

## Approval Gates

| Gate | Name | Output owner/phase | Reviewer checks | Approved transition |
|---|---|---|---|---|
| H1 | Requirement Approval | Requirement Gathering and Analysis Agent | SRS, requirements, stories, acceptance criteria, quality findings | `DESIGN_IN_PROGRESS` |
| H2 | Design and Planning Approval | Project Management and Design Agent | Backlog, sprint, UML/API/DB/UI artifacts, traceability | `TEST_PLANNING_IN_PROGRESS` |
| H3 | Pre-Code Test Approval | Testing, Validation and Security Agent — Pre-Code | Test specifications/skeletons, security cases, mappings | `IMPLEMENTATION_IN_PROGRESS` |
| H4 | Implementation Approval | Implementation and Git Automation Agent | Modules, repository/branch metadata, build/runtime logs | `VALIDATION_IN_PROGRESS` |
| H5 | Final Validation Approval | Testing, Validation and Security Agent — Post-Code | Test/security/bug reports and validation evidence | `COMPLETED` |

Canonical decisions are:

- `APPROVE` — lock the reviewed artifact version, record the decision, and permit only the defined next stage.
- `REJECT` — mark the stage rejected, record the reason, block progression, and route to the responsible component.
- `REQUEST_CHANGES` — record a change-request event, keep the gate pending, and permit revision/regeneration.
- `HOLD` — set runtime status to `ON_HOLD` and block next-step execution until an authorized reviewer releases it.

Every decision requires `project_id`, `gate_id`, reviewer name or role, `decision`, `comment`, `timestamp`, `artifact_version`, and `next_stage`. No output is silently approved.

## Forward Transition Rules

| Current stage | Trigger | Minimum condition | Next stage |
|---|---|---|---|
| `PROJECT_CREATED` | Start requirements | Client input exists | `REQUIREMENTS_IN_PROGRESS` |
| `REQUIREMENTS_IN_PROGRESS` | Requirements generated | Requirement package saved | `H1_WAITING_APPROVAL` |
| `H1_WAITING_APPROVAL` | H1 approved | Decision is `APPROVE` | `DESIGN_IN_PROGRESS` |
| `DESIGN_IN_PROGRESS` | Design generated | Design/backlog artifacts saved | `H2_WAITING_APPROVAL` |
| `H2_WAITING_APPROVAL` | H2 approved | Decision is `APPROVE` | `TEST_PLANNING_IN_PROGRESS` |
| `TEST_PLANNING_IN_PROGRESS` | Test package generated | Test package saved | `H3_WAITING_APPROVAL` |
| `H3_WAITING_APPROVAL` | H3 approved | Decision is `APPROVE` | `IMPLEMENTATION_IN_PROGRESS` |
| `IMPLEMENTATION_IN_PROGRESS` | Prototype generated/run | Code metadata and logs saved | `H4_WAITING_APPROVAL` |
| `H4_WAITING_APPROVAL` | H4 approved | Decision is `APPROVE` | `VALIDATION_IN_PROGRESS` |
| `VALIDATION_IN_PROGRESS` | Validation completed | Reports saved | `H5_WAITING_APPROVAL` |
| `H5_WAITING_APPROVAL` | H5 approved | Decision is `APPROVE` | `COMPLETED` |

Before moving, the Orchestrator validates required artifacts, persists the new state, creates a `STAGE_CHANGED` event, and identifies the next responsible component. A missing approval or artifact blocks the transition.

## Failure Routing and Correction Loops

| Failure | Example | Route | Required result |
|---|---|---|---|
| Requirement issue | Ambiguous, missing, conflicting, duplicated requirement | Requirement Gathering and Analysis Agent | Clarification and revised requirement package, then H1 review |
| Design/planning issue | Wrong backlog, missing API, inconsistent DB/UI mapping | Project Management and Design Agent | Revised design/backlog and H2 review as applicable |
| Build/runtime failure | Dependency, syntax, configuration, simple runtime error | Implementation and Git Automation Agent | Logged bounded self-fix and rerun |
| Test failure | Unit/API/integration/UI/regression failure | Orchestrator → Design Agent + Implementation Agent | Bug record, plan/code correction, retest |
| Security issue | Dependency risk, secret leak, weak authorization/validation | Orchestrator → Design Agent + Implementation Agent | Security record, design/code correction, rescan |
| Traceability gap | Required artifact link missing | Responsible artifact owner | Updated traceability links |

Before routing, create the relevant bug/task/security/failure record and a `FAILURE_ROUTED` workflow event. Return only the affected stage to correction; do not restart the entire project. After a successful correction, return to the validation/review point that failed.

## Retry and Escalation Rules

Every automatic attempt stores `retry_count` and `last_error_summary`. Attempts append logs rather than overwriting them.

| Loop | Allowed action | Limit | Escalation |
|---|---|---:|---|
| Requirement clarification | Regenerate after human clarification | Manual until approved | Supervisor/client review |
| Build/runtime self-fix | Limited syntax, dependency, configuration, simple runtime fixes | 3 | Implementation review |
| Test correction | Route to Design/Implementation, then retest | 2 | Human technical review |
| Security correction | Route to Design/Implementation, then rescan | 2 | Security reviewer decision |

Exhausted automatic retries set runtime control state to `HUMAN_REVIEW_REQUIRED`. No other retry limits are established.

## Shared Knowledge Base Interaction

The Orchestrator verifies stage output before progression and updates:

- `projects` on creation and every stage transition;
- `requirements`, `design_artifacts`, `backlog_items`, `test_cases`, and `implementation_artifacts` after generation/revision and relevant approval;
- `execution_logs` during implementation, validation, and retries;
- `test_results`, `security_findings`, and `bug_reports` when evidence/findings arise;
- `approvals` for every H1-H5 decision;
- `traceability_links` at artifact creation/correction/final reporting;
- `workflow_events` for every Orchestrator action.

The specialized workflow source omits `client_inputs` in its update table, but File 06 defines it as the canonical collection for input sources.

## Workflow Events

Create an event when:

- a project is created;
- an agent starts or completes work;
- an artifact is generated, revised, approved, rejected, or locked;
- a stage changes;
- a failure is detected/routed;
- each retry is attempted and resolved/exhausted;
- final reports are generated and H5 is approved.

Defined event fields are `event_id`, `project_id`, `event_type`, `source_component`, `target_component`, `stage_before`, `stage_after`, `message`, `metadata`, and `created_at`. Defined EventType values are `AGENT_STARTED`, `ARTIFACT_GENERATED`, `APPROVAL_DECISION`, `FAILURE_ROUTED`, `RETRY_ATTEMPT`, and `STAGE_CHANGED`; names for other required event circumstances need contract approval.

## Human-Review UI Behavior

- Show only actions valid for the current stage.
- Keep locked/approved stages read-only unless changes are formally requested.
- Show artifact summary, reviewer comment input, and Approve/Reject/Request Changes controls at every gate; HOLD must be supported where the workflow contract applies.
- Show current stage, active agent, pending gate, failures, retry count, and recent events.
- Show clear workflow-rule errors and never simulate invalid progression in local UI state.

## API Relationship

Canonical routes are defined only in [API_CONTRACT.md](../api-contracts/API_CONTRACT.md), including:

- `GET /api/v1/projects/{project_id}/workflow`
- `POST /api/v1/projects/{project_id}/orchestrator/next-step`
- `POST /api/v1/projects/{project_id}/orchestrator/route-failure`
- `GET /api/v1/projects/{project_id}/events`
- gate-specific H1-H5 approval routes

File 12's non-versioned `{projectId}` examples do not override File 06. File 12 mentions an Orchestrator retry endpoint, but File 06 does not establish it; that route remains an unresolved contract decision.

## Completion Rule

A project reaches `COMPLETED` only after validation reports are stored, traceability is present, and H5 records `APPROVE`. Completion cannot bypass final evidence or human review.

## Contract Resolution Notes

1. File 12 supplies the canonical detailed stage sequence.
2. File 06 supplies canonical API paths; File 12 supplies workflow semantics.
3. Testing, Validation and Security is one agent used in two phases.
4. `WorkflowStage`, `ArtifactStatus`, `ApprovalDecision`, `ApprovalGate`, `EventType`, and runtime controls remain separate.
5. The retry-route path and names for several required event circumstances are unresolved and need human contract approval before implementation.
