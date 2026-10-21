import json

import pytest

from app.modules.agents.requirements.discovery.storage import DiscoveryStorage, DiscoveryStorageError
from app.modules.agents.requirements.infrastructure.artifact_paths import RequirementArtifactKind, RequirementArtifactPaths
from app.modules.agents.requirements.infrastructure.artifact_store import JsonArtifactStore


def test_discovery_storage_missing_and_malformed_artifacts(tmp_path):
    storage = DiscoveryStorage(JsonArtifactStore(tmp_path))
    assert storage.load_chunks("AGP-001", "DOC-001") is None
    path = RequirementArtifactPaths(tmp_path).for_source("AGP-001", "DOC-001", RequirementArtifactKind.CHUNK_RESULT)
    path.parent.mkdir(parents=True)
    path.write_text("{malformed", encoding="utf-8")
    with pytest.raises(DiscoveryStorageError, match="artifact is unavailable"):
        storage.load_chunks("AGP-001", "DOC-001")


def test_discovery_storage_rejects_unsafe_identity(tmp_path):
    storage = DiscoveryStorage(JsonArtifactStore(tmp_path))
    with pytest.raises(DiscoveryStorageError):
        storage.load_chunks("../AGP-001", "DOC-001")
