"""Lazy local Sentence Transformers implementation of the embedding boundary."""

from importlib.metadata import PackageNotFoundError, version
from threading import Lock

from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256
from app.modules.agents.requirements.quality.contracts import EmbeddingModelIdentity
from app.modules.agents.requirements.quality.semantic_duplicates.protocol import (
    RequirementEmbeddingProviderError,
)


DEFAULT_EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSION = 384


class SentenceTransformerEmbeddingProvider:
    def __init__(self, *, model_id: str = DEFAULT_EMBEDDING_MODEL_ID,
                 revision: str | None = None, device: str = "cpu",
                 batch_size: int = 32, local_files_only: bool = False,
                 embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION) -> None:
        if not model_id or not device or batch_size < 1 or embedding_dimension < 1:
            raise ValueError("Embedding provider configuration is invalid")
        self._model_id = model_id
        self._revision = revision
        self._device = device
        self._batch_size = batch_size
        self._local_files_only = local_files_only
        self._embedding_dimension = embedding_dimension
        self._model = None
        self._lock = Lock()

    @property
    def model_identity(self) -> EmbeddingModelIdentity:
        try:
            provider_version = version("sentence-transformers")
        except PackageNotFoundError:
            provider_version = "unavailable"
        values = {
            "provider_type": "SENTENCE_TRANSFORMERS",
            "provider_version": provider_version,
            "model_id": self._model_id,
            "requested_revision": self._revision,
            "resolved_revision": self._revision,
            "device": self._device,
            "normalize_embeddings": True,
            "embedding_dimension": self._embedding_dimension,
            "batch_size": self._batch_size,
            "preprocessing_policy": "EXACT_PERSISTED_STATEMENT",
        }
        return EmbeddingModelIdentity(
            **values, configuration_fingerprint=stable_json_sha256(values)
        )

    def encode(self, statements: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not statements:
            return ()
        model = self._get_model()
        try:
            encoded = model.encode(
                list(statements), batch_size=self._batch_size,
                normalize_embeddings=True, convert_to_numpy=True,
                show_progress_bar=False,
            )
            return tuple(tuple(float(value) for value in row) for row in encoded)
        except Exception as exc:
            raise RequirementEmbeddingProviderError(
                "Requirement embeddings could not be generated"
            ) from exc

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self._model_id, revision=self._revision, device=self._device,
                    local_files_only=self._local_files_only,
                )
            except Exception as exc:
                raise RequirementEmbeddingProviderError(
                    "Requirement embedding model is unavailable"
                ) from exc
        return self._model
