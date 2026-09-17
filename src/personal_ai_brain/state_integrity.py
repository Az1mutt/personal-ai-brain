from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import yaml


class TextReader(Protocol):
    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        ...


@dataclass(slots=True)
class IntegrityFinding:
    severity: str
    code: str
    subject: str
    message: str


@dataclass(slots=True)
class IntegrityReport:
    findings: list[IntegrityFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[IntegrityFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[IntegrityFinding]:
        return [finding for finding in self.findings if finding.severity == "warning"]


@dataclass(slots=True)
class _LoadedState:
    path: str
    attention: str
    status: str
    sync_status: str
    last_verified: str
    raw: dict[str, Any]


class StateIntegrityChecker:
    """Deterministic integrity checks for multi-workstream Project OS rollups."""

    NON_BLOCKING_ATTENTION = {"deferred", "parked", "none", "future", "background"}
    FUTURE_STATUSES = {
        "future_unassigned",
        "future_project_not_initialized",
        "not_active",
    }
    TERMINAL_ROOT_STATUSES = {"completed", "paused", "inactive", "archived"}

    def __init__(
        self,
        reader: TextReader,
        central_repository: str = "Az1mutt/personal-project-brain",
        project_map_path: str = "core/project-map.yaml",
        ref: str = "main",
    ) -> None:
        self.reader = reader
        self.central_repository = central_repository
        self.project_map_path = project_map_path
        self.ref = ref

    def check(self) -> IntegrityReport:
        report = IntegrityReport()

        try:
            project_map = self._load_yaml(
                self.central_repository,
                self.project_map_path,
            )
        except Exception:
            # CoreAgent already owns missing/unreadable Project Map reporting.
            return report

        projects = project_map.get("projects")
        if not isinstance(projects, list):
            return report

        for project in projects:
            if not isinstance(project, dict):
                continue
            workstreams = project.get("workstreams")
            if not isinstance(workstreams, list) or not workstreams:
                continue
            self._check_project(project, workstreams, report)

        return report

    def _check_project(
        self,
        project: dict[str, Any],
        workstreams: list[Any],
        report: IntegrityReport,
    ) -> None:
        project_name = str(project.get("name", project.get("id", "unknown")))
        storage = project.get("storage")
        repository = (
            str(project.get("repository"))
            if storage == "project_repo"
            else self.central_repository
        )
        root_path = project.get("state_path")

        if not root_path or not repository or repository == "None":
            return

        root = self._read_state(
            repository=repository,
            path=str(root_path),
            attention=str(project.get("core_attention", "unspecified")),
        )
        if root is None:
            return

        children: list[_LoadedState] = []
        map_paths: set[str] = set()

        for workstream in workstreams:
            if not isinstance(workstream, dict):
                continue
            path = workstream.get("state_path")
            if not path:
                continue
            path = str(path)
            map_paths.add(path)
            child = self._read_state(
                repository=repository,
                path=path,
                attention=str(
                    workstream.get(
                        "core_attention",
                        project.get("core_attention", "unspecified"),
                    )
                ),
            )
            if child is not None:
                children.append(child)

        if not children:
            return

        self._check_rollup_shape(project_name, root, map_paths, report)
        active_children = [
            child for child in children if not self._is_non_blocking(child)
        ]
        self._check_generated_sources(
            project_name,
            root,
            active_children,
            map_paths,
            report,
        )
        self._check_freshness(project_name, root, active_children, report)
        self._check_sync(project_name, root, active_children, report)
        self._check_status(project_name, root, active_children, report)

    def _check_rollup_shape(
        self,
        project_name: str,
        root: _LoadedState,
        map_paths: set[str],
        report: IntegrityReport,
    ) -> None:
        state_scope = str(root.raw.get("state_scope", ""))
        if state_scope != "project_rollup":
            report.findings.append(
                IntegrityFinding(
                    "warning",
                    "multi_workstream_root_not_rollup",
                    project_name,
                    (
                        "Project map declares workstreams but root state_scope is "
                        f"{state_scope!r}, not 'project_rollup'."
                    ),
                )
            )

        declared_paths = {
            str(item.get("path"))
            for item in (root.raw.get("workstreams") or [])
            if isinstance(item, dict) and item.get("path")
        }

        missing = sorted(map_paths - declared_paths)
        extra = sorted(declared_paths - map_paths)

        if missing:
            report.findings.append(
                IntegrityFinding(
                    "warning",
                    "rollup_missing_workstream_declaration",
                    project_name,
                    "Root rollup does not declare mapped workstream(s): "
                    + ", ".join(missing),
                )
            )
        if extra:
            report.findings.append(
                IntegrityFinding(
                    "warning",
                    "rollup_declares_unknown_workstream",
                    project_name,
                    "Root rollup declares workstream path(s) absent from project map: "
                    + ", ".join(extra),
                )
            )

    def _check_generated_sources(
        self,
        project_name: str,
        root: _LoadedState,
        active_children: list[_LoadedState],
        map_paths: set[str],
        report: IntegrityReport,
    ) -> None:
        rollup_policy = root.raw.get("rollup_policy") or {}
        if not isinstance(rollup_policy, dict):
            rollup_policy = {}

        generated_from = {
            str(path)
            for path in (rollup_policy.get("generated_from") or [])
            if path
        }
        required = {child.path for child in active_children}

        missing = sorted(required - generated_from)
        extra = sorted(generated_from - map_paths)

        if missing:
            report.findings.append(
                IntegrityFinding(
                    "warning",
                    "rollup_missing_active_source",
                    project_name,
                    "Active workstream state is not listed in rollup_policy.generated_from: "
                    + ", ".join(missing),
                )
            )
        if extra:
            report.findings.append(
                IntegrityFinding(
                    "warning",
                    "rollup_generated_from_unknown_source",
                    project_name,
                    "rollup_policy.generated_from references unmapped path(s): "
                    + ", ".join(extra),
                )
            )

    def _check_freshness(
        self,
        project_name: str,
        root: _LoadedState,
        active_children: list[_LoadedState],
        report: IntegrityReport,
    ) -> None:
        root_date = self._parse_date(root.last_verified)
        if root_date is None:
            return

        newer = [
            child
            for child in active_children
            if (child_date := self._parse_date(child.last_verified)) is not None
            and child_date > root_date
        ]
        if not newer:
            return

        newest = max(newer, key=lambda child: self._parse_date(child.last_verified))
        report.findings.append(
            IntegrityFinding(
                "warning",
                "rollup_outdated",
                project_name,
                (
                    f"Root rollup was verified {root.last_verified}, but workstream "
                    f"{newest.path} was verified later on {newest.last_verified}."
                ),
            )
        )

    def _check_sync(
        self,
        project_name: str,
        root: _LoadedState,
        active_children: list[_LoadedState],
        report: IntegrityReport,
    ) -> None:
        unsynced = [
            child
            for child in active_children
            if child.sync_status != "synced"
        ]
        if root.sync_status != "synced" or not unsynced:
            return

        details = ", ".join(
            f"{child.path}={child.sync_status}" for child in unsynced
        )
        report.findings.append(
            IntegrityFinding(
                "warning",
                "rollup_sync_conflict",
                project_name,
                (
                    "Root rollup claims sync.status='synced' while active workstream "
                    f"state is not synced: {details}"
                ),
            )
        )

    def _check_status(
        self,
        project_name: str,
        root: _LoadedState,
        active_children: list[_LoadedState],
        report: IntegrityReport,
    ) -> None:
        if root.status not in self.TERMINAL_ROOT_STATUSES:
            return

        active = [child for child in active_children if child.status == "active"]
        if not active:
            return

        report.findings.append(
            IntegrityFinding(
                "error",
                "rollup_status_conflict",
                project_name,
                (
                    f"Root rollup status is {root.status!r}, but active workstream(s) "
                    "still exist: " + ", ".join(child.path for child in active)
                ),
            )
        )

    def _read_state(
        self,
        *,
        repository: str,
        path: str,
        attention: str,
    ) -> _LoadedState | None:
        try:
            raw = self._load_yaml(repository, path)
        except Exception:
            # CoreAgent reports unreadable state files already.
            return None

        verification = raw.get("verification") or {}
        if not isinstance(verification, dict):
            verification = {}
        sync = raw.get("sync") or {}
        if not isinstance(sync, dict):
            sync = {}

        return _LoadedState(
            path=path,
            attention=attention,
            status=str(raw.get("status", "unknown")),
            sync_status=str(sync.get("status", "unknown")),
            last_verified=str(verification.get("last_verified", "")),
            raw=raw,
        )

    def _load_yaml(self, repository: str, path: str) -> dict[str, Any]:
        text = self.reader.get_text(repository, path, self.ref)
        parsed = yaml.safe_load(text)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected YAML mapping at {repository}:{path}")
        return parsed

    def _is_non_blocking(self, state: _LoadedState) -> bool:
        return (
            state.attention in self.NON_BLOCKING_ATTENTION
            or state.status in self.FUTURE_STATUSES
        )

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
