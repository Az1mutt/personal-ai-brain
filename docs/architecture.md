# Architecture

## v0.1 — implemented slice

```text
GitHub Project OS
      ↓
GitHubReader (read-only)
      ↓
CoreAgent
      ├─ discovery
      ├─ YAML parsing
      ├─ integrity checks
      └─ attention/state interpretation
      ↓
Markdown / CLI report
```

No LLM, database, scheduler or write-capable tool is required for this slice.

## Target architecture

```text
                         ┌────────────────────────┐
                         │ Human / Chat / UI      │
                         └───────────┬────────────┘
                                     │
                         ┌───────────▼────────────┐
                         │ Orchestrator / Router  │
                         │ policy + task graph    │
                         └───────────┬────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
      ┌───────▼───────┐      ┌──────▼──────┐       ┌──────▼──────┐
      │ Core Agent    │      │ Repo Steward│  ...  │ Domain Agent│
      └───────┬───────┘      └──────┬──────┘       └──────┬──────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
                         ┌───────────▼────────────┐
                         │ Tool / Connector Layer│
                         │ GitHub, Supabase,     │
                         │ Homelab APIs, etc.    │
                         └───────────┬────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
     ┌────────▼────────┐   ┌────────▼────────┐    ┌────────▼────────┐
     │ Durable State   │   │ Event / Audit   │    │ Memory/Knowledge│
     │ Project OS etc. │   │ log / queue     │    │ DB/vector/RAG   │
     └─────────────────┘   └─────────────────┘    └─────────────────┘
```

## Key boundaries

### Durable operational state

Project/workstream truth lives in explicit durable state such as Project OS YAML and project databases. Chat history is context, not the operational source of truth.

### Agent registry

Each future agent should declare:

- responsibility;
- inputs;
- outputs;
- tools it may use;
- resources it may read;
- resources it may write;
- approval requirements;
- events it consumes/emits.

### Tool adapters

External systems should be wrapped behind narrow adapters instead of giving every agent arbitrary access.

Examples:

- GitHub reader/writer;
- Supabase client;
- Homelab service adapters;
- notification adapter;
- calendar/mail integrations.

### Policy / approvals

Write and action permissions are separate from reasoning capability.

A model being able to decide something does not imply it is permitted to execute it.

### Event layer

A later event bus/queue can turn milestones into workflows, for example:

```text
project_state.updated
→ Core Agent refresh
→ portfolio signal detected
→ Career Evidence Agent evaluates
→ Repo Steward checks documentation drift
```

Do not introduce the queue before there is real event volume.

### Memory & Knowledge

The earlier PostgreSQL + pgvector + Ollama concept belongs here.

Possible responsibilities:

- documents/notes ingestion;
- embeddings and semantic retrieval;
- structured entities/relationships;
- long-term agent context;
- provenance-aware memory.

It must not overwrite explicit operational state with inferred memory.

## Deployment

Initial execution can be manual from a developer machine.

After Homelab migration closure, the preferred persistent runtime is Docker on the Ubuntu Server host. Deployment, scheduling and secrets management are later milestones.
