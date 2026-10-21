"""Lazy local Hugging Face sequence-pair NLI conflict provider."""

from importlib.metadata import PackageNotFoundError, version
from threading import Lock

from app.modules.agents.requirements.quality.contracts import (
    NliRelation,
    NliRelationScore,
    NliScoreVector,
)
from app.modules.agents.requirements.quality.conflicts.protocol import (
    RequirementConflictProviderError,
)


DEFAULT_NLI_MODEL_ID = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_NLI_MODEL_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"


class TransformerRequirementConflictProvider:
    def __init__(self, *, model_id: str = DEFAULT_NLI_MODEL_ID,
                 revision: str | None = DEFAULT_NLI_MODEL_REVISION,
                 device: str = "cpu", batch_size: int = 8,
                 local_files_only: bool = False, loader=None) -> None:
        if not model_id.strip() or device not in {"cpu", "cuda"} or not 1 <= batch_size <= 32:
            raise ValueError("Conflict provider configuration is invalid")
        self._model_id = model_id.strip()
        self._revision = revision.strip() if revision else None
        self._device = device
        self._batch_size = batch_size
        self._local_files_only = local_files_only
        self._loader = loader or self._load
        self._tokenizer = None
        self._model = None
        self._label_indices = None
        self._resolved_revision = None
        self._initialization_lock = Lock()
        self._inference_lock = Lock()

    @property
    def configuration(self) -> dict[str, object]:
        try:
            provider_version = version("transformers")
        except PackageNotFoundError:
            provider_version = "unavailable"
        return {
            "provider_type": "HUGGING_FACE_SEQUENCE_PAIR_NLI",
            "provider_version": provider_version,
            "model_id": self._model_id,
            "requested_revision": self._revision,
            # The configured commit is the stable identity authority. Runtime
            # cache metadata must not make identical detections state-dependent.
            "resolved_revision": self._revision,
            "device": self._device,
            "task": "text-pair-natural-language-inference",
            "label_mapping_policy": {
                relation: "RESOLVE_FROM_MODEL_ID2LABEL" for relation in NliRelation
            },
            "batch_size": self._batch_size,
            "preprocessing_policy": "EXACT_PERSISTED_STATEMENT_SEQUENCE_PAIR",
        }

    def evaluate(self, pairs):
        if not pairs:
            return ()
        tokenizer, model, label_indices = self._get_components()
        output = []
        try:
            import torch
            with self._inference_lock, torch.inference_mode():
                for start in range(0, len(pairs), self._batch_size):
                    batch = pairs[start:start + self._batch_size]
                    encoded = tokenizer(
                        [item[0] for item in batch], [item[1] for item in batch],
                        padding=True, truncation=True, return_tensors="pt",
                    )
                    encoded = {key: value.to(self._device) for key, value in encoded.items()}
                    probabilities = torch.softmax(model(**encoded).logits, dim=-1).detach().cpu().tolist()
                    if len(probabilities) != len(batch):
                        raise ValueError("Incomplete NLI output")
                    for row in probabilities:
                        if len(row) != len(label_indices):
                            raise ValueError("Malformed NLI output")
                        output.append(NliScoreVector(scores=tuple(
                            NliRelationScore(relation=relation, score=float(row[index]))
                            for relation, index in label_indices.items()
                        )))
        except RequirementConflictProviderError:
            raise
        except Exception as exc:
            raise RequirementConflictProviderError(
                "Requirement conflict inference failed"
            ) from exc
        return tuple(output)

    def _get_components(self):
        if self._model is not None:
            return self._tokenizer, self._model, self._label_indices
        with self._initialization_lock:
            if self._model is not None:
                return self._tokenizer, self._model, self._label_indices
            try:
                tokenizer, model, resolved = self._loader()
                indices = self._resolve_labels(model.config.id2label)
            except Exception as exc:
                raise RequirementConflictProviderError(
                    "Requirement conflict model is unavailable"
                ) from exc
            self._tokenizer, self._model = tokenizer, model
            self._label_indices, self._resolved_revision = indices, resolved
        return self._tokenizer, self._model, self._label_indices

    def _load(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        if self._device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Configured device is unavailable")
        tokenizer = AutoTokenizer.from_pretrained(
            self._model_id, revision=self._revision,
            local_files_only=self._local_files_only,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self._model_id, revision=self._revision,
            local_files_only=self._local_files_only, use_safetensors=True,
        ).to(self._device)
        model.eval()
        return tokenizer, model, getattr(model.config, "_commit_hash", None)

    @staticmethod
    def _resolve_labels(id2label):
        if not isinstance(id2label, dict) or len(id2label) != 3:
            raise ValueError("NLI label mapping is unavailable")
        resolved = {}
        for raw_index, raw_label in id2label.items():
            label = str(raw_label).strip().upper()
            matches = [relation for relation in NliRelation if relation.value in label]
            if len(matches) != 1:
                raise ValueError("NLI label mapping is ambiguous")
            resolved[matches[0]] = int(raw_index)
        if set(resolved) != set(NliRelation) or len(set(resolved.values())) != 3:
            raise ValueError("NLI label mapping is incomplete")
        return resolved
