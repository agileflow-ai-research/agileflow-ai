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
- **Authentication:** optional/not formally defined for the MVP; no authentication contract is established here
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

The only verified HTTP endpoint is `GET /health` at the application root. It is an implemented foundation diagnostic, not a member of the planned `/api/v1` domain contract. FastAPI also supplies `/docs` automatically. Every route below is **Planned / later sprint**.

## Project Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects` | Create a project | Core/Foundation | Project create body: not formally defined; Project fields are the reference | Project | Initializes workflow before H1 | Planned |
| GET | `/api/v1/projects` | List projects for the dashboard | Core/Foundation | None | Project list; list wrapper details not formally defined | Shows current stages/gates | Planned |
| GET | `/api/v1/projects/{project_id}` | Get project details/current state | Core/Foundation | Path parameter | Project | Shows gate context | Planned |
| PATCH | `/api/v1/projects/{project_id}` | Update basic project metadata | Core/Foundation | Project update body: not formally defined | Project | No direct gate transition | Planned |

## Workflow and Orchestrator Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| GET | `/api/v1/projects/{project_id}/workflow` | Get current stage and gate state | Central SDLC Orchestrator | Path parameter | Project, Approval, WorkflowEvent; aggregate body not formally defined | Reports H1-H5 state | Planned |
| POST | `/api/v1/projects/{project_id}/orchestrator/next-step` | Validate and perform the next allowed action | Central SDLC Orchestrator | Not formally defined | Workflow state; body not formally defined | Must block at unapproved gates | Planned |
| POST | `/api/v1/projects/{project_id}/orchestrator/route-failure` | Route requirement, build, test, security, or traceability failure | Central SDLC Orchestrator | Not formally defined | WorkflowEvent and relevant issue reference | May return work to gate owner | Planned |
| GET | `/api/v1/projects/{project_id}/events` | Get workflow activity timeline | Central SDLC Orchestrator | Path parameter | WorkflowEvent list | Includes approval events | Planned |

File 12 describes a retry action but File 06 does not include a canonical retry route. No retry endpoint is established by this contract; retry execution requires human contract approval before implementation.

## Requirement Gathering and Analysis Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/inputs` | Upload or submit client inputs | Requirement Gathering and Analysis Agent | Body/upload fields not formally defined | Client input schema not formally defined | Input to H1 artifacts | Planned |
| GET | `/api/v1/projects/{project_id}/inputs` | List submitted input sources | Requirement Gathering and Analysis Agent | Path parameter | Client input schema not formally defined | Supports H1 review | Planned |
| POST | `/api/v1/projects/{project_id}/requirements/process` | Generate structured requirements | Requirement Gathering and Analysis Agent | Input references/body not formally defined | Requirement, UserStory, AcceptanceCriteria | Produces H1 package | Planned |
| GET | `/api/v1/projects/{project_id}/requirements` | Get requirements, stories, and acceptance criteria | Requirement Gathering and Analysis Agent | Path parameter | Requirement, UserStory, AcceptanceCriteria | Reviewed at H1 | Planned |
| POST | `/api/v1/projects/{project_id}/requirements/clarifications` | Add clarification questions or human feedback | Requirement Gathering and Analysis Agent | Not formally defined | Not formally defined | Supports H1 correction loop | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h1` | Record requirement decision | Requirement Gathering and Analysis Agent / Orchestrator | Approval fields | Approval | H1 | Planned |

## Project Management and Design Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/design/generate` | Generate planning/design package from approved requirements | Project Management and Design Agent | Requirement references; body not formally defined | DesignArtifact, BacklogItem | Requires H1; produces H2 package | Planned |
| GET | `/api/v1/projects/{project_id}/backlog` | Get epics, stories, tasks, subtasks, and bugs | Project Management and Design Agent | Path parameter | BacklogItem list | Reviewed at H2 | Planned |
| GET | `/api/v1/projects/{project_id}/design/artifacts` | Get UML/API/DB/UI/wireframe artifacts | Project Management and Design Agent | Path parameter | DesignArtifact list | Reviewed at H2 | Planned |
| GET | `/api/v1/projects/{project_id}/design/traceability` | Get requirement-to-design mapping | Project Management and Design Agent | Path parameter | TraceabilityLink; response aggregation not formally defined | H2 evidence | Planned |
| POST | `/api/v1/projects/{project_id}/design/jira-sync` | Mock or later approved real Jira synchronization | Project Management and Design Agent | Not formally defined | Not formally defined | Does not replace H2 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h2` | Record planning/design decision | Project Management and Design Agent / Orchestrator | Approval fields | Approval | H2 | Planned |

## Testing, Validation and Security — Pre-Code Routes

These routes belong to the pre-code phase of the single Testing, Validation and Security Agent.

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/tests/pre-code/generate` | Generate test specifications and skeleton metadata | Testing, Validation and Security Agent | Approved requirement/design references; body not formally defined | TestCase | Requires H2; produces H3 package | Planned |
| GET | `/api/v1/projects/{project_id}/tests/pre-code` | Get draft/approved pre-code package | Testing, Validation and Security Agent | Path parameter | TestCase list | Reviewed at H3 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h3` | Record pre-code test decision | Testing, Validation and Security Agent / Orchestrator | Approval fields | Approval | H3 | Planned |

## Implementation and Git Automation Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/implementation/generate` | Generate or simulate selected prototype modules | Implementation and Git Automation Agent | Approved artifacts; body not formally defined | CodeModule / ImplementationArtifact | Requires H3; produces H4 package | Planned |
| GET | `/api/v1/projects/{project_id}/implementation/modules` | Get generated module metadata | Implementation and Git Automation Agent | Path parameter | CodeModule / ImplementationArtifact list | Reviewed at H4 | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/git/init` | Mock or later approved repository setup | Implementation and Git Automation Agent | Not formally defined | Git metadata schema not formally defined | H4 evidence | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/run` | Run or simulate build/execution | Implementation and Git Automation Agent | Not formally defined | Execution-log schema not formally defined | H4 evidence/failure routing | Planned |
| GET | `/api/v1/projects/{project_id}/implementation/logs` | Get build/runtime logs | Implementation and Git Automation Agent | Path parameter | Execution-log schema not formally defined | Reviewed at H4 | Planned |
| POST | `/api/v1/projects/{project_id}/implementation/self-fix` | Apply a bounded build/runtime self-fix | Implementation and Git Automation Agent / Orchestrator | Not formally defined | Execution-log/workflow-event details not formally defined | Does not bypass H4 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h4` | Record implementation decision | Implementation and Git Automation Agent / Orchestrator | Approval fields | Approval | H4 | Planned |

## Testing, Validation and Security — Post-Code Routes

| Method | Path | Purpose | Owner | Request schema/reference | Response schema/reference | Approval relevance | Status |
|---|---|---|---|---|---|---|---|
| POST | `/api/v1/projects/{project_id}/validation/run-tests` | Run or simulate post-code tests | Testing, Validation and Security Agent | Approved implementation reference; body not formally defined | Test results schema not formally defined; BugReport where applicable | Requires H4; contributes to H5 | Planned |
| POST | `/api/v1/projects/{project_id}/validation/security-scan` | Run or simulate security validation | Testing, Validation and Security Agent | Approved implementation reference; body not formally defined | SecurityFinding | Contributes to H5 | Planned |
| GET | `/api/v1/projects/{project_id}/validation/report` | Get combined validation report | Testing, Validation and Security Agent | Path parameter | Validation report schema not formally defined | Reviewed at H5 | Planned |
| POST | `/api/v1/projects/{project_id}/approvals/h5` | Record final validation decision | Testing, Validation and Security Agent / Orchestrator | Approval fields | Approval | H5 | Planned |

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

## Contract Resolution Notes

1. **API route versioning:** File 06 is the dedicated API authority, so `/api/v1` and `{project_id}` are canonical. Non-versioned File 11/File 12 examples are not a second API family.
2. **Response envelope:** File 06 is authoritative. File 09's `metadata` wrapper and File 11's alternate fields are examples not adopted here.
3. **Workflow stages:** Stage values in payloads come from File 12, the specialized workflow authority, not File 06's older stage list.
4. **Testing component:** Pre-code and post-code routes belong to one Testing, Validation and Security Agent.
5. **Undefined bodies:** Request fields not supplied by File 06 remain formally undefined and require contract approval before implementation.
