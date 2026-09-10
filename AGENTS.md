# AGENTS.md

## Project mission

Build a local-first personal multi-agent platform incrementally, with explicit state, tool boundaries and verifiable autonomy.

## Instruction refresh

Before any task that will write to GitHub, read the current `AGENTS.md` from the repository default branch. Do not rely on an older chat copy of these rules when the repository version is available.

## Current implementation priority

Core Agent v0.1 is read-only.

Do not add write-capable GitHub actions, LLM frameworks, databases, queues or orchestration libraries unless the current milestone explicitly requires them.

## Coding principles

- Python 3.11+.
- Prefer the standard library for simple infrastructure.
- Keep external dependencies minimal.
- Keep domain logic separate from adapters.
- Deterministic validation should remain deterministic.
- Every external action must have an explicit permission boundary before it is enabled.
- Never commit tokens, API keys or private secrets.
- Tests should cover state/attention edge cases before autonomy is expanded.

## Git workflow

Use a risk-based workflow. A branch is a safety tool, not a mandatory ceremony.

### Routine Sync Lane — direct to `main` allowed

Direct commits to the default branch are allowed for small, deterministic, easily reversible synchronization of already verified reality, including:

- updating `.project/state.yaml` after a meaningful verified milestone;
- synchronizing README/roadmap/current-state documentation to implementation that is already verified;
- small wording, link, metadata, or documentation corrections;
- low-risk generated/reporting metadata that does not change agent behavior or permissions.

Routine Sync Lane must not be used for code behavior changes, dependencies, CI behavior, tool permissions, GitHub write capability, agent autonomy, deployment configuration, security-sensitive changes, major architecture decisions, or ambiguous changes.

### Change / Review Lane — branch + PR required

Use a dedicated branch and pull request for changes with meaningful implementation, security, autonomy, or review risk, including:

- Python or other executable code changes;
- dependency or build/CI changes;
- new tool adapters/integrations;
- write-capable actions or expanded permissions;
- agent autonomy/policy changes;
- Docker/deployment/runtime changes;
- database/schema/memory infrastructure;
- major architecture changes, broad refactors, deletes or renames.

Keep unrelated changes out of the branch. Run applicable tests/checks before merge.

### Branch lifecycle ownership

If you create a branch, you own its lifecycle.

- If Igor has already approved the intended change, do not ask for a second approval merely to merge the resulting PR.
- After applicable checks pass and the implemented scope still matches the approved change, merge the PR as part of completing the task.
- Prefer squash merge unless there is a reason to preserve individual commits.
- Delete the merged branch when the available GitHub tooling supports branch deletion.
- If branch deletion is unavailable, explicitly report the leftover merged branch instead of silently leaving cleanup to Igor.
- Do not merge if checks fail, the scope materially changed, or new consequential risk appeared; surface that instead.
- Use draft PRs only for genuinely unfinished work, not by default.

## Project OS

This repository owns `.project/state.yaml`.

Meaningful verified milestones should update that state as part of milestone closure. Ordinary discussion or speculative design does not require a state write.

## Architecture direction

The future system may include an orchestrator, agent registry, event bus, memory/RAG and multiple domain agents. Those are target layers, not permission to introduce premature framework complexity into the current milestone.
