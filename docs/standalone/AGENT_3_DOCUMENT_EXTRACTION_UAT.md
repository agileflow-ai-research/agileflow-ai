# Agent 3 Document Extraction UAT

Step 2A.1 performs deterministic document extraction only. It does not run OCR,
image understanding, readiness validation, or code generation.

Generate disposable manual-test documents outside the repository:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\agent3\extraction_uat_samples.py `
  --output-dir "$env:TEMP\agileflow-agent3-extraction-uat"
```

The generator creates a two-page text PDF, a DOCX with a heading/paragraph/table,
TXT, Markdown, JSON, YAML, and a PDF containing only a raster image. Upload each
file as a `DOCUMENT`; the raster-only PDF is expected to return `FAILED` with no
extractable text because OCR is intentionally out of scope.

For successful or partial extractions, open **Review Extracted Content** and
confirm the source structure and warnings are shown as text—not rendered HTML.
Remove each input afterward to verify its upload metadata and extraction sidecar
are deleted together.
