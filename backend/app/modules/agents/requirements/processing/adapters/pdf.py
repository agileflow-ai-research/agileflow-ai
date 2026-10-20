from pathlib import Path

import fitz


class NoMachineReadableTextError(ValueError):
    pass


def extract_pdf_text(path: Path) -> tuple[str, int]:
    with fitz.open(path) as document:
        pages = [document.load_page(index).get_text("text").strip() for index in range(document.page_count)]
        text = "\n\n".join(page for page in pages if page).strip()
        if not text:
            raise NoMachineReadableTextError(
                "No machine-readable text was found in this PDF"
            )
        return text, document.page_count

