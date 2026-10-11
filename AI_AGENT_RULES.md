# AgileFlow AI — AI-Assisted Implementation Policy

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**  
Project ID: **J26-SE-358**

AI tools may assist implementation, but the team owns every decision and change. A responsible member must inspect, test, document, and approve AI output before it is merged.

## Governance Principles

1. **Human control:** AI output is a proposal, never an automatic project decision.
2. **Bounded tasks:** Every task names the branch, component, exact allowed files, protected files, expected result, and validation commands.
3. **Protected architecture:** Preserve exactly four intelligent research agents, the Central SDLC Orchestrator, Shared Knowledge Base, reports/traceability, and H1-H5.
4. **No architecture drift:** Do not rename official components, canonical stages, API paths, schema fields, collections, IDs, or theme tokens without approved contract changes.
5. **Documentation first:** Read the relevant contracts before acting; update approved implementation documentation with any authorized contract change.
6. **Security first:** Never expose or commit secrets, credentials, private connection strings, private keys, tokens, or confidential client data.
7. **Traceability:** Preserve Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction links.
8. **Review and testing:** Report changed files and validation results. Never treat generated code as accepted merely because it compiles.

## Protected Architecture and Contracts

AI must follow these implementation authorities:

- [README.md](README.md) — implementation overview and verified status.
- [API_CONTRACT.md](docs/api-contracts/API_CONTRACT.md) — canonical `/api/v1` routes and response envelope.
- [DATA_SCHEMAS.md](docs/schemas/DATA_SCHEMAS.md) — schema names, fields, IDs, statuses, and collections.
- [ORCHESTRATOR_WORKFLOW.md](docs/architecture/ORCHESTRATOR_WORKFLOW.md) — canonical stages, gates, routing, and retries.
- [FRONTEND_GUIDE.md](docs/implementation-rules/FRONTEND_GUIDE.md) and [BACKEND_GUIDE.md](docs/implementation-rules/BACKEND_GUIDE.md) — implementation structure.
- [TASK_ASSIGNMENT.md](TASK_ASSIGNMENT.md) — branch and component ownership.

When documents conflict, use the concern-specific authority recorded in those contracts. Do not silently create a new interpretation; document unresolved conflicts for human approval.

## Explicit Prohibitions

An AI agent must not independently:

- create an additional research agent or describe pre-code testing as a fifth agent;
- remove, merge, rename, skip, or automatically approve H1-H5;
- bypass human approval or let an individual agent advance global workflow state;
- rename or add canonical workflow stages without approved workflow-contract changes;
- create a second API family such as `/api/projects/...` beside `/api/v1/projects/...`;
- rename canonical fields or invent request/response fields unsupported by the contracts;
- create duplicate schema models, routers, services, repositories, database clients, API clients, or frontend themes;
- create alternate MongoDB collection names;
- introduce Kafka, RabbitMQ, Redis, Celery, Kubernetes, GraphQL, microservices, event sourcing, another database, or other infrastructure without explicit approval;
- hardcode or commit credentials, tokens, passwords, private keys, private URLs, private client data, or credential-bearing MongoDB strings;
- disable validation, hide failures, overwrite evidence, or erase retry history to make a task appear successful;
- modify another owner's component, protected shared files, source documents, or unrelated modules outside the prompt's allowed scope;
- perform broad refactors, mass formatting, file deletion/renaming, or dependency changes outside the requested task;
- run Git write operations unless the human explicitly authorizes the exact operation.

## Prompt Contract

Every coding request must contain the component and owner area, current branch, exact allowed files, protected files, relevant contracts, a clear task, acceptance criteria, expected outputs, validation commands, and security/scope constraints.

Reusable template:

```text
You are working on:
AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation

Component: [official component name]
Current branch: [feature branch]

Allowed files/folders:
- [exact paths]

Do not modify:
- [protected and out-of-scope paths]

Follow:
- README.md
- docs/api-contracts/API_CONTRACT.md
- docs/schemas/DATA_SCHEMAS.md
- docs/architecture/ORCHESTRATOR_WORKFLOW.md if workflow-related
- docs/implementation-rules/FRONTEND_GUIDE.md or docs/implementation-rules/BACKEND_GUIDE.md as relevant
- AI_AGENT_RULES.md
- TASK_ASSIGNMENT.md

Task:
[single bounded task]

Requirements:
- Reuse existing shared models, clients, components, services, and constants.
- Do not rename routes, fields, stages, statuses, gates, collections, or official components.
- Do not create duplicates or change unrelated files.
- Do not expose secrets or private data.
- Preserve traceability and approval behavior where applicable.

Expected output:
- [artifacts/change requested]
- changed-files summary
- validation results
- assumptions/problems

Validation commands:
- [exact commands]
```

## Allowed and Protected Work

AI may create boilerplate, focused APIs, reusable UI components, tests, mock outputs, small refactors, error explanations, and documentation drafts when the prompt explicitly permits the relevant files.

Shared backend infrastructure (`app/main.py`, `app/core`, `app/database`, `app/common`), shared schemas, Orchestrator logic, root governance documents, API/data/workflow contracts, frontend routes/layout/theme/common components, dependencies, and environment examples are protected. They require explicit file-level permission and appropriate human review.

Component work remains within the ownership boundaries in `TASK_ASSIGNMENT.md`. Cross-component changes require coordination with every affected owner.

## Backend and Frontend Rules

- Backend follows `router → service → repository → database`.
- Routers handle HTTP concerns only; services own module behavior; repositories own persistence; schemas own validation/serialization.
- Use the single shared MongoDB client, collection constants, canonical `/api/v1` routes, and shared contract utilities.
- Do not place global workflow decisions in repositories or individual agent services, and never return raw exceptions or credentials.
- Frontend uses centralized tokens, approved reusable components, one API client, and module services.
- Pages must not directly call `fetch`/Axios, hardcode project IDs, or recreate shared layouts, status badges, approval cards, state components, or themes.
- Include accessible labels, visible focus, text alongside status colors, and loading/error/empty states.

## Expected Output and Validation

At completion, report files created/modified, implementation summary, exact validation commands/results, contract/security impacts, assumptions or unresolved decisions, and confirmation that protected/out-of-scope files and Git state were not changed. Never claim a planned feature is implemented without inspecting code and tests.

Example checks:

```powershell
# Backend
Set-Location backend
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pytest -q

# Frontend, after initialization
npm run lint
npm run build
```

The human reviewer checks scope, architecture, ownership, naming, duplicates, security, tests, documentation, approval behavior, workflow events, and traceability. AI-generated portions must be identified in the PR.

## Security Rules

- Use ignored `.env` files locally and safe placeholders in `.env.example`.
- Do not paste real secrets or private client data into AI tools.
- Do not log uploaded private content, tokens, credentials, or connection strings.
- Inspect generated code for insecure CORS, unsafe paths/uploads, missing input validation, leaked stack traces, and unnecessary dependencies.
- Preserve security findings and link them to affected requirements, tests, and code where supported.

## Final Rule

AI can generate code and documentation, but the team owns the system. Every AI output must be bounded, reviewed, tested, documented, and human-approved before it becomes part of AgileFlow AI.
