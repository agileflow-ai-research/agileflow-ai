import hashlib
import json

from app.modules.agents.testing_validation.contracts.sources import (
    TestGenerationInputSourceType,
)
from app.modules.agents.testing_validation.schemas import TestGenerationOutputCode
from app.modules.agents.testing_validation.sources.schemas import (
    TestGenerationSourceRecord,
)
from app.modules.agents.testing_validation.workflow.schemas import (
    canonical_test_generation_outputs,
)


SOURCE_SET_DIGEST_VERSION = "A4-N1-SOURCES-V1"
OUTPUT_SELECTION_DIGEST_VERSION = "A4-N1-OUTPUTS-V1"


def _stable_json_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def source_set_digest(sources: list[TestGenerationSourceRecord]) -> str:
    entries: list[dict[str, object]] = []
    for source in sorted(sources, key=lambda item: item.source_id):
        entry: dict[str, object] = {
            "artifact_type": source.artifact_type.value,
            "collection_status": source.collection_status.value,
            "label": source.label,
            "normally_supplied_by": source.normally_supplied_by.value,
            "source_id": source.source_id,
            "source_type": source.source_type.value,
            "supplied_via": source.supplied_via.value,
        }
        if source.source_type is TestGenerationInputSourceType.TEXT:
            entry["content_sha256"] = hashlib.sha256(
                source.text_content.encode("utf-8")
            ).hexdigest()
        else:
            entry.update(
                {
                    "extension": source.extension,
                    "mime_type": source.mime_type,
                    "original_filename": source.original_filename,
                    "sha256": source.sha256,
                    "size_bytes": source.size_bytes,
                }
            )
        entries.append(entry)
    return _stable_json_sha256(
        {"contract_version": SOURCE_SET_DIGEST_VERSION, "sources": entries}
    )


def output_selection_digest(outputs: list[TestGenerationOutputCode]) -> str:
    canonical = canonical_test_generation_outputs(outputs)
    return _stable_json_sha256(
        {
            "contract_version": OUTPUT_SELECTION_DIGEST_VERSION,
            "selected_outputs": [output.value for output in canonical],
        }
    )
