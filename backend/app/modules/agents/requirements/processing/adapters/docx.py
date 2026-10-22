from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.modules.agents.requirements.processing.adapters.provenance import (
    combine_with_offsets,
)


def extract_docx_text(
    path: Path,
) -> tuple[str, int, int, list[tuple[int, str, str, int, int]]]:
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 2_000 or sum(entry.file_size for entry in entries) > 50 * 1024 * 1024:
            raise ValueError("DOCX expanded content exceeds the processing safety limit")
    document = Document(path)
    parts: list[tuple[str, str]] = []
    paragraph_count = 0
    table_count = 0
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            text = Paragraph(child, document).text.strip()
            if text:
                parts.append(("PARAGRAPH", text))
                paragraph_count += 1
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rendered = "\n".join(
                "\t".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
            ).strip()
            if rendered:
                parts.append(("TABLE", rendered))
                table_count += 1
    text, offsets = combine_with_offsets([part_text for _, part_text in parts])
    if not text:
        raise ValueError("No machine-readable text was found in this DOCX document")
    block_spans = [
        (block_index, block_type, block_text, start_offset, end_offset)
        for block_index, (
            (block_type, block_text),
            (start_offset, end_offset),
        ) in enumerate(zip(parts, offsets, strict=True))
    ]
    return text, paragraph_count, table_count, block_spans

