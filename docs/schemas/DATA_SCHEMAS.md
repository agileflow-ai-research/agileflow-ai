# AgileFlow AI Shared Data Schemas

Project ID: **J26-SE-358**  
Primary authority: **File 06 — API and Data Schema Plan**  
Workflow/approval authority: **File 12 — Orchestrator Workflow and Approval Rules**

This document is the shared data-contract baseline. The current repository implements shared enums and foundation ID helpers; Pydantic models for User, Project, Approval, WorkflowEvent, TraceabilityLink, BaseArtifact, the six Agent 1 artifact types, and the API response envelope; module request/response models for registration, login, access tokens, `/auth/me`, and ClientInput; and authenticated Project ownership for current Project-scoped APIs. Fields below remain authoritative; do not create alternate names or infer missing fields.

## Current Schema Implementation Status

- **Implemented schemas and helpers:** User, Project, Approval, WorkflowEvent, pairwise TraceabilityLink, BaseArtifact, Requirement, UserStory, AcceptanceCriteria, QualityFinding, Persona, SrsDocument, API success/error response models, registration and ClientInput request/response models, shared enums, and ID-format/generation helpers including `USR-###`.
- **Implemented O2 foundation:** Approval request validation, authenticated H1-H5 POST APIs, append-only persistence, `APP-###` allocation, effective/latest repository lookup, and `APPROVAL_DECISION` event generation are implemented without Project stage mutation.
- **Implemented:** O3.5 specialist handoff consumption/validation uses an existing `ARTIFACT_GENERATED` WorkflowEvent plus minimum project-scoped persisted evidence; it adds no schema, collection, EventType, or Project readiness field. Actual specialist emission remains planned.
- **Schema only:** TraceabilityLink has a shared pairwise schema, but traceability persistence and generation are not implemented.
- **ClientInput foundation only:** request validation, project-scoped persistence, and response serialization are implemented; requirement extraction, analysis, generation, and clarification behavior remain planned.
- **Implemented:** login/JWT DTOs and `/auth/me` safe public responses.
- **Implemented:** Project includes validated `owner_user_id`; current Project, ClientInput, and Orchestrator APIs enforce authenticated ownership.
- **Contract closure only:** Agent 1 artifact schemas and initial traceability relation values are implemented, but their repositories, services, routes, ID allocation, persistence, generation, and readiness-event emission remain planned.
- Other planned domain artifacts and their persistence are not implied to be implemented by their definitions in this document.

## Contract Rules

- Use one `project_id` across all artifacts.
- Important artifacts use a human-readable artifact ID, positive package version, status, creator, timestamps, and optional denormalized traceability references.
- Producers write to the Shared Knowledge Base; consumers read the approved/versioned artifacts they need.
- Exact field requiredness is not generally classified by File 06. Unless a section explicitly says **required**, listed fields are contract fields whose validation requirement must be confirmed when the Pydantic model is approved.
- No optional fields are formally designated in File 06's schema examples.
- WorkflowStage, ArtifactStatus, ApprovalGate, ApprovalDecision, EventType, and runtime control states are separate concepts.

## Identifier Families

| Artifact | Format |
|---|---|
| Project | `PRJ-###` |
| Requirement | `REQ-###` |
| User story | `US-###` |
| Acceptance criteria | `AC-###` |
| Design artifact | `DES-###` |
| API endpoint specification | `API-###` |
| Database entity | `DB-###` |
| Backlog item/task | `TASK-###` |
| Test case | `TEST-###` |
| Code module | `CODE-###` |
| Bug report | `BUG-###` |
| Security finding | `SEC-###` |
| Traceability link | `TRACE-###` |
| Workflow event | `EVT-###` |
| Approval | `APP-###` |
| User | `USR-###` |

The approved shared convention uses `APP-###` for Approval identifiers, consistent with File 06's `APP-001` example.

`USR-###` is implemented by the shared ID helper and User registration foundation.

ClientInput has no approved public identifier or ID prefix. In particular, no `INPUT-###` family is established. MongoDB `_id` is internal persistence state and must not be exposed through the public API.

## User

- **Purpose:** represent one authenticated application user who may own multiple independent projects.
- **Public ID:** `user_id` using `USR-###`; server-controlled.
- **Canonical fields:** `user_id`, `name`, `email`, `password_hash`, `is_active`, `created_at`, `updated_at`.
- **Client-provided registration fields:** `name`, `email`, `password`.
- **Public response fields:** `user_id`, `name`, `email`, `is_active`, `created_at`, `updated_at`.
- **Internal field:** `password_hash`; never accepted as a public API field and never returned.
- **Email:** client-provided, normalized/validated, unique, and used for login.
- **Password:** accepted only by registration/login request models, hashed with Argon2, and never persisted or returned in plaintext.
- **Lifecycle:** `is_active` defaults to `true`; `created_at` and `updated_at` are server-controlled UTC timestamps.

No additional profile fields, roles, organizations, teams, or collaboration fields are approved.

## Common Artifact Fields

File 11 requires every important artifact to carry:

| Field | Purpose |
|---|---|
| `project_id` | Owning project |
| `artifact_id` | Human-readable artifact identifier |
| `artifact_type` | Artifact category |
| `title` | Human-readable title |
| `status` | Artifact lifecycle status |
| `approval_gate` | Relevant H1-H5 gate |
| `created_by_agent` | Producing official component |
| `created_at` | Creation timestamp |
| `updated_at` | Last-update timestamp |
| `version` | Positive approval-package snapshot version; historical versions are separate documents and must not be overwritten |
| `traceability_refs` | Optional denormalized/cache list of related `TRACE-###` identifiers; never the authoritative trace graph |

These common fields are a cross-artifact requirement. BaseArtifact implements the shared foundation and requires `version >= 1`, nonblank `artifact_type`, `title`, and `created_by_agent`, and `updated_at >= created_at`. `traceability_refs` defaults to an empty list. The authoritative relationship representation is the `traceability_links` collection.

### Stable Artifact Identity and Complete Snapshots

`artifact_id` is the stable conceptual identity of an artifact. The canonical stored identity is `(project_id, artifact_id, version)`. A revision keeps the same `artifact_id` and persists a new MongoDB document with a higher package version. Approved historical versions are never updated in place.

For each approval gate, `version` identifies a complete human-review snapshot. Every artifact retained in a newer snapshot is persisted again with the same `artifact_id` and the new version; changed artifacts use their existing ID and new version; new artifacts receive a new ID at the current version; removed artifacts are absent from the newer snapshot.

No `artifact_packages` collection exists. A package is identified logically by `(project_id, gate_id, artifact_version)`. For H1, that tuple selects all `requirements` documents with the same `project_id`, `approval_gate = H1`, and `version = artifact_version`.

For the Agent 1 foundation, package artifacts move from `IN_PROGRESS` to `WAITING_FOR_APPROVAL` only after the complete snapshot is persisted and ready for H1 review. `APPROVED` may later be materialized for presentation or query efficiency, but Approval records remain authoritative. Artifact status is not an O3.5 readiness predicate.

## Separate Domain Enumerations

### WorkflowStage

Canonical values from File 12:

```text
PROJECT_CREATED
REQUIREMENTS_IN_PROGRESS
H1_WAITING_APPROVAL
DESIGN_IN_PROGRESS
H2_WAITING_APPROVAL
TEST_PLANNING_IN_PROGRESS
H3_WAITING_APPROVAL
IMPLEMENTATION_IN_PROGRESS
H4_WAITING_APPROVAL
VALIDATION_IN_PROGRESS
H5_WAITING_APPROVAL
COMPLETED
```

### ArtifactStatus

Shared artifact/status values from File 06:

```text
PENDING
IN_PROGRESS
WAITING_FOR_APPROVAL
APPROVED
REJECTED
REQUEST_CHANGES
FAILED
RETRYING
COMPLETED
```

### ApprovalGate

```text
H1
H2
H3
H4
H5
```

These mean Requirement Approval, Design and Planning Approval, Pre-Code Test Approval, Implementation Approval, and Final Validation Approval respectively. Older compound examples such as `H1_REQUIREMENTS` are not the canonical gate values.

### ApprovalDecision

Canonical values from File 12:

```text
APPROVE
REJECT
REQUEST_CHANGES
HOLD
```

File 06's example uses past-tense `APPROVED | REJECTED | REQUEST_CHANGES`; File 12 is the specialized authority for approval decisions. Artifact status may still become `APPROVED` or `REJECTED` after the corresponding decision.

### EventType

File 12 explicitly defines:

```text
AGENT_STARTED
ARTIFACT_GENERATED
APPROVAL_DECISION
FAILURE_ROUTED
RETRY_ATTEMPT
STAGE_CHANGED
```

The workflow rules also require events for project creation, agent completion, artifact revision/approval/rejection/locking, retry results, report generation, and H5 approval, but names for those additional event types are not formally defined. Do not invent them without approval.

#### O3.5 `ARTIFACT_GENERATED` Readiness Metadata — Implemented for Consumption/Validation

O3.5 uses `ARTIFACT_GENERATED`; it does not introduce a completion EventType. A final specialist readiness event contains safe metadata with:

| Metadata field | Contract |
|---|---|
| `handoff_ready` | Required literal `true` |
| `source_stage` | Required current specialist in-progress WorkflowStage |
| `target_stage` | Required matching `Hx_WAITING_APPROVAL` WorkflowStage |
| `artifact_version` | Required positive integer representing the specialist approval-package version |

The event's `project_id` scopes the readiness evidence. Its `source_component` is the responsible specialist and its `target_component` is `Central SDLC Orchestrator`. The Orchestrator selects the newest valid event matching `project_id`, expected source stage, expected target stage, and expected source component. Reviewer identity, comments, email, JWTs, passwords, password hashes, and other private authentication data are prohibited from readiness metadata.

The readiness event is necessary but not sufficient. O3.5 also requires project-scoped persisted evidence: `requirements` for H1; both `design_artifacts` and `backlog_items` for H2; `test_cases` for H3; both `implementation_artifacts` and `execution_logs` for H4; and `test_results` for H5. Each named collection must contain at least one record for the same project. No new package collection is approved.

`WAITING_FOR_APPROVAL` and `COMPLETED` remain available ArtifactStatus values but are not O3.5 readiness predicates. The readiness `artifact_version` is handoff evidence only and is not yet cross-validated against O2 `Approval.artifact_version` or specialist artifact versions.

### Runtime Control States

`ON_HOLD` and `HUMAN_REVIEW_REQUIRED` are Orchestrator runtime/control states from File 12. They are not silently added to ArtifactStatus or WorkflowStage.

## Project

- **Purpose:** project metadata and current global workflow position.
- **Producer:** Core/Foundation and Central SDLC Orchestrator.
- **Consumers:** all components.
- **ID:** `project_id` using `PRJ-###`.
- **Contract fields:** `project_id`, `owner_user_id`, `name`, `domain`, `description`, `current_stage`, `status`, `created_by`, `created_at`, `updated_at`.
- **Relationships:** parent identifier for every project-scoped artifact and event.
- **Traceability:** referenced by all artifacts; no separate traceability field is defined in the File 06 Project example.
- **Lifecycle:** `current_stage` uses WorkflowStage; `status` uses the applicable project/artifact status concept pending model approval.

File 06's sample `REQUIREMENT_GATHERING` stage is superseded by File 12's canonical detailed stages.

`owner_user_id` is server-controlled, uses `USR-###`, is assigned from the authenticated user during project creation, and cannot be supplied or changed by a client. A user may own multiple projects; no cross-user sharing is approved.

The Project create request requires client-provided `name` and `domain` and accepts optional `description`. When omitted, `description` is persisted as an empty string; it is not derived from ClientInput. The server derives both `created_by` and `owner_user_id` from the authenticated user's `user_id`, so they are equal for a normally created Project. Clients cannot supply `created_by`, `owner_user_id`, `project_id`, `current_stage`, `status`, `created_at`, or `updated_at` during creation, and neither identity field is mutable through the Project metadata PATCH API.

## Multi-Project Isolation

Authentication establishes the user, `project_id` establishes the active project, and `Project.owner_user_id` authorizes access. Every project-owned record remains scoped by `project_id`, including ClientInputs, requirements, design artifacts, backlog items, test cases, implementation artifacts, execution logs, test results, security findings, bug reports, approvals, traceability links, workflow events, and future agent executions.

Repositories and services must filter by the active `project_id`; an operation for one project must never retrieve or mutate another project's records. Project ownership must be checked before any project-scoped Agent, Orchestrator, Approval, Artifact, Traceability, or Report operation.

## ClientInput

- **Purpose:** preserve project-owned client input before requirement processing.
- **Producer:** client/user through the Requirement Gathering and Analysis Agent input API.
- **Consumers:** Requirement Gathering and Analysis Agent and Central SDLC Orchestrator.
- **Public ID:** none. MongoDB `_id` remains internal and is never returned as a public identifier.
- **Required client-provided fields:** `input_type`, `content`.
- **Optional client-provided fields:** `original_filename`, `mime_type`, `metadata`.
- **Server-controlled fields:** `project_id`, `created_at`.
- **Relationships:** belongs to exactly one `PRJ-###` project and may later be referenced by requirements.
- **Lifecycle:** creation stores input only; it does not advance workflow, process requirements, call an LLM, or create an H1 approval.

`content` is a string for the Sprint 1 foundation. Approved `input_type` values are:

| Value | Semantics |
|---|---|
| `TEXT` | Typed or chat textual input. `content` contains the client-provided text. |
| `DOCUMENT` | Document-based input. `content` may initially contain a stored reference or already-extracted textual representation. |
| `AUDIO` | Recorded audio input. `content` may initially contain a stored reference or already-extracted textual representation. |
| `VIDEO` | Recorded video input. `content` may initially contain a stored reference or already-extracted textual representation. |
| `LIVE_INTERVIEW` | Captured live-interview input. `content` may initially contain a stored reference or already-extracted textual representation. |

Actual multipart upload behavior and fields are not defined. No storage-path guarantee is established beyond allowing `content` to hold a reference in the prototype. Transcription, parsing, extraction, live capture, and AI processing are outside this contract.

The `PROJECT_CREATED` → `REQUIREMENTS_IN_PROGRESS` Orchestrator transition requires at least one ClientInput belonging to the project. Without one, the project stage remains unchanged and no `STAGE_CHANGED` workflow event is created.

## Requirement

- **Purpose:** functional/non-functional requirement with provenance and quality findings.
- **Producer:** Requirement Gathering and Analysis Agent.
- **Consumers:** Design, Testing, Implementation, Orchestrator, Reports/Traceability.
- **Artifact discriminator:** `REQUIREMENT`.
- **ID:** inherited `artifact_id` using `REQ-###`.
- **Contract fields beyond BaseArtifact:** `requirement_kind`, `statement`, optional `rationale`, optional `priority`, `source_reference`, and `quality_flags`.
- **Relationships:** source client input; related stories and acceptance criteria; downstream design/test/code/finding links.
- **Traceability:** starts the principal end-to-end traceability chain.
- **Lifecycle:** draft/revised through H1, then approved/versioned for downstream use.

`requirement_kind` is exactly `FUNCTIONAL` or `NON_FUNCTIONAL`. Priority and quality-flag vocabularies remain intentionally open for the prototype.

## UserStory

- **Purpose:** express a requirement as role, goal, and benefit.
- **Producer:** Requirement Gathering and Analysis Agent.
- **Consumers:** Design, Testing, Implementation, Traceability.
- **Artifact discriminator:** `USER_STORY`.
- **ID:** inherited `artifact_id` using `US-###`.
- **Contract fields beyond BaseArtifact:** `actor`, `goal`, `benefit`, `story_text`.
- **Relationships:** requirement and acceptance-criterion relationships are authoritative pairwise TraceabilityLinks rather than duplicated foreign-key fields.
- **Traceability:** connects requirement intent to backlog, tests, and implementation.
- **Lifecycle/status:** no UserStory-specific lifecycle field is defined; common artifact behavior applies when adopted.

## AcceptanceCriteria

- **Purpose:** define verifiable Given/When/Then behavior.
- **Producer:** Requirement Gathering and Analysis Agent.
- **Consumers:** Design and Testing primarily; Implementation and Traceability also consume it.
- **Artifact discriminator:** `ACCEPTANCE_CRITERION`.
- **ID:** inherited `artifact_id` using `AC-###`.
- **Contract fields beyond BaseArtifact:** `criterion`.
- **Relationships:** user-story and requirement relationships are authoritative pairwise TraceabilityLinks; the criterion may contain Given/When/Then text without duplicating story linkage.
- **Traceability:** links approved intent to `TEST-###` evidence.
- **Lifecycle/status:** no criteria-specific status is defined; H1 controls the package.

## QualityFinding

- **Purpose:** record an Agent 1 quality issue without creating another collection.
- **Artifact discriminator:** `QUALITY_FINDING`.
- **ID:** inherited `artifact_id` using `REQ-###`.
- **Contract fields beyond BaseArtifact:** `finding_type`, `description`, optional `suggested_clarification`, `affected_artifact_ids`.
- **Finding types:** `AMBIGUITY`, `MISSING_INFORMATION`, `CONFLICT`, `DUPLICATE`, `INCONSISTENCY`.
- **Relationships:** `affected_artifact_ids` supports review presentation; authoritative graph relationships use `IDENTIFIES_ISSUE_IN` TraceabilityLinks.

## Persona

- **Purpose:** capture a non-sensitive prototype user archetype for requirement context.
- **Artifact discriminator:** `PERSONA`.
- **ID:** inherited `artifact_id` using `REQ-###`.
- **Contract fields beyond BaseArtifact:** `name`, `role`, `goals`, `pain_points`, `context`.
- **Boundary:** do not model sensitive demographics or real-person identity data.

## SrsDocument

- **Purpose:** structured H1 SRS/index artifact that organizes a review package without copying every artifact body.
- **Artifact discriminator:** `SRS_DOCUMENT`.
- **ID:** inherited `artifact_id` using `REQ-###`.
- **Contract fields beyond BaseArtifact:** `overview`, `scope`, `assumptions`, `constraints`, `requirement_ids`, `user_story_ids`, `acceptance_criteria_ids`, `persona_ids`, `quality_finding_ids`.
- **Relationships:** reference lists organize the exact H1 snapshot; pairwise TraceabilityLinks remain authoritative for traversal.

### Requirements Collection Discriminator and ID Mapping

The single `requirements` collection stores six concrete Agent 1 document types selected by `artifact_type`:

| `artifact_type` | ID prefix |
|---|---|
| `REQUIREMENT` | `REQ-###` |
| `USER_STORY` | `US-###` |
| `ACCEPTANCE_CRITERION` | `AC-###` |
| `QUALITY_FINDING` | `REQ-###` |
| `PERSONA` | `REQ-###` |
| `SRS_DOCUMENT` | `REQ-###` |

No `PERSONA`, `SRS`, `QF`, or `INPUT` ID family and no separate Agent 1 artifact collection is approved.

## DesignArtifact

- **Purpose:** represent UML, API, database, wireframe, or UI-flow design output.
- **Producer:** Project Management and Design Agent.
- **Consumers:** Testing, Implementation, Orchestrator, Reports/Traceability.
- **ID:** `design_id` using `DES-###`; API/DB sub-artifacts may use `API-###` and `DB-###` where modeled.
- **Contract fields:** `design_id`, `project_id`, `artifact_type`, `title`, `linked_requirement_ids`, `content`, `status`.
- **Relationships:** links one or more requirements to implementation/test planning.
- **Traceability:** requirement-to-design and later design-to-code/test links.
- **Lifecycle:** generated/revised and reviewed at H2.

Source-supported `artifact_type` examples are `API_SPEC`, `DB_SCHEMA`, `UML`, `WIREFRAME`, and `UI_FLOW`.

## BacklogItem

- **Purpose:** represent Jira-ready/mock epics, stories, tasks, subtasks, and bugs.
- **Producer:** Project Management and Design Agent.
- **Consumers:** Design, Implementation, Orchestrator, Reports/Traceability.
- **ID:** `task_id` using `TASK-###`.
- **Contract fields:** `task_id`, `project_id`, `item_type`, `title`, `description`, `linked_requirement_ids`, `priority`, `sprint`, `status`.
- **Relationships:** links requirements to planned implementation; may represent correction work.
- **Traceability:** Requirement → Backlog → Code/Test/Fix.
- **Lifecycle:** planned and reviewed at H2; later updated through approved correction flows.

Source-supported `item_type` examples are `EPIC`, `STORY`, `TASK`, `SUBTASK`, and `BUG`; complete priority/sprint rules are not formally defined.

## TestCase

- **Purpose:** pre-code or executable test specification, including security/regression cases.
- **Producer:** Testing, Validation and Security Agent in its pre-code phase.
- **Consumers:** Implementation, post-code Testing/Validation/Security, Orchestrator, Reports/Traceability.
- **ID:** `test_id` using `TEST-###`.
- **Contract fields:** `test_id`, `project_id`, `test_type`, `title`, `linked_requirement_ids`, `preconditions`, `steps`, `expected_result`, `execution_status`.
- **Relationships:** validates requirements/acceptance criteria and later links to code, results, bugs, and findings.
- **Traceability:** Requirement/Acceptance Criteria → Test → Code/Result/Finding.
- **Lifecycle:** generated/revised at H3; execution status updated during post-code validation.

Source-supported `test_type` values are `UNIT`, `API`, `INTEGRATION`, `UI`, `SECURITY`, and `REGRESSION`.

## CodeModule / ImplementationArtifact

- **Purpose:** metadata for generated prototype modules, files, branch/commit information, and build state.
- **Producer:** Implementation and Git Automation Agent.
- **Consumers:** Testing/Validation/Security, Orchestrator, Reports/Traceability.
- **ID:** `code_id` using `CODE-###`.
- **Contract fields from File 06 CodeModule:** `code_id`, `project_id`, `module_name`, `module_type`, `file_paths`, `linked_requirement_ids`, `branch_name`, `commit_hash`, `build_status`.
- **Relationships:** connects approved requirement/design/test inputs to generated files and execution logs.
- **Traceability:** Code links back to REQ/API/DB/UI/TEST identifiers and forward to BUG/SEC/validation evidence.
- **Lifecycle:** generated and executed before H4; revised only through approved/corrective versions.

Source-supported `module_type` values are `BACKEND`, `FRONTEND`, `CONFIG`, and `DATABASE`. `ImplementationArtifact` is repository/collection terminology; no separate field set beyond CodeModule and common artifact fields is formally defined.

## BugReport

- **Purpose:** record a failed test or discovered defect and its correction status.
- **Producer:** Testing, Validation and Security Agent; Design/Implementation participate in tracking/fixing.
- **Consumers:** Orchestrator, Design, Implementation, Reports/Traceability.
- **ID:** `bug_id` using `BUG-###`.
- **Contract fields:** `bug_id`, `project_id`, `title`, `severity`, `source`, `linked_test_id`, `linked_requirement_ids`, `assigned_to_agent`, `status`.
- **Relationships:** links failed test/requirement to the responsible correction path.
- **Traceability:** Test → Bug → Code/Design Correction → Validation.
- **Lifecycle:** opened on detection, routed, corrected/retested, and retained as evidence. Complete severity/status enums are not formally defined.

## SecurityFinding

- **Purpose:** record a vulnerability or security weakness and recommendation.
- **Producer:** Testing, Validation and Security Agent.
- **Consumers:** Orchestrator, Design, Implementation, Reports/Traceability.
- **ID:** `security_id` using `SEC-###`.
- **Contract fields:** `security_id`, `project_id`, `title`, `severity`, `category`, `linked_code_id`, `recommendation`, `status`.
- **Relationships:** links affected code to design/implementation correction and re-scan evidence.
- **Traceability:** Code/Test → Security Finding → Correction → Validation/Report.
- **Lifecycle:** detected, routed, corrected, rescanned, and preserved. Complete severity/category/status enums are not formally defined.

## Approval

- **Purpose:** immutable evidence of a human decision at H1-H5.
- **Producer:** human reviewer through approval UI/API; stored/coordinated by the Orchestrator.
- **Consumers:** Orchestrator, all agents, workflow UI, Reports/Traceability.
- **ID:** `approval_id` using the approved `APP-###` format.
- **Active O2 fields:** `approval_id`, `project_id`, `gate_id`, `reviewer_name`, `reviewer_role`, `decision`, `comment`, `timestamp`, `artifact_version`, `next_stage`.
- **Client-provided fields:** `reviewer_name`, `reviewer_role`, `decision`, `comment`, `artifact_version`. At least one reviewer identity field is required; `decision` and `comment` are required; `artifact_version` is a required positive integer.
- **Route-derived/server-controlled fields:** `project_id`, `gate_id`, `approval_id`, `timestamp`, `next_stage`. The client must not submit these fields. `project_id` uses `PRJ-###`, `approval_id` uses `APP-###`, the route supplies the project, the endpoint supplies the gate, and the server generates the identifier and timestamp.
- **Relationships:** refers to one gate and reviewed artifact version; an approved decision permits only the defined next stage.
- **Traceability:** decision/comment/version become workflow and report evidence.
- **Lifecycle:** append immutable decision records; never overwrite earlier history. Multiple records for the same `project_id + gate_id` are allowed, and the newest record for that pair is the effective/current decision. No uniqueness constraint is defined on `project_id + gate_id`.

For O2, `artifact_version` is supplied by the reviewer/client and represents the positive integer version of the artifact or artifact package reviewed at the gate. O2 does not validate it against, update, or lock component-specific artifact collections and does not define multi-artifact version matching. Artifact-lock enforcement remains planned with the relevant artifact pipelines.

For H1, the reviewed package is identified logically by `(project_id, H1, artifact_version)`. The effective H1 Approval is the sole approval authority: the package is approved only when its effective decision is `APPROVE` and the Approval version equals the requested package version. Future approved retrieval must first resolve that effective Approval and then select the exact matching H1 snapshot. `ArtifactStatus.APPROVED` alone never establishes approval truth, and O2 does not mutate artifact status.

`next_stage` is server-derived. An `APPROVE` records the canonical forward stage for the gate: H1 → `DESIGN_IN_PROGRESS`, H2 → `TEST_PLANNING_IN_PROGRESS`, H3 → `IMPLEMENTATION_IN_PROGRESS`, H4 → `VALIDATION_IN_PROGRESS`, and H5 → `COMPLETED`. `REJECT`, `REQUEST_CHANGES`, and `HOLD` record the current matching `Hx_WAITING_APPROVAL` stage. O2 persists the decision but does not mutate `Project.current_stage`.

File 06 historically mentions `artifact_type`, but it is not part of the active approved O2 Approval schema. `reviewer_user_id` is also not approved. File 06's legacy `gate`, `reviewer_comment`, `reviewed_by`, and `reviewed_at` names remain superseded by `gate_id`, `comment`, reviewer name/role, and `timestamp`.

Every successfully persisted Approval creates exactly one `APPROVAL_DECISION` WorkflowEvent and no `STAGE_CHANGED` event. The implemented O3 next-step behavior separately consumes the effective APPROVE and creates one `STAGE_CHANGED` while leaving Approval history immutable. O4 owns later REJECT/REQUEST_CHANGES routing, and O6 owns richer HOLD persistence and release behavior.

The O2 API, persistence, effective/latest lookup, and event behavior are implemented. O3 approval-driven H1-H5 transitions are implemented; O4 correction/routing and O6 richer HOLD/release behavior remain planned.

## TraceabilityLink

- **Purpose:** preserve end-to-end relationships among artifacts.
- **Producer:** all agents and Reports/Traceability functionality.
- **Consumers:** all components and final reports.
- **ID:** `trace_id` using `TRACE-###`.
- **Approved pairwise fields:** `trace_id`, `project_id`, `source_artifact_id`, `source_artifact_type`, `target_artifact_id`, `target_artifact_type`, `relation_type`, `created_at`.
- **Relationships:** Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction.
- **Lifecycle:** append immutable links at artifact creation, correction, validation, and report generation; exact duplicate creation is idempotent.

The approved implementation decision uses immutable pairwise TraceabilityLink records. The aggregate representation described in File 06 is not the current storage model, and implementations must not create a competing aggregate model. `traceability_links` is authoritative; `BaseArtifact.traceability_refs` is optional cache metadata and correctness must not depend on it being complete.

The initial Agent 1 `relation_type` vocabulary is `DERIVED_FROM`, `REFINES`, `ACCEPTANCE_CRITERION_FOR`, `IDENTIFIES_ISSUE_IN`, and `RELATED_TO`. Direction is source artifact to target artifact. Examples include UserStory `REFINES` Requirement, AcceptanceCriteria `ACCEPTANCE_CRITERION_FOR` UserStory, QualityFinding `IDENTIFIES_ISSUE_IN` Requirement, and SrsDocument `DERIVED_FROM` its indexed artifacts.

A logical edge is uniquely identified by `(project_id, source_artifact_id, target_artifact_id, relation_type)`. Exact duplicate creation must be idempotent. No update/delete API is required for the initial foundation.

ClientInput has no public artifact ID and is not a TraceabilityLink endpoint. Raw-input provenance begins in `Requirement.source_reference`; pairwise traceability begins with canonical artifacts.

## WorkflowEvent

- **Purpose:** append workflow audit evidence for state changes, agent work, approvals, failures, retries, and completion.
- **Producer:** Central SDLC Orchestrator.
- **Consumers:** Orchestrator, workflow UI, all agents as context, Reports/Traceability.
- **ID:** `event_id` using `EVT-###`.
- **Fields from File 12:** `event_id`, `project_id`, `event_type`, `source_component`, `target_component`, `stage_before`, `stage_after`, `message`, `metadata`, `created_at`.
- **Relationships:** links a project/stage transition to components, artifacts, retry counts, errors, and report references through `metadata`.
- **Traceability:** provides auditable sequence evidence; `metadata` may carry relevant IDs without replacing TraceabilityLink.
- **Lifecycle:** append-only event history; previous retry/failure logs must not be overwritten.

Whether `target_component`, `stage_before`, or `stage_after` may be absent for non-transition events is not formally defined.

## Schemas Mentioned but Not Formally Defined

The sources mention ApiSpec, DbSchema, GitMetadata, ExecutionLog, TestResult, ValidationReport, final reports, and export payloads, but do not provide complete field contracts. Their fields must be approved before implementation rather than inferred here.

## Canonical MongoDB Collections

| Constant/value | Purpose |
|---|---|
| `users` | Authentication identities and internal Argon2 password hashes |
| `projects` | Project metadata and current workflow state |
| `client_inputs` | Project-owned text/document/audio/video/live-interview content and metadata |
| `requirements` | Requirements, user stories, acceptance criteria, quality findings, personas, and SRS index documents, discriminated by `artifact_type` |
| `design_artifacts` | UML/API/DB/UI/wireframe artifacts |
| `backlog_items` | Epics, stories, tasks, subtasks, bugs/sprint items |
| `test_cases` | Pre-code and executable test specifications |
| `implementation_artifacts` | Code-module/generated-file/Git metadata |
| `execution_logs` | Build, runtime, tool, retry, and execution logs |
| `test_results` | Executed test outcomes and coverage summaries |
| `security_findings` | Vulnerabilities and recommendations |
| `bug_reports` | Defect records and correction status |
| `approvals` | H1-H5 decisions and comments |
| `traceability_links` | Artifact relationships |
| `workflow_events` | Orchestrator audit timeline |

These are the 15 canonical collections. Do not introduce alternate user collection names such as `user_details`, `accounts`, or `auth_users`. MongoDB is the Shared Knowledge Base for structured project artifacts and workflow information.

## Contract Resolution Notes

1. Workflow stages use File 12 values rather than File 06's older stage list.
2. ApprovalDecision uses File 12 action values, while ArtifactStatus retains approved/rejected state values.
3. `ON_HOLD` and `HUMAN_REVIEW_REQUIRED` remain runtime controls, not generic artifact statuses.
4. Approval uses the approved File 12 field names, and TraceabilityLink uses the approved pairwise storage model; legacy aliases and a competing aggregate model are not implemented.
5. The canonical connection implementation is `backend/app/database/mongodb.py`; this document defines data contracts, not another client.
