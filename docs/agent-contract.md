# Agent Contract v0.1

Personal AI Brain uses declarative agent contracts so an agent's purpose and permissions are explicit before orchestration or autonomy is added.

The contract is deliberately small. It describes **what an agent is allowed to be**, not how an LLM framework happens to implement it.

## Why this exists

A future multi-agent system needs a stable answer to questions such as:

- What is this agent responsible for?
- What can it read?
- What can it write?
- Which tools may it call?
- Which actions require approval?
- Which events can wake it up?
- Which events can it emit for other agents?

Without an explicit contract, those boundaries tend to live inside prompts, chat history, or orchestration code and become difficult to audit.

## Manifest location

Agent manifests live under:

```text
agents/*.yaml
```

The first registered agent is:

```text
agents/core-agent.yaml
```

## Contract shape

Example:

```yaml
schema_version: "0.1"

id: "core-agent"
name: "Core Agent"
version: "0.1"
enabled: true
entrypoint: "personal_ai_brain.core_agent:CoreAgent"

responsibility: >
  Read durable Project OS state and generate a cross-project snapshot.

autonomy: "read_only"

inputs:
  - "project_map"
  - "project_state"

outputs:
  - "core_snapshot"
  - "integrity_findings"

tools:
  - id: "github.contents"
    access: "read"
    approval_required: false

resources:
  reads:
    - "github:Az1mutt/personal-project-brain/**"
  writes: []

approval:
  required_for:
    - "any_write"
    - "external_side_effect"

events:
  consumes:
    - "project_state.changed"
  emits:
    - "core_snapshot.generated"
```

## Autonomy levels

The current schema recognizes these levels:

- `read_only` — may only use read tools/resources; no external mutation.
- `draft_only` — may prepare proposed changes but not apply them.
- `write_with_approval` — writes require an approval boundary.
- `bounded_write` — may write only inside an explicitly constrained envelope.
- `autonomous` — reserved for later, after reliability and policy controls exist.

Recognition of a level in the schema does **not** mean it is currently enabled operationally.

Core Agent remains `read_only`.

## Tool permissions

Each tool grant has:

- `id`
- `access`: `read`, `write`, or `execute`
- `approval_required`

The contract loader rejects a `read_only` agent that declares a write/execute tool.

## Resource permissions

Resources are declared separately from tool capability.

This matters because:

> being technically capable of calling GitHub does not imply permission to read or write every repository/path.

`resources.reads` and `resources.writes` are declarative policy strings. Runtime enforcement will be added later; v0.1 validates the contract boundary itself.

## Approval policy

`approval.required_for` records action classes that must cross a human/policy boundary before execution.

Examples:

- `any_write`
- `external_side_effect`
- `destructive_action`
- `financial_action`

The initial Core Agent never reaches these actions because it has no write-capable tools.

## Events

`events.consumes` and `events.emits` define the future routing surface between agents without requiring an event bus today.

For example:

```text
project_state.changed
        ↓
     Core Agent
        ↓
core_snapshot.generated
```

Later this can become:

```text
core_snapshot.generated
        ↓
portfolio signal detected
        ↓
Career Evidence Agent
```

The event names are contracts first; transport comes later.

## Registry

`AgentRegistry` loads YAML manifests from the `agents/` directory, validates each contract, and rejects duplicate agent IDs.

CLI examples:

```bash
personal-ai-brain agents validate
personal-ai-brain agents list
personal-ai-brain agents show core-agent
```

## Current boundary

This milestone adds **declarative platform structure only**.

It does not add:

- LLM orchestration;
- background execution;
- GitHub writes;
- queue/event infrastructure;
- database-backed registry;
- dynamic plugin loading;
- Homelab deployment.

Those layers should consume this contract rather than replace it.
