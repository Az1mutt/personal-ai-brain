from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import yaml


class TextReader(Protocol):
    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        ...


@dataclass(slots=True)
class Finding:
    severity: str
    code: str
    subject: str
    message: str


@dataclass(slots=True)
class StateRecord:
    project_id: str
    project_name: str
    scope: str
    repository: str
    path: str
    attention: str
    status: str
    phase: str
    last_verified: str
    sync_status: str
    current_gate: str
    exact_next_action: str


@dataclass(slots=True)
class CoreSnapshot:
    generated_on: str
    records: list[StateRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


class CoreAgent:
    """Read-only Project OS aggregator.

    v0.1 deliberately avoids LLM reasoning and GitHub writes. Its job is to make
    state discovery, validation and cross-project reporting deterministic.
    """

    NON_BLOCKING_ATTENTION = {"deferred", "parked", "none", "future", "background"}
    STALE_STATUSES = {"stale_needs_refresh", "needs_initialization"}
    NON_CURRENT_MAP_STATUSES = {
        "future_project_not_initialized",
        "future_unassigned",
        "deferred_manual",
        "synced_but_old",
    }

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

    def collect(self) -> CoreSnapshot:
        snapshot = CoreSnapshot(generated_on=date.today().isoformat())

        try:
            project_map = self._load_yaml(
                self.central_repository,
                self.project_map_path,
                "Core project map",
            )
        except Exception as exc:  # converted to one clear top-level finding
            snapshot.findings.append(
                Finding(
                    "error",
                    "project_map_unreadable",
                    "Core project map",
                    str(exc),
                )
            )
            return snapshot

        projects = project_map.get("projects")
        if not isinstance(projects, list):
            snapshot.findings.append(
                Finding(
                    "error",
                    "project_map_invalid",
                    "Core project map",
                    "'projects' must be a list",
                )
            )
            return snapshot

        for project in projects:
            self._collect_project(project, snapshot)

        return snapshot

    def _collect_project(self, project: dict[str, Any], snapshot: CoreSnapshot) -> None:
        project_id = str(project.get("id", "unknown"))
        project_name = str(project.get("name", project_id))
        attention = str(project.get("core_attention", "unspecified"))
        map_status = str(project.get("state_status", "unknown"))
        storage = project.get("storage")
        state_path = project.get("state_path")

        if not state_path:
            snapshot.findings.append(
                Finding(
                    "error",
                    "state_path_missing",
                    project_name,
                    "Project map entry has no state_path",
                )
            )
            return

        repository = (
            str(project.get("repository"))
            if storage == "project_repo"
            else self.central_repository
        )
        if not repository or repository == "None":
            snapshot.findings.append(
                Finding(
                    "error",
                    "repository_missing",
                    project_name,
                    "Project repository is not defined",
                )
            )
            return

        root = self._read_state(
            project_id=project_id,
            project_name=project_name,
            scope="project",
            repository=repository,
            path=str(state_path),
            attention=attention,
            snapshot=snapshot,
        )

        if root is not None:
            snapshot.records.append(root)
            self._validate_record(root, map_status, snapshot)

        workstreams = project.get("workstreams") or []
        if isinstance(workstreams, list):
            for workstream in workstreams:
                self._collect_workstream(
                    project_id,
                    project_name,
                    repository,
                    attention,
                    workstream,
                    snapshot,
                )

    def _collect_workstream(
        self,
        project_id: str,
        project_name: str,
        repository: str,
        parent_attention: str,
        workstream: dict[str, Any],
        snapshot: CoreSnapshot,
    ) -> None:
        workstream_id = str(workstream.get("id", "unknown"))
        path = workstream.get("state_path")
        if not path:
            snapshot.findings.append(
                Finding(
                    "error",
                    "workstream_state_path_missing",
                    f"{project_name}/{workstream_id}",
                    "Workstream has no state_path",
                )
            )
            return

        attention = str(workstream.get("core_attention", parent_attention))
        map_status = str(workstream.get("state_status", "unknown"))
        record = self._read_state(
            project_id=project_id,
            project_name=f"{project_name} / {workstream_id}",
            scope="workstream",
            repository=repository,
            path=str(path),
            attention=attention,
            snapshot=snapshot,
        )
        if record is not None:
            snapshot.records.append(record)
            self._validate_record(record, map_status, snapshot)

    def _read_state(
        self,
        *,
        project_id: str,
        project_name: str,
        scope: str,
        repository: str,
        path: str,
        attention: str,
        snapshot: CoreSnapshot,
    ) -> StateRecord | None:
        try:
            state = self._load_yaml(repository, path, project_name)
        except Exception as exc:
            snapshot.findings.append(
                Finding(
                    "error",
                    "state_unreadable",
                    project_name,
                    str(exc),
                )
            )
            return None

        verification = state.get("verification") or {}
        sync = state.get("sync") or {}

        return StateRecord(
            project_id=project_id,
            project_name=project_name,
            scope=scope,
            repository=repository,
            path=path,
            attention=attention,
            status=str(state.get("status", "unknown")),
            phase=str(state.get("phase", "")),
            last_verified=str(verification.get("last_verified", "")),
            sync_status=str(sync.get("status", "unknown")),
            current_gate=self._fold_text(state.get("current_gate")),
            exact_next_action=self._fold_text(state.get("exact_next_action")),
        )

    def _validate_record(
        self,
        record: StateRecord,
        map_status: str,
        snapshot: CoreSnapshot,
    ) -> None:
        non_blocking = record.attention in self.NON_BLOCKING_ATTENTION

        if record.sync_status != "synced" and not non_blocking:
            snapshot.findings.append(
                Finding(
                    "warning",
                    "state_not_synced",
                    record.project_name,
                    f"sync.status is {record.sync_status!r}",
                )
            )

        if record.status in self.STALE_STATUSES and not non_blocking:
            snapshot.findings.append(
                Finding(
                    "warning",
                    "state_needs_refresh",
                    record.project_name,
                    f"state status is {record.status!r}",
                )
            )

        if (
            map_status in self.NON_CURRENT_MAP_STATUSES
            and not non_blocking
            and record.status not in {"future_unassigned"}
        ):
            snapshot.findings.append(
                Finding(
                    "warning",
                    "map_marks_state_non_current",
                    record.project_name,
                    f"project map state_status is {map_status!r}",
                )
            )

        if not record.last_verified and not non_blocking:
            snapshot.findings.append(
                Finding(
                    "warning",
                    "verification_date_missing",
                    record.project_name,
                    "verification.last_verified is empty",
                )
            )

    def render_markdown(self, snapshot: CoreSnapshot | None = None) -> str:
        snapshot = snapshot or self.collect()

        lines = [
            f"# Core Agent Report — {snapshot.generated_on}",
            "",
            "Read-only report generated from durable Project OS state on GitHub.",
            "",
            "## Health",
            "",
            f"- States read: **{len(snapshot.records)}**",
            f"- Errors: **{len(snapshot.errors)}**",
            f"- Warnings: **{len(snapshot.warnings)}**",
            "",
        ]

        if snapshot.findings:
            lines.extend(["## Findings", ""])
            for finding in snapshot.findings:
                lines.append(
                    f"- **{finding.severity.upper()} · {finding.code} · "
                    f"{finding.subject}:** {finding.message}"
                )
            lines.append("")
        else:
            lines.extend(["## Findings", "", "No state integrity findings.", ""])

        lines.extend(
            [
                "## States",
                "",
                "| Attention | Scope | Project / Workstream | Status | Phase | Verified |",
                "|---|---|---|---|---|---|",
            ]
        )
        for record in sorted(
            snapshot.records,
            key=lambda r: (self._attention_rank(r.attention), r.project_name),
        ):
            lines.append(
                "| "
                + " | ".join(
                    [
                        self._cell(record.attention),
                        self._cell(record.scope),
                        self._cell(record.project_name),
                        self._cell(record.status),
                        self._cell(record.phase),
                        self._cell(record.last_verified or "unknown"),
                    ]
                )
                + " |"
            )

        lines.extend(["", "## Current gates and next actions", ""])
        for record in sorted(
            snapshot.records,
            key=lambda r: (self._attention_rank(r.attention), r.project_name),
        ):
            if record.attention in {"none", "future"}:
                continue
            lines.append(f"### {record.project_name}")
            lines.append(f"- Attention: **{record.attention}**")
            lines.append(f"- Gate: {record.current_gate or 'Not specified.'}")
            lines.append(
                f"- Next: {record.exact_next_action or 'Not specified.'}"
            )
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def _load_yaml(self, repository: str, path: str, subject: str) -> dict[str, Any]:
        text = self.reader.get_text(repository, path, self.ref)
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML for {subject}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected YAML mapping for {subject}")
        return parsed

    @staticmethod
    def _fold_text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())

    @staticmethod
    def _cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    @staticmethod
    def _attention_rank(attention: str) -> int:
        ranking = {
            "urgent_time_bound": 0,
            "active": 1,
            "active_secondary": 2,
            "background": 3,
            "deferred": 4,
            "parked": 5,
            "none": 6,
            "future": 7,
        }
        return ranking.get(attention, 8)
