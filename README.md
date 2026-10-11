# AgileFlow AI

**Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**  
Project ID: **J26-SE-358**

AgileFlow AI is a final-year Software Engineering research prototype for moving a raw client software idea through a controlled Agile SDLC workflow. It is intended to demonstrate coordinated artifact generation, human approval, failure routing, and end-to-end traceability. It is not a complete autonomous or production-ready software-development platform, and it does not replace developers, reviewers, clients, or security specialists.

## Research Prototype Scope

The target outcome is a structured Agile project environment and a validated runnable prototype foundation. Inputs may include text, documents, links, audio/video metadata, and interview responses. Outputs may include requirements, planning and design artifacts, pre-code tests, implementation metadata, validation evidence, findings, and final traceability reports.

The first implementation may use mock or template outputs and local storage. Structured prompts and structured JSON are the initial AI-integration approach; RAG and external Jira, GitHub, Docker, testing, or security-tool integrations are later options only where justified and approved.

## Architecture

AgileFlow AI has exactly four intelligent research agents:

1. **Requirement Gathering and Analysis Agent** — structures client input into requirements, user stories, acceptance criteria, and quality findings.
2. **Project Management and Design Agent** — creates backlog, sprint, UML, API, database, UI, and requirement-to-design artifacts.
3. **Implementation and Git Automation Agent** — generates selected prototype modules and records Git/workspace and execution metadata.
4. **Testing, Validation and Security Agent** — creates pre-code test artifacts and later performs post-code testing, validation, bug reporting, and security analysis.

Pre-code test planning and post-code validation are two phases of the fourth agent, not a fifth research agent.

Supporting shared components are:

- **Central SDLC Orchestrator** — controls stage order, handovers, approvals, bounded retries, failure routing, and workflow events. It does not perform the agents' domain work.
- **Shared Knowledge Base** — MongoDB storage for structured project artifacts, workflow information, approvals, logs, and traceability links.
- **Reports / Traceability** — shared functionality for evidence, exports, and the Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction chain.

## Human-in-the-Loop Workflow

The Orchestrator must never advance past an approval gate without a recorded human decision.

```text
Client Input
  → Requirement Gathering and Analysis Agent
  → H1 Requirement Approval
  → Project Management and Design Agent
  → H2 Design and Planning Approval
  → Testing, Validation and Security Agent (Pre-Code)
  → H3 Pre-Code Test Approval
  → Implementation and Git Automation Agent
  → H4 Implementation Approval
  → Testing, Validation and Security Agent (Post-Code)
  → H5 Final Validation Approval
  → Final Reports / Traceability / Completion
```

The canonical workflow stages are defined in [ORCHESTRATOR_WORKFLOW.md](docs/architecture/ORCHESTRATOR_WORKFLOW.md). The canonical API contract is [API_CONTRACT.md](docs/api-contracts/API_CONTRACT.md); its base prefix is `/api/v1`.

## Approved Technology Stack

| Area | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic, pydantic-settings |
| Shared Knowledge Base | MongoDB, PyMongo |
| Backend testing | Pytest, HTTPX |
| Initial file storage | Local `/storage` structure |
| AI integration | Structured prompts and structured JSON first; optional RAG later where justified |
| External integrations | Mock-first and progressively replaced where approved |

Kafka, RabbitMQ, Redis, Celery, Kubernetes, GraphQL, microservices, event sourcing, and additional databases are not part of the approved baseline.

## Repository Structure

```text
agileflow-ai/
├── backend/       FastAPI foundation and future backend modules
├── frontend/      React/Vite/Tailwind application (not initialized yet)
├── docs/          Implementation contracts, guides, and approved source documents
├── storage/       Local upload, generated-artifact, log, and report directories
├── sample-data/   Future non-confidential demonstration data
├── README.md
├── CONTRIBUTING.md
├── AI_AGENT_RULES.md
└── TASK_ASSIGNMENT.md
```

## Branch Structure

| Branch | Purpose |
|---|---|
| `main` | Stable milestone/final version only |
| `develop` | Reviewed integration branch; must remain runnable |
| `feature/project-foundation` | Shared repository and backend foundation |
| `feature/ui-design-system` | Central theme, layout, and reusable UI |
| `feature/agent-requirements` | Requirement Gathering and Analysis Agent |
| `feature/agent-design-planning` | Project Management and Design Agent |
| `feature/agent-implementation` | Implementation and Git Automation Agent |
| `feature/agent-testing-validation` | Testing, Validation and Security Agent |
| `feature/orchestrator` | Workflow, approvals, routing, and retries |
| `feature/reports-traceability` | Reports and traceability |

> Incomplete feature branch is acceptable. Broken develop branch is not acceptable.

## Backend Setup

The current backend foundation provides the FastAPI application, `GET /health`, automatic Swagger UI at `/docs`, environment-based settings, and shared MongoDB connection helpers. A local MongoDB server is optional for the health endpoint and unit tests; it is required only for a live database ping.

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

Open:

- Health: `http://127.0.0.1:8000/health`
- Swagger UI: `http://127.0.0.1:8000/docs`

Run tests:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

Optional MongoDB connectivity check:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -c "from app.database.mongodb import ping_database, close_mongodb_client; print(ping_database()); close_mongodb_client()"
```

## Frontend Setup

**Planned / not yet available.** The `frontend/` directory currently contains only a placeholder. React, Vite, Tailwind CSS, routes, components, and package scripts have not been initialized. Follow [FRONTEND_GUIDE.md](docs/implementation-rules/FRONTEND_GUIDE.md) when that work is approved.

## Environment Configuration

Copy `backend/.env.example` to `backend/.env` for local settings. Never commit `.env` or credentials. The safe example contains `APP_NAME`, `APP_ENV`, `API_V1_PREFIX`, `FRONTEND_ORIGIN`, `MONGODB_URI`, and `MONGODB_DATABASE`.

Use local or placeholder values in documentation and examples. Never add passwords, Atlas credentials, API keys, GitHub/Jira tokens, private client data, or private connection strings.

## Documentation Map

| Document | Purpose |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branch, review, security, and contribution workflow |
| [AI_AGENT_RULES.md](AI_AGENT_RULES.md) | Policy for bounded AI-assisted implementation |
| [TASK_ASSIGNMENT.md](TASK_ASSIGNMENT.md) | Team ownership and branch map |
| [API_CONTRACT.md](docs/api-contracts/API_CONTRACT.md) | Canonical `/api/v1` endpoint contract |
| [DATA_SCHEMAS.md](docs/schemas/DATA_SCHEMAS.md) | Shared schemas, IDs, statuses, and collections |
| [ORCHESTRATOR_WORKFLOW.md](docs/architecture/ORCHESTRATOR_WORKFLOW.md) | Canonical stages, approvals, routing, and retries |
| [FRONTEND_GUIDE.md](docs/implementation-rules/FRONTEND_GUIDE.md) | Frontend structure, tokens, components, and routes |
| [BACKEND_GUIDE.md](docs/implementation-rules/BACKEND_GUIDE.md) | Backend layers, database foundation, and testing rules |
| [COMPONENT_PLAN.md](docs/architecture/COMPONENT_PLAN.md) | Implementation-facing component boundaries |

Approved source documents are retained under `docs/source/` and must not be edited as implementation documentation.

## Current Implementation Status

| Capability | Status |
|---|---|
| Repository/backend folder foundation | Implemented |
| FastAPI application and `GET /health` | Implemented |
| FastAPI Swagger UI at `/docs` | Available through FastAPI |
| Environment-based settings | Implemented |
| Shared PyMongo client, configured database accessor, ping, close | Implemented |
| Fourteen centralized MongoDB collection constants | Implemented |
| Shared enums, domain schemas, ID conventions, and API response models | Implemented |
| Project CRUD APIs and persistence | Implemented |
| ClientInput APIs and persistence foundation | Implemented; requirement processing remains planned |
| First Orchestrator transition and WorkflowEvent persistence | Implemented only for `PROJECT_CREATED` → `REQUIREMENTS_IN_PROGRESS`, with a ClientInput prerequisite |
| Backend test suite | Implemented; 76 tests passing in the current verified suite |
| Frontend application | Planned; not initialized |
| Agent intelligence, approval APIs, and later workflow stages | Planned |
| Remaining artifact persistence, traceability behavior, reports, and integrations | Planned |

This is a Sprint 1 prototype foundation, not a production-ready system. The presence of a module directory or a planned route in documentation does not mean that functionality is implemented.
