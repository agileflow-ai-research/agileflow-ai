# Agent 3 GEN-R1.1 — Approved AgentRun Input Loader

**Status:** Implemented on `feature/agent3-gen-r1.1`  
**Scope:** Internal backend foundation; no public API addition

## Implemented boundary

GEN-R1.1 adds `app/modules/agents/implementation/generation/` as the internal
boundary between final Agent 3 approval and later generation milestones. Its
loader accepts an authenticated user, project ID, and run ID; delegates owner
and project/run isolation to the shared `StandaloneService`; and returns a
detached, frozen `ApprovedGenerationContext`.

The loader reads only the immutable `AgentRun.input_snapshot`. It never queries
the live project specification, readiness sidecars, project forms, output
selection, or GitHub setup to reconstruct historical approval. There is no
additional freshness check against mutable project state: freshness was
validated when the run was approved, and the approved run remains the audit
record even if live state later changes.

## Validation and failure handling

Loading requires:

- an owner-accessible Agent 3 project and project-scoped run;
- the Agent 3 implementation snapshot kind and `READY_FOR_GENERATION` snapshot
  state (the shared operational run may remain `QUEUED`);
- an `APPROVED` final approval and all mandatory embedded context;
- only the eight existing `ImplementationOutputCode` values, with no duplicates;
- matching project/specification/readiness/approval identities and digests;
- a recomputable selected-output digest, readiness fingerprint, and approval
  fingerprint;
- exact agreement between the trusted readiness outputs, effective stack,
  optional stack adaptation, and their top-level snapshot copies;
- resolved specification conflicts, valid readiness, exact warning evidence,
  and the complete existing traceability-root set.

Failures use `ApprovedGenerationInputError` with a stable
`GenerationInputErrorCode`. Messages do not include snapshot content,
credentials, local filesystem roots, or persistence details. Missing/foreign
projects remain non-disclosing through the existing shared authorization
boundary.

## Generation context

`ApprovedGenerationContext` carries run/project identity, shared operational
status, complete trusted specification, complete trusted readiness, selected
outputs in approved order, frozen effective PP1 stack, original requested
technology-stack items where present, stack-adaptation evidence, final approval,
safe delivery metadata, traceability roots, and all preserved fingerprints and
digests. Existing nested domain schemas are reused rather than duplicated.

The context is detached from persistence and has no update/save operation.
Mutating a nested working copy cannot modify the stored AgentRun.

## Planning and workspace contracts

GEN-R1.1 defines schemas for future generation-plan identity, selected-output
mapping, planned files, relative paths, file responsibility, supporting
requirement/specification references, generation status, and validation errors.
It does not instantiate a generation plan.

Output paths use canonical POSIX-style relative paths. Validation rejects empty
or non-canonical paths, absolute POSIX/Windows paths, drive/UNC forms, backslash
separators, `.`/`..` traversal, control characters, alternate data stream
syntax, unsafe trailing characters, overlong components, and Windows reserved
names. A resolver verifies containment beneath an absolute server-selected
project/run workspace without creating directories or files. A future writer
must additionally recheck symlinks/reparse points immediately before opening a
destination.

## Downstream work

GEN-R1.2 now builds a deterministic, validated in-memory plan from this context.
GEN-R1.3 may integrate an approved generation provider and a later milestone may
add a safe file writer. Those milestones must retain selected-output
authorization and file-to-specification traceability.

**GEN-R1.1 does not generate source code.** It performs no model inference,
workspace creation, source-file write, command execution, build, test, delivery,
or AgentRun transition.
