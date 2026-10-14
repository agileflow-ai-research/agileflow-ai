from typing import Any

from app.common.model_provider import ModelProviderError
from app.common.status import AgentRunMode, AgentType
from app.modules.agents.design_planning.engine import Agent2Engine, StructuredOutputInvalidError
from app.modules.agents.design_planning.schemas import Agent2InputContext, Agent2RunRequest, Agent2RunResult
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject, AgentRun, AgentRunMessage
from app.modules.standalone.service import StandaloneService


class WrongAgentProjectTypeError(ValueError):
    pass


class Agent2Service:
    def __init__(self, standalone_service: StandaloneService, engine: Agent2Engine) -> None:
        self._standalone = standalone_service
        self._engine = engine

    def run(
        self,
        agent_project_id: str,
        request: Agent2RunRequest,
        current_user: UserPublicResponse,
    ) -> Agent2RunResult:
        project = self._standalone.require_active_project(current_user.user_id, agent_project_id)
        if project.agent_type is not AgentType.DESIGN_PLANNING:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type DESIGN_PLANNING"
            )
        context = self.normalize(project, request)
        selected = [code.value for code in request.selected_outputs]
        run = self._standalone.create_run(
            current_user.user_id,
            agent_project_id,
            AgentRunMode.DEFAULT,
            selected,
            context.model_dump(mode="json", exclude_none=True),
        )
        run = self._standalone.mark_run_running(current_user.user_id, agent_project_id, run.run_id)
        try:
            execution = self._engine.execute_with_metadata(context, request.selected_outputs)
            outputs = execution.outputs
            warnings = self._warnings_for(request)
            if execution.correction_attempts:
                warnings.append(AgentRunMessage(
                    code="OUTPUT_CORRECTED",
                    message="Generated output passed validation after a bounded correction attempt",
                    details={
                        "correction_attempts": execution.correction_attempts,
                    },
                ))
            warning_findings = [
                finding.as_dict()
                for finding in execution.validation_findings
                if finding.severity == "WARNING"
            ]
            if warning_findings:
                warnings.append(AgentRunMessage(
                    code="PLANNING_ESTIMATE_WARNINGS",
                    message="Deterministic planning checks produced estimate warnings",
                    details={"findings": warning_findings},
                ))
            run = self._standalone.complete_run(
                current_user.user_id, agent_project_id, run.run_id, outputs, warnings
            )
        except StructuredOutputInvalidError as exc:
            run = self._fail(
                run,
                "STRUCTURED_OUTPUT_INVALID",
                str(exc),
                details={"findings": [finding.as_dict() for finding in exc.findings]},
            )
        except ModelProviderError:
            run = self._fail(
                run,
                "MODEL_EXECUTION_FAILED",
                "The configured model provider could not generate the requested outputs",
            )
        except Exception:
            run = self._fail(run, "INTERNAL_ERROR", "Agent 2 execution failed unexpectedly")
        return self.to_result(run)

    @staticmethod
    def normalize(project: AgentProject, request: Agent2RunRequest) -> Agent2InputContext:
        source_values = [
            ("REQUIREMENTS", request.requirements),
            ("SRS", request.srs),
            ("USER_STORIES", request.user_stories),
            ("ACCEPTANCE_CRITERIA", request.acceptance_criteria),
        ]
        sources = [
            {"source_id": f"SPEC-{index:03d}", "source_type": source_type, "content": content}
            for index, (source_type, content) in enumerate(
                ((kind, value) for kind, value in source_values if value), start=1
            )
        ]
        optional: dict[str, Any] = request.model_dump(
            mode="python",
            exclude={"requirements", "srs", "user_stories", "acceptance_criteria", "selected_outputs"},
            exclude_none=True,
        )
        return Agent2InputContext(
            project_name=project.name.strip(),
            domain=project.domain.strip(),
            specification_sources=sources,
            **optional,
        )

    @staticmethod
    def _warnings_for(request: Agent2RunRequest) -> list[AgentRunMessage]:
        warnings: list[AgentRunMessage] = []
        design_selected = any(code.value in {
            "SYSTEM_ARCHITECTURE", "DATABASE_SCHEMA", "API_SPECIFICATION", "WIREFRAMES", "UI_FLOW"
        } for code in request.selected_outputs)
        if design_selected and not any((
            request.preferred_technology_stack,
            request.deployment_preference,
            request.database_preference,
            request.architecture_notes,
        )):
            warnings.append(AgentRunMessage(
                code="DESIGN_ASSUMPTIONS_USED",
                message="Technical preferences were not supplied; generated design assumptions are explicit in the outputs",
            ))
        if any(code.value in {"TASK_ASSIGNMENT", "JIRA_PLAN"} for code in request.selected_outputs):
            warnings.append(AgentRunMessage(
                code="HEURISTIC_ASSIGNMENT",
                message="Task assignments are heuristic recommendations and are not mathematically optimized",
            ))
        if any(code.value == "JIRA_PLAN" for code in request.selected_outputs):
            warnings.append(AgentRunMessage(
                code="JIRA_NOT_SYNCHRONIZED",
                message="The Jira plan is export-ready structured data; no Jira Cloud synchronization was performed",
            ))
            if request.sprint_duration is None:
                warnings.append(AgentRunMessage(
                    code="SPRINT_DURATION_ASSUMED",
                    message="Jira sprint duration was not supplied; the generated sprint structure contains an explicit planning assumption",
                ))
        return warnings

    def _fail(
        self,
        run: AgentRun,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> AgentRun:
        return self._standalone.fail_run(
            run.owner_user_id,
            run.agent_project_id,
            run.run_id,
            [AgentRunMessage(code=code, message=message, details=details)],
        )

    @staticmethod
    def to_result(run: AgentRun) -> Agent2RunResult:
        return Agent2RunResult(
            run_id=run.run_id,
            agent_project_id=run.agent_project_id,
            agent_type=run.agent_type,
            run_mode=run.run_mode,
            status=run.status,
            selected_outputs=run.selected_outputs,
            started_at=run.started_at,
            completed_at=run.completed_at,
            outputs=run.output_manifest,
            warnings=run.warnings,
            errors=run.errors,
        )
