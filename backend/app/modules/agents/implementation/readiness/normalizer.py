from app.modules.agents.implementation.extraction.schemas import (
    DOCXContent,
    DocumentExtractionResult,
    DocumentType,
    MarkdownContent,
    PDFContent,
    StructuredContent,
    TextContent,
)
from app.modules.agents.implementation.readiness.constants import (
    DESIGN_ARTIFACTS,
    IMPLEMENTATION_ARTIFACTS,
    REQUIREMENTS_ARTIFACTS,
    TEST_ARTIFACTS,
)
from app.modules.agents.implementation.readiness.schemas import (
    ArtifactManifestEntry,
    NormalizedArtifact,
    NormalizedBlockProvenance,
    NormalizedProvenance,
    ReadinessTextInput,
)
from app.modules.agents.implementation.schemas import (
    ImplementationArtifactType,
    ImplementationInputSourceType,
    UploadedFileMetadata,
)


def artifact_group(
    artifact_type: ImplementationArtifactType,
    source_type: ImplementationInputSourceType,
) -> str:
    if source_type is ImplementationInputSourceType.IMAGE:
        return "VISUAL"
    if artifact_type in REQUIREMENTS_ARTIFACTS:
        return "REQUIREMENTS"
    if artifact_type in DESIGN_ARTIFACTS:
        return "DESIGN"
    if artifact_type in IMPLEMENTATION_ARTIFACTS:
        return "IMPLEMENTATION"
    if artifact_type in TEST_ARTIFACTS:
        return "TESTS"
    return "DESIGN"


def normalize_text_input(item: ReadinessTextInput) -> NormalizedArtifact:
    return NormalizedArtifact(
        source_id=item.input_id,
        source_type=ImplementationInputSourceType.TEXT,
        artifact_type=item.artifact_type,
        label=item.label,
        text_content=item.content,
        provenance=NormalizedProvenance(),
    )


def normalize_document(
    metadata: UploadedFileMetadata,
    extraction: DocumentExtractionResult,
) -> NormalizedArtifact:
    content = extraction.content
    structured_content = None
    page_numbers: list[int] = []
    blocks: list[NormalizedBlockProvenance] = []
    if isinstance(content, PDFContent):
        text = content.combined_text
        page_numbers = [page.page_number for page in content.pages]
    elif isinstance(content, DOCXContent):
        text = content.combined_text
        blocks = [
            NormalizedBlockProvenance(
                block_index=block.block_index,
                block_type=block.type.value,
                heading_level=block.level,
            )
            for block in content.blocks
        ]
    elif isinstance(content, TextContent):
        text = content.text
    elif isinstance(content, MarkdownContent):
        text = content.markdown
    elif isinstance(content, StructuredContent):
        text = content.normalized_text
        structured_content = content.structured_content
    else:  # pragma: no cover - guarded by the strict extraction schema
        raise ValueError("Unsupported extraction content")
    return NormalizedArtifact(
        source_id=metadata.upload_id,
        source_type=ImplementationInputSourceType.DOCUMENT,
        artifact_type=metadata.artifact_type,
        label=metadata.label,
        text_content=text,
        structured_content=structured_content,
        extraction_status=extraction.status,
        extraction_version=extraction.extractor_version,
        provenance=NormalizedProvenance(
            upload_id=metadata.upload_id,
            original_filename=metadata.original_filename,
            source_sha256=metadata.sha256,
            document_type=extraction.document_type,
            page_numbers=page_numbers,
            blocks=blocks,
        ),
    )


def manifest_entry(
    metadata: UploadedFileMetadata,
    availability: str,
) -> ArtifactManifestEntry:
    return ArtifactManifestEntry(
        group=artifact_group(metadata.artifact_type, metadata.source_type),
        source_id=metadata.upload_id,
        source_type=metadata.source_type,
        artifact_type=metadata.artifact_type,
        label=metadata.label,
        availability=availability,
    )


def text_manifest_entry(item: ReadinessTextInput) -> ArtifactManifestEntry:
    return ArtifactManifestEntry(
        group=artifact_group(
            item.artifact_type, ImplementationInputSourceType.TEXT
        ),
        source_id=item.input_id,
        source_type=ImplementationInputSourceType.TEXT,
        artifact_type=item.artifact_type,
        label=item.label,
        availability="AVAILABLE",
    )
