from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from personal_ai_brain.agent_contract import (
    AgentContract,
    AgentContractError,
    load_agent_contract,
)


class AgentRegistryError(ValueError):
    """Raised when the registry cannot be built consistently."""


@dataclass(slots=True)
class AgentRegistry:
    agents: dict[str, AgentContract] = field(default_factory=dict)

    @classmethod
    def from_directory(cls, directory: str | Path) -> "AgentRegistry":
        root = Path(directory)
        if not root.exists():
            raise AgentRegistryError(f"agent directory does not exist: {root}")
        if not root.is_dir():
            raise AgentRegistryError(f"agent path is not a directory: {root}")

        registry = cls()
        manifest_paths = sorted(
            path
            for pattern in ("*.yaml", "*.yml")
            for path in root.rglob(pattern)
            if path.is_file()
        )

        if not manifest_paths:
            raise AgentRegistryError(f"no agent manifests found under {root}")

        for manifest_path in manifest_paths:
            try:
                contract = load_agent_contract(manifest_path)
            except AgentContractError as exc:
                raise AgentRegistryError(str(exc)) from exc
            registry.register(contract, source=str(manifest_path))

        return registry

    def register(self, contract: AgentContract, source: str | None = None) -> None:
        if contract.id in self.agents:
            where = f" from {source}" if source else ""
            raise AgentRegistryError(
                f"duplicate agent id {contract.id!r}{where}"
            )
        self.agents[contract.id] = contract

    def get(self, agent_id: str) -> AgentContract:
        try:
            return self.agents[agent_id]
        except KeyError as exc:
            raise AgentRegistryError(f"unknown agent id: {agent_id}") from exc

    def list(self, enabled_only: bool = False) -> list[AgentContract]:
        contracts = self.agents.values()
        if enabled_only:
            contracts = (contract for contract in contracts if contract.enabled)
        return sorted(contracts, key=lambda contract: contract.id)
