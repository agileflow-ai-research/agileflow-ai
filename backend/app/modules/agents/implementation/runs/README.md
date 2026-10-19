# RUN-R1 implementation approval

RUN-R1 reuses the shared standalone `AgentRun` collection and lifecycle. It
does not define another run entity. Agent 3-specific, approved inputs are
validated as `ImplementationRunInputSnapshot` and stored in the shared run's
immutable `input_snapshot`.

The shared operational status remains `QUEUED`; this is an inert stored state.
Existing agents move their own newly-created runs to `RUNNING` explicitly in
their services. RUN-R1 never calls that transition and no background worker
polls queued runs. The approved snapshot has the more precise milestone state
`READY_FOR_GENERATION`.

The snapshot embeds complete validated copies of the trusted project
specification and trusted readiness result because their live files retain
only the current version. Rebuilding either live artifact cannot change the
approved historical context. Agent 3 routes expose create, list, and get only;
there is no snapshot update route.

GitHub is not a pre-code approval prerequisite. All implementation outputs,
including `GIT_SUMMARY`, may create a run without GitHub. A safe, allow-listed
view of any current connection/repository binding is copied when available.
`GIT_SUMMARY` records that repository configuration is required before a later
delivery execution, not before generation approval. Credentials and secrets
are never copied; later delivery must reacquire ephemeral credentials.

An idempotency key identifies one explicit approval attempt. Retrying the same
attempt returns its existing run. A later deliberate attempt supplies a new
key and may create another run from the same still-current approved state.
