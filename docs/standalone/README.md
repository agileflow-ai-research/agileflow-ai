# AgileFlow AI Standalone Agent Contracts

Project: **AgileFlow AI — Human-in-the-Loop Multi-Agent Framework for Agile SDLC Automation**

Contract version: **v1.0 — frozen for Progress Presentation 1**

## Purpose

This documentation pack defines the shared architecture and input/output contracts for reusable standalone specialist agents. It enables the four research members to implement their agent components in parallel without duplicating shared project, run, authentication, history, or results infrastructure.

Standalone Agent Mode supplements, and does not replace or redesign, Integrated Multi-Agent Project Mode. The integrated four-agent workflow, Central SDLC Orchestrator, Shared Knowledge Base, traceability, H1–H5 human approval gates, and correction loops remain the final coordinated research workflow. Their specialist integration continues after Progress Presentation 1.

These documents are contracts, not implementation. The planned schemas, collections, APIs, screens, providers, and exports described here are not created by S0.

## S1 Backend Foundation Status

S1 implements the shared backend project/run foundation described by these contracts: the `agent_projects` and `agent_runs` collections, `AGP-###` and `RUN-###` allocation, strict common schemas, authenticated owner-scoped project APIs and run reads, internal run creation, and guarded run lifecycle transitions. It does not implement specialist execution endpoints, agent intelligence, providers, queues, or standalone/integrated transfer.

## Contract Index

1. [Standalone Agent Architecture](STANDALONE_AGENT_ARCHITECTURE.md) — mode boundaries, common execution layers, engine reuse, provider abstraction, research boundary, ownership split, and milestone target.
2. [Common Agent Project Contract](COMMON_AGENT_PROJECT_CONTRACT.md) — exact `AgentProject`, `AgentRun`, identifiers, ownership, lifecycle, snapshots, manifests, errors, and isolation semantics.
3. [Standalone UI and API Contract](STANDALONE_UI_AND_API_CONTRACT.md) — common journey, reusable screens, planned routes, access rules, response behavior, and export direction.
4. [Agent 1 Requirements Contract](AGENT_1_REQUIREMENTS_CONTRACT.md) — Requirement Gathering and Analysis Agent inputs, source priorities, selectable outputs, result expectations, and clarification loop.
5. [Agent 2 Design and Planning Contract](AGENT_2_DESIGN_PLANNING_CONTRACT.md) — Project Management and Design Agent specification/team inputs, conditional planning validation, outputs, and Jira-compatible plan boundary.
6. [Agent 3 Implementation Contract](AGENT_3_IMPLEMENTATION_CONTRACT.md) — Implementation and Git Automation Agent inputs, selectable outputs, mandatory execution evidence, runnable-code goal, correction loop, and Git boundary.
7. [Agent 4 Testing and Validation Contract](AGENT_4_TESTING_VALIDATION_CONTRACT.md) — Testing, Validation and Security Agent's separate `TEST_GENERATION` and `VALIDATION` modes, inputs, outputs, flows, and traceability.

## Required Reading

Every member must read this README plus:

- the architecture contract;
- the common project/run contract;
- the UI/API contract; and
- the contract for the member's assigned specialist agent.

The shared-foundation owners must read all seven contracts because they own the common infrastructure consumed by every agent. Agent-specific implementers should consult other agent contracts when defining interoperability, but must not modify or redefine another member's contract independently.

## Change Control

These contracts are frozen at v1.0 for Progress Presentation 1. A change that affects another member, shared infrastructure, a frozen enum, an output code, a route, a field, or a mode boundary requires team agreement and coordinated contract updates before implementation. An implementation must not silently create aliases or alternative names.

## Mode Boundary

- **Standalone Agent Mode:** a user manually supplies the context for one chosen specialist agent, selects outputs, runs it independently, and retains isolated run history.
- **Integrated Multi-Agent Project Mode:** the Central SDLC Orchestrator coordinates the same reusable specialist engines through Shared Knowledge Base inputs, traceability, H1–H5, and correction loops.

Standalone outputs are not automatically written into an integrated Project, and standalone execution never advances the integrated Orchestrator. Optional import/export between modes is a future decision.
