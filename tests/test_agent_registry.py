from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from personal_ai_brain.agent_contract import AgentContract, AgentContractError
from personal_ai_brain.agent_registry import AgentRegistry, AgentRegistryError


def write_yaml(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def base_contract(agent_id: str = "core-agent") -> dict:
    return {
        "schema_version": "0.1",
        "id": agent_id,
        "name": "Core Agent",
        "version": "0.1",
        "responsibility": "Read Project OS state.",
        "autonomy": "read_only",
        "entrypoint": "personal_ai_brain.core_agent:CoreAgent",
        "tools": [
            {
                "id": "github.contents",
                "access": "read",
                "approval_required": False,
            }
        ],
        "resources": {
            "reads": ["github:Az1mutt/personal-project-brain/**"],
            "writes": [],
        },
        "approval": {"required_for": ["any_write"]},
        "events": {
            "consumes": ["project_state.changed"],
            "emits": ["core_snapshot.generated"],
        },
    }


def test_read_only_contract_accepts_only_read_permissions() -> None:
    contract = AgentContract.from_mapping(base_contract())

    assert contract.id == "core-agent"
    assert contract.autonomy == "read_only"
    assert contract.tools[0].access == "read"
    assert contract.resources.writes == ()


def test_read_only_contract_rejects_write_tool() -> None:
    value = base_contract()
    value["tools"][0]["access"] = "write"

    with pytest.raises(AgentContractError, match="read_only agents"):
        AgentContract.from_mapping(value)


def test_read_only_contract_rejects_writable_resource() -> None:
    value = base_contract()
    value["resources"]["writes"] = ["github:Az1mutt/example/**"]

    with pytest.raises(AgentContractError, match="writable resources"):
        AgentContract.from_mapping(value)


def test_registry_loads_manifests_and_sorts_by_id(tmp_path: Path) -> None:
    write_yaml(tmp_path / "z.yaml", base_contract("z-agent"))
    write_yaml(tmp_path / "a.yaml", base_contract("a-agent"))

    registry = AgentRegistry.from_directory(tmp_path)

    assert [contract.id for contract in registry.list()] == ["a-agent", "z-agent"]
    assert registry.get("a-agent").name == "Core Agent"


def test_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    write_yaml(tmp_path / "one.yaml", base_contract("same-agent"))
    write_yaml(tmp_path / "two.yaml", base_contract("same-agent"))

    with pytest.raises(AgentRegistryError, match="duplicate agent id"):
        AgentRegistry.from_directory(tmp_path)


def test_registry_rejects_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(AgentRegistryError, match="does not exist"):
        AgentRegistry.from_directory(missing)
