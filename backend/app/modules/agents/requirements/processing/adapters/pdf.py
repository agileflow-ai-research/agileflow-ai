from pathlib import Path

import fitz

from app.modules.agents.requirements.processing.adapters.provenance import (
    combine_with_offsets,
)


class NoMachineReadableTextError(ValueError):
    pass


def extract_pdf_text(
    path: Path,
) -> tuple[str, int, list[tuple[int, str, int, int]]]:
    with fitz.open(path) as document:
        pages = [document.load_page(index).get_text("text").strip() for index in range(document.page_count)]
        text, offsets = combine_with_offsets(pages)
        if not text:
            raise NoMachineReadableTextError(
                "No machine-readable text was found in this PDF"
            )
        page_spans = [
            (page_number, page_text, start_offset, end_offset)
            for page_number, (page_text, (start_offset, end_offset)) in enumerate(
                zip(pages, offsets, strict=True), start=1
            )
        ]
        return text, document.page_count, page_spans

