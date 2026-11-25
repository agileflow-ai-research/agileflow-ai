# Agent 3 GEN-R1.3D: deterministic code adherence validation

## Scope

GEN-R1.3D adds a deterministic validation stage after GEN-R1.3B structural
content validation. It does not write generated files, execute generated code,
call a model, change an approved AgentRun, or change a GenerationPlan.

The stage exists because the controlled GEN-R1.3C smoke test returned valid JSON
and structurally acceptable JavaScript while still inventing a `Booking` model,
unapproved persistence methods, a relative module, and an HTTP 500 response. It
also used CommonJS in a package that declared `"type": "module"`.

Structural validation is therefore retained as one result, not treated as code
adherence approval.

## Architecture

```text
ModelFileResponse
  -> GeneratedContentValidator
  -> structural GeneratedContentCandidate
  -> CodeAdherenceValidator
  -> fingerprint-bound CodeAdherenceReport
  -> candidate.writer_eligible
```

`generation/adherence/service.py` owns the deterministic policy. The typed
report and finding contracts live with the existing generation schemas so the
candidate can carry one immutable report without introducing a second pipeline.

Policy version: `GEN-R1.3D-1`.

## Report contract and acceptance policy

The report binds the plan, file, approved-context fingerprint, content SHA-256,
policy version, checks, findings, result, and report fingerprint. Findings use
three severities:

- `BLOCKING`: demonstrable contract violation; automatic writing is forbidden.
- `REVIEW_REQUIRED`: evidence is insufficient; automatic writing is forbidden.
- `INFORMATIONAL`: limitation or observation that does not independently block.

Report statuses are `PASS`, `BLOCKED`, `REVIEW_REQUIRED`, and `NOT_CHECKED`.
`writer_eligible` is true only for `PASS`, and only when the existing candidate
is structurally `VALIDATED`. Missing-information candidates remain blocked.

No file writer exists in this milestone.

## Implemented JavaScript and Express checks

The validator currently checks:

- ESM/CommonJS compatibility from a validated `package.json` dependency;
- static ESM imports and literal CommonJS `require` calls;
- external packages against package declarations and approved PP1 frameworks;
- safe logical resolution of relative imports against validated planned-file
  dependencies;
- imported names against statically declared dependency exports;
- persistence-style calls only when their receiver derives from an unverified
  imported interface;
- explicit database-package conflicts, including Mongoose or MongoDB in the
  exclusively approved MySQL stack;
- Express HTTP method and path against trusted API PSI items;
- Express `:parameter` equivalence with specification `{parameter}` syntax;
- explicit response status codes and destructured request fields;
- missing, additional, and mount-prefix-dependent endpoints;
- preservation of PSI references and dependency content fingerprints; and
- model-reported missing mandatory information.

The real smoke-test output now produces blocking findings including
`MODULE_SYSTEM_MISMATCH`, `UNVERIFIED_MODULE_IMPORT`,
`UNVERIFIED_IMPORTED_INTERFACE`, `UNVERIFIED_PERSISTENCE_INTERFACE`, and
`UNAPPROVED_HTTP_STATUS`.

## Explicit limitations

No approved JavaScript AST parser is installed. GEN-R1.3D therefore records the
`JAVASCRIPT_PARSER` check as `NOT_CHECKED`, emits
`JAVASCRIPT_PARSER_UNAVAILABLE`, and uses conservative lexical analysis. It does
not claim full syntax or semantic correctness. Dynamic module references,
alias-heavy code, computed properties, complex router composition, re-exports,
and runtime dependency injection can require human review or escape detection.

The current detailed policy targets JavaScript Express REST route files.
Dedicated React/JSX, SQL/MySQL, JSON configuration, CSS, HTML, YAML, and shell
validators remain future work. Unsupported types return an explicit review or
not-checked result rather than false success.

Passing adherence establishes only that the implemented deterministic checks
found no conflict. It does not prove security, functional correctness,
executability, or complete requirement satisfaction.

## Research evidence

The immutable report supports comparison of structural acceptance, adherence
acceptance, unsupported interface counts, API violations, module-system
violations, review requirements, and manually labeled false positives/negative
cases. This supports controlled comparisons between raw local generation,
planned generation, planned generation with deterministic checks, and planned
generation with checks plus HITL. No accuracy improvement is claimed without a
benchmark.

## Remaining work before GEN-R1.4

- Decide whether a non-executing JavaScript parser should be approved and
  pinned.
- Expand declared-interface analysis or define a server-owned dependency
  interface manifest.
- Add language-specific validation for other planned file categories.
- Add the explicit human acceptance boundary for `REVIEW_REQUIRED` results.
- Revalidate adherence, paths, symlinks/reparse points, identity, and hashes
  immediately before any future write.

GEN-R1.3D does not generate, persist, or execute application code.
