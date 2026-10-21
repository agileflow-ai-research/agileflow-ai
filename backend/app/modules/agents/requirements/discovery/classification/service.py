"""Classification validation and deterministic uncertainty policy."""

from app.modules.agents.requirements.discovery.classification.protocol import (
    RequirementClassifier,
    RequirementClassifierError,
)
from app.modules.agents.requirements.discovery.contracts import (
    ClassificationPolicyReason,
    ClassifierModelIdentity,
    RequirementCandidateSet,
    RequirementClassification,
    RequirementClassificationLabel,
    RequirementClassificationSet,
)
from app.modules.agents.requirements.infrastructure.digests import stable_json_sha256


class RequirementClassificationError(RuntimeError):
    pass


class RequirementClassificationService:
    def __init__(
        self,
        classifier: RequirementClassifier,
        *,
        minimum_confidence: float = 0.5,
        minimum_margin: float | None = 0.1,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("Minimum confidence must be between zero and one")
        if minimum_margin is not None and not 0.0 <= minimum_margin <= 1.0:
            raise ValueError("Minimum margin must be between zero and one")
        self._classifier = classifier
        self._minimum_confidence = minimum_confidence
        self._minimum_margin = minimum_margin

    def classify(self, candidates: RequirementCandidateSet) -> RequirementClassificationSet:
        if not candidates.candidates:
            return RequirementClassificationSet(
                candidate_set=candidates,
                model=self._model_identity(),
                classifications=(),
            )
        try:
            predictions = self._classifier.classify(candidates.candidates)
        except RequirementClassifierError as exc:
            raise RequirementClassificationError(
                "Requirement candidates could not be classified"
            ) from exc
        except Exception as exc:
            raise RequirementClassificationError(
                "Requirement classifier returned an invalid result"
            ) from exc
        if len(predictions) != len(candidates.candidates):
            raise RequirementClassificationError(
                "Requirement classifier returned an incomplete result"
            )
        results = []
        for candidate, prediction in zip(candidates.candidates, predictions, strict=True):
            if prediction.candidate_id != candidate.candidate_id:
                raise RequirementClassificationError(
                    "Requirement classifier changed candidate ordering"
                )
            scores = prediction.scores
            if {item.label for item in scores} != set(RequirementClassificationLabel) or len(scores) != 3:
                raise RequirementClassificationError(
                    "Requirement classifier returned an incomplete score vector"
                )
            score_by_label = {item.label: item.score for item in scores}
            winner_score = score_by_label[prediction.winner]
            if winner_score != max(score_by_label.values()):
                raise RequirementClassificationError(
                    "Requirement classifier winner does not match its scores"
                )
            ordered_scores = sorted(score_by_label.values(), reverse=True)
            reason = None
            label = prediction.winner
            if prediction.winner is not RequirementClassificationLabel.OTHER:
                if winner_score < self._minimum_confidence:
                    reason = ClassificationPolicyReason.LOW_CONFIDENCE
                    label = RequirementClassificationLabel.OTHER
                elif self._minimum_margin is not None and ordered_scores[0] - ordered_scores[1] < self._minimum_margin:
                    reason = ClassificationPolicyReason.INSUFFICIENT_MARGIN
                    label = RequirementClassificationLabel.OTHER
            results.append(
                RequirementClassification(
                    candidate_id=candidate.candidate_id,
                    candidate_identity=candidate.candidate_identity,
                    label=label,
                    confidence=winner_score,
                    scores=scores,
                    raw_winner=prediction.winner,
                    policy_reason=reason,
                )
            )
        return RequirementClassificationSet(
            candidate_set=candidates,
            model=self._model_identity(),
            classifications=tuple(results),
        )

    def _model_identity(self) -> ClassifierModelIdentity:
        configuration = self._classifier.configuration
        values = {
            "provider_type": configuration.provider_type,
            "provider_version": configuration.provider_version,
            "model_id": configuration.model_id,
            "requested_revision": configuration.requested_revision,
            "resolved_revision": configuration.resolved_revision,
            "task": configuration.task,
            "label_descriptions": {
                label.value: description
                for label, description in configuration.label_descriptions.items()
            },
            "hypothesis_template": configuration.hypothesis_template,
            "minimum_confidence": self._minimum_confidence,
            "minimum_margin": self._minimum_margin,
            "device": configuration.device,
            "batch_size": configuration.batch_size,
            "local_files_only": configuration.local_files_only,
        }
        return ClassifierModelIdentity(
            **values, configuration_fingerprint=stable_json_sha256(values)
        )
