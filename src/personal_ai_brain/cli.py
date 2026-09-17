from __future__ import annotations

import argparse
import sys
from pathlib import Path

from personal_ai_brain.agent_registry import AgentRegistry, AgentRegistryError
from personal_ai_brain.core_agent import CoreAgent
from personal_ai_brain.github_reader import GitHubReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal-ai-brain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser(
        "core-report",
        help="Read Project OS state from GitHub and render a Core report.",
    )
    report.add_argument(
        "--central-repo",
        default="Az1mutt/personal-project-brain",
        help="Repository containing core/project-map.yaml.",
    )
    report.add_argument("--ref", default="main")
    report.add_argument(
        "--output",
        type=Path,
        help="Optional output Markdown file. Prints to stdout when omitted.",
    )
    report.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when warnings are present.",
    )

    agents = subparsers.add_parser(
        "agents",
        help="Inspect and validate declarative agent contracts.",
    )
    agents.add_argument(
        "--directory",
        type=Path,
        default=Path("agents"),
        help="Directory containing agent YAML manifests.",
    )
    agent_subparsers = agents.add_subparsers(dest="agents_command", required=True)

    agent_subparsers.add_parser("list", help="List registered agents.")

    show = agent_subparsers.add_parser("show", help="Show one registered agent.")
    show.add_argument("agent_id")

    agent_subparsers.add_parser(
        "validate",
        help="Validate all manifests and registry uniqueness.",
    )

    return parser


def _load_registry(directory: Path) -> AgentRegistry:
    try:
        return AgentRegistry.from_directory(directory)
    except AgentRegistryError as exc:
        print(f"Agent registry error: {exc}", file=sys.stderr)
        raise


def _print_agent(contract) -> None:
    print(f"id: {contract.id}")
    print(f"name: {contract.name}")
    print(f"version: {contract.version}")
    print(f"enabled: {str(contract.enabled).lower()}")
    print(f"autonomy: {contract.autonomy}")
    print(f"entrypoint: {contract.entrypoint or '-'}")
    print(f"responsibility: {contract.responsibility}")
    print("tools:")
    if contract.tools:
        for tool in contract.tools:
            suffix = " (approval required)" if tool.approval_required else ""
            print(f"  - {tool.id}: {tool.access}{suffix}")
    else:
        print("  - none")
    print(f"read resources: {len(contract.resources.reads)}")
    print(f"write resources: {len(contract.resources.writes)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "core-report":
        agent = CoreAgent(
            GitHubReader(),
            central_repository=args.central_repo,
            ref=args.ref,
        )
        snapshot = agent.collect()
        report = agent.render_markdown(snapshot)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(report, end="")

        if snapshot.errors:
            return 2
        if args.strict and snapshot.warnings:
            return 1
        return 0

    if args.command == "agents":
        try:
            registry = _load_registry(args.directory)
        except AgentRegistryError:
            return 2

        if args.agents_command == "list":
            for contract in registry.list():
                status = "enabled" if contract.enabled else "disabled"
                print(
                    f"{contract.id}\t{contract.autonomy}\t{status}\t{contract.name}"
                )
            return 0

        if args.agents_command == "show":
            try:
                contract = registry.get(args.agent_id)
            except AgentRegistryError as exc:
                print(f"Agent registry error: {exc}", file=sys.stderr)
                return 2
            _print_agent(contract)
            return 0

        if args.agents_command == "validate":
            print(f"Valid agent registry: {len(registry.agents)} agent(s)")
            return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
