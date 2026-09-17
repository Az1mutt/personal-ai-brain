from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from personal_ai_brain.agent_registry import AgentRegistry, AgentRegistryError
from personal_ai_brain.core_agent import CoreAgent, Finding
from personal_ai_brain.github_reader import GitHubReader
from personal_ai_brain.machine_snapshot import build_machine_snapshot
from personal_ai_brain.rollup_proposal import RollupProposalEngine
from personal_ai_brain.state_integrity import StateIntegrityChecker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal-ai-brain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser(
        "core-report",
        help="Read Project OS state from GitHub and render a Core report.",
    )
    _add_core_source_arguments(report)
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

    snapshot = subparsers.add_parser(
        "core-snapshot",
        help="Render machine-readable Core state for automation/orchestration.",
    )
    _add_core_source_arguments(snapshot)
    _add_structured_output_arguments(snapshot, default_format="json")

    proposals = subparsers.add_parser(
        "rollup-proposals",
        help="Generate deterministic read-only project rollup proposals.",
    )
    _add_core_source_arguments(proposals)
    _add_structured_output_arguments(proposals, default_format="yaml")

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


def _add_core_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--central-repo",
        default="Az1mutt/personal-project-brain",
        help="Repository containing core/project-map.yaml.",
    )
    parser.add_argument("--ref", default="main")


def _add_structured_output_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_format: str,
) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "yaml"),
        default=default_format,
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. Prints to stdout when omitted.",
    )


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


def _collect_core(
    *,
    central_repo: str,
    ref: str,
):
    reader = GitHubReader()
    agent = CoreAgent(
        reader,
        central_repository=central_repo,
        ref=ref,
    )
    snapshot = agent.collect()

    integrity = StateIntegrityChecker(
        reader,
        central_repository=central_repo,
        ref=ref,
    ).check()
    snapshot.findings.extend(
        Finding(
            finding.severity,
            finding.code,
            finding.subject,
            finding.message,
        )
        for finding in integrity.findings
    )

    proposals = RollupProposalEngine(
        reader,
        central_repository=central_repo,
        ref=ref,
    ).propose()
    return agent, snapshot, proposals


def _render_structured(value: Any, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(value, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True)


def _write_or_print(text: str, output: Path | None) -> None:
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"Wrote {output}")
    else:
        print(text, end="")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "core-report":
        agent, snapshot, _ = _collect_core(
            central_repo=args.central_repo,
            ref=args.ref,
        )
        report = agent.render_markdown(snapshot)
        _write_or_print(report, args.output)

        if snapshot.errors:
            return 2
        if args.strict and snapshot.warnings:
            return 1
        return 0

    if args.command == "core-snapshot":
        _, snapshot, proposals = _collect_core(
            central_repo=args.central_repo,
            ref=args.ref,
        )
        payload = build_machine_snapshot(snapshot, proposals)
        _write_or_print(_render_structured(payload, args.format), args.output)
        return 2 if snapshot.errors else 0

    if args.command == "rollup-proposals":
        reader = GitHubReader()
        proposals = RollupProposalEngine(
            reader,
            central_repository=args.central_repo,
            ref=args.ref,
        ).propose()
        payload = {
            "schema_version": "0.1",
            "proposal_count": len(proposals),
            "proposals": [proposal.to_dict() for proposal in proposals],
        }
        _write_or_print(_render_structured(payload, args.format), args.output)
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
