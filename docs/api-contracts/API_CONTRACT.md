# AgileFlow AI API Contract

Project ID: **J26-SE-358**  
Contract authority: **File 06 — API and Data Schema Plan**

This is the canonical implementation API contract. It describes planned interfaces as well as verified implementation status; a listed route is not necessarily implemented.

## Conventions

- **API version:** v1
- **Base path:** `/api/v1`
- **Project-scoped pattern:** `/api/v1/projects/{project_id}/...`
- **Request content:** `application/json`; `multipart/form-data` only for upload endpoints where needed
- **Response content:** `application/json`; report export formats are planned for later
- **Authentication:** registration, JWT Bearer login, token validation, `/auth/me`, and Project ownership enforcement are implemented for the current Project-scoped APIs
- **Path parameter:** use `{project_id}`, not `{projectId}`

Do not create a parallel `/api/projects/...` family. Non-versioned routes in general implementation or workflow guides are examples superseded by File 06 for API naming.

## Response Envelope

Successful APIs use the File 06 envelope:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {},
  "errors": [],
  "workflow_stage": "DESIGN_IN_PROGRESS",
  "next_action": "H2_WAITING_APPROVAL"
}
```

Validation/error responses use:

```json
{
  "success": false,
  "message": "Validation failed",
  "data": null,
  "errors": [
    {
      "field": "project_id",
      "message": "Project not found"
    }
  ],
  "workflow_stage": "REQUIREMENTS_IN_PROGRESS",
  "next_action": "FIX_INPUT"
}
```

The envelope fields are `success`, `message`, `data`, `errors`, `workflow_stage`, and `next_action`. File 09's separate `metadata` wrapper and File 11's `workflow_status`, `traceability_updated`, `error_code`, and `details` examples are not canonical additions. Concrete error-code behavior is not formally defined in the primary API contract.

## Schema References

Schema names and supported fields are defined in [DATA_SCHEMAS.md](../schemas/DATA_SCHEMAS.md). Where File 06 does not define a request or response body, this contract says **Not formally defined** rather than inventing fields. All planned responses are wrapped in the standard envelope.

## Current Implementation Status

The implemented HTTP surface currently consists of `GET /health`, the three Authentication routes, the four Project routes, the two ClientInput routes, and the three Orchestrator routes listed below. FastAPI also supplies `/docs` automatically. Registration, login, JWT issuance/validation, `/auth/me`, and authenticated Project ownership for every currently implemented Project-scoped route are implemented; every other unimplemented route remains **Planned / later sprint**.

## Authentication Routes

| Method | Path | Purpose | Authentication | Request | Response data | Status |
|---|---|---|---|---|---|---|
| POST | `/api/v1/auth/register` | Register one active user | Public | `name`, `email`, `password` | Safe User data only | Implemented |
| POST | `/api/v1/auth/login` | Verify credentials and issue an access token | Public | `email`, `password` | `access_token`, `token_type: bearer` | Implemented |
| GET | `/api/v1/auth/me` | Return the authenticated user's safe public data | Bearer token required | None | `user_id`, `name`, `email`, `is_active`, `created_at`, `updated_at` | Implemented |

Registration normalizes and validates email through normal schema validation, rejects duplicate email, hashes the password with Argon2, generates `USR-###`, sets `is_active` to `true`, records UTC timestamps, and persists to `users`. It returns user information only; registration does not create a Project or issue a token. The user must call login separately.

Login locates the normalized email, requires an active user, verifies the Argon2 hash, and issues a JWT access token. Invalid credentials must not reveal whether the email or password was incorrect. Public responses must never contain `password` or `password_hash`.

`GET /api/v1/auth/me` requires `Authorization: Bearer <access_token>` and returns only the safe public User fields shown above.

The access token minimally contains `sub = user_id` and may include standard `iat` and `exp` claims. It must not contain passwords, password hashes, project IDs, or private user information. Signing configuration comes from `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`; the prototype recommendations are `HS256` and 60 minutes. `JWT_SECRET_KEY` has no production-suitable default and may use only a clearly non-production placeholder in `.env.example`.

No logout route, refresh token, token-revocation store, session database, OAuth/social provider, MFA, organization, team, collaboration, role, RBAC, or administrator contract is approved. With stateless access tokens, client-side token removal represents logout unless a later contract establishes revocation.

## Project Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects` | Create a project | Core/Foundation | Project create body: not formally defined; Project fields are the reference | Project | Initializes workflow before H1 | Implemented |
| GET | `/api/v1/projects` | List projects for the dashboard | Core/Foundation | None | Project list; list wrapper details not formally defined | Shows current stages/gates | Implemented |
| GET | `/api/v1/projects/{project_id}` | Get project details/current state | Core/Foundation | Path parameter | Project | Shows gate context | Implemented |
| PATCH | `/api/v1/projects/{project_id}` | Update basic project metadata | Core/Foundation | Project update body: not formally defined | Project | No direct gate transition | Implemented |

All four Project routes require Bearer authentication. Project creation sets server-controlled `owner_user_id` from the authenticated user's `user_id`; clients cannot provide or patch it. Project listing returns only projects owned by the authenticated user. Project detail and update require ownership. Missing, ownerless legacy, and non-owned Projects use the same HTTP 404 response.

## Workflow and Orchestrator Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/projects/{project_id}/workflow` | Get current and canonical next-stage state | Central SDLC Orchestrator | Path parameter | Read-only workflow snapshot | Reports structural gate association without fabricating decisions | Implemented |
| POST | `/api/v1/projects/{project_id}/orchestrator/next-step` | Validate and perform the next allowed action | Central SDLC Orchestrator | Not formally defined | Workflow state; body not formally defined | Must block at unapproved gates | Implemented for the first transition only |
| POST | `/api/v1/projects/{project_id}/orchestrator/route-failure` | Route requirement, build, test, security, or traceability failure | Central SDLC Orchestrator | Not formally defined | WorkflowEvent and relevant issue reference | May return work to gate owner | Planned |
| GET | `/api/v1/projects/{project_id}/events` | Get workflow activity timeline | Central SDLC Orchestrator | Path parameter | Project-scoped WorkflowEvent list | Includes approval events when that behavior is later implemented | Implemented |

File 12 describes a retry action but File 06 does not include a canonical retry route. No retry endpoint is established by this contract; retry execution requires human contract approval before implementation.

The canonical forward transition sequence and stage ownership metadata are implemented as a centralized policy, but only the first approved transition is executable: `PROJECT_CREATED` → `REQUIREMENTS_IN_PROGRESS`. The Orchestrator verifies that at least one ClientInput exists for the project. If no ClientInput exists, the transition is blocked: the project stage is not changed and no `STAGE_CHANGED` event is created. A successful transition updates `current_stage` and `updated_at` and persists one `STAGE_CHANGED` WorkflowEvent. The workflow snapshot distinguishes the canonical next stage from current executability, and event history is project-scoped and chronological. Later executable transitions and approval-gate processing remain planned.

## Requirement Gathering and Analysis Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/inputs` | Submit a client input | Requirement Gathering and Analysis Agent | ClientInput creation request | ClientInput | Input to H1 artifacts; does not advance workflow | Implemented |
| GET | `/api/v1/projects/{project_id}/inputs` | List submitted input sources | Requirement Gathering and Analysis Agent | Path parameter | Project-scoped ClientInput list without MongoDB `_id` | Supports H1 review | Implemented |
| POST | `/api/v1/projects/{project_id}/requirements/process` | Generate structured requirements | Requirement Gathering and Analysis Agent | Input references/body not formally defined | Requirement, UserStory, AcceptanceCriteria | Produces H1 package | Planned |
| GET | `/api/v1/projects/{project_id}/requirements` | Get requirements, stories, and acceptance criteria | Requirement Gathering and Analysis Agent | Path parameter | Requirement, UserStory, AcceptanceCriteria | Reviewed at H1 | Planned |
| POST | `/api/v1/projects/{project_id}/requirements/clarifications` | Add clarification questions or human feedback | Requirement Gathering and Analysis Agent | Not formally defined | Not formally defined | Supports H1 correction loop | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h1` | Record requirement decision | Requirement Gathering and Analysis Agent / Orchestrator | O2 Approval request | Approval | H1 | Planned |

### ClientInput Request and Response Contract

The ClientInput creation request has these required client-provided fields:

- `input_type`
- `content`

It may also include these optional client-provided fields:

- `original_filename`
- `mime_type`
- `metadata`

The server supplies `project_id` from the canonical path parameter and sets `created_at`. These fields are not client-controlled. MongoDB `_id` is an internal persistence field and must never be exposed as a public API identifier. ClientInput has no public ID and no new ID prefix is established.

`content` is a string in the Sprint 1 foundation. Supported `input_type` values and meanings are:

| `input_type` | Meaning |
|---|---|
| `TEXT` | Typed or chat textual input; `content` contains the client-provided text. |
| `DOCUMENT` | Document-based input; `content` may initially contain a stored reference or already-extracted textual representation. |
| `AUDIO` | Recorded audio input; `content` may initially contain a stored reference or already-extracted textual representation. |
| `VIDEO` | Recorded video input; `content` may initially contain a stored reference or already-extracted textual representation. |
| `LIVE_INTERVIEW` | Captured live-interview input; `content` may initially contain a stored reference or already-extracted textual representation. |

Multipart upload fields and behavior are not defined. This contract does not establish storage-path guarantees beyond permitting `content` to hold a prototype reference. It does not include transcription, parsing, extraction, live capture, requirement processing, or AI/LLM behavior.

Creating a ClientInput persists it for the path project only. Creation must not change the project's workflow stage, process requirements, call an LLM, or create an H1 approval. Listing inputs returns only records belonging to the path project and excludes internal MongoDB `_id`.

## Project-Scoped Authorization

Authenticated Project ownership is implemented for every currently implemented project-scoped API, including ClientInput POST/GET and Orchestrator `next-step`. The same boundary is required for all future Agent, Approval, Artifact, Traceability, Workflow, and Report endpoints.

```text
authenticated user_id
        ↓
project.owner_user_id
        ↓
must match
```

A syntactically valid `project_id` is not authorization. Missing or invalid authentication returns HTTP 401. For this prototype, an authenticated user requesting a project they do not own receives HTTP 404 so the API does not reveal whether another user's project identifier exists. No ownership data for another user's project may be returned.

## Project Management and Design Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/design/generate` | Generate planning/design package from approved requirements | Project Management and Design Agent | Requirement references; body not formally defined | DesignArtifact, BacklogItem | Requires H1; produces H2 package | Planned |
| GET | `/api/v1/projects/{project_id}/backlog` | Get epics, stories, tasks, subtasks, and bugs | Project Management and Design Agent | Path parameter | BacklogItem list | Reviewed at H2 | Planned |
| GET | `/api/v1/projects/{project_id}/design/artifacts` | Get UML/API/DB/UI/wireframe artifacts | Project Management and Design Agent | Path parameter | DesignArtifact list | Reviewed at H2 | Planned |
| GET | `/api/v1/projects/{project_id}/design/traceability` | Get requirement-to-design mapping | Project Management and Design Agent | Path parameter | TraceabilityLink; response aggregation not formally defined | H2 evidence | Planned |
| POST | `/api/v1/projects/{project_id}/design/jira-sync` | Mock or later approved real Jira synchronization | Project Management and Design Agent | Not formally defined | Not formally defined | Does not replace H2 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h2` | Record planning/design decision | Project Management and Design Agent / Orchestrator | O2 Approval request | Approval | H2 | Planned |

## Testing, Validation and Security — Pre-Code Routes

These routes belong to the pre-code phase of the single Testing, Validation and Security Agent.

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/tests/pre-code/generate` | Generate test specifications and skeleton metadata | Testing, Validation and Security Agent | Approved requirement/design references; body not formally defined | TestCase | Requires H2; produces H3 package | Planned |
| GET | `/api/v1/projects/{project_id}/tests/pre-code` | Get draft/approved pre-code package | Testing, Validation and Security Agent | Path parameter | TestCase list | Reviewed at H3 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h3` | Record pre-code test decision | Testing, Validation and Security Agent / Orchestrator | O2 Approval request | Approval | H3 | Planned |

## Implementation and Git Automation Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/implementation/generate` | Generate or simulate selected prototype modules | Implementation and Git Automation Agent | Approved artifacts; body not formally defined | CodeModule / ImplementationArtifact | Requires H3; produces H4 package | Planned |
| GET | `/api/v1/projects/{project_id}/implementation/modules` | Get generated module metadata | Implementation and Git Automation Agent | Path parameter | CodeModule / ImplementationArtifact list | Reviewed at H4 | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/git/init` | Mock or later approved repository setup | Implementation and Git Automation Agent | Not formally defined | Git metadata schema not formally defined | H4 evidence | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/run` | Run or simulate build/execution | Implementation and Git Automation Agent | Not formally defined | Execution-log schema not formally defined | H4 evidence/failure routing | Planned |
| GET | `/api/v1/projects/{project_id}/implementation/logs` | Get build/runtime logs | Implementation and Git Automation Agent | Path parameter | Execution-log schema not formally defined | Reviewed at H4 | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/self-fix` | Apply a bounded build/runtime self-fix | Implementation and Git Automation Agent / Orchestrator | Not formally defined | Execution-log/workflow-event details not formally defined | Does not bypass H4 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h4` | Record implementation decision | Implementation and Git Automation Agent / Orchestrator | O2 Approval request | Approval | H4 | Planned |

## Testing, Validation and Security — Post-Code Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/validation/run-tests` | Run or simulate post-code tests | Testing, Validation and Security Agent | Approved implementation reference; body not formally defined | Test results schema not formally defined; BugReport where applicable | Requires H4; contributes to H5 | Planned |
| POST | `/api/v1/projects/{project_id}/validation/security-scan` | Run or simulate security validation | Testing, Validation and Security Agent | Approved implementation reference; body not formally defined | SecurityFinding | Contributes to H5 | Planned |
| GET | `/api/v1/projects/{project_id}/validation/report` | Get combined validation report | Testing, Validation and Security Agent | Path parameter | Validation report schema not formally defined | Reviewed at H5 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h5` | Record final validation decision | Testing, Validation and Security Agent / Orchestrator | O2 Approval request | Approval | H5 | Planned |

## Reports and Traceability Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/projects/{project_id}/traceability` | Get the end-to-end traceability matrix | Reports / Traceability | Path parameter | TraceabilityLink list/matrix | Evidence across H1-H5 | Planned |
| POST | `/api/v1/projects/{project_id}/traceability/rebuild` | Rebuild links from current artifacts | Reports / Traceability | Body not formally defined | TraceabilityLink list/matrix | Must preserve approved versions | Planned |
| GET | `/api/v1/projects/{project_id}/reports/final` | Get final report summary | Reports / Traceability | Path parameter | Final report schema not formally defined | Final output after H5 approval | Planned |
| GET | `/api/v1/projects/{project_id}/reports/export` | Export reports later | Reports / Traceability | Export query/body not formally defined | PDF/DOCX/JSON mentioned as later possibilities; exact contract not defined | Final evidence | Planned |
| GET | `/api/v1/projects/{project_id}/artifacts` | List Shared Knowledge Base artifacts | Reports / Traceability / Foundation | Path parameter | Cross-artifact response not formally defined | Review/evidence support | Planned |

## Approval Behavior

Approval decisions are `APPROVE`, `REJECT`, `REQUEST_CHANGES`, and `HOLD` under the specialized workflow authority in File 12. Approval records use the fields documented in `DATA_SCHEMAS.md`. No approval route may silently approve, skip a gate, or advance an invalid stage.

### Approved O2 Approval Request Contract

Orchestrator Phase O2 approves decision persistence only; it remains **not implemented** until the corresponding backend code is added. Each H1-H5 endpoint requires Bearer authentication and authenticated Project ownership through `get_current_user` and `authorize_project_access`. The endpoint is valid only when the Project is at its matching waiting stage: H1 through H5 correspond respectively to `H1_WAITING_APPROVAL` through `H5_WAITING_APPROVAL`.

The client supplies `reviewer_name`, `reviewer_role`, `decision`, `comment`, and `artifact_version`. At least one of `reviewer_name` or `reviewer_role` is required; `decision`, `comment`, and `artifact_version` are required; and `artifact_version` is a positive integer. The client must not submit the server-controlled fields `approval_id`, `project_id`, `gate_id`, `timestamp`, or `next_stage`. The server derives `project_id` from the route, derives `gate_id` from the endpoint, generates `approval_id` as `APP-###`, generates the timestamp, and derives `next_stage` from the gate and decision. `reviewer_user_id` and `artifact_type` are not part of the approved O2 request or Approval schema.

For `APPROVE`, `next_stage` is `DESIGN_IN_PROGRESS`, `TEST_PLANNING_IN_PROGRESS`, `IMPLEMENTATION_IN_PROGRESS`, `VALIDATION_IN_PROGRESS`, or `COMPLETED` for H1 through H5 respectively. For `REJECT`, `REQUEST_CHANGES`, and `HOLD`, `next_stage` remains the matching `Hx_WAITING_APPROVAL` stage. In O2 this field records the decision's currently permitted or intended outcome; no decision mutates `Project.current_stage`.

O2 records the reviewed `artifact_version` but does not validate, update, or lock records in specialist artifact collections. Artifact-lock enforcement remains planned with the relevant artifact pipelines.

Every successfully persisted decision appends one immutable Approval record and exactly one `APPROVAL_DECISION` WorkflowEvent. The event uses `Human Stakeholder / Reviewer` as `source_component`, `Central SDLC Orchestrator` as `target_component`, and the same matching waiting stage for `stage_before` and `stage_after`. Its metadata is limited to safe audit identifiers such as `approval_id`, `gate_id`, `decision`, and `artifact_version`; reviewer comments and authentication data are not included. O2 never creates `STAGE_CHANGED`.

Multiple Approval records for the same `project_id + gate_id` are allowed. The newest record is the effective decision, while earlier records remain immutable history. There is no uniqueness constraint on that pair. O3 will later consume an effective `APPROVE`, perform the canonical Project transition, and create `STAGE_CHANGED`; O4 will later implement REJECT and REQUEST_CHANGES routing; O6 will later implement full `ON_HOLD` persistence and release/resume behavior.

## Contract Resolution Notes

1. **API route versioning:** File 06 is the dedicated API authority, so `/api/v1` and `{project_id}` are canonical. Non-versioned File 11/File 12 examples are not a second API family.
2. **Response envelope:** File 06 is authoritative. File 09's `metadata` wrapper and File 11's alternate fields are examples not adopted here.
3. **Workflow stages:** Stage values in payloads come from File 12, the specialized workflow authority, not File 06's older stage list.
4. **Testing component:** Pre-code and post-code routes belong to one Testing, Validation and Security Agent.
5. **Undefined bodies:** Request fields not supplied by File 06 remain formally undefined and require contract approval before implementation.
