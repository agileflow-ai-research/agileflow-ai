"""
Internal Agent 4 zero-shot classification capability (N3, DeBERTa, stage Z1).

Modules:
  constants.py   pinned model ID/revision, hypothesis template, batch/truncation policy
  runtime.py     lazy model loader and raw inference caller (MODEL BOUNDARY)
  classifier.py  candidate mapping, score validation, batch isolation
  service.py     N3 gate checks, cache reuse, and manifest creation
  storage.py     atomic persistence of <source_id>.zero-shot.json
Raw scores are evidence only. H1 hybrid decides how they are used.
"""

