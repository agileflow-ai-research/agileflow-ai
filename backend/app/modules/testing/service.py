from typing import Any

from app.common.model_provider import ModelProviderError
from app.common.status import AgentRunMode, AgentType
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject, AgentRun, AgentRunMessage
from app.modules.standalone.service import StandaloneService
from app.modules.testing.engine import Agent4Engine, StructuredOutputInvalidError, ToolExecutionError
from app.modules.testing.schemas import Agent4InputContext, Agent4RunRequest, Agent4RunResult


class WrongAgentProjectTypeError(ValueError):
    pass


class Agent4Service:
    def __init__(self, standalone_service: StandaloneService, engine: Agent4Engine) -> None:
        self._standalone = standalone_service
        self._engine = engine

    def run(
        self,
        agent_project_id: str,
        request: Agent4RunRequest,
        current_user: UserPublicResponse,
    ) -> Agent4RunResult:
        project = self._standalone.require_active_project(current_user.user_id, agent_project_id)
        if project.agent_type is not AgentType.TESTING_VALIDATION:
            raise WrongAgentProjectTypeError("Agent project must have agent_type TESTING_VALIDATION")

        context = self.normalize(project, request)
        run = self._standalone.create_run(
            current_user.user_id,
            agent_project_id,
            request.run_mode,
            list(request.selected_outputs),
            context.model_dump(mode="json", exclude_none=True),
        )
        run = self._standalone.mark_run_running(current_user.user_id, agent_project_id, run.run_id)
        try:
            outputs = self._engine.execute(context, request.selected_outputs)
            warnings = self._warnings_for(request, outputs)
            run = self._standalone.complete_run(
                current_user.user_id, agent_project_id, run.run_id, outputs, warnings
            )
        except StructuredOutputInvalidError as exc:
            run = self._fail(run, "STRUCTURED_OUTPUT_INVALID", str(exc))
        except ToolExecutionError as exc:
            run = self._fail(run, "TOOL_EXECUTION_FAILED", str(exc))
        except ModelProviderError:
            run = self._fail(
                run, "MODEL_EXECUTION_FAILED",
                "The configured model provider could not generate the requested test outputs",
            )
        except Exception:
            run = self._fail(run, "INTERNAL_ERROR", "Agent 4 execution failed unexpectedly")
        return self.to_result(run)

    @staticmethod
    def normalize(project: AgentProject, request: Agent4RunRequest) -> Agent4InputContext:
        dumped = request.model_dump(
            mode="python", by_alias=False,
            exclude={"run_mode", "selected_outputs"}, exclude_none=True,
        )
        if request.run_mode is AgentRunMode.TEST_GENERATION:
            source_values = [
                ("REQUIREMENT", request.requirements),
                ("USER_STORY", request.user_stories),
                ("ACCEPTANCE_CRITERION", request.acceptance_criteria),
                ("SRS", request.srs),
            ]
            dumped["sources"] = [
                {"source_id": f"SRC-{index:03d}", "source_type": kind, "content": content}
                for index, (kind, content) in enumerate(
                    ((kind, value) for kind, value in source_values if value), start=1
                )
            ]
            for key in ("requirements", "user_stories", "acceptance_criteria", "srs"):
                dumped.pop(key, None)
        return Agent4InputContext(
            project_name=project.name.strip(), domain=project.domain.strip(),
            run_mode=request.run_mode, inputs=dumped,
        )

    @staticmethod
    def _warnings_for(request: Agent4RunRequest, outputs: dict[str, Any]) -> list[AgentRunMessage]:
        warnings: list[AgentRunMessage] = []
        if request.run_mode is AgentRunMode.TEST_GENERATION and not (
            request.existing_source_code and request.technology_stack
        ):
            warnings.append(AgentRunMessage(
                code="SPECIFICATION_ONLY",
                message="Source code and technology stack were not both supplied; generated tests are specifications and were not executed",
            ))
        coverage = outputs.get("COVERAGE_REPORT")
        if coverage and coverage.get("status") != "MEASURED":
            warnings.append(AgentRunMessage(
                code="COVERAGE_NOT_MEASURED", message=coverage["reason"]
            ))
        test_report = outputs.get("TEST_EXECUTION_REPORT")
        if test_report and test_report.get("status") == "SKIPPED":
            warnings.append(AgentRunMessage(
                code="TEST_EXECUTION_SKIPPED",
                message="No test/run command was supplied, so no tests were executed",
            ))
        security = outputs.get("SECURITY_FINDINGS")
        if security and security.get("executed"):
            warnings.append(AgentRunMessage(
                code="SECURITY_SCANNER_SCOPE",
                message="Security evidence is limited to the reported built-in static scanner scope; no external scanner was claimed",
            ))
        return warnings

    def _fail(self, run: AgentRun, code: str, message: str) -> AgentRun:
        return self._standalone.fail_run(
            run.owner_user_id, run.agent_project_id, run.run_id,
            [AgentRunMessage(code=code, message=message)],
        )

    @staticmethod
    def to_result(run: AgentRun) -> Agent4RunResult:
        return Agent4RunResult(
            run_id=run.run_id, agent_project_id=run.agent_project_id,
            agent_type=run.agent_type, run_mode=run.run_mode, status=run.status,
            selected_outputs=run.selected_outputs, started_at=run.started_at,
            completed_at=run.completed_at, outputs=run.output_manifest,
            warnings=run.warnings, errors=run.errors,
        )
