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
│   │   └── collections.py      # 15 canonical collection constants
│   ├── common/
│   │   ├── response.py         # shared response models
│   │   ├── status.py           # shared enums
│   │   ├── id_generator.py     # canonical ID helpers
│   │   └── traceability.py     # shared traceability validation
│   ├── modules/
│   │   ├── auth/               # registration, login, JWT, and /auth/me
│   │   ├── projects/           # Project CRUD module
│   │   ├── approvals/          # package placeholder
│   │   ├── orchestrator/       # first transition only
│   │   ├── requirements/       # ClientInput foundation only
│   │   ├── design/             # package placeholder
│   │   ├── testing/            # package placeholder
│   │   ├── implementation/     # package placeholder
│   │   └── reports/            # package placeholder
│   └── schemas/                # shared domain schemas
├── tests/                       # 146-test backend suite
├── .env.example
└── requirements.txt
```

Implemented: FastAPI application, CORS setting, `GET /health`, automatic `/docs`, environment loading, one PyMongo client, database access/ping/close helpers, 15 collection constants, shared enums/schemas/response and ID helpers, User persistence and registration with Argon2 hashing, JWT login and validation, `/auth/me`, reusable `get_current_user` authentication, centralized Project ownership authorization, owner-scoped Project CRUD and ClientInput access, the centralized Orchestrator transition policy and stage ownership metadata, workflow snapshot/event-history endpoints, the owner-scoped first transition with ClientInput prerequisite and WorkflowEvent persistence, and backend tests.

Not implemented: Project sharing/collaboration, Requirement Agent processing or intelligence, approval APIs/gate processing, later executable Orchestrator transitions, failure routing, retry loops, traceability persistence/generation, reports, frontend, LLM/RAG, or external Jira, GitHub, Docker, and security-scanner integrations. The implemented modules preserve `router` → `service` → `repository` → database layering.

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

Preserve the ID families `USR`, `PRJ`, `REQ`, `US`, `AC`, `DES`, `API`, `DB`, `TASK`, `TEST`, `CODE`, `BUG`, `SEC`, `TRACE`, `EVT`, and `APP` as documented. `USR-###` identifies a user; `Project.owner_user_id` is assigned server-side from that authenticated user. The required research trace is:

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

Every major action should create/update the relevant artifacts, traceability links, and workflow events when those features are implemented.

### Approved O2 Approval Persistence Contract

O2 is approved but not implemented. Its future approval routes must follow `get_current_user` → `authorize_project_access` → approval service → approval repository. The route supplies `project_id`, the gate-specific endpoint supplies `gate_id`, and the server generates `APP-###` `approval_id`, UTC `timestamp`, and `next_stage`. Clients supply only `reviewer_name`, `reviewer_role`, `decision`, `comment`, and a positive integer `artifact_version`; at least one reviewer identity field is required. Extra server-controlled fields, `artifact_type`, and `reviewer_user_id` must be rejected. O2 records the reviewed version but does not validate, update, or lock specialist artifact records.

Approval records are immutable and append-only. Multiple records for one `project_id + gate_id` are permitted, the newest is effective, and no uniqueness constraint may be placed on that pair. The canonical persistence target is the existing `approvals` collection. A prototype largest-`APP-###` scan-and-increment allocator may be used later, with its concurrency limitation documented; no counter collection is approved.

Every successfully persisted O2 decision creates exactly one `APPROVAL_DECISION` WorkflowEvent, with the matching waiting stage used for both `stage_before` and `stage_after`. O2 never changes `Project.current_stage` and never creates `STAGE_CHANGED`. APPROVE records the canonical forward `next_stage`; REJECT, REQUEST_CHANGES, and HOLD record the current waiting stage and block forward progression. O3 owns the later APPROVE transition and `STAGE_CHANGED`; O4 owns correction/routing; O6 owns richer HOLD/release behavior.

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
