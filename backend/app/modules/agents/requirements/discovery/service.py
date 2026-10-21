"""Authenticated read boundary for persisted N3 artifacts."""

from app.modules.agents.requirements.discovery.contracts import (
    DiscoveryExecutionArtifacts,
)
from app.modules.agents.requirements.discovery.storage import DiscoveryStorage
from app.modules.agents.requirements.inputs.upload.service import require_requirements_project
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


class DiscoveryResultError(ValueError):
    pass


class DiscoveryResultService:
    def __init__(self, standalone_service, workflow_storage, discovery_storage) -> None:
        self._standalone = standalone_service
        self._workflows: RequirementWorkflowStorage = workflow_storage
        self._artifacts: DiscoveryStorage = discovery_storage

    def get(self, agent_project_id, execution_id, current_user):
        project = require_requirements_project(
            self._standalone, agent_project_id, current_user
        )
        record = self._workflows.load(
            agent_project_id=project.agent_project_id,
            owner_user_id=current_user.user_id,
        )
        execution = next(
            (item for item in record.n3_executions if item.execution_id == execution_id),
            None,
        ) if record is not None else None
        if execution is None:
            raise DiscoveryResultError("N3 execution is unavailable")
        candidates = self._artifacts.load_candidates(agent_project_id, execution_id)
        classifications = self._artifacts.load_classifications(
            agent_project_id, execution_id
        )
        structured = self._artifacts.load_structured_requirements(
            agent_project_id, execution_id
        )
        if (
            candidates.agent_project_id != agent_project_id
            or candidates.n2_execution_id != execution.n2_execution_id
            or classifications.candidate_set != candidates
            or structured.agent_project_id != agent_project_id
            or structured.discovery_input_identity != execution.discovery_input_identity
            or structured.chunk_set_digest != execution.chunk_set_digest
        ):
            raise DiscoveryResultError("N3 artifacts do not match the requested execution")
        return DiscoveryExecutionArtifacts(
            execution_id=execution_id,
            candidates=candidates,
            classifications=classifications,
            structured=structured,
        )
