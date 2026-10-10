from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import errno
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest

from personal_ai_brain import work_contract as contract
from personal_ai_brain import work_store as storage
from personal_ai_brain import work_sandbox as sandbox
from personal_ai_brain.work_runner import Runner

BASE = 'a' * 40

def request(**changes):
    value = {'schema_version': '0.1', 'task_id': str(uuid.uuid4()),
             'task_type': contract.TASK_TYPE, 'repository': contract.REPOSITORY,
             'base_ref': BASE, 'goal': contract.GOAL, 'acceptance_criteria': contract.CRITERIA,
             'requested_at': contract.timestamp(), 'deadline_seconds': 20}
    return {**value, **changes}

def parsed(**changes):
    return contract.parse(json.dumps(request(**changes)).encode())

@pytest.mark.parametrize('change', [
    {'schema_version': '1.0'}, {'task_type': 'shell'}, {'repository': 'Other/repo'},
    {'base_ref': 'main'}, {'task_id': '../../escape'}, {'deadline_seconds': True},
    {'deadline_seconds': 0}, {'deadline_seconds': 61}, {'command': 'id'},
    {'goal': 'Run arbitrary code'}, {'acceptance_criteria': ['anything']},
    {'requested_at': '2026-10-10T00:00:00'},
])
def test_contract_rejects_unsafe_or_ambiguous_payloads(change):
    with pytest.raises(contract.Rejected): parsed(**change)

def test_duplicate_json_keys_and_size():
    with pytest.raises(contract.Rejected): contract.parse(b'{"schema_version":"0.1","schema_version":"0.1"}')
    with pytest.raises(contract.Rejected): contract.parse(b' ' * 8193)
    with pytest.raises(contract.Rejected): contract.parse(b'{"x":NaN}')

def test_duplicates_conflicts_and_stale_duplicate(tmp_path):
    store = storage.Store(tmp_path)
    value = parsed()
    first, created = store.submit(value, BASE)
    assert created
    again, created = storage.Store(tmp_path).submit(value, BASE)
    assert not created and again == first
    with pytest.raises(contract.Rejected, match='conflict'):
        store.submit({**value, 'deadline_seconds': 19}, BASE)
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    with pytest.raises(contract.Rejected, match='stale'):
        store.submit(parsed(requested_at=old), BASE)
    with pytest.raises(contract.Rejected, match='base_not'):
        store.submit(parsed(base_ref='b' * 40), BASE)

def test_concurrent_admission_executes_once(tmp_path):
    value = parsed()
    storage.Store(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: storage.Store(tmp_path).submit(value, BASE), range(4)))
    assert sum(created for _, created in results) == 1

def make_runner(tmp_path, monkeypatch, executor=None):
    store = storage.Store(tmp_path)
    policy = {'base_ref': BASE, 'min_free_bytes': 8388608}
    runner = Runner(store, policy, executor=executor or (lambda *args: ('succeeded', 'fixture_completed')))
    def prepare(record, deadline):
        path = store.workspaces / record['task_id'] / 'repo'
        path.mkdir(parents=True)
        return path
    monkeypatch.setattr(runner, 'prepare', prepare)
    return store, runner

def test_state_history_and_no_rerun(tmp_path, monkeypatch):
    store, runner = make_runner(tmp_path, monkeypatch)
    value = parsed()
    store.submit(value, BASE)
    assert runner.tick()
    record = store.load(value['task_id'])
    assert record['status'] == 'succeeded' and record['attempts'] == 1
    assert [event['status'] for event in record['history']] == ['submitted', 'reserved', 'running', 'succeeded']
    runner.recovery()
    assert not runner.tick()
    assert json.loads((store.audit / value['task_id'] / 'result.json').read_text()) == record

def test_service_stop_wins_child_exit_race(tmp_path, monkeypatch):
    store, runner = make_runner(tmp_path, monkeypatch)
    stopped = False
    runner.stopping = lambda: stopped
    def executor(*args):
        nonlocal stopped
        stopped = True
        return 'failed', 'sandbox_failed'
    runner.executor = executor
    value = parsed()
    store.submit(value, BASE)
    runner.tick()
    record = store.load(value['task_id'])
    assert record['status'] == 'interrupted'
    assert record['history'][-1]['code'] == 'service_stopping'

@pytest.mark.parametrize('state', ['reserved', 'running'])
def test_restart_interrupts_without_replay(tmp_path, monkeypatch, state):
    store, runner = make_runner(tmp_path, monkeypatch)
    value = parsed()
    store.submit(value, BASE)
    store.transition(value['task_id'], 'reserved', 'test', attempts=1)
    if state == 'running': store.transition(value['task_id'], state, 'test')
    runner.recovery()
    record = store.load(value['task_id'])
    assert record['status'] == 'interrupted' and record['attempts'] == 1
    assert not runner.tick()
    assert not store.submit(value, BASE)[1]

def test_cancel_before_reserve_and_at_completion(tmp_path, monkeypatch):
    store, runner = make_runner(tmp_path, monkeypatch)
    value = parsed()
    store.submit(value, BASE)
    store.cancel(value['task_id'])
    assert store.transition(value['task_id'], 'reserved', 'race')['status'] == 'cancelled'
    assert not runner.tick()
    other = parsed()
    store.submit(other, BASE)
    def execute(*args):
        store.cancel(other['task_id'])
        return 'succeeded', 'fixture_completed'
    runner.executor = execute
    runner.tick()
    assert store.load(other['task_id'])['status'] == 'cancelled'

def test_storage_preflight_blocks_without_execution(tmp_path, monkeypatch):
    store, runner = make_runner(tmp_path, monkeypatch)
    runner.policy['min_free_bytes'] = 2 ** 63
    value = parsed()
    store.submit(value, BASE)
    runner.tick()
    assert store.load(value['task_id'])['status'] == 'blocked'
    assert not (store.workspaces / value['task_id']).exists()
    assert (store.audit / value['task_id'] / 'result.json').exists()

def test_enospc_releases_reserve_and_records_failure(tmp_path, monkeypatch):
    def execute(*args): raise OSError(errno.ENOSPC, 'injected')
    store, runner = make_runner(tmp_path, monkeypatch, execute)
    value = parsed()
    store.submit(value, BASE)
    runner.tick()
    record = store.load(value['task_id'])
    assert record['status'] == 'failed'
    assert record['history'][-1]['code'] == 'storage_error'
    assert not (store.audit / value['task_id'] / 'emergency.reserve').exists()
    assert (store.audit / value['task_id'] / 'execution.log').read_text().startswith('storage_error')
    assert (store.workspaces / value['task_id']).is_dir()

def test_failed_terminal_commit_never_reexecutes(tmp_path, monkeypatch):
    store, runner = make_runner(tmp_path, monkeypatch)
    value = parsed()
    store.submit(value, BASE)
    original = storage.atomic_json
    def fail_once(path, data):
        if path == store.path(value['task_id']) and data['status'] == 'succeeded':
            raise OSError(errno.ENOSPC, 'injected terminal commit failure')
        return original(path, data)
    monkeypatch.setattr(storage, 'atomic_json', fail_once)
    runner.tick()
    assert store.load(value['task_id'])['status'] == 'failed'
    assert not runner.tick()

def test_corrupt_state_and_orphan_admission_fail_closed(tmp_path):
    store = storage.Store(tmp_path)
    value = parsed()
    store.submit(value, BASE)
    store.path(value['task_id']).write_text('{')
    with pytest.raises(ValueError): store.submit(value, BASE)
    other = parsed()
    (store.audit / other['task_id']).mkdir()
    with pytest.raises(FileExistsError): store.submit(other, BASE)

def test_single_worker_lock(tmp_path):
    with storage.locked(tmp_path / 'worker.lock'):
        with pytest.raises(BlockingIOError):
            with storage.locked(tmp_path / 'worker.lock', nonblocking=True): pass

def exercise_collector(tmp_path, monkeypatch, code, seconds=2):
    workspace, artifacts = tmp_path / 'repo', tmp_path / 'audit'
    workspace.mkdir(exist_ok=True)
    artifacts.mkdir(exist_ok=True)
    # This test replaces the sandbox with a harmless subprocess to exercise only
    # supervisor bounds/collection. It is not claimed as isolation acceptance.
    monkeypatch.setattr(sandbox, 'command', lambda *args: ['/usr/bin/python3', '-c', code])
    return sandbox.execute(workspace, artifacts, time.monotonic() + seconds,
                           lambda: False, lambda: False, Path('/unused'))

def test_deadline_cleans_child_and_retains_evidence(tmp_path, monkeypatch):
    seen = []
    original = sandbox.subprocess.Popen
    def capture(*args, **kwargs):
        process = original(*args, **kwargs)
        seen.append(process)
        return process
    monkeypatch.setattr(sandbox.subprocess, 'Popen', capture)
    result = exercise_collector(tmp_path, monkeypatch, 'import time; time.sleep(5)', seconds=0.1)
    assert result == ('failed', 'deadline_exceeded') and seen[0].poll() is not None
    assert json.loads((tmp_path / 'audit/test-result.json').read_text())['code'] == 'deadline_exceeded'

def test_output_limit(tmp_path, monkeypatch):
    result = exercise_collector(tmp_path, monkeypatch, 'print("x" * 20000)')
    assert result == ('failed', 'output_limit')
    assert (tmp_path / 'audit/execution.log').stat().st_size <= 16384

def test_collector_rejects_symlink(tmp_path, monkeypatch):
    workspace = tmp_path / 'repo'
    workspace.mkdir()
    outside = tmp_path / 'outside'
    outside.write_bytes(sandbox.CONTENT)
    (workspace / 'builder-fixture.txt').symlink_to(outside)
    report = {'ok': True, 'fixture': 'fixture.patch-test.v1', 'checks': dict.fromkeys(sandbox.CHECKS, True)}
    result = exercise_collector(tmp_path, monkeypatch, 'print(' + repr(json.dumps(report)) + ')')
    assert result == ('failed', 'artifact_validation_failed')
