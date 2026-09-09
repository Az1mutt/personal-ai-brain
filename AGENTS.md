# AGENTS.md

## Project mission

Build a local-first personal multi-agent platform incrementally, with explicit state, tool boundaries and verifiable autonomy.

## Current implementation priority

Core Agent v0.1 is read-only.

Do not add write-capable GitHub actions, LLM frameworks, databases, queues or orchestration libraries unless the current milestone explicitly requires them.

## Coding principles

- Python 3.11+.
- Prefer the standard library for simple infrastructure.
- Keep external dependencies minimal.
- Keep domain logic separate from adapters.
- Deterministic validation should remain deterministic.
- Every external action must eventually have an explicit permission boundary.
- Never commit tokens, API keys or private secrets.
- Tests should cover state/attention edge cases before autonomy is expanded.

## Project OS

This repository owns `.project/state.yaml`.

Meaningful verified milestones should update that state as part of milestone closure.

## Architecture direction

The future system may include an orchestrator, agent registry, event bus, memory/RAG and multiple domain agents. Those are target layers, not permission to introduce premature framework complexity into v0.1.
