# Contributing to AgileFlow AI

This guide applies to AgileFlow AI (J26-SE-358). All contributions must preserve the four-agent architecture, human approval gates, canonical contracts, and end-to-end traceability.

## Branch and Integration Strategy

- `main` is protected and contains stable milestone/final versions only. Do not develop or push directly to it.
- `develop` is the integration branch. After initial setup, changes enter through reviewed pull requests; it must remain runnable.
- Each member works in the assigned feature branch documented in [TASK_ASSIGNMENT.md](TASK_ASSIGNMENT.md).
- Create focused changes in the owning module. Do not mix unrelated formatting, refactors, or another member's component into a PR.
- Update a feature branch from `develop` before opening its PR. Resolve and test integration issues on the feature branch.
- Target feature PRs to `develop`, not `main`.
- At least one other member reviews every PR. The group leader reviews changes to shared schemas, APIs, workflow rules, routes, layout, database infrastructure, or other protected files.

Daily workflow:

1. Update local `develop`.
2. Switch to the assigned feature branch and integrate the latest `develop`.
3. Make one bounded change within owned files.
4. Review changed files and run relevant checks.
5. Push the feature branch and open a PR into `develop`.

Use Git commands deliberately. Never commit `.env`, virtual environments, `node_modules`, generated logs, secrets, or private client data.

> Incomplete feature branch is acceptable. Broken develop branch is not acceptable.

## Ownership and Protected Areas

| Area | Owner / coordination rule |
|---|---|
| `backend/app/core/`, `backend/app/database/`, `backend/app/main.py` | Foundation team; protected shared backend infrastructure |
| Requirement backend/UI area | Requirement Gathering and Analysis owner |
| Design backend/UI area | Project Management and Design owner |
| Implementation backend/UI area | Implementation and Git Automation owner |
| Testing backend/UI area | Testing, Validation and Security owner |
| Orchestrator and workflow controls | Group leader/foundation with shared review |
| Reports and traceability | Shared work with assigned integration review |
| Frontend layout, routes, theme, common/workflow components | Foundation/UI design owners; shared changes require review |
| Contract and governance documents | All members may propose; group approval is required for contract changes |

Protected shared files include the root governance documents, `docs/api-contracts/API_CONTRACT.md`, `docs/schemas/DATA_SCHEMAS.md`, `docs/architecture/ORCHESTRATOR_WORKFLOW.md`, backend core/database/common files, frontend app routes, `MainLayout`, centralized theme files, and shared UI/workflow components. Do not modify them incidentally during component work.

## Contract Change Procedures

### API contract

Before or with an endpoint change:

1. Propose the method, canonical `/api/v1` path, owner, request/response effect, and approval/workflow impact.
2. Obtain review from affected component owners and the foundation/integration owner.
3. Update `docs/api-contracts/API_CONTRACT.md` and affected frontend service references in the same PR.
4. Add or update tests. Do not create a parallel `/api/projects/...` family.

### Data schema

Before changing a field, ID, relationship, collection, or shared status:

1. Check `docs/schemas/DATA_SCHEMAS.md` and existing shared models.
2. Describe producer, consumers, persistence impact, compatibility, and traceability impact.
3. Obtain shared-contract approval.
4. Update the schema document, tests, and approved sample data together. Do not create duplicate models.

### Workflow contract

Workflow stages, H1-H5 behavior, failure routing, and retry limits come from `docs/architecture/ORCHESTRATOR_WORKFLOW.md`. Changes require human team approval and coordinated updates to backend, frontend, events, tests, and documentation. An individual agent must not advance the global workflow or bypass a gate.

### Theme and shared components

Theme values and reusable component names come from `docs/implementation-rules/FRONTEND_GUIDE.md`. Propose shared changes through the UI/foundation owner. Update the central token/component once; do not create page-specific themes or duplicate shared components.

## Engineering Expectations

- Keep routers limited to HTTP handling; business/workflow behavior belongs in services and persistence in repositories.
- Use the shared database client, collection constants, response conventions, IDs, statuses, and traceability model.
- Frontend pages use the shared API client/service layer and reusable components; pages must not issue ad hoc `fetch`/Axios calls.
- Do not hardcode project IDs, credentials, status variants, endpoint variants, or theme colors.
- Preserve Requirement → Design → Backlog → Test → Code → Bug/Security Finding → Validation → Report/Correction links.
- Keep changes simple and proportional to the research prototype.

## AI-Assisted Contributions

Follow [AI_AGENT_RULES.md](AI_AGENT_RULES.md). Every AI task must state its component, current branch, exact allowed files, protected files, governing documents, expected output, and validation commands. Humans remain responsible for reviewing, testing, documenting, and approving AI-generated work.

AI must not change architecture, create another research agent, bypass H1-H5, rename canonical stages or routes, introduce duplicate schemas/clients/themes, add unnecessary infrastructure, expose secrets, or broadly refactor unrelated modules.

## Security and Secrets

- Store local configuration in ignored `.env` files and maintain only safe placeholders in `.env.example`.
- Never commit passwords, API keys, JWT secrets, GitHub/Jira/OpenAI tokens, private keys, Atlas credentials, credential-bearing connection strings, or confidential client data.
- Do not log credentials or private uploaded content.
- Sanitize upload filenames and keep project files under project-specific storage when uploads are implemented.
- Return structured errors; do not expose raw stack traces to frontend users.
- Check new dependencies and integrations for necessity and security before approval.

## Commits and Pull Requests

Use small logical commits. File 07 recommends the format `component-name: short description`; do not invent additional mandatory naming rules.

A PR should include:

- purpose;
- changed files;
- API impact;
- schema impact;
- workflow/approval impact;
- testing performed and commands used;
- screenshots for UI changes;
- known issues or limitations;
- which portions were AI-generated or AI-modified.

Reviewers verify ownership, scope, architecture, naming, duplicates, secrets, traceability, contract updates, and relevant tests. Shared changes require the relevant owners' review.

## Testing and Merge Expectations

Before a PR, run the checks appropriate to the changed area:

- Backend: install requirements, start FastAPI, load `/docs`, run `pytest`, and exercise changed endpoints where applicable.
- Frontend when initialized: lint/build, run the dev server, inspect the browser console, and verify responsive/loading/error/empty states.
- Integration: verify service-to-API behavior, approval restrictions, workflow state, persistence, event creation, and traceability where applicable.
- AI-generated work: manually inspect the diff for hallucinated imports, dead code, unsafe placeholders, duplicate files, and unrelated changes.

Merge only after review, successful relevant checks, documentation updates, and confirmation that `develop` remains runnable.
