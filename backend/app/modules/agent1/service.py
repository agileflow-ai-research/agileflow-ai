from typing import Any

from pydantic import JsonValue

from app.common.status import AgentRunMode, AgentType
from app.modules.agent1.engine import Agent1Engine, StructuredOutputInvalidError
from app.common.model_provider import ModelProviderError
from app.modules.agent1.schemas import (
    Agent1InputContext,
    Agent1RunRequest,
    Agent1RunResult,
)
from app.modules.auth.schemas import UserPublicResponse
from app.modules.standalone.schemas import AgentProject, AgentRun, AgentRunMessage
from app.modules.standalone.service import StandaloneService


class WrongAgentProjectTypeError(ValueError):
    pass


class Agent1Service:
    def __init__(
        self,
        standalone_service: StandaloneService,
        engine: Agent1Engine,
    ) -> None:
        self._standalone = standalone_service
        self._engine = engine

    def run(
        self,
        agent_project_id: str,
        request: Agent1RunRequest,
        current_user: UserPublicResponse,
    ) -> Agent1RunResult:
        project = self._standalone.require_active_project(
            current_user.user_id, agent_project_id
        )
        if project.agent_type is not AgentType.REQUIREMENTS:
            raise WrongAgentProjectTypeError(
                "Agent project must have agent_type REQUIREMENTS"
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
        run = self._standalone.mark_run_running(
            current_user.user_id, agent_project_id, run.run_id
        )
        try:
            outputs = self._engine.execute(context, request.selected_outputs)
            warnings = self._warnings_for(outputs, selected)
            run = self._standalone.complete_run(
                current_user.user_id,
                agent_project_id,
                run.run_id,
                outputs,
                warnings,
            )
        except StructuredOutputInvalidError as exc:
            run = self._fail(run, "STRUCTURED_OUTPUT_INVALID", str(exc))
        except ModelProviderError:
            run = self._fail(
                run,
                "MODEL_EXECUTION_FAILED",
                "The configured model provider could not generate the requested outputs",
            )
        except Exception:
            run = self._fail(
                run,
                "INTERNAL_ERROR",
                "Agent 1 execution failed unexpectedly",
            )
        return self.to_result(run)

    @staticmethod
    def normalize(
        project: AgentProject,
        request: Agent1RunRequest,
    ) -> Agent1InputContext:
        return Agent1InputContext(
            project_name=project.name.strip(),
            domain=project.domain.strip(),
            sources=[
                {
                    "source_id": "TEXT-001",
                    "source_type": "TEXT",
                    "content": request.text.strip(),
                }
            ],
            background_context=request.background_context,
            business_goals=request.business_goals,
            known_constraints=request.known_constraints,
            existing_requirements=request.existing_requirements,
            additional_notes=request.additional_notes,
        )

    def _fail(self, run: AgentRun, code: str, message: str) -> AgentRun:
        return self._standalone.fail_run(
            run.owner_user_id,
            run.agent_project_id,
            run.run_id,
            [AgentRunMessage(code=code, message=message)],
        )

    @staticmethod
    def _warnings_for(
        outputs: dict[str, Any], selected: list[str]
    ) -> list[AgentRunMessage]:
        supplemental = sorted(set(outputs) - set(selected))
        if not supplemental:
            return []
        return [
            AgentRunMessage(
                code="CLARIFICATION_REQUIRED",
                message="Quality issues required supplemental clarification evidence",
                details={"supplemental_outputs": supplemental},
            )
        ]

    @staticmethod
    def to_result(run: AgentRun) -> Agent1RunResult:
        return Agent1RunResult(
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
