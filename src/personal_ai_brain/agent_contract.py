from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class AgentContractError(ValueError):
    """Raised when an agent contract is invalid."""


_ALLOWED_AUTONOMY = {
    "read_only",
    "draft_only",
    "write_with_approval",
    "bounded_write",
    "autonomous",
}
_ALLOWED_TOOL_ACCESS = {"read", "write", "execute"}


def _as_string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AgentContractError(f"{field_name} must be a list of strings")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class ToolGrant:
    id: str
    access: str
    approval_required: bool = False

    @classmethod
    def from_mapping(cls, value: Any) -> "ToolGrant":
        if not isinstance(value, dict):
            raise AgentContractError("tools entries must be mappings")

        tool_id = value.get("id")
        access = value.get("access")
        approval_required = value.get("approval_required", False)

        if not isinstance(tool_id, str) or not tool_id.strip():
            raise AgentContractError("tool id must be a non-empty string")
        if access not in _ALLOWED_TOOL_ACCESS:
            raise AgentContractError(
                f"tool {tool_id!r} access must be one of {sorted(_ALLOWED_TOOL_ACCESS)}"
            )
        if not isinstance(approval_required, bool):
            raise AgentContractError(
                f"tool {tool_id!r} approval_required must be boolean"
            )

        return cls(
            id=tool_id,
            access=access,
            approval_required=approval_required,
        )


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any) -> "ResourcePolicy":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise AgentContractError("resources must be a mapping")
        return cls(
            reads=_as_string_tuple(value.get("reads", []), "resources.reads"),
            writes=_as_string_tuple(value.get("writes", []), "resources.writes"),
        )


@dataclass(frozen=True, slots=True)
class ApprovalPolicy:
    required_for: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any) -> "ApprovalPolicy":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise AgentContractError("approval must be a mapping")
        return cls(
            required_for=_as_string_tuple(
                value.get("required_for", []), "approval.required_for"
            )
        )


@dataclass(frozen=True, slots=True)
class EventPolicy:
    consumes: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Any) -> "EventPolicy":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise AgentContractError("events must be a mapping")
        return cls(
            consumes=_as_string_tuple(value.get("consumes", []), "events.consumes"),
            emits=_as_string_tuple(value.get("emits", []), "events.emits"),
        )


@dataclass(frozen=True, slots=True)
class AgentContract:
    schema_version: str
    id: str
    name: str
    version: str
    responsibility: str
    autonomy: str
    entrypoint: str | None = None
    enabled: bool = True
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    tools: tuple[ToolGrant, ...] = ()
    resources: ResourcePolicy = field(default_factory=ResourcePolicy)
    approval: ApprovalPolicy = field(default_factory=ApprovalPolicy)
    events: EventPolicy = field(default_factory=EventPolicy)

    @classmethod
    def from_mapping(cls, value: Any) -> "AgentContract":
        if not isinstance(value, dict):
            raise AgentContractError("agent contract must be a mapping")

        agent_id = value.get("id")
        name = value.get("name")
        version = value.get("version")
        responsibility = value.get("responsibility")
        autonomy = value.get("autonomy")
        schema_version = value.get("schema_version", "0.1")
        entrypoint = value.get("entrypoint")
        enabled = value.get("enabled", True)

        for field_name, field_value in (
            ("id", agent_id),
            ("name", name),
            ("version", version),
            ("responsibility", responsibility),
            ("schema_version", schema_version),
        ):
            if not isinstance(field_value, str) or not field_value.strip():
                raise AgentContractError(f"{field_name} must be a non-empty string")

        if autonomy not in _ALLOWED_AUTONOMY:
            raise AgentContractError(
                f"autonomy must be one of {sorted(_ALLOWED_AUTONOMY)}"
            )
        if entrypoint is not None and not isinstance(entrypoint, str):
            raise AgentContractError("entrypoint must be a string or null")
        if not isinstance(enabled, bool):
            raise AgentContractError("enabled must be boolean")

        raw_tools = value.get("tools", [])
        if not isinstance(raw_tools, list):
            raise AgentContractError("tools must be a list")
        tools = tuple(ToolGrant.from_mapping(item) for item in raw_tools)

        tool_ids = [tool.id for tool in tools]
        if len(tool_ids) != len(set(tool_ids)):
            raise AgentContractError("tool ids must be unique within an agent contract")

        contract = cls(
            schema_version=schema_version,
            id=agent_id,
            name=name,
            version=version,
            responsibility=responsibility,
            autonomy=autonomy,
            entrypoint=entrypoint,
            enabled=enabled,
            inputs=_as_string_tuple(value.get("inputs", []), "inputs"),
            outputs=_as_string_tuple(value.get("outputs", []), "outputs"),
            tools=tools,
            resources=ResourcePolicy.from_mapping(value.get("resources")),
            approval=ApprovalPolicy.from_mapping(value.get("approval")),
            events=EventPolicy.from_mapping(value.get("events")),
        )
        contract._validate_autonomy_boundary()
        return contract

    def _validate_autonomy_boundary(self) -> None:
        if self.autonomy != "read_only":
            return

        mutating_tools = [tool.id for tool in self.tools if tool.access != "read"]
        if mutating_tools:
            raise AgentContractError(
                "read_only agents may not declare write/execute tools: "
                + ", ".join(sorted(mutating_tools))
            )
        if self.resources.writes:
            raise AgentContractError(
                "read_only agents may not declare writable resources"
            )


def load_agent_contract(path: str | Path) -> AgentContract:
    contract_path = Path(path)
    try:
        parsed = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentContractError(f"could not read {contract_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AgentContractError(f"invalid YAML in {contract_path}: {exc}") from exc

    try:
        return AgentContract.from_mapping(parsed)
    except AgentContractError as exc:
        raise AgentContractError(f"{contract_path}: {exc}") from exc
