from __future__ import annotations

import yaml

from personal_ai_brain.state_integrity import StateIntegrityChecker


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


def build_files(
    *,
    root: dict,
    child: dict,
    child_attention: str = "active",
) -> dict[tuple[str, str, str], str]:
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
                        "core_attention": child_attention,
                    }
                ],
            }
        ]
    }
    return {
        (central, "core/project-map.yaml", "main"): dump(project_map),
        (repo, ".project/state.yaml", "main"): dump(root),
        (repo, ".project/workstreams/infra.yaml", "main"): dump(child),
    }


def base_root() -> dict:
    return {
        "state_scope": "project_rollup",
        "status": "active",
        "workstreams": [
            {
                "id": "infra",
                "path": ".project/workstreams/infra.yaml",
            }
        ],
        "rollup_policy": {
            "generated_from": [".project/workstreams/infra.yaml"],
        },
        "verification": {"last_verified": "2026-09-10"},
        "sync": {"status": "synced"},
    }


def base_child() -> dict:
    return {
        "state_scope": "workstream",
        "status": "active",
        "verification": {"last_verified": "2026-09-10"},
        "sync": {"status": "synced"},
    }


def test_newer_active_workstream_marks_rollup_outdated() -> None:
    root = base_root()
    child = base_child()
    child["verification"]["last_verified"] = "2026-09-11"

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    codes = {finding.code for finding in report.findings}
    assert "rollup_outdated" in codes


def test_future_or_nonblocking_workstream_does_not_make_rollup_stale() -> None:
    root = base_root()
    root["rollup_policy"]["generated_from"] = []
    child = base_child()
    child["status"] = "future_unassigned"
    child["verification"]["last_verified"] = "2026-09-20"

    report = StateIntegrityChecker(
        FakeReader(build_files(root=root, child=child, child_attention="none"))
    ).check()

    codes = {finding.code for finding in report.findings}
    assert "rollup_outdated" not in codes
    assert "rollup_missing_active_source" not in codes


def test_missing_active_generated_source_warns() -> None:
    root = base_root()
    root["rollup_policy"]["generated_from"] = []
    child = base_child()

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    codes = {finding.code for finding in report.findings}
    assert "rollup_missing_active_source" in codes


def test_synced_rollup_with_unsynced_active_child_warns() -> None:
    root = base_root()
    child = base_child()
    child["sync"]["status"] = "pending_review"

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    codes = {finding.code for finding in report.findings}
    assert "rollup_sync_conflict" in codes


def test_terminal_rollup_with_active_child_is_error() -> None:
    root = base_root()
    root["status"] = "completed"
    child = base_child()

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    assert any(
        finding.code == "rollup_status_conflict" and finding.severity == "error"
        for finding in report.findings
    )


def test_rollup_workstream_declaration_must_match_project_map() -> None:
    root = base_root()
    root["workstreams"] = [
        {
            "id": "other",
            "path": ".project/workstreams/other.yaml",
        }
    ]
    child = base_child()

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    codes = {finding.code for finding in report.findings}
    assert "rollup_missing_workstream_declaration" in codes
    assert "rollup_declares_unknown_workstream" in codes


def test_non_rollup_root_warns_for_multi_workstream_project() -> None:
    root = base_root()
    root["state_scope"] = "project"
    child = base_child()

    report = StateIntegrityChecker(FakeReader(build_files(root=root, child=child))).check()

    assert any(
        finding.code == "multi_workstream_root_not_rollup"
        for finding in report.findings
    )
