"""Manual real-model smoke test for the Agent 3 zero-shot baseline.

This script is intentionally outside pytest so automated tests never download or
load the large model. Run from the backend directory after installing requirements.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Some application modules initialize the Mongo client at import time. This
# inference-only script must never depend on or contact the configured database.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

from app.modules.agents.implementation.extraction.schemas import DocumentType
from app.modules.agents.implementation.semantic_discovery.schemas import (
    ArtifactDetectionLabel,
    ChunkContext,
    ChunkProvenance,
    SemanticChunk,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.classifier import (
    ZeroShotClassifier,
)
from app.modules.agents.implementation.semantic_discovery.zero_shot.constants import (
    MODEL_ID,
    MODEL_REVISION,
)


SAMPLES = (
    "FR-001: The system shall allow users to book an available appointment.",
    "POST /api/bookings returns HTTP 201 and HTTP 409 when the slot is unavailable.",
    "CREATE TABLE bookings (id BIGINT PRIMARY KEY, user_id BIGINT FOREIGN KEY REFERENCES users(id));",
    "Our company was established in 2020.",
)

EXPECTED_LABELS = (
    (ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,),
    (ArtifactDetectionLabel.API_SPECIFICATION, ArtifactDetectionLabel.ACCEPTANCE_CRITERIA),
    (ArtifactDetectionLabel.DATABASE_SCHEMA,),
    (ArtifactDetectionLabel.OTHER_CONTEXT,),
)


def make_chunk(index: int, text: str) -> SemanticChunk:
    digest = hashlib.sha256(text.encode()).hexdigest()
    return SemanticChunk(
        chunk_id=f"CHK-{index:020X}",
        chunk_index=index,
        text=text,
        text_hash=digest,
        token_count=len(text.split()),
        character_count=len(text),
        context=ChunkContext(),
        provenance=ChunkProvenance(
            upload_id="A3UP-0123456789abcdef0123456789abcdef",
            agent_project_id="AGP-003",
            original_filename="manual-zero-shot-smoke.txt",
            source_sha256="a" * 64,
            document_type=DocumentType.TXT,
            line_start=index + 1,
            line_end=index + 1,
        ),
    )


def summarize(outcomes):
    return [
        {
            "chunk_id": outcome.chunk_id,
            "top_labels": [
                {"label": score.label.value, "score": score.score}
                for score in sorted(outcome.scores, key=lambda item: -item.score)[:4]
            ],
            "probe_scores": {
                label.value: next(score.score for score in outcome.scores if score.label is label)
                for label in EXPECTED_LABELS[index]
            },
            "token_count": outcome.model_token_count,
            "truncated": outcome.input_truncated,
            "inference_ms": outcome.inference_ms,
        }
        for index, outcome in enumerate(outcomes)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    chunks = [make_chunk(index, text) for index, text in enumerate(SAMPLES, start=1)]
    classifier = ZeroShotClassifier(local_files_only=args.local_files_only)

    first_started = perf_counter()
    loaded, first = classifier.classify_chunks(chunks)
    first_ms = round((perf_counter() - first_started) * 1000, 3)
    repeat_started = perf_counter()
    _, repeated = classifier.classify_chunks(chunks)
    repeat_ms = round((perf_counter() - repeat_started) * 1000, 3)

    if any(outcome.error or len(outcome.scores) != 13 for outcome in first + repeated):
        raise SystemExit("Smoke test failed: incomplete classifier output")
    print(json.dumps({
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "device": loaded.device,
        "model_max_length": loaded.model_max_length,
        "first_load_and_inference_ms": first_ms,
        "repeated_inference_ms": repeat_ms,
        "first_run": summarize(first),
        "repeated_run": summarize(repeated),
    }, indent=2))


if __name__ == "__main__":
    main()
