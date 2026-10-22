from pathlib import Path
from threading import Lock

import pytest
from pydantic import BaseModel

from app.modules.agents.implementation.infrastructure.digests import (
    stable_json_sha256,
)
from app.modules.agents.implementation.infrastructure.sidecar import (
    load_model_sidecar,
    project_sidecar_path,
    save_model_sidecar,
)


class ExampleSidecar(BaseModel):
    project_id: str
    value: int


class ExampleStorageError(RuntimeError):
    pass


def test_sidecar_round_trip_is_atomic_and_missing_is_distinct(tmp_path: Path):
    path = project_sidecar_path(
        tmp_path,
        "AGP-001",
        "example.json",
        error_type=ExampleStorageError,
        unsafe_path_message="unsafe",
    )
    assert load_model_sidecar(
        path,
        ExampleSidecar,
        error_type=ExampleStorageError,
        unavailable_message="unavailable",
    ) is None

    expected = ExampleSidecar(project_id="AGP-001", value=7)
    save_model_sidecar(
        path,
        expected,
        lock=Lock(),
        error_type=ExampleStorageError,
        failure_message="failed",
    )

    assert load_model_sidecar(
        path,
        ExampleSidecar,
        error_type=ExampleStorageError,
        unavailable_message="unavailable",
    ) == expected
    assert not path.with_suffix(".json.part").exists()


def test_sidecar_rejects_escape_and_malformed_content(tmp_path: Path):
    with pytest.raises(ExampleStorageError, match="unsafe"):
        project_sidecar_path(
            tmp_path,
            "../outside",
            "example.json",
            error_type=ExampleStorageError,
            unsafe_path_message="unsafe",
        )

    path = tmp_path / "malformed.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ExampleStorageError, match="unavailable"):
        load_model_sidecar(
            path,
            ExampleSidecar,
            error_type=ExampleStorageError,
            unavailable_message="unavailable",
        )


def test_stable_json_digest_ignores_mapping_order():
    assert stable_json_sha256({"b": 2, "a": 1}) == stable_json_sha256(
        {"a": 1, "b": 2}
    )
