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

## v0.2 — Rollups and state integrity

- derive/validate multi-workstream project rollups
- detect contradictions between rollup and child workstreams
- freshness policy by project/attention type
- machine-readable Core snapshot output
- clearer schema validation

**Exit gate:** Core can detect state drift without a human comparing files.

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

Each gets its own tools and permission envelope.

## v0.7 — Events and orchestration

- event schema
- task/event queue if justified by volume
- agent registry
- routing rules
- retries/idempotency
- cross-agent handoffs
- policy engine

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
