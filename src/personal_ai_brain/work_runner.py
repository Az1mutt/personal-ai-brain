"""Offline, single-worker Work Runner v0.1. Administrative local CLI only."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from .work_contract import Rejected, REPOSITORY, parse, timestamp
from .work_store import Store, TERMINAL, atomic_json, locked
from .work_sandbox import execute, kill_tree

ROOT = Path('/var/lib/personal-ai-brain/builder')
PROFILE = Path('/etc/personal-ai-brain/builder/profile.json')

def profile(path=PROFILE):
    value = json.loads(path.read_bytes())
    if (set(value) != {'schema_version', 'repository', 'base_ref', 'seed', 'min_free_bytes'}
            or value['schema_version'] != '0.1' or value['repository'] != REPOSITORY
            or not re.fullmatch('[0-9a-f]{40}', value['base_ref'])
            or value['seed'] != '/opt/personal-ai-brain/builder/repository.git'
            or type(value['min_free_bytes']) is not int or value['min_free_bytes'] < 8388608):
        raise ValueError('invalid_operator_profile')
    return value

class Abort(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code

class Runner:
    def __init__(self, store, policy, stopping=lambda: False, executor=execute):
        self.store, self.policy, self.stopping, self.executor = store, policy, stopping, executor

    def recovery(self):
        # systemd KillMode=control-group clears children before restarting us.
        for record in self.store.records():
            if record['status'] in {'reserved', 'running'}:
                identifier = record['task_id']
                atomic_json(self.store.audit / identifier / 'test-result.json',
                            {'status': 'not_completed', 'code': 'interrupted_no_retry'})
                self.store.transition(identifier, 'interrupted', 'interrupted_no_retry')

    def guard(self, identifier, deadline):
        if self.stopping():
            raise Abort('interrupted', 'service_stopping')
        if self.store.load(identifier)['cancel_requested']:
            raise Abort('cancelled', 'cancellation_requested')
        if time.monotonic() >= deadline:
            raise Abort('failed', 'deadline_exceeded')

    def git(self, identifier, deadline, *arguments):
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LC_ALL': 'C',
               'GIT_TERMINAL_PROMPT': '0'}
        process = subprocess.Popen(['/usr/bin/git', *arguments], env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True, close_fds=True)
        try:
            while process.poll() is None:
                self.guard(identifier, deadline)
                time.sleep(0.025)
            self.guard(identifier, deadline)
            if process.returncode:
                raise Abort('failed', 'workspace_preparation_failed')
        finally:
            kill_tree(process)

    def prepare(self, record, deadline):
        identifier = record['task_id']
        parent = self.store.workspaces / identifier
        parent.mkdir(mode=0o700)
        workspace = parent / 'repo'
        self.git(identifier, deadline, 'clone', '--no-hardlinks', '--no-local', '--no-checkout',
                 self.policy['seed'], str(workspace))
        self.git(identifier, deadline, '-C', str(workspace), 'checkout', '-b',
                 'builder/' + identifier, record['request']['base_ref'])
        self.git(identifier, deadline, '-C', str(workspace), 'remote', 'remove', 'origin')
        # Only the approved fixture can run, never repo scripts/config/hooks.
        if ((workspace / '.gitmodules').exists() or (workspace / 'builder-fixture.txt').exists()
                or any(p.is_file() and os.access(p, os.X_OK) and not p.name.endswith('.sample')
                       for p in (workspace / '.git/hooks').glob('*'))):
            raise Abort('blocked', 'unsupported_repository_content')
        return workspace

    def tick(self):
        candidates = [r for r in self.store.records() if r['status'] == 'submitted']
        if not candidates:
            return False
        record = min(candidates, key=lambda r: r['history'][0]['at'])
        identifier = record['task_id']
        artifacts = self.store.audit / identifier
        deadline = time.monotonic() + record['request']['deadline_seconds']
        try:
            record = self.store.transition(identifier, 'reserved', 'worker_reserved',
                                           attempts=1, base_sha=record['request']['base_ref'],
                                           branch='builder/' + identifier)
            if record['status'] in TERMINAL:
                return True
            if shutil.disk_usage(self.store.root).free < self.policy['min_free_bytes']:
                self.store.transition(identifier, 'blocked', 'insufficient_storage')
                return True
            workspace = self.prepare(record, deadline)
            self.guard(identifier, deadline)
            record = self.store.transition(identifier, 'running', 'sandbox_starting', started_at=timestamp())
            if record['status'] in TERMINAL:
                return True
            status, code = self.executor(workspace, artifacts, deadline,
                                         lambda: self.store.load(identifier)['cancel_requested'],
                                         self.stopping, Path(__file__).with_name('work_fixture.py'))
            if self.stopping():
                status, code = 'interrupted', 'service_stopping'
            self.store.transition(identifier, status, code)
        except Abort as error:
            atomic_json(artifacts / 'test-result.json', {'status': 'not_completed', 'code': error.code})
            self.store.transition(identifier, error.status, error.code)
        except OSError:
            self.store.storage_failure(identifier)
        except Exception:
            # Fixed diagnostics only, preserve workspace and prior evidence.
            atomic_json(artifacts / 'test-result.json', {'status': 'not_completed', 'code': 'runner_error'})
            self.store.transition(identifier, 'failed', 'runner_error')
        return True

def serve(store, policy):
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    with locked(store.state / 'worker.lock', nonblocking=True):
        runner = Runner(store, policy, stopping=lambda: stopped)
        runner.recovery()
        print('work_runner_ready', flush=True)
        while not stopped:
            if not runner.tick():
                time.sleep(0.1)

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['serve', 'submit', 'status', 'cancel'])
    parser.add_argument('task_id', nargs='?')
    arguments = parser.parse_args()
    try:
        store = Store(ROOT)
        policy = profile()
        if arguments.action == 'serve':
            serve(store, policy)
            return 0
        if arguments.action == 'submit':
            request = parse(sys.stdin.buffer.read(8193))
            record, created = store.submit(request, policy['base_ref'])
            print(json.dumps({'task_id': record['task_id'], 'status': record['status'],
                              'created': created, 'payload_hash': record['payload_hash']}))
        elif arguments.action == 'cancel':
            print(json.dumps(store.cancel(arguments.task_id)))
        else:
            record = store.load(arguments.task_id)
            if record is None:
                raise Rejected('unknown_task')
            print(json.dumps(record))
        return 0
    except Rejected as error:
        print(json.dumps({'error': str(error)}))
        return 2
    except Exception:
        print('{"error":"runner_unavailable_or_state_error"}', flush=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
