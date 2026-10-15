# Agent 3 GitHub Repository Setup (Step 1D)

Step 1D requires `GITHUB_APP_PRIVATE_KEY_PATH` to reference the readable PEM
private key for the configured GitHub App. Keep that PEM outside this repository;
never commit it or copy its contents into application configuration examples.

For the PP1 standalone Agent 3 workflow:

- GitHub connections remain user-level and support personal accounts only.
- Each Agent 3 project can create and bind exactly one new GitHub repository.
- Existing repositories cannot be listed or selected.
- The repository is created with `auto_init=false`, so it is empty.
- No README, license, `.gitignore`, branch, ref, or initial commit is created.
- Branches, commits, pushes, and pull requests belong to later Git automation work.

The GitHub App JWT and installation access token are generated only for the
repository-creation request and are never persisted. The project binding stores
only safe repository metadata in `github_repository_bindings`.

Repository creation and MongoDB binding are not a distributed transaction. The
backend retries the binding write once. If GitHub succeeds but both local writes
fail, the API reports a partial failure and records only safe reconciliation
metadata in logs. It does not automatically delete the remote repository.
