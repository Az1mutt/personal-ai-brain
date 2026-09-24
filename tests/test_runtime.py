import json
from pathlib import Path

import pytest

from personal_ai_brain import runtime
from personal_ai_brain.core_agent import CoreAgent, CoreSnapshot, Finding
from personal_ai_brain.github_reader import GitHubReadError


def test_validation_findings_are_not_runtime_failure():
    snapshot = CoreSnapshot("2026-09-24", findings=[Finding("error", "state_required_field_missing", "example", "dependencies")])
    assert runtime.classify(snapshot, 0) == ("findings", 0)


@pytest.mark.parametrize("code", ["state_unreadable", "project_map_unreadable"])
def test_source_failure_is_distinct_from_findings(code):
    snapshot = CoreSnapshot("2026-09-24", findings=[Finding("error", code, "example", "unreadable")])
    assert runtime.classify(snapshot, 0) == ("source_read_failure", 3)


def test_cached_read_failure_remains_visible(monkeypatch):
    calls = []
    def fail(*args):
        calls.append(args)
        raise GitHubReadError("HTTP 401")
    reader = runtime.RunReader("fake-token")
    monkeypatch.setattr(reader.reader, "get_text", fail)
    for _ in range(2):
        with pytest.raises(GitHubReadError):
            reader.get_text("owner/repo", "state.yaml")
    assert len(calls) == 1
    assert reader.read_failures == 1
    assert runtime.classify(CoreSnapshot("2026-09-24"), reader.read_failures) == ("source_read_failure", 3)


@pytest.mark.parametrize("error", [TimeoutError("network timeout"), json.JSONDecodeError("invalid", "", 0)])
def test_transport_and_api_response_failures_are_source_failures(monkeypatch, error):
    reader = runtime.RunReader("fake-token")
    def fail(*args):
        raise error
    monkeypatch.setattr(reader.reader, "get_text", fail)
    _, snapshot, proposals = runtime.collect(reader)
    assert runtime.classify(snapshot, reader.read_failures) == ("source_read_failure", 3)
    assert proposals == []


def test_unreadable_project_map_does_not_crash_collector():
    class Reader:
        def get_text(self, *args):
            raise GitHubReadError("HTTP 403")
    _, snapshot, proposals = runtime.collect(Reader())
    assert snapshot.findings[0].code == "project_map_unreadable"
    assert proposals == []


def test_health_requires_current_process_heartbeat(tmp_path):
    beat = tmp_path / "heartbeat.json"
    runtime.atomic_json(tmp_path / "latest.json", {"status": "ok"})
    assert runtime.health(tmp_path, beat, now=100)[0]["runtime"] == "unavailable"
    runtime.atomic_json(beat, {"time": 50})
    assert runtime.health(tmp_path, beat, now=100)[1] == 1
    runtime.atomic_json(beat, {"time": 99})
    assert runtime.health(tmp_path, beat, now=100)[1] == 0


@pytest.mark.parametrize("status,expected", [("findings", 0), ("source_read_failure", 3), ("runtime_failure", 1)])
def test_health_keeps_liveness_separate_from_run_status(tmp_path, status, expected):
    beat = tmp_path / "heartbeat.json"
    runtime.atomic_json(beat, {"time": 100})
    runtime.atomic_json(tmp_path / "latest.json", {"status": status})
    result, code = runtime.health(tmp_path, beat, now=100)
    assert result["runtime"] == "available"
    assert code == expected


def test_missing_credential_is_source_failure_without_secret_output(tmp_path):
    result, code = runtime.run_job("core-snapshot", tmp_path, tmp_path / "absent")
    assert code == 3
    assert result["reason"] == "credential_unavailable"
    assert json.loads((tmp_path / "latest.json").read_text()) == result


def test_unexpected_failure_persists_sanitized_diagnostic(tmp_path, monkeypatch):
    token = tmp_path / "credential"
    token.write_text("do-not-log-this-secret")
    def fail(reader):
        raise RuntimeError("do-not-log-this-secret")
    monkeypatch.setattr(runtime, "collect", fail)
    result, code = runtime.run_job("core-report", tmp_path, token)
    assert code == 1
    assert result["status"] == "runtime_failure"
    assert "do-not-log" not in (tmp_path / "latest.json").read_text()


@pytest.mark.parametrize("command", runtime.COMMANDS)
def test_manual_jobs_persist_outputs_despite_validation_errors(tmp_path, monkeypatch, command):
    token = tmp_path / "credential"
    token.write_text("fake-token")
    snapshot = CoreSnapshot("2026-09-24", findings=[Finding("error", "state_required_field_missing", "example", "dependencies")])
    monkeypatch.setattr(runtime, "collect", lambda reader: (CoreAgent(reader), snapshot, []))
    result, code = runtime.run_job(command, tmp_path, token)
    assert code == 0
    assert result["status"] == "findings"
    directory = Path(result["artifact_dir"])
    assert (directory / "core-snapshot.json").is_file()
    assert (directory / (command + (".md" if command == "core-report" else ".json"))).is_file()
    assert json.loads((directory / "result.json").read_text())["health"]["errors"] == 1


def test_concurrent_run_is_rejected_without_overwriting_last_result(tmp_path):
    with (tmp_path / "run.lock").open("a") as lock:
        runtime.fcntl.flock(lock, runtime.fcntl.LOCK_EX | runtime.fcntl.LOCK_NB)
        result, code = runtime.run_job("core-report", tmp_path, tmp_path / "absent")
    assert (result, code) == ({"status": "busy"}, 5)
    assert not (tmp_path / "latest.json").exists()
