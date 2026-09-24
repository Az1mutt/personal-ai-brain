"""Manual read-only jobs in a persistent, network-listener-free container."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import threading
import time
import uuid

from personal_ai_brain.agent_registry import AgentRegistry
from personal_ai_brain.core_agent import CoreAgent, Finding
from personal_ai_brain.github_reader import GitHubReader, GitHubReadError
from personal_ai_brain.machine_snapshot import build_machine_snapshot
from personal_ai_brain.rollup_proposal import RollupProposalEngine
from personal_ai_brain.state_integrity import StateIntegrityChecker
from personal_ai_brain.state_quality import ProjectStateQualityChecker

COMMANDS = ("core-report", "rollup-proposals", "core-snapshot")
STATE = Path(os.environ.get("PAB_STATE_DIR", "/state"))
HEARTBEAT = Path(os.environ.get("PAB_HEARTBEAT", "/tmp/pab-heartbeat.json"))
TOKEN_FILE = Path(os.environ.get("GITHUB_TOKEN_FILE", "/run/secrets/github_token"))
SOURCE_CODES = {"project_map_unreadable", "state_unreadable"}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class RunReader:
    """One consistent, read-only source view per manual run, including failures."""
    def __init__(self, token):
        self.reader = GitHubReader(token=token)
        self.cache = {}
        self.read_failures = 0

    def get_text(self, repository, path, ref="main"):
        key = (repository, path, ref)
        if key not in self.cache:
            try:
                self.cache[key] = self.reader.get_text(repository, path, ref)
            except GitHubReadError as error:
                self.read_failures += 1
                self.cache[key] = error
        value = self.cache[key]
        if isinstance(value, Exception):
            raise value
        return value


def collect(reader):
    agent = CoreAgent(reader)
    snapshot = agent.collect()
    # A missing/malformed project map is already an explicit source finding.
    if any(f.code in {"project_map_unreadable", "project_map_invalid"} for f in snapshot.findings):
        return agent, snapshot, []
    for checker in (StateIntegrityChecker(reader), ProjectStateQualityChecker(reader)):
        snapshot.findings.extend(Finding(f.severity, f.code, f.subject, f.message) for f in checker.check().findings)
    return agent, snapshot, RollupProposalEngine(reader).propose()


def classify(snapshot, read_failures):
    if read_failures or any(f.code in SOURCE_CODES for f in snapshot.findings):
        return "source_read_failure", 3
    if snapshot.findings:
        return "findings", 0
    return "ok", 0


def run_job(command, state=STATE, token_file=TOKEN_FILE, reader_factory=RunReader):
    """No writes to sources; outputs are private local runtime artifacts only."""
    state.mkdir(parents=True, exist_ok=True)
    with (state / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "busy"}, 5
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        directory = state / "runs" / run_id
        directory.mkdir(parents=True)
        result = {"run_id": run_id, "command": command, "started_at": timestamp()}
        try:
            try:
                token = token_file.read_text().strip()
                if not token:
                    raise OSError("empty credential")
            except OSError:
                result.update(status="source_read_failure", reason="credential_unavailable")
                exit_code = 3
            else:
                reader = reader_factory(token)
                agent, snapshot, proposals = collect(reader)
                status, exit_code = classify(snapshot, reader.read_failures)
                machine = build_machine_snapshot(snapshot, proposals)
                atomic_json(directory / "core-snapshot.json", machine)
                if command == "core-report":
                    (directory / "core-report.md").write_text(agent.render_markdown(snapshot), encoding="utf-8")
                elif command == "rollup-proposals":
                    atomic_json(directory / "rollup-proposals.json", {"proposal_count": len(proposals), "proposals": [p.to_dict() for p in proposals]})
                result.update(status=status, health=machine["health"], source_read_failures=reader.read_failures)
        except Exception as error:
            # Never persist arbitrary exception messages, which can contain credentials.
            result.update(status="runtime_failure", error_type=type(error).__name__)
            exit_code = 1
        result.update(finished_at=timestamp(), exit_code=exit_code, artifact_dir=str(directory))
        atomic_json(directory / "result.json", result)
        atomic_json(state / "latest.json", result)
        return result, exit_code


def health(state=STATE, heartbeat=HEARTBEAT, now=None):
    now = time.time() if now is None else now
    try:
        beat = json.loads(heartbeat.read_text())
        if not 0 <= now - beat["time"] <= 30:
            raise ValueError("stale heartbeat")
    except (OSError, ValueError, KeyError, TypeError):
        return {"runtime": "unavailable"}, 1
    try:
        last = json.loads((state / "latest.json").read_text())
    except FileNotFoundError:
        return {"runtime": "available", "last_run": {"status": "not_checked"}}, 4
    except (OSError, ValueError):
        return {"runtime": "available", "last_run": {"status": "runtime_failure", "reason": "invalid_status_file"}}, 1
    status = last.get("status") if isinstance(last, dict) else None
    code = {"ok": 0, "findings": 0, "source_read_failure": 3, "runtime_failure": 1}.get(status, 1)
    return {"runtime": "available", "last_run": last, "source_check": "last_manual_run_only"}, code


def serve(state=STATE, heartbeat=HEARTBEAT):
    state.mkdir(parents=True, exist_ok=True)
    AgentRegistry.from_directory(Path("agents"))
    logger = logging.getLogger("personal-ai-brain.runtime")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(state / "service.log", maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logger.info("runtime_started; manual read-only jobs enabled; no scheduler")
    print("Personal AI Brain runtime ready (manual, read-only).", flush=True)
    try:
        while not stop.is_set():
            atomic_json(heartbeat, {"time": time.time()})
            stop.wait(5)
    finally:
        heartbeat.unlink(missing_ok=True)
        logger.info("runtime_stopped")


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("serve")
    check = sub.add_parser("health")
    check.add_argument("--liveness", action="store_true")
    job = sub.add_parser("run")
    job.add_argument("command", choices=COMMANDS)
    args = parser.parse_args(argv)
    if args.action == "serve":
        serve()
        return 0
    if args.action == "health":
        result, code = health()
        if args.liveness:
            return 0 if result["runtime"] == "available" else 1
    else:
        live, _ = health()
        if live["runtime"] != "available":
            print(json.dumps(live))
            return 1
        result, code = run_job(args.command)
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
