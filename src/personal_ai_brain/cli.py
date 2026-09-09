from __future__ import annotations

import argparse
import sys
from pathlib import Path

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

    return parser


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

    return 2


if __name__ == "__main__":
    sys.exit(main())
