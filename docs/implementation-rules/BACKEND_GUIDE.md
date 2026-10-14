# AgileFlow AI Backend Guide

Project ID: **J26-SE-358**  
Primary authority: **File 11 — Backend Implementation Guide**  
API/data authority: **File 06**; workflow authority: **File 12**

## Current Backend Status

The repository currently contains:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py        # shared constants
│   │   └── errors.py           # placeholder
│   ├── database/
│   │   ├── mongodb.py          # shared client/database/ping/close helpers
│   │   └── collections.py      # 17 canonical collection constants
│   ├── common/
│   │   ├── response.py         # shared response models
│   │   ├── status.py           # shared enums
│   │   ├── id_generator.py     # canonical ID helpers
│   │   └── traceability.py     # shared traceability validation
│   ├── modules/
│   │   ├── auth/               # registration, login, JWT, and /auth/me
│   │   ├── projects/           # Project CRUD module
│   │   ├── approvals/          # H1-H5 Approval persistence and effective lookup
│   │   ├── orchestrator/       # deterministic transitions, readiness, and events
│   │   ├── requirements/       # ClientInput, Agent 1 artifacts, H1 snapshots/publication
│   │   ├── standalone/         # owner-scoped AgentProject/AgentRun foundation
│   │   ├── shared_knowledge/   # read-only approved/structured retrieval facade
│   │   ├── design/             # package placeholder
│   │   ├── testing/            # package placeholder
│   │   ├── implementation/     # package placeholder
│   │   └── reports/            # immutable Agent 1 traceability persistence/query
│   └── schemas/                # shared domain schemas
├── tests/                       # 456-test backend suite
├── .env.example
└── requirements.txt
```

Implemented: FastAPI application, CORS setting, `GET /health`, automatic `/docs`, environment loading, one PyMongo client, database access/ping/close helpers, 17 collection constants, shared enums/schemas/response and ID helpers, User persistence and registration with Argon2 hashing, JWT login and validation, `/auth/me`, reusable authentication/ownership authorization, integrated Project CRUD and ClientInput access, the isolated standalone AgentProject/AgentRun foundation, Agent 1 typed/versioned snapshot persistence, internal Agent 1 traceability persistence, internal H1 publication and readiness emission, the centralized Orchestrator policy, workflow snapshot/event-history endpoints, all 11 canonical forward transitions, O2 H1-H5 Approval persistence, O3 effective-APPROVE transitions, O3.5 specialist-handoff validation and gate-entry `STAGE_CHANGED` evidence, WorkflowEvent persistence, and backend tests.

Not implemented: Project sharing/collaboration, specialist-agent processing/intelligence, Agent 2-4 readiness emission and artifact adapters, O4 REJECT/REQUEST_CHANGES routing, O6 full HOLD/release behavior, failure routing, retry loops, traceability traversal/matrix generation, reports, LLM/RAG, or external Jira, GitHub, Docker, and security-scanner integrations. The implemented modules preserve `router` → `service` → `repository` → database layering.

## Approved Backend Stack

| Area | Technology |
|---|---|
| Framework | FastAPI |
| Validation/serialization | Pydantic |
| Environment settings | pydantic-settings and python-dotenv support |
| Shared Knowledge Base | MongoDB |
| Driver | PyMongo |
| Testing | Pytest and HTTPX/FastAPI TestClient |
| API documentation | FastAPI OpenAPI/Swagger |

File 11 permits Motor or PyMongo generally; the repository and approved dependency use PyMongo. Do not add a second driver/client.

## Local Setup

From the repository root in PowerShell:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Run tests:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pytest -q
```

The health endpoint and unit tests do not require a live MongoDB server. A real ping does:

```powershell
.\.venv\Scripts\python.exe -c "from app.database.mongodb import ping_database, close_mongodb_client; print(ping_database()); close_mongodb_client()"
```

## Environment Configuration

`app/core/config.py` resolves `backend/.env` relative to the backend directory, preserving behavior across working directories. Current settings are:

- `APP_NAME`
- `APP_ENV`
- `API_V1_PREFIX` (default `/api/v1`)
- `FRONTEND_ORIGIN`
- `MONGODB_URI` (safe local default)
- `MONGODB_DATABASE`
- `JWT_SECRET_KEY` with no production-suitable default; `.env.example` may contain only a safe placeholder
- `JWT_ALGORITHM` with recommended prototype value `HS256`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` with recommended prototype value `60`

Keep real values in ignored `.env`; `.env.example` contains safe examples only. Never hardcode or document credentials.

## Intended Module Pattern

When a module is implemented, use:

```text
app/modules/<module_name>/
├── router.py
├── service.py
├── repository.py
├── schemas.py
└── sample_data.py
```

| Layer | Responsibility | Boundary |
|---|---|---|
| `router.py` | HTTP routing, request binding, service call, response return | No business logic or direct database access |
| `service.py` | Module business/workflow validation, generation coordination, repository calls | No uncontrolled raw persistence where a repository exists; no raw HTTP formatting |
| `repository.py` | MongoDB reads/writes for the module | No UI behavior or global workflow decisions |
| `schemas.py` | Pydantic validation and serialization | No persistence, generation, or workflow logic |
| `sample_data.py` | Temporary approved mock/demo output | No permanent production behavior or credentials |
| `database/` | Shared database connection/infrastructure and collection names | No agent queries or business/workflow logic |
| `common/` | Shared errors, responses, statuses, IDs, traceability helpers | Shared changes require review |

The direction is `router → service → repository → database`. Services may call the Orchestrator through an approved interface but must not duplicate global transition rules.

### Agent 4 validation executor boundary

Agent 4 executable validation uses:

```text
Agent4Engine
  -> ValidationExecutor
  -> SandboxedValidationExecutor
  -> bounded local Docker container
```

`Agent4Engine` does not invoke raw host commands. A temporary directory is not a
sandbox; it is only the staging and cleanup location. The Docker executor mounts only
that location at `/workspace`, disables networking, pulls no images at runtime, runs
with a numeric non-root UID/GID, uses a read-only container root, drops all
capabilities, applies
`no-new-privileges`, and enforces the centrally declared limits in
`app/modules/testing/executor.py`: 1 CPU, 512 MiB memory, 128 PIDs, 64 MiB temporary
storage, and 30 seconds per command.

Supported profiles are `PYTHON_PYTEST` and `NODE_NPM_TEST`. Their executable and
arguments are server-owned templates. User-supplied executable names or additional
arguments are prohibited. Runtime network/dependency resolution is prohibited; local
images are built explicitly by an operator when dependencies are available:

```powershell
docker build -f docker/agent4/Dockerfile.python-pytest -t agileflow/agent4-python-pytest:1.0 .
docker build -f docker/agent4/Dockerfile.node-npm-test -t agileflow/agent4-node-test:1.0 .
```

Docker, daemon, or image unavailability fails executable validation with
`TOOL_EXECUTION_FAILED`; there is no host-execution fallback. Project paths are
validated using POSIX and Windows rules, resolved beneath the temporary root, checked
for symlink/reparse-point escape, and written with bounded size/count and exclusive
no-follow creation where supported. Containers are force-removed after success,
failure, or timeout.

### Shared Knowledge Base Internal Boundary

The Shared Knowledge Base is an internal service/facade over the existing MongoDB artifact collections, not another database, vector store, RAG system, or LLM memory. SKB-5 implements it at `app/modules/shared_knowledge/` for typed Agent 1 reads. It coordinates project-scoped retrieval through collection-specific repositories owned by `requirements` and Reports/Traceability plus the Approval read boundary; it does not implement a dynamic repository that accepts arbitrary collection names. Future `design`, `testing`, and `implementation` adapters extend this pattern.

The foundation follows **INTERNAL SERVICE FIRST**. Do not add public `/knowledge-base` or generic `/artifacts` routes during SKB implementation. Human-facing workspaces continue to use specialist APIs. Traceability remains a separate shared service responsibility under `app/modules/reports/`; the SKB may consume its queries but does not own final matrix/report generation.

The shared authentication and ownership boundary is:

```text
request
  → get_current_user
  → authorize_project_access
  → component service
```

JWT parsing is implemented in the reusable `get_current_user` authentication dependency. Project ownership authorization is implemented in the shared `authorize_project_access` boundary; routers and agents must not duplicate either concern.

## Shared MongoDB Foundation

`app/database/mongodb.py` is the canonical database module. It creates one reusable `MongoClient` from `settings.mongodb_uri`, selects `settings.mongodb_database`, exposes `get_database()`, supplies `ping_database()`, and supplies `close_mongodb_client()`.

Rules:

- Reuse this client; do not create clients inside repositories or agent modules.
- Repositories select only their approved collections using `app/database/collections.py` constants.
- Do not put agent queries, workflow decisions, or repository methods in `mongodb.py`.
- Do not hardcode credentials or Atlas strings.
- Close the client during an approved application shutdown lifecycle when lifecycle handling is implemented.

The canonical collection set contains 15 implemented constants: `users`, `projects`, `client_inputs`, `requirements`, `design_artifacts`, `backlog_items`, `test_cases`, `implementation_artifacts`, `execution_logs`, `test_results`, `security_findings`, `bug_reports`, `approvals`, `traceability_links`, and `workflow_events`. Do not create alternate user collections.

## API and Response Rules

[API_CONTRACT.md](../api-contracts/API_CONTRACT.md) is the canonical API contract. All domain routes use `/api/v1` and project-scoped routes use `/api/v1/projects/{project_id}/...`. Do not implement File 11's older non-versioned `/api/projects/...` examples.

Use the shared response shape:

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

Validation/error responses retain the same fields with `success: false`, `data: null`, and structured error items. File 11's alternate `workflow_status`, `traceability_updated`, `error_code`, and `details` shape is not the canonical envelope.

JWT Bearer registration, login, token validation, and `/auth/me` are implemented. Missing or invalid authentication returns HTTP 401. Every currently implemented Project-scoped endpoint enforces ownership through the Project record. Authenticated access to a missing, ownerless legacy, or non-owned Project returns HTTP 404 to avoid disclosing another user's project identifier. Future Project-scoped routes must reuse the same boundary.

## Data, IDs, and Traceability

Follow [DATA_SCHEMAS.md](../schemas/DATA_SCHEMAS.md). Important artifacts carry project/artifact identifiers, type, title, status, approval gate, creator, timestamps, version, and traceability references. Do not duplicate Project, Requirement, TestCase, Approval, or traceability models.

For Agent 1, the `requirements` collection stores Requirement, UserStory, AcceptanceCriteria, QualityFinding, Persona, and SrsDocument documents distinguished by `artifact_type`. Each schema inherits BaseArtifact and uses the ID mapping in `DATA_SCHEMAS.md`. The stable stored identity is `(project_id, artifact_id, version)`, and each H1 version is a complete immutable snapshot. Do not overwrite historical versions or create an `artifact_packages` collection.

The SKB-2 requirements repository returns concrete Pydantic artifact types and excludes MongoDB `_id`. Its internal snapshot service validates the full package before writing, allocates missing IDs with the established max-scan approach, shares one `REQ` sequence across all four REQ-family artifact types, and preserves caller-supplied IDs for later versions. Reads and identity checks are project-scoped. Ordered `insert_many` is used without requiring MongoDB transactions; max-scan allocation races and partial writes after an infrastructure failure remain documented prototype limitations.

Effective Approval records, not `ArtifactStatus.APPROVED`, are the source of approval truth. SKB-5 reuses `ApprovalRepository.get_effective_approval`, requires `APPROVE`, and selects the exact H1 package version in `Approval.artifact_version`; a newer draft never supersedes that selection. Missing referenced snapshots fail as consistency errors. `traceability_links` is the authoritative graph; `BaseArtifact.traceability_refs` is optional denormalized cache metadata. ClientInput has no public artifact ID and is not a TraceabilityLink endpoint; raw-input provenance is recorded in `Requirement.source_reference`.

SKB-3 implements immutable conceptual-identity links for persisted Agent 1 artifacts under `app/modules/reports/`. It validates same-project endpoint existence, stable artifact types across versions, and the approved directed relation/type combinations before creation. Exact logical duplicates return the existing link; incoming, outgoing, exact-edge, trace-ID, and project listings remain project-scoped and typed. TraceabilityLink has no version fields: package-specific consumers intersect conceptual links with membership in a selected artifact version, as SKB-5 does for its approved-H1 link view. SKB-3 itself has no update/delete operations, public routes, graph traversal, package publication, or approval-selection logic. The max-scan TRACE allocator and application-level idempotency retain concurrent-writer race limitations.

SKB-4 publishes an already-persisted H1 snapshot through an internal Requirements service. It validates project/stage, schema-valid snapshot membership and statuses, at least one Requirement, required UserStory/AcceptanceCriteria/QualityFinding/SrsDocument traceability within the selected version, then changes only selected `IN_PROGRESS` artifacts to `WAITING_FOR_APPROVAL`. After that succeeds it appends or reuses the exact O3.5 `ARTIFACT_GENERATED` marker through the existing Orchestrator repository and EVT allocator. Publication never changes Project stage or creates an Approval; existing next-step remains the sole gate-entry path. Status and event writes are not transactional, so retry logic supports a waiting package whose marker write failed. Concurrent publishers can still race between the application-level marker check, max-scan EVT allocation, and event insert; SKB-4 adds no transaction, counter, or unique-index infrastructure.

SKB-5 adds a read-only `SharedKnowledgeService`. Exact-version and latest-version artifact lookups are deliberately distinct; latest is never treated as approved. Structured lists support only project, Agent 1 type, version, and status filters. Approved H1 retrieval returns typed artifacts even when their lifecycle status remains `WAITING_FOR_APPROVAL`, because human Approval is authoritative. One-hop incoming/outgoing queries delegate to Reports/Traceability, and an approved-snapshot link view intersects both conceptual endpoints with exact package membership. H2-H5 approved adapters, graph traversal, public SKB routes, and semantic/vector retrieval remain unimplemented. Downstream agents must consume approved upstream context through `get_approved_h1_snapshot(project_id)` rather than a latest-artifact query.

Preserve the ID families `USR`, `PRJ`, `REQ`, `US`, `AC`, `DES`, `API`, `DB`, `TASK`, `TEST`, `CODE`, `BUG`, `SEC`, `TRACE`, `EVT`, and `APP` as documented. `USR-###` identifies a user. Project creation accepts required `name` and `domain` plus optional `description`, defaulting an omitted description to an empty string. Both `Project.created_by` and `Project.owner_user_id` are assigned server-side from the authenticated user's `user_id` and cannot be client-controlled or patched. The required research trace is:

```text
Requirement → Design → Backlog → Test → Code
            → Bug / Security Finding → Validation
            → Report / Correction
```

Agent 1 creates requirement/story/criteria IDs; Agent 2 links them to design/backlog IDs; Agent 4 links them to test IDs; Agent 3 links code to approved inputs; post-code validation links bugs/security findings back to requirements, tests, and code.

## Orchestrator Integration

Follow [ORCHESTRATOR_WORKFLOW.md](../architecture/ORCHESTRATOR_WORKFLOW.md). An agent service completes its assigned work, persists output, and notifies/returns control to the Orchestrator. It cannot select the global next stage.

The Orchestrator alone enforces:

- one active canonical stage;
- H1-H5 approval prerequisites;
- required artifact checks;
- failure routing and bounded retries;
- append-only workflow event evidence;
- final completion only after H5 approval and validation evidence.

Every major action should create/update the relevant artifacts, append idempotent immutable traceability links, and append workflow events when those features are implemented.

### Implemented O3.5 Specialist Handoff Consumption/Validation Contract

All specialist-to-approval-gate transitions reuse the existing next-step service and `POST /api/v1/projects/{project_id}/orchestrator/next-step`; no completion or handoff route is added. The authenticated owner may invoke the HTTP endpoint after specialist processing. Specialist services persist artifacts and append a final `ARTIFACT_GENERATED` readiness marker but never mutate global stage. The Orchestrator service owns readiness validation, stage mutation, and `STAGE_CHANGED` creation.

The readiness event must be the newest valid marker for the active `project_id`, current specialist source stage, matching waiting target stage, and expected official specialist component. It targets `Central SDLC Orchestrator` and carries only `handoff_ready: true`, `source_stage`, `target_stage`, and a positive integer `artifact_version` as readiness metadata. It must not carry reviewer comments or identity, credentials, tokens, passwords, password hashes, or private authentication data.

Repository evidence checks are project-scoped and use the existing canonical collections:

- requirements to H1: at least one `requirements` record;
- design to H2: at least one `design_artifacts` and one `backlog_items` record;
- pre-code testing to H3: at least one `test_cases` record;
- implementation to H4: at least one `implementation_artifacts` and one `execution_logs` record;
- validation to H5: at least one `test_results` record.

The same service-level readiness evaluator must drive both next-step and the read-only workflow snapshot. Missing readiness returns HTTP 409, keeps the Project unchanged, and creates no `STAGE_CHANGED` or Approval. Success updates `current_stage` and `updated_at` and creates exactly one `STAGE_CHANGED` from `Central SDLC Orchestrator` to `Human Stakeholder / Reviewer`. Approval records remain reviewer-decision records created later through H1-H5.

O3.5 does not require ArtifactStatus `WAITING_FOR_APPROVAL` or `COMPLETED`, successful build/runtime status, a positive finding count, or machine-checkable traceability completeness. Package `artifact_version` is recorded in readiness evidence but is not yet cross-validated against O2 Approval versions. The implementation must add no collection, EventType, Project readiness field, or package schema.

### Approved O2 Approval Persistence Contract

O2 is implemented. Its approval routes follow `get_current_user` → `authorize_project_access` → approval service → approval repository. The route supplies `project_id`, the gate-specific endpoint supplies `gate_id`, and the server generates `APP-###` `approval_id`, UTC `timestamp`, and `next_stage`. Clients supply only `reviewer_name`, `reviewer_role`, `decision`, `comment`, and a positive integer `artifact_version`; at least one reviewer identity field is required. Extra server-controlled fields, `artifact_type`, and `reviewer_user_id` are rejected. O2 records the reviewed version but does not validate, update, or lock specialist artifact records.

Approval records are immutable and append-only. Multiple records for one `project_id + gate_id` are permitted, the newest is effective, and no uniqueness constraint is placed on that pair. The canonical persistence target is the existing `approvals` collection. The prototype uses largest-`APP-###` scan-and-increment allocation with its known concurrency limitation; no counter collection is used.

Every successfully persisted O2 decision creates exactly one `APPROVAL_DECISION` WorkflowEvent, with the matching waiting stage used for both `stage_before` and `stage_after`. O2 never changes `Project.current_stage` and never creates `STAGE_CHANGED`. APPROVE records the canonical forward `next_stage`; REJECT, REQUEST_CHANGES, and HOLD record the current waiting stage and block forward progression. O3 uses the shared effective/latest lookup and centralized policy to make only canonical effective-APPROVE transitions executable through next-step, creating one `STAGE_CHANGED`; O4 owns correction/routing and O6 owns richer HOLD/release behavior.

## Error Handling and Logging

Return structured errors; never expose raw Python exceptions or stack traces. File 11 identifies planned error categories including `PROJECT_NOT_FOUND`, `INVALID_WORKFLOW_STAGE`, `APPROVAL_REQUIRED`, `ARTIFACT_NOT_FOUND`, `VALIDATION_ERROR`, `GENERATION_FAILED`, and `RETRY_LIMIT_EXCEEDED`. Their exact placement in the canonical File 06 envelope is not formally defined and requires contract approval before implementation.

Use:

- `execution_logs` for build/runtime/tool/self-fix/test execution details;
- `workflow_events` for transitions, approvals, routing, retries, and handovers.

Do not overwrite prior retry logs or hide workflow-affecting failures.

## Testing Strategy

Current tests cover `/health`, settings defaults/environment overrides, exact collection constants, and database helper behavior using in-test fakes. They make no external MongoDB/Atlas call.

For future modules, test at the appropriate layers:

- schemas: accepted/rejected payloads and stable field names;
- repositories: collection choice and persistence behavior using an approved isolated strategy;
- services: workflow prerequisites, artifact/traceability behavior, and failure paths;
- routers: method/path, response envelope, status handling, and invalid IDs;
- Orchestrator: every allowed/blocked transition, H1-H5, routing, retry limits, escalation, and event creation;
- security: secret handling, validation, upload paths, and safe errors.

Tests must not depend on private Atlas credentials. Keep the app importable and run the existing suite before every backend PR.

## Module Ownership

| Area | Owner |
|---|---|
| `core`, `database`, `common`, `main.py` | Foundation team |
| projects, approvals, Orchestrator foundation | Foundation/group leader with shared review |
| requirements | N A Illangasinghe — IT23391536 |
| design | Kulunu Kasthuri Arachchi — IT23375628 |
| implementation | W M D D Karunarathna — IT23145320 |
| testing (pre-code and post-code) | R A K Hansika — IT23140998 |
| reports/traceability | Shared, coordinated through assigned branch/reviewer |

Cross-module or shared-contract changes require coordination and documentation updates.

## Security and Secrets

- Keep secrets only in ignored local environment configuration.
- Hash passwords with Argon2; never persist or return plaintext passwords, and never expose `password_hash`.
- Load JWT signing secrets from environment configuration; never hardcode them or place private user data or project IDs in tokens.
- Keep authentication and ownership centralized through reusable dependencies/helpers; do not trust a syntactically valid `project_id` without ownership authorization.
- Maintain safe `.env.example` placeholders; never store usernames/passwords or private URIs.
- Do not log credentials, tokens, private uploaded data, or complete sensitive content.
- Sanitize upload names and use project-scoped storage when uploads are implemented.
- Validate all request and generated artifact structures with approved schemas.
- Review CORS before non-local deployment; the current foundation reads one frontend origin from settings.
- Justify and approve dependencies; do not introduce unnecessary infrastructure.
- Preserve security findings and their requirement/test/code links.

## Definition of Done for Backend Work

- Work stays in the owned module and follows the layer boundaries.
- Canonical API/data/workflow contracts are unchanged or updated through approval.
- Shared clients, constants, schemas, statuses, IDs, responses, and errors are reused.
- Relevant tests pass and FastAPI imports/starts.
- `/docs` reflects endpoint changes where applicable.
- Workflow events/traceability/persistence are handled where the feature requires them.
- No credentials, unrelated edits, duplicate abstractions, or alternate routes are introduced.
- PR explains files, contract impacts, tests, limitations, and AI-generated portions.

## Contract Resolution Notes

1. PyMongo and `backend/app/database/mongodb.py` are canonical for this repository; do not add Motor or `connection.py`.
2. File 06 overrides File 11's non-versioned API and alternate response examples.
3. File 12 supplies canonical workflow stages and approval semantics.
4. Planned error-code placement in the File 06 envelope requires human contract approval.
