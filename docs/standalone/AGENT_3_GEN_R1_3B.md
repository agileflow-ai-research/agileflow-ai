# Agent 3 GEN-R1.3B — Local Code-Generation Model Integration

**Status:** Implemented on `feature/agent3-gen-r1.1`  
**Scope:** Internal backend inference foundation; no public API, persistence, or execution

## Model and runtime boundary

GEN-R1.3B adds a disabled-by-default local provider for
`qwen2.5-coder:3b`, corresponding to Qwen2.5-Coder-3B-Instruct, through
Ollama's native HTTP API. The model executes in the separate Ollama process;
FastAPI does not load another PyTorch model. The backend never installs Ollama,
pulls weights, starts a server, substitutes a model tag, or falls back to a
hosted provider.

The provider uses `GET /api/tags` to require the exact installed model and
capture its digest/quantization metadata, `GET /api/version` for runtime
identity, and `POST /api/generate` for inference. Generation uses Ollama's
native JSON-schema `format`, `stream: false`, temperature `0`, bounded
`num_ctx`/`num_predict`, an explicit timeout, and `keep_alive: 0`. Temperature
zero reduces sampling variability but does not guarantee complete
reproducibility.

Only canonical HTTP origins on `127.0.0.1` or `::1` are accepted. Credentials,
hostnames, HTTPS/cloud origins, query strings, fragments, and URL paths are
rejected. HTTP redirects are disabled and rejected. Responses are streamed
through a byte limit, and one provider instance serializes inference with a
lock.

## Configuration

```text
AGENT3_CODE_GEN_PROVIDER=ollama
AGENT3_CODE_GEN_LOCAL_ENABLED=false
AGENT3_OLLAMA_BASE_URL=http://127.0.0.1:11434
AGENT3_OLLAMA_MODEL=qwen2.5-coder:3b
AGENT3_OLLAMA_EXPECTED_MODEL_DIGEST=
AGENT3_OLLAMA_KEEP_ALIVE=0
AGENT3_CODE_GEN_TIMEOUT_SECONDS=180
AGENT3_CODE_GEN_MAX_OUTPUT_TOKENS=2048
AGENT3_CODE_GEN_CONTEXT_TOKENS=8192
AGENT3_CODE_GEN_MAX_RETRIES=1
AGENT3_CODE_GEN_MAX_RESPONSE_BYTES=262144
AGENT3_CODE_GEN_MAX_CONTENT_CHARS=100000
```

Local inference remains off unless `AGENT3_CODE_GEN_LOCAL_ENABLED=true` is
explicitly configured. Setting `AGENT3_OLLAMA_EXPECTED_MODEL_DIGEST` binds an
experiment to the exact digest returned by Ollama; a mismatch fails rather than
silently using changed weights. No probe occurs during backend startup or run
approval.

## Generation context and prompt

`FileGenerationContextBuilder` accepts only a validated
`ApprovedGenerationContext`, its deterministic `GenerationPlan`, one exact
`PlannedFileEntry`, and validated in-memory dependency candidates. It carries:

- the approved effective stack and authorized outputs;
- the server-selected path, responsibility, and content type;
- only the PSI items referenced by that planned file;
- source/traceability identities already present in the approved snapshot; and
- exact validated dependency contents and SHA-256 fingerprints.

A missing, foreign, unsuccessful, or hash-inconsistent dependency produces
`MISSING_DEPENDENCY_CONTEXT`. Mutable project forms are never queried.

Prompt template `agent3-local-file-generation-v1`, under generation policy
`GEN-R1.3B-1`, treats all specification and dependency text as untrusted data.
It forbids invented domain facts, arbitrary dependencies, shell execution,
filesystem operations, and GitHub operations. If all mandatory material cannot
fit in the configured input budget, generation fails with
`CONTEXT_LIMIT_EXCEEDED`; mandatory evidence is never silently removed. Because
the serialized prompt is ASCII, the guard conservatively counts one possible
token per prompt byte and reserves 128 tokens in addition to the configured
output budget rather than relying on an unavailable local tokenizer.

## Structured response and validation

Ollama receives the Pydantic JSON schema for this compact model response:

```json
{
  "content": "generated textual file content",
  "missing_information": [],
  "bounded_assumptions": [],
  "diagnostics": []
}
```

The schema forbids extra fields, so the model cannot supply authoritative paths,
IDs, output codes, requirement references, or approvals. The provider rejects
invalid JSON, schema violations, incomplete finish states, absent models,
timeouts, unreachable servers, redirects, oversized responses, and digest
mismatches with stable safe error codes. Only invalid JSON/schema responses may
receive one response-format correction retry.

Content validation enforces nonempty UTF-8 text, configured character limits,
no NUL/replacement/control characters, server-owned binding, output
authorization, dependency fingerprints, and no unresolved mandatory
information. JSON planned files receive deterministic JSON parsing. Syntax
validation for JavaScript, JSX, SQL, CSS, HTML, YAML, Markdown, environment, and
plain-text outputs is recorded as `UNAVAILABLE` because no approved
non-executing parser currently exists. Structured validation does not establish
that generated code is executable, secure, or requirement-correct.

Successful output is a frozen in-memory `GeneratedContentCandidate` containing
project/run/plan/file identities, the server-owned relative path, authorized
outputs, PSI references, dependency fingerprints, model tag/digest,
quantization, Ollama version, prompt/policy versions, content SHA-256, validation
findings, attempts, duration, and token counts. The approved AgentRun is never
updated.

## Resource and security limits

- One request at a time per provider instance.
- 8192-token context and 2048-token output defaults.
- 180-second timeout and one format-only retry.
- 262144-byte HTTP response and 100000-character content defaults.
- Immediate model unload by default through `keep_alive: 0`.
- No API key, cloud fallback, tools, model download, file writing, code
  execution, GitHub operation, workflow transition, or public endpoint.

## Offline tests

Ordinary tests use a deterministic fake provider and `httpx.MockTransport`.
They require neither Ollama nor model weights and cover evidence selection,
dependencies, stable prompts, injection boundaries, structured parsing,
content limits, retries, endpoint security, disabled inference, Ollama failure
classification, metadata conversion, hashing, traceability, AgentRun
immutability, and the absence of generated files or GitHub calls. These tests
validate integration behavior, not Qwen generation quality.

## Manual smoke test (not run by GEN-R1.3B)

1. Review and accept the Qwen Research License for the intended use.
2. Install Ollama manually and start its local server outside AgileFlow.
3. Pull `qwen2.5-coder:3b` manually; AgileFlow must not perform the pull.
4. Inspect `http://127.0.0.1:11434/api/tags`, record the exact model digest and
   quantization, and set `AGENT3_OLLAMA_EXPECTED_MODEL_DIGEST`.
5. Inspect `http://127.0.0.1:11434/api/version` and record the runtime version.
6. Enable `AGENT3_CODE_GEN_LOCAL_ENABLED=true` only for the controlled session.
7. Invoke the internal service from an approved sanitized QuickBook context and
   one non-blocked plan entry; do not add an API endpoint or writer.
8. Verify schema-valid output, candidate metadata, content hash, duration/token
   counts, and that no project file or AgentRun changed.
9. Disable local inference again after the experiment.

## Licensing and research use

Qwen2.5-Coder-3B-Instruct is published under the **Qwen Research License**. Its
model materials are restricted to non-commercial research/evaluation unless a
separate commercial license is obtained. The weights are not bundled in this
repository. Production, commercial use, redistribution, and output-policy
questions require legal/license review. The authoritative runtime identity for
an experiment is the configured tag plus Ollama digest, quantization, runtime
version, prompt version, policy version, limits, and options.

This milestone enables later comparison of direct local generation,
deterministic-plan grounding, validation, and HITL. It makes no accuracy claim;
that requires controlled benchmarks.

## Future boundary

GEN-R1.4 should add a deliberate human review/acceptance contract and a secure
workspace writer that revalidates paths, containment, symlinks/reparse points,
exclusive creation, quotas, and approved candidate fingerprints immediately
before writing. Execution, builds, correction loops, Git delivery, and Agent 4
orchestration remain later milestones.

**GEN-R1.3B does not produce persisted application files or execute generated programs.**
