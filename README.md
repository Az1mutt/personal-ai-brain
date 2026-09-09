# Personal AI Brain

A local-first personal agent platform for coordinating Igor's projects, tools, knowledge and future autonomous workflows.

The long-term target is a real multi-agent system. The first implementation is intentionally smaller: a **read-only Core Agent** that consumes Project OS state from GitHub and produces a deterministic cross-project view.

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

## Core Agent v0.1

Implemented:

- read-only GitHub Contents API adapter;
- discovery through `personal-project-brain/core/project-map.yaml`;
- support for project rollups and specialist workstream states;
- deterministic validation of missing, stale and unsynchronized state;
- distinction between active, background, deferred, parked and future work;
- Markdown Core report generation;
- CLI;
- automated tests.

Explicitly **not** implemented in v0.1:

- GitHub writes;
- LLM planning;
- autonomous project actions;
- persistent scheduler;
- database;
- vector memory;
- multi-agent orchestration.

Those are future layers, not prerequisites for proving the read path.

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

Write a report to disk:

```bash
personal-ai-brain core-report --output reports/core.md
```

Run tests:

```bash
pytest -q
```

Do not commit tokens or other secrets.

## Repository structure

```text
.project/                         Project OS state for this project
src/personal_ai_brain/            Python package
tests/                            deterministic unit tests
docs/vision.md                    long-term destination
docs/architecture.md              architecture and boundaries
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
8. **The sci-fi version is allowed — after every autonomy boundary has earned its way in.**

## Memory / RAG

The repository originally started as a local knowledge/RAG concept using PostgreSQL, pgvector and Ollama. That idea is retained, but repositioned as a future **Memory & Knowledge subsystem** of the broader agent platform rather than the platform itself.
