from __future__ import annotations

import yaml

from personal_ai_brain.core_agent import CoreAgent


class FakeReader:
    def __init__(self, files: dict[tuple[str, str, str], str]) -> None:
        self.files = files

    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        key = (repository, path, ref)
        if key not in self.files:
            raise RuntimeError(f"missing fixture: {key}")
        return self.files[key]


def dump(value: dict) -> str:
    return yaml.safe_dump(value, sort_keys=False)


def test_active_stale_state_warns_but_deferred_stale_does_not() -> None:
    central = "Az1mutt/personal-project-brain"
    project_map = {
        "projects": [
            {
                "id": "active",
                "name": "Active Project",
                "storage": "central",
                "state_path": "projects/active/state.yaml",
                "state_status": "synced",
                "core_attention": "active",
            },
            {
                "id": "deferred",
                "name": "Deferred Project",
                "storage": "central",
                "state_path": "projects/deferred/state.yaml",
                "state_status": "deferred_manual",
                "core_attention": "deferred",
            },
        ]
    }
    stale = {
        "status": "stale_needs_refresh",
        "phase": "unknown",
        "verification": {"last_verified": "2026-08-13"},
        "sync": {"status": "synced"},
    }

    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (central, "projects/active/state.yaml", "main"): dump(stale),
            (central, "projects/deferred/state.yaml", "main"): dump(stale),
        }
    )

    snapshot = CoreAgent(reader).collect()

    warnings = {(f.code, f.subject) for f in snapshot.warnings}
    assert ("state_needs_refresh", "Active Project") in warnings
    assert ("state_needs_refresh", "Deferred Project") not in warnings
    assert len(snapshot.errors) == 0


def test_multi_workstream_project_reads_root_and_children() -> None:
    central = "Az1mutt/personal-project-brain"
    repo = "Az1mutt/example"
    project_map = {
        "projects": [
            {
                "id": "example",
                "name": "Example",
                "storage": "project_repo",
                "repository": repo,
                "state_path": ".project/state.yaml",
                "state_status": "synced",
                "core_attention": "active",
                "workstreams": [
                    {
                        "id": "infra",
                        "state_path": ".project/workstreams/infra.yaml",
                        "state_status": "synced",
                    },
                    {
                        "id": "agent",
                        "state_path": ".project/workstreams/agent.yaml",
                        "state_status": "future_unassigned",
                        "core_attention": "none",
                    },
                ],
            }
        ]
    }
    root = {
        "status": "active",
        "phase": "rollup",
        "verification": {"last_verified": "2026-09-09"},
        "sync": {"status": "synced"},
    }
    infra = {
        "status": "active",
        "phase": "build",
        "verification": {"last_verified": "2026-09-09"},
        "sync": {"status": "synced"},
    }
    future = {
        "status": "future_unassigned",
        "phase": "not_active",
        "verification": {"last_verified": "2026-09-09"},
        "sync": {"status": "synced"},
    }

    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (repo, ".project/state.yaml", "main"): dump(root),
            (repo, ".project/workstreams/infra.yaml", "main"): dump(infra),
            (repo, ".project/workstreams/agent.yaml", "main"): dump(future),
        }
    )

    snapshot = CoreAgent(reader).collect()

    assert len(snapshot.records) == 3
    assert {r.scope for r in snapshot.records} == {"project", "workstream"}
    assert len(snapshot.errors) == 0
    assert len(snapshot.warnings) == 0


def test_missing_state_becomes_error_instead_of_crashing() -> None:
    central = "Az1mutt/personal-project-brain"
    project_map = {
        "projects": [
            {
                "id": "missing",
                "name": "Missing",
                "storage": "central",
                "state_path": "projects/missing/state.yaml",
                "state_status": "synced",
                "core_attention": "active",
            }
        ]
    }

    reader = FakeReader(
        {(central, "core/project-map.yaml", "main"): dump(project_map)}
    )

    snapshot = CoreAgent(reader).collect()

    assert len(snapshot.errors) == 1
    assert snapshot.errors[0].code == "state_unreadable"


def test_markdown_report_contains_gate_and_next_action() -> None:
    central = "Az1mutt/personal-project-brain"
    project_map = {
        "projects": [
            {
                "id": "recipe",
                "name": "Recipe",
                "storage": "central",
                "state_path": "projects/recipe/state.yaml",
                "state_status": "synced",
                "core_attention": "active",
            }
        ]
    }
    state = {
        "status": "active",
        "phase": "batch-test",
        "current_gate": "Validate the batch.",
        "exact_next_action": "Run five URLs.",
        "verification": {"last_verified": "2026-09-09"},
        "sync": {"status": "synced"},
    }
    reader = FakeReader(
        {
            (central, "core/project-map.yaml", "main"): dump(project_map),
            (central, "projects/recipe/state.yaml", "main"): dump(state),
        }
    )

    report = CoreAgent(reader).render_markdown()

    assert "Validate the batch." in report
    assert "Run five URLs." in report
