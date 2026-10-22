from pathlib import Path


def extract_text(path: Path) -> str:
    content = path.read_bytes()
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = content.decode("utf-16")
    else:
        text = content.decode("utf-8-sig")
    if not text.strip():
        raise ValueError("No machine-readable text was found in this text document")
    return text
