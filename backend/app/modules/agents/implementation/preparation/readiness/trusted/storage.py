from pathlib import Path
from threading import Lock

from app.modules.agents.implementation.infrastructure.sidecar import (
    load_model_sidecar,
    project_sidecar_path,
    save_model_sidecar,
)

from .schemas import (
    TrustedReadinessContinuationDecision,
    TrustedReadinessSnapshot,
)


class TrustedReadinessStorageError(RuntimeError):
    pass


class TrustedReadinessStorage:
    _lock = Lock()

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def load(self, project_id: str) -> TrustedReadinessSnapshot | None:
        path = self._path(project_id)
        value = load_model_sidecar(
            path,
            TrustedReadinessSnapshot,
            error_type=TrustedReadinessStorageError,
            unavailable_message="Trusted readiness state is unavailable",
        )
        if value is None:
            return None
        if value.agent_project_id != project_id:
            raise TrustedReadinessStorageError(
                "Trusted readiness state identity is invalid"
            )
        return value

    def save(self, value: TrustedReadinessSnapshot) -> None:
        save_model_sidecar(
            self._path(value.agent_project_id),
            value,
            lock=self._lock,
            error_type=TrustedReadinessStorageError,
            failure_message="Trusted readiness state could not be stored",
        )

    def load_continuation(
        self, project_id: str
    ) -> TrustedReadinessContinuationDecision | None:
        path = self._continuation_path(project_id)
        value = load_model_sidecar(
            path,
            TrustedReadinessContinuationDecision,
            error_type=TrustedReadinessStorageError,
            unavailable_message="Trusted readiness continuation is unavailable",
        )
        if value is None:
            return None
        if value.agent_project_id != project_id:
            raise TrustedReadinessStorageError(
                "Trusted readiness continuation identity is invalid"
            )
        return value

    def save_continuation(
        self, value: TrustedReadinessContinuationDecision
    ) -> None:
        save_model_sidecar(
            self._continuation_path(value.agent_project_id),
            value,
            lock=self._lock,
            error_type=TrustedReadinessStorageError,
            failure_message="Trusted readiness continuation could not be stored",
        )

    def _path(self, project_id: str) -> Path:
        return project_sidecar_path(
            self._root,
            project_id,
            "implementation-readiness.json",
            error_type=TrustedReadinessStorageError,
            unsafe_path_message="Unsafe trusted readiness storage path",
        )

    def _continuation_path(self, project_id: str) -> Path:
        return self._path(project_id).with_name(
            "implementation-readiness-continuation.json"
        )
