# Personal AI Brain

A local-first personal agent platform for coordinating Igor's projects, tools, knowledge and future autonomous workflows.

The long-term target is a real multi-agent system. The current implementation stays deliberately conservative: read-only agents consume durable Project OS state, validate it deterministically and expose structured outputs before any autonomous write path is introduced.

## Why this exists

Project work happens in specialist chats and repositories. Project OS gives each project/workstream a durable YAML state. Personal AI Brain is the automation layer that will increasingly read, coordinate and act on that state without Igor manually carrying deltas between chats.

Current flow:

```text
specialist chat
    ↓
owned Project / Workstream State
    ↓
GitHub
    ↓
Core Agent
    ├─ integrity checks
    ├─ rollup proposals
    └─ machine-readable snapshot
    ↓
cross-project health / gates / next actions
```

Future flow:

```text
                       ┌─ Repo Steward
                       ├─ Career Evidence Agent
Project State → Core ──┼─ Homelab Agent
                       ├─ Recipe Agent
                       ├─ Trading Agent
                       └─ Memory / Knowledge Agent
                              ↓
                       orchestrated actions
```

## Core Agent

Implemented:

- read-only GitHub Contents API adapter;
- discovery through `personal-project-brain/core/project-map.yaml`;
- support for project rollups and specialist workstream states;
- deterministic validation of missing, stale and unsynchronized state;
- multi-workstream rollup integrity/conflict detection;
- deterministic read-only rollup proposals;
- machine-readable JSON/YAML Core snapshots;
- distinction between active, background, deferred, parked and future work;
- Markdown Core report generation;
- CLI;
- automated tests and CI.

The rollup proposal layer intentionally refuses to invent a shared narrative when multiple blocking workstreams are active. In that case it proposes only unambiguous structural/freshness fields and marks semantic synthesis as required.

Explicitly **not** implemented yet:

- GitHub writes from Core Agent;
- LLM planning/synthesis;
- autonomous project actions;
- persistent scheduler/runtime;
- database/vector memory;
- multi-agent orchestration.

## Agent Contract + Registry

Agent manifests live under `agents/` and define responsibility, inputs/outputs, tool permissions, readable/writable resources, approval boundaries and future event contracts.

Core Agent is the first registered agent and remains strictly `read_only`.

```bash
personal-ai-brain agents validate
personal-ai-brain agents list
personal-ai-brain agents show core-agent
```

See [Agent Contract v0.1](docs/agent-contract.md).

## Quick start

Requirements:

- Python 3.11+
- a GitHub token with read access to `Az1mutt/personal-project-brain`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export GITHUB_TOKEN="..."
personal-ai-brain core-report
```

Generate machine-readable state for future automation/orchestration:

```bash
personal-ai-brain core-snapshot --format json --output reports/core.json
personal-ai-brain core-snapshot --format yaml --output reports/core.yaml
```

Inspect deterministic rollup proposals without writing them:

```bash
personal-ai-brain rollup-proposals
personal-ai-brain rollup-proposals --format json
```

Run tests:

```bash
pytest -q
```

Do not commit tokens or other secrets.

## Repository structure

```text
.project/                         Project OS state for this project
agents/                           declarative agent contracts
src/personal_ai_brain/            Python package
tests/                            deterministic unit tests
docs/vision.md                    long-term destination
docs/architecture.md              architecture and boundaries
docs/agent-contract.md            agent permission/contract model
docs/roadmap.md                   staged implementation plan
database/                         reserved for future memory/state services
docker/                           reserved for Homelab deployment
```

## Architecture philosophy

1. **Manual before autonomous.**
2. **Read before write.**
3. **Deterministic rules where deterministic rules are enough.**
4. **Use LLM judgment only where semantic reasoning adds value.**
5. **Every agent owns a narrow responsibility.**
6. **Durable state lives outside chat memory.**
7. **Agents should coordinate through explicit state/events, not hidden assumptions.**
8. **Capability and permission are separate: a tool existing does not imply an agent may use it.**
9. **A proposal is not permission to write.**
10. **The sci-fi version is allowed — after every autonomy boundary has earned its way in.**

## Memory / RAG

The repository originally started as a local knowledge/RAG concept using PostgreSQL, pgvector and Ollama. That idea is retained, but repositioned as a future **Memory & Knowledge subsystem** of the broader agent platform rather than the platform itself.
