import json
from io import BytesIO
from zipfile import BadZipFile

import pytest
from docx import Document

from app.common.document_extraction.extractors import (
    extract_docx,
    extract_structured,
    extract_text,
)
from app.common.document_extraction.schemas import ExtractionStatus


def test_shared_json_parser_is_deterministic_and_rejects_malformed_json(tmp_path):
    valid = tmp_path / "valid.json"
    valid.write_text('{"z":1,"a":{"value":2}}', encoding="utf-8")
    status, content, _, _ = extract_structured(valid, max_characters=1_000)
    assert status is ExtractionStatus.SUCCESS
    assert content.structured_content == {"z": 1, "a": {"value": 2}}
    assert content.normalized_text == json.dumps(
        content.structured_content, ensure_ascii=False, indent=2, sort_keys=True
    )

    malformed = tmp_path / "invalid.json"
    malformed.write_text('{"missing":', encoding="utf-8")
    status, content, _, warnings = extract_structured(
        malformed, max_characters=1_000
    )
    assert status is ExtractionStatus.FAILED
    assert content.structured_content is None
    assert warnings[0].code.value == "INVALID_STRUCTURED_CONTENT"


def test_shared_yaml_uses_safe_loader_and_yml_has_identical_mechanics(tmp_path):
    for extension in ("yaml", "yml"):
        path = tmp_path / f"valid.{extension}"
        path.write_text("z: 1\na:\n  value: 2\n", encoding="utf-8")
        status, content, _, _ = extract_structured(
            path, max_characters=1_000, yaml_document=True
        )
        assert status is ExtractionStatus.SUCCESS
        assert content.structured_content == {"z": 1, "a": {"value": 2}}

    unsafe = tmp_path / "unsafe.yaml"
    unsafe.write_text(
        "!!python/object/apply:builtins.str [unsafe]", encoding="utf-8"
    )
    status, _, _, warnings = extract_structured(
        unsafe, max_characters=1_000, yaml_document=True
    )
    assert status is ExtractionStatus.FAILED
    assert warnings[0].code.value == "INVALID_STRUCTURED_CONTENT"


def test_shared_text_preserves_formatting_and_reports_truncation(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Heading\n\n- first\n- second", encoding="utf-8")
    status, content, _, warnings = extract_text(
        path, max_characters=12, markdown=True
    )
    assert status is ExtractionStatus.PARTIAL
    assert content.markdown == "# Heading\n\n-"[:12]
    assert warnings[0].code.value == "CONTENT_TRUNCATED"


def test_shared_docx_archive_limits_are_enforced(tmp_path):
    document = Document()
    document.add_paragraph("content")
    stream = BytesIO()
    document.save(stream)
    path = tmp_path / "document.docx"
    path.write_bytes(stream.getvalue())
    with pytest.raises(ValueError, match="safety limit"):
        extract_docx(
            path,
            max_characters=1_000,
            max_uncompressed_bytes=1,
            max_archive_entries=10_000,
        )

    malformed = tmp_path / "malformed.docx"
    malformed.write_bytes(b"not-a-zip-archive")
    with pytest.raises(BadZipFile):
        extract_docx(
            malformed,
            max_characters=1_000,
            max_uncompressed_bytes=1_000,
            max_archive_entries=100,
        )
