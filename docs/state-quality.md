# Project State Quality v0.2

This layer validates the machine contract around Project OS state before a future runtime or orchestrator consumes it.

It remains read-only and deterministic.

## Schema validation

The checker validates the canonical Project State v0.2 shape derived from `personal-project-brain/templates/project-state.yaml`.

Required top-level fields:

- `project`
- `status`
- `phase`
- `current_gate`
- `current_state`
- `exact_next_action`
- `blockers`
- `dependencies`
- `important_open_loops`
- `portfolio`
- `verification`
- `sync`

It also checks:

- `schema_version == "0.2"`
- `project.name` and `project.owner`
- `project.workstream` for specialist workstream states
- `state_scope: project_rollup` for multi-workstream roots
- `state_scope: workstream` for specialist workstream states
- list/string/boolean types for canonical fields
- `portfolio.milestone` and `portfolio.signal`
- `verification.last_verified` ISO date shape
- `verification.sources`
- `sync.status`
- `sync.storage` matching the path resolved through the Project Map

The validator does not constrain project-specific `status` or `phase` vocabularies beyond their types.

## Freshness policy

Freshness is based on Core attention, not one universal age threshold.

Default policy:

| Attention | Max age |
|---|---:|
| `urgent_time_bound` | 2 days |
| `active` | 7 days |
| `active_secondary` | 14 days |
| `needs_refresh` | 0 days |
| `background` | 30 days |
| unknown attention | 14 days |

Freshness checking is disabled for:

- `deferred`
- `deferred_until_feasibility`
- `parked`
- `none`
- `future`

States with explicit future/deferred statuses such as `future_unassigned` and `deferred_manual` are also excluded.

This avoids stale-warning noise from intentionally parked work.

## Configuration

Built-in defaults match:

`config/freshness-policy.yaml`

To use an explicit policy file:

```bash
personal-ai-brain core-report \
  --freshness-policy config/freshness-policy.yaml

personal-ai-brain core-snapshot \
  --freshness-policy config/freshness-policy.yaml \
  --format json
```

A Project Map entry may override its attention threshold with:

```yaml
freshness_days: 21
```

or disable freshness for that entry with:

```yaml
freshness_days: null
```

## Design boundary

Freshness means only:

> the durable state has not been re-verified within the configured interval.

It does **not** mean the project is wrong, blocked, unhealthy, or low quality.

Likewise, schema validity means the state is machine-readable; it does not imply that its narrative content is true. Truth remains owned by the specialist project/workstream and its verification process.
