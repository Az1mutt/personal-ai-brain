# Roadmap

The roadmap deliberately grows autonomy in layers. The long-term destination is multi-agent; the implementation order is evidence-driven.

## v0.1 — Core Agent read path

Goal: remove manual Core consolidation.

- Python package and CLI
- read-only GitHub adapter
- Project OS project/workstream discovery
- YAML validation
- stale/missing/sync findings
- attention-aware Core report
- unit tests and CI
- first run against real private Project OS state

**Exit gate:** real Project OS can be read and summarized reliably without manual deltas.

The implementation is merged and CI-tested. The first live run against the private Project OS remains a runtime acceptance check rather than a blocker for continued platform development.

## v0.2 — Platform contracts and state integrity

Goal: define a stable multi-agent platform boundary before adding runtime orchestration.

### v0.2a — Agent Contract + Registry

Implemented and merged:

- declarative agent contract schema
- explicit responsibility, inputs and outputs
- tool permissions and resource boundaries
- approval policy declaration
- future event consume/emit surface
- local YAML agent registry
- Core Agent registered as the first `read_only` agent
- deterministic contract tests and CLI inspection

### v0.2b — Project rollups and state integrity

Current implementation scope:

- validate multi-workstream project rollup shape
- detect root/workstream path drift against the Project Map
- detect active workstreams missing from `rollup_policy.generated_from`
- detect root rollups older than active child workstreams
- detect `synced` rollups sitting above unsynchronized active child states
- detect hard status contradictions such as a completed project with an active workstream
- feed integrity findings into the normal `core-report`

Still planned inside v0.2b:

- deterministic rollup derivation proposal/output
- freshness policy configuration by project/attention type
- machine-readable Core snapshot output
- clearer Project State schema validation

**Exit gate:** the platform has explicit agent boundaries and Core can detect state drift without a human comparing files.

## v0.3 — Persistent Homelab runtime

- Docker packaging
- read-only GitHub token/secrets handling
- scheduled/manual trigger
- run logs
- health checks
- notification of meaningful findings only

**Exit gate:** Core Agent runs reliably without an interactive ChatGPT session.

## v0.4 — Repo Steward

First write-capable specialist agent.

- inspect documentation after verified milestones
- propose README/architecture/roadmap/state changes
- open PRs instead of directly changing main
- approval boundaries and audit trail

**Exit gate:** safe repository maintenance through reviewable PRs.

## v0.5 — Career Evidence Agent

- consume verified portfolio signals
- map evidence to CV/LinkedIn/interview stories
- distinguish evidence from inference
- draft updates without inventing impact

## v0.6 — Domain agents

Introduce only where real repetitive workflows exist.

Candidates:

- Homelab / Media Agent
- Recipe Ingestion / Curation Agent
- Trading Intelligence Agent

Each gets its own contract, tools and permission envelope.

## v0.7 — Events and orchestration

- event schema transport
- task/event queue if justified by volume
- routing rules
- retries/idempotency
- cross-agent handoffs
- policy engine
- orchestrator/router that consumes the Agent Registry

Example:

```text
Recipe milestone
→ state update
→ Core refresh
→ Repo Steward docs check
→ Career Agent portfolio evaluation
```

## v1 — Multi-agent Personal AI Brain

The sci-fi version, earned rather than faked:

- orchestrator/router
- multiple specialist agents
- durable memory
- local event-driven runtime
- tool ecosystem
- approval/policy framework
- observability
- selective autonomous actions
- conversational control surface

## Memory & Knowledge track

PostgreSQL, pgvector, embeddings, Ollama/local models and semantic search remain a parallel future track. Add them when agents actually need long-term knowledge retrieval; do not block operational agents on RAG infrastructure.
