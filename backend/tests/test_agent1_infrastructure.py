from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict

from app.modules.agents.requirements.contracts.schemas import RequirementSourceType
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.infrastructure.sidecar import (
    load_model_sidecar,
    remove_sidecar,
    save_model_sidecar,
)
from app.modules.agents.requirements.workflow.orchestration import (
    n2_chunk_set_digest,
    n2_execution_key,
)
from app.modules.agents.requirements.workflow.schemas import (
    RequirementN1Confirmation,
    RequirementN2Execution,
    RequirementN2ResultSummary,
    RequirementN2SourceProgress,
    RequirementN2SourceSnapshot,
    RequirementN2SourceStatus,
    RequirementN2Status,
    RequirementOutputCode,
    RequirementWorkflowRecord,
)
from app.modules.agents.requirements.workflow.service import (
    selection_digest,
    source_set_digest,
)
from app.modules.agents.requirements.workflow.storage import RequirementWorkflowStorage


class SidecarFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int


class SidecarFixtureError(RuntimeError):
    pass


LOCK = RLock()


def test_legacy_service_reexports_neutral_project_type_error():
    from app.modules.agents.requirements.contracts.errors import (
        WrongAgentProjectTypeError,
    )
    from app.modules.agents.requirements.service import (
        WrongAgentProjectTypeError as LegacyImport,
    )

    assert LegacyImport is WrongAgentProjectTypeError


def test_stable_digest_preserves_output_selection_hash():
    payload = {
        "contract_version": "requirements-output-selection-v1",
        "selected_outputs": ["FUNCTIONAL_REQUIREMENTS", "SRS"],
    }
    expected = "f09f97672544c1869fb91937323c393fd2754a0fec83c01467afc12b58fd7e4e"

    assert stable_json_sha256(payload) == expected
    assert selection_digest(
        [RequirementOutputCode.SRS, RequirementOutputCode.FUNCTIONAL_REQUIREMENTS]
    ) == expected


def test_stable_digest_preserves_source_set_hash():
    sources = [
        SimpleNamespace(
            source_id="DOC-002",
            source_type=RequirementSourceType.DOCUMENT,
            sha256="a" * 64,
        ),
        SimpleNamespace(
            source_id="AUD-001",
            source_type=RequirementSourceType.AUDIO,
            sha256="b" * 64,
        ),
    ]
    payload = {
        "contract_version": "requirements-source-set-v1",
        "sources": [
            {
                "source_id": "AUD-001",
                "source_type": "AUDIO",
                "sha256": "b" * 64,
            },
            {
                "source_id": "DOC-002",
                "source_type": "DOCUMENT",
                "sha256": "a" * 64,
            },
        ],
    }
    expected = "d49dd30ba844aee1e18e3036b1669d8b9443a7ef3682edf2c6aeeb5c7887034f"

    assert stable_json_sha256(payload) == expected
    assert source_set_digest(sources) == expected


def test_stable_digest_preserves_n2_execution_identity_hash():
    payload = {
        "agent_project_id": "AGP-020",
        "contract_version": "requirements-n2-orchestration-v1",
        "node_id": "PROCESSING_AND_CHUNKING",
        "node_version": "1",
        "source_set_digest": "a" * 64,
        "selection_digest": "b" * 64,
    }
    expected = "145b2d2a493922b50143ed867cbbd7ec00836bd42b2f5b61d4434fd3364cfe2c"

    assert stable_json_sha256(payload) == expected
    assert n2_execution_key("AGP-020", "a" * 64, "b" * 64) == expected


def test_stable_digest_preserves_n2_chunk_set_hash():
    chunks = [
        {
            "source_id": "DOC-002",
            "chunk_count": 2,
            "chunk_set_digest": "d" * 64,
        },
        {
            "source_id": "AUD-001",
            "chunk_count": 7,
            "chunk_set_digest": "c" * 64,
        },
    ]
    payload = {
        "contract_version": "requirements-n2-chunk-set-v1",
        "node_version": "1",
        "source_set_digest": "a" * 64,
        "sources": list(reversed(chunks)),
    }
    expected = "321f1959cc83c331b0c26802fc43dad5c454a428fd4f588f2446ea1c43820bdf"

    assert stable_json_sha256(payload) == expected
    assert n2_chunk_set_digest("a" * 64, chunks) == expected


def test_typed_sidecar_round_trip_is_atomic(tmp_path):
    path = tmp_path / "state.json"
    value = SidecarFixture(name="ready", count=2)

    save_model_sidecar(
        path,
        value,
        lock=LOCK,
        error_type=SidecarFixtureError,
        failure_message="Could not save sidecar",
    )

    assert path.read_text(encoding="utf-8") == value.model_dump_json()
    assert not (tmp_path / "state.json.part").exists()
    assert load_model_sidecar(
        path,
        SidecarFixture,
        error_type=SidecarFixtureError,
        unavailable_message="Could not load sidecar",
    ) == value


def test_typed_sidecar_missing_and_orphan_part_are_not_loaded(tmp_path):
    path = tmp_path / "state.json"
    partial_path = tmp_path / "state.json.part"
    partial_path.write_text('{"name":"partial","count":1}', encoding="utf-8")

    assert load_model_sidecar(
        path,
        SidecarFixture,
        error_type=SidecarFixtureError,
        unavailable_message="Could not load sidecar",
    ) is None
    assert partial_path.exists()


@pytest.mark.parametrize(
    "payload",
    ["not-json", '{"name":"missing-count"}'],
)
def test_typed_sidecar_wraps_malformed_and_schema_invalid_json(tmp_path, payload):
    path = tmp_path / "state.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(SidecarFixtureError, match="Could not load sidecar"):
        load_model_sidecar(
            path,
            SidecarFixture,
            error_type=SidecarFixtureError,
            unavailable_message="Could not load sidecar",
        )


def test_typed_sidecar_cleans_partial_after_atomic_save_failure(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    original_replace = Path.replace

    def fail_replace(self, target):
        if self.name == "state.json.part":
            raise OSError("filesystem detail")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(SidecarFixtureError, match="Could not save sidecar"):
        save_model_sidecar(
            path,
            SidecarFixture(name="ready", count=2),
            lock=LOCK,
            error_type=SidecarFixtureError,
            failure_message="Could not save sidecar",
        )
    assert not (tmp_path / "state.json.part").exists()


def test_typed_sidecar_removal_removes_final_and_partial(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")
    (tmp_path / "state.json.part").write_text("{}", encoding="utf-8")

    remove_sidecar(
        path,
        lock=LOCK,
        error_type=SidecarFixtureError,
        failure_message="Could not remove sidecar",
    )

    assert not path.exists()
    assert not (tmp_path / "state.json.part").exists()


def test_existing_workflow_and_n2_execution_sidecar_reload(tmp_path):
    now = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
    execution_id = "N2-ABCDEF0123456789-001"
    execution = RequirementN2Execution(
        node_version="1",
        execution_id=execution_id,
        attempt_id="ATT-001",
        execution_key="c" * 64,
        attempt_number=1,
        status=RequirementN2Status.COMPLETE,
        confirmed_source_set_digest="a" * 64,
        confirmed_selection_digest="b" * 64,
        input_sources=[
            RequirementN2SourceSnapshot(
                source_id="AUD-001",
                source_type=RequirementSourceType.AUDIO,
                sha256="d" * 64,
            )
        ],
        source_progress=[
            RequirementN2SourceProgress(
                source_id="AUD-001",
                processing_status=RequirementN2SourceStatus.COMPLETE,
                preparation_status=RequirementN2SourceStatus.COMPLETE,
                chunk_count=7,
            )
        ],
        created_at=now,
        started_at=now,
        completed_at=now,
        result_summary=RequirementN2ResultSummary(
            source_count=1,
            completed_source_count=1,
            chunk_count=7,
        ),
        chunk_set_digest="e" * 64,
    )
    record = RequirementWorkflowRecord(
        schema_version="2",
        workflow_version="W2",
        agent_project_id="AGP-020",
        owner_user_id="USR-001",
        selected_outputs=[RequirementOutputCode.SRS],
        selection_revision=1,
        selection_digest="b" * 64,
        source_set_digest="a" * 64,
        n1_confirmation=RequirementN1Confirmation(
            source_set_digest="a" * 64,
            selection_digest="b" * 64,
            confirmed_at=now,
        ),
        n2_executions=[execution],
        current_n2_execution_id=execution_id,
        created_at=now,
        updated_at=now,
    )
    workflow_path = tmp_path / "AGP-020" / "workflow.json"
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text(record.model_dump_json(), encoding="utf-8")

    loaded = RequirementWorkflowStorage(tmp_path).load(
        agent_project_id="AGP-020", owner_user_id="USR-001"
    )

    assert loaded == record
    assert loaded is not None
    assert loaded.n2_executions == [execution]
