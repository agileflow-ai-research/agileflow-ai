import json
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from app.common.id_generator import validate_id
from app.modules.agents.testing_validation.workflow.constants import (
    AGENT4_TEST_GENERATION_WORKFLOW_FILENAME,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    Agent4N3SubStageStatus,
    Agent4TestGenerationWorkflowRecord,
)


AGENT4_WORKFLOW_STATE_LOCK = RLock()


class Agent4WorkflowStorageError(RuntimeError):
    pass


class Agent4WorkflowStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def load(
        self, *, agent_project_id: str, owner_user_id: str
    ) -> Agent4TestGenerationWorkflowRecord | None:
        path = self._workflow_path(agent_project_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._add_fact_extraction_node(payload)
            self._add_human_approval_node(payload)
            record = Agent4TestGenerationWorkflowRecord.model_validate(payload)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise Agent4WorkflowStorageError(
                "Agent 4 workflow could not be loaded"
            ) from exc
        if (
            record.agent_project_id != agent_project_id
            or record.owner_user_id != owner_user_id
        ):
            raise Agent4WorkflowStorageError(
                "Agent 4 workflow identity does not match"
            )
        return record

    @staticmethod
    def _add_fact_extraction_node(payload: dict) -> None:
        """Upgrade persisted six-node workflows without discarding N3 progress."""
        nodes = payload.get("nodes") or []
        if any(item.get("node_id") == "TESTING_FACT_EXTRACTION" for item in nodes):
            return
        intelligence_index = next((
            index for index, item in enumerate(nodes)
            if item.get("node_id") == "TESTING_INTELLIGENCE"
        ), None)
        if intelligence_index is None:
            return
        now = payload.get("updated_at") or nodes[intelligence_index].get("updated_at")
        fact_status = "LOCKED"
        executions = payload.get("n3_executions") or []
        current_id = payload.get("current_n3_execution_id")
        execution = next((
            item for item in reversed(executions)
            if item.get("execution_id") == current_id
        ), None)
        fact_stage = next((
            stage
            for stage in (execution or {}).get("sub_stages", [])
            if stage.get("stage") == "TI_FACT_EXTRACTION"
        ), None)
        if fact_stage is None:
            source_fact_stages = [
                stage
                for source in (execution or {}).get("sources", [])
                for stage in source.get("sub_stages", [])
                if stage.get("stage") == "TI_FACT_EXTRACTION"
            ]
            fact_stage = next((
                stage for stage in source_fact_stages
                if stage.get("status") in {
                    "FAILED", "INTERRUPTED", "RUNNING", "QUEUED",
                }
            ), None)
        if fact_stage is None and any(
            source.get("status") == "SEMANTIC_EXTRACTION"
            for source in (execution or {}).get("sources", [])
        ):
            fact_stage = {"status": "RUNNING"}
        if execution and execution.get("status") == "COMPLETED":
            fact_status = "COMPLETED"
        elif fact_stage and fact_stage.get("status") in {
            Agent4N3SubStageStatus.QUEUED.value,
            Agent4N3SubStageStatus.RUNNING.value,
            Agent4N3SubStageStatus.FAILED.value,
            Agent4N3SubStageStatus.INTERRUPTED.value,
        }:
            fact_status = {
                "INTERRUPTED": "FAILED",
            }.get(fact_stage["status"], fact_stage["status"])
            nodes[intelligence_index]["status"] = "COMPLETED"
            payload["current_node_id"] = "TESTING_FACT_EXTRACTION"
        human_index = next((
            index for index, item in enumerate(nodes)
            if item.get("node_id") == "HUMAN_APPROVAL"
        ), None)
        insert_index = (
            human_index + 1 if human_index is not None else intelligence_index + 1
        )
        nodes.insert(insert_index, {
            "node_id": "TESTING_FACT_EXTRACTION",
            "status": fact_status,
            "updated_at": now,
        })

    @staticmethod
    def _add_human_approval_node(payload: dict) -> None:
        """Upgrade persisted workflows by promoting N3 review to a main node."""
        nodes = payload.get("nodes") or []
        if any(item.get("node_id") == "HUMAN_APPROVAL" for item in nodes):
            return
        intelligence_index = next((
            index for index, item in enumerate(nodes)
            if item.get("node_id") == "TESTING_INTELLIGENCE"
        ), None)
        if intelligence_index is None:
            return
        now = payload.get("updated_at") or nodes[intelligence_index].get("updated_at")
        approval_status = "LOCKED"
        executions = payload.get("n3_executions") or []
        current_id = payload.get("current_n3_execution_id")
        execution = next((
            item for item in reversed(executions)
            if item.get("execution_id") == current_id
        ), None)
        human_stage = next((
            stage for stage in (execution or {}).get("sub_stages", [])
            if stage.get("stage") == "TI_HUMAN_REVIEW"
        ), None)
        if human_stage is None:
            human_stages = [
                stage
                for source in (execution or {}).get("sources", [])
                for stage in source.get("sub_stages", [])
                if stage.get("stage") == "TI_HUMAN_REVIEW"
            ]
            human_stage = next((
                stage for stage in human_stages
                if stage.get("status") == "WAITING_FOR_HUMAN"
            ), human_stages[0] if human_stages else None)
        current_node = payload.get("current_node_id")
        if execution and execution.get("status") == "WAITING_FOR_HUMAN":
            approval_status = "WAITING_FOR_HUMAN"
            nodes[intelligence_index]["status"] = "COMPLETED"
            payload["current_node_id"] = "HUMAN_APPROVAL"
        elif (
            execution and execution.get("status") == "COMPLETED"
        ) or current_node in {
            "TESTING_FACT_EXTRACTION", "CONTEXT_TESTABILITY",
            "TEST_PLANNING_REVIEW", "TEST_GENERATION_RESULTS",
        } or (human_stage and human_stage.get("status") in {
            "COMPLETED", "NOT_APPLICABLE",
        }):
            approval_status = "COMPLETED"
        nodes.insert(intelligence_index + 1, {
            "node_id": "HUMAN_APPROVAL",
            "status": approval_status,
            "updated_at": now,
        })

    def save(self, record: Agent4TestGenerationWorkflowRecord) -> None:
        path = self._workflow_path(record.agent_project_id)
        partial_path = path.with_suffix(path.suffix + ".part")
        with AGENT4_WORKFLOW_STATE_LOCK:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                partial_path.write_text(record.model_dump_json(), encoding="utf-8")
                partial_path.replace(path)
            except OSError as exc:
                try:
                    partial_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise Agent4WorkflowStorageError(
                    "Agent 4 workflow could not be persisted"
                ) from exc

    def _workflow_path(self, agent_project_id: str) -> Path:
        try:
            validate_id(agent_project_id, "AGP")
        except ValueError as exc:
            raise Agent4WorkflowStorageError("Unsafe Agent 4 workflow path") from exc
        project_directory = (self._root / agent_project_id).resolve()
        try:
            project_directory.relative_to(self._root)
        except ValueError as exc:  # pragma: no cover - ID validation is primary
            raise Agent4WorkflowStorageError("Unsafe Agent 4 workflow path") from exc
        return project_directory / AGENT4_TEST_GENERATION_WORKFLOW_FILENAME
