from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import yaml


class TextReader(Protocol):
    def get_text(self, repository: str, path: str, ref: str = "main") -> str:
        ...


@dataclass(slots=True)
class _WorkstreamState:
    id: str
    path: str
    owner: str
    attention: str
    status: str
    last_verified: str
    raw: dict[str, Any]


@dataclass(slots=True)
class RollupProposal:
    project_id: str
    project_name: str
    repository: str
    root_path: str
    basis_paths: list[str]
    changes: dict[str, Any] = field(default_factory=dict)
    manual_synthesis_required: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "repository": self.repository,
            "root_path": self.root_path,
            "basis_paths": list(self.basis_paths),
            "manual_synthesis_required": self.manual_synthesis_required,
            "changes": self.changes,
            "notes": list(self.notes),
        }


class RollupProposalEngine:
    """Build deterministic, read-only rollup proposals from Project OS state.

    The engine only proposes fields that can be derived without semantic judgment.
    When multiple active workstreams exist, narrative fields are intentionally not
    synthesized; a later LLM/human layer may do that explicitly.
    """

    NON_BLOCKING_ATTENTION = {"deferred", "parked", "none", "future", "background"}
    NON_BLOCKING_STATUSES = {
        "future_unassigned",
        "future_project_not_initialized",
        "not_active",
        "deferred_manual",
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

    def propose(self) -> list[RollupProposal]:
        project_map = self._load_yaml(self.central_repository, self.project_map_path)
        projects = project_map.get("projects")
        if not isinstance(projects, list):
            return []

        proposals: list[RollupProposal] = []
        for project in projects:
            if not isinstance(project, dict):
                continue
            workstreams = project.get("workstreams")
            if not isinstance(workstreams, list) or not workstreams:
                continue
            proposal = self._propose_project(project, workstreams)
            if proposal is not None and (proposal.changes or proposal.notes):
                proposals.append(proposal)
        return proposals

    def _propose_project(
        self,
        project: dict[str, Any],
        workstreams: list[Any],
    ) -> RollupProposal | None:
        project_id = str(project.get("id", "unknown"))
        project_name = str(project.get("name", project_id))
        root_path = project.get("state_path")
        if not root_path:
            return None

        repository = (
            str(project.get("repository"))
            if project.get("storage") == "project_repo"
            else self.central_repository
        )
        if not repository or repository == "None":
            return None

        try:
            root = self._load_yaml(repository, str(root_path))
        except Exception:
            return None

        children: list[_WorkstreamState] = []
        for item in workstreams:
            if not isinstance(item, dict) or not item.get("state_path"):
                continue
            path = str(item["state_path"])
            try:
                raw = self._load_yaml(repository, path)
            except Exception:
                continue
            verification = raw.get("verification") or {}
            if not isinstance(verification, dict):
                verification = {}
            children.append(
                _WorkstreamState(
                    id=str(item.get("id", "unknown")),
                    path=path,
                    owner=str(item.get("owner", "unassigned")),
                    attention=str(item.get("core_attention", project.get("core_attention", "unspecified"))),
                    status=str(raw.get("status", item.get("state_status", "unknown"))),
                    last_verified=str(verification.get("last_verified", "")),
                    raw=raw,
                )
            )

        if not children:
            return None

        active = [child for child in children if not self._is_non_blocking(child)]
        proposal = RollupProposal(
            project_id=project_id,
            project_name=project_name,
            repository=repository,
            root_path=str(root_path),
            basis_paths=[child.path for child in active],
        )

        self._propose_structure(root, workstreams, active, children, proposal)
        self._propose_freshness(root, active, proposal)
        self._propose_unambiguous_narrative(root, active, proposal)
        return proposal

    def _propose_structure(
        self,
        root: dict[str, Any],
        workstreams: list[Any],
        active: list[_WorkstreamState],
        children: list[_WorkstreamState],
        proposal: RollupProposal,
    ) -> None:
        self._set_if_changed(root, "state_scope", "project_rollup", proposal)

        desired_workstreams: list[dict[str, Any]] = []
        for item in workstreams:
            if not isinstance(item, dict) or not item.get("state_path"):
                continue
            entry: dict[str, Any] = {
                "id": str(item.get("id", "unknown")),
                "path": str(item["state_path"]),
                "owner": str(item.get("owner", "unassigned")),
            }
            if item.get("state_status"):
                entry["status"] = str(item["state_status"])
            desired_workstreams.append(entry)

        self._set_if_changed(root, "workstreams", desired_workstreams, proposal)

        desired_generated_from = [child.path for child in active]
        rollup_policy = root.get("rollup_policy") or {}
        if not isinstance(rollup_policy, dict):
            rollup_policy = {}

        if rollup_policy.get("specialist_writes_root") is not False:
            proposal.changes["rollup_policy.specialist_writes_root"] = False
        if rollup_policy.get("generated_from") != desired_generated_from:
            proposal.changes["rollup_policy.generated_from"] = desired_generated_from

        has_non_blocking = len(active) != len(children)
        if has_non_blocking and rollup_policy.get("future_workstreams_do_not_block_rollup") is not True:
            proposal.changes["rollup_policy.future_workstreams_do_not_block_rollup"] = True

    def _propose_freshness(
        self,
        root: dict[str, Any],
        active: list[_WorkstreamState],
        proposal: RollupProposal,
    ) -> None:
        verification = root.get("verification") or {}
        if not isinstance(verification, dict):
            verification = {}
        root_value = str(verification.get("last_verified", ""))
        root_date = self._parse_date(root_value)

        dated_children = [
            (self._parse_date(child.last_verified), child)
            for child in active
            if self._parse_date(child.last_verified) is not None
        ]
        if not dated_children:
            return

        newest_date, newest_child = max(dated_children, key=lambda pair: pair[0])
        if root_date is None or newest_date > root_date:
            proposal.changes["verification.last_verified"] = newest_child.last_verified

    def _propose_unambiguous_narrative(
        self,
        root: dict[str, Any],
        active: list[_WorkstreamState],
        proposal: RollupProposal,
    ) -> None:
        if len(active) == 1:
            child = active[0]
            for field_name in ("status", "phase", "current_gate", "exact_next_action"):
                if field_name not in child.raw:
                    continue
                value = child.raw[field_name]
                if root.get(field_name) != value:
                    proposal.changes[field_name] = value
            proposal.notes.append(
                "Narrative proposal is unambiguous because exactly one blocking workstream is active."
            )
            return

        if len(active) > 1:
            proposal.manual_synthesis_required = True
            proposal.notes.append(
                "Multiple blocking workstreams are active; narrative rollup fields are intentionally not synthesized deterministically."
            )
        else:
            proposal.notes.append(
                "No blocking active workstream exists; only structural rollup fields can be proposed safely."
            )

    def _set_if_changed(
        self,
        root: dict[str, Any],
        key: str,
        value: Any,
        proposal: RollupProposal,
    ) -> None:
        if root.get(key) != value:
            proposal.changes[key] = value

    def _is_non_blocking(self, child: _WorkstreamState) -> bool:
        return (
            child.attention in self.NON_BLOCKING_ATTENTION
            or child.status in self.NON_BLOCKING_STATUSES
        )

    def _load_yaml(self, repository: str, path: str) -> dict[str, Any]:
        parsed = yaml.safe_load(self.reader.get_text(repository, path, self.ref))
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected YAML mapping at {repository}:{path}")
        return parsed

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
