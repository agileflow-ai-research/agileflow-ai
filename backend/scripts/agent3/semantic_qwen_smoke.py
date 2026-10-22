"""Manual, non-pytest smoke run for the pinned local Qwen semantic adapter."""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

from app.core.config import settings
from app.modules.agents.implementation.preparation.canonical.schemas import (
    ApiSpecificationData, CanonicalArtifact, CanonicalSourceRef,
    CanonicalStatus, DatabaseSchemaData, FunctionalRequirementsData,
    NonFunctionalRequirementsData,
)
from app.modules.agents.implementation.preparation.schemas import (
    ArtifactDetectionLabel,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.adapter import (
    LocalSemanticExtractorAdapter, SemanticModelGenerationError,
    SemanticModelOutputInvalidError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.model_loader import (
    SemanticModelUnavailableError,
)
from app.modules.agents.implementation.preparation.semantic_extraction.local_model.prompt_builder import (
    build_proposal_prefix,
)
from app.modules.agents.implementation.preparation.semantic_extraction.schemas import (
    SemanticExtractionRequest,
)
from app.modules.agents.implementation.preparation.semantic_extraction.service import (
    SemanticExtractionService,
)


UPLOAD_ID = "A3UP-0123456789abcdef0123456789abcdef"
PROJECT_ID = "AGP-003"
MAX_DIAGNOSTIC_SUFFIX_CHARS = 1000


class DiagnosticLocalSemanticExtractorAdapter(LocalSemanticExtractorAdapter):
    """Manual-UAT-only adapter that retains a bounded last raw suffix."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_raw_suffix = None

    def _generate(self, loaded, prompt, artifact_type):
        output, input_tokens, output_tokens, generation_ms = super()._generate(
            loaded, prompt, artifact_type
        )
        prefix = build_proposal_prefix(artifact_type)
        raw_suffix = output[len(prefix):] if output.startswith(prefix) else output
        self.last_raw_suffix = raw_suffix[-MAX_DIAGNOSTIC_SUFFIX_CHARS:]
        return output, input_tokens, output_tokens, generation_ms


EXAMPLES = (
    (
        "functional_requirement",
        ArtifactDetectionLabel.FUNCTIONAL_REQUIREMENTS,
        "Customers can reserve an available appointment time, and the same time must not be assigned to two customers.",
        FunctionalRequirementsData(requirements=[]),
    ),
    (
        "incomplete_api",
        ArtifactDetectionLabel.API_SPECIFICATION,
        "Create a booking using name, email and a selected slot.",
        ApiSpecificationData(endpoints=[]),
    ),
    (
        "database_prose",
        ArtifactDetectionLabel.DATABASE_SCHEMA,
        "The booking stores the customer's email.",
        DatabaseSchemaData(entities=[]),
    ),
    (
        "performance_nfr",
        ArtifactDetectionLabel.NON_FUNCTIONAL_REQUIREMENTS,
        "The response time must remain below 2 seconds.",
        NonFunctionalRequirementsData(requirements=[]),
    ),
)


def make_request(index, label, text, data):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    chunk_id = f"CHK-{index:020X}"
    source = CanonicalSourceRef(
        upload_id=UPLOAD_ID, chunk_id=chunk_id, text_hash=digest,
        original_filename="semantic-smoke.txt", line_start=index, line_end=index,
    )
    artifact = CanonicalArtifact(
        artifact_id=f"CA-{index:024X}", artifact_type=label,
        status=CanonicalStatus.UNRESOLVED, data=data,
        source_refs=[source], unresolved_items=[],
        canonical_schema_version="1", extractor_version="1",
        created_at=datetime.now(timezone.utc),
    )
    return SemanticExtractionRequest(
        project_id=PROJECT_ID, upload_id=UPLOAD_ID,
        chunk_id=chunk_id, chunk_text_hash=digest,
        artifact_type=label, verified_labels=[label],
        source_text=text, deterministic_artifact=artifact,
        unresolved_items=[], target_schema_version="1",
        semantic_contract_version="1",
    )


def main():
    adapter = DiagnosticLocalSemanticExtractorAdapter(
        model_id=settings.agent3_semantic_model_id,
        revision=settings.agent3_semantic_model_revision,
        local_files_only=settings.agent3_semantic_local_files_only,
        device=settings.agent3_semantic_device,
    )
    service = SemanticExtractionService()
    reports = []
    for index, (name, label, text, data) in enumerate(EXAMPLES, start=1):
        started = perf_counter()
        try:
            result = service.run(make_request(index, label, text, data), adapter)
            metadata = adapter.last_generation_metadata
            reports.append({
                "example": name, "json_valid": True,
                "status": result.validation.proposal_status.value,
                "accepted_facts": result.validation.accepted_facts,
                "rejected_facts": result.validation.rejected_facts,
                "conflicts": result.validation.conflict_count,
                "attempts": metadata.attempt_count,
                "input_tokens": metadata.input_token_count,
                "output_tokens": metadata.output_token_count,
                "generation_ms": metadata.generation_ms,
                "elapsed_ms": round((perf_counter() - started) * 1000),
            })
        except SemanticModelOutputInvalidError as exc:
            failure_type = (type(exc.__cause__).__name__
                            if exc.__cause__ is not None
                            else type(exc).__name__)
            diagnostic = {
                "example": name,
                "failure_type": failure_type,
                "raw_generated_suffix": adapter.last_raw_suffix,
            }
            print(json.dumps({"invalid_output_diagnostic": diagnostic},
                             ensure_ascii=False), flush=True)
            metadata = adapter.last_generation_metadata
            reports.append({
                "example": name, "json_valid": False,
                "status": "MODEL_OUTPUT_INVALID",
                "failure_type": failure_type,
                "attempts": metadata.attempt_count,
                "input_tokens": metadata.input_token_count,
                "output_tokens": metadata.output_token_count,
                "generation_ms": metadata.generation_ms,
                "elapsed_ms": round((perf_counter() - started) * 1000),
            })
        except (SemanticModelUnavailableError, SemanticModelGenerationError) as exc:
            reports.append({"example": name, "json_valid": False,
                            "status": type(exc).__name__})
            print(json.dumps({"model_id": settings.agent3_semantic_model_id,
                              "revision": settings.agent3_semantic_model_revision,
                              "results": reports}, indent=2))
            raise SystemExit(1) from exc
    first_load_ms = adapter.last_generation_metadata.first_model_load_ms
    summary = {
        "model_id": settings.agent3_semantic_model_id,
        "revision": settings.agent3_semantic_model_revision,
        "device": adapter.last_generation_metadata.device,
        "first_model_load_ms": first_load_ms,
        "successful_json_rate": sum(item["json_valid"] for item in reports) / len(reports),
        "grounded_fact_count": sum(item.get("accepted_facts", 0) for item in reports),
        "rejected_fact_count": sum(item.get("rejected_facts", 0) for item in reports),
        "conflict_count": sum(item.get("conflicts", 0) for item in reports),
        "results": reports,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
