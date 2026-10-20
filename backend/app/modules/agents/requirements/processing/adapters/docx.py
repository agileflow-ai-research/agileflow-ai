from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def extract_docx_text(path: Path) -> tuple[str, int, int]:
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 2_000 or sum(entry.file_size for entry in entries) > 50 * 1024 * 1024:
            raise ValueError("DOCX expanded content exceeds the processing safety limit")
    document = Document(path)
    parts: list[str] = []
    paragraph_count = 0
    table_count = 0
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            text = Paragraph(child, document).text.strip()
            if text:
                parts.append(text)
                paragraph_count += 1
        elif isinstance(child, CT_Tbl):
            table = Table(child, document)
            rendered = "\n".join(
                "\t".join(cell.text.strip() for cell in row.cells)
                for row in table.rows
            ).strip()
            if rendered:
                parts.append(rendered)
                table_count += 1
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("No machine-readable text was found in this DOCX document")
    return text, paragraph_count, table_count

