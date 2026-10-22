# Trusted implementation readiness

Policy version `1` evaluates only the current `READY` final trusted project
specification plus the validated selected-output list. The server loads the
specification; clients cannot submit specification facts. Results are stored
atomically in `implementation-readiness.json` and are invalid when the policy,
selected outputs, project-specification identity, source-set digest, decision
digest, or stack-adaptation fingerprint changes.

Required groups below use **OR** within a group and **AND** between groups.
Recommended categories produce warnings only.

| Selected output | Required trusted categories | Recommended trusted categories |
| --- | --- | --- |
| `PROJECT_STRUCTURE` | functional requirements OR user stories OR implementation tasks | system architecture, technology stack, technical constraints |
| `FRONTEND_CODE` | functional requirements OR user stories OR acceptance criteria | UI flow, acceptance criteria, test cases |
| `BACKEND_CODE` | functional requirements OR user stories OR API specification | API specification, acceptance criteria, non-functional requirements, test cases |
| `DATABASE_IMPLEMENTATION` | (functional requirements OR user stories OR implementation tasks) AND database schema | technical constraints, acceptance criteria, test cases |
| `API_IMPLEMENTATION` | (functional requirements OR user stories OR implementation tasks) AND API specification | acceptance criteria, non-functional requirements, test cases |
| `CONFIGURATION_FILES` | functional requirements OR user stories OR implementation tasks | technology stack, technical constraints |
| `CONTAINER_CONFIGURATION` | functional requirements OR user stories OR implementation tasks | technology stack, technical constraints |
| `GIT_SUMMARY` | functional requirements OR user stories OR implementation tasks | none |

GitHub connection, repository, branch, PR, and delivery settings are not
implementation-readiness inputs. They belong to the later Delivery Setup node.
The legacy `/readiness/evaluate` endpoint intentionally retains its standalone
file/input behavior, including its historical GitHub rule.

Unsupported explicit technology declarations block readiness. A human may
approve `ADAPT_TO_SUPPORTED_STACK`; that decision is project-, specification-,
policy-, and technology-fingerprint bound. It records an implementation-plan
adaptation and never edits the trusted project specification.
