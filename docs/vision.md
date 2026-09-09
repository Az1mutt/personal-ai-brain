# Vision

Personal AI Brain is a local-first personal multi-agent platform.

Its purpose is not merely to answer questions over notes. It should become an operational layer that understands durable project state, coordinates specialist agents, uses tools safely, maintains useful memory, and helps execute Igor's real workflows.

## End-state

The intended mature system contains specialized agents with explicit responsibilities, for example:

- **Core Agent** — cross-project state, priorities, blockers and dependencies;
- **Repo Steward** — documentation/state consistency and safe repository maintenance;
- **Career Evidence Agent** — converts verified project milestones into career/portfolio signals;
- **Homelab Agent** — observes and later operates allowed infrastructure/media workflows;
- **Recipe Agent** — ingestion, classification, review and recommendation workflows;
- **Trading Intelligence Agent** — market-data, alerts, risk and explainable plan support;
- **Memory & Knowledge Agent** — structured knowledge, retrieval and long-term contextual memory.

A later orchestrator should decide which specialist agent/tool is appropriate for a task and coordinate multi-step workflows.

## Human role

Igor remains the owner of goals, risk tolerance and high-impact decisions.

The platform should remove coordination overhead, repeated checking and manual information transport — not hide consequential actions.

Autonomy increases by demonstrated reliability:

```text
read
→ analyze
→ recommend
→ draft
→ low-risk write
→ constrained action
→ coordinated multi-agent execution
```

## Local-first

The preferred runtime is Igor's Homelab. Cloud models/APIs may provide intelligence, but orchestration, state, logs, policies and sensitive integrations should remain controllable locally where practical.

## Memory

Structured data, documents, embeddings and semantic retrieval remain part of the vision. They form a Memory & Knowledge subsystem that agents can query; they are not a substitute for explicit Project State or operational truth.
