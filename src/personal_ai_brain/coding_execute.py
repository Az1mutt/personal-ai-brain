"""Model proposal, deterministic patch validation, then independent offline tests."""
import json
import os
from pathlib import Path
import resource
import selectors
import subprocess
from .coding_agent import BrokerAgent
from .coding_protocol import CodingFailure
from .coding_workspace import Workspace
from .coding_policy import MODEL
from .work_contract import timestamp
from .work_store import atomic_bytes, atomic_json
from .work_sandbox import command, kill_tree, limits

def test_limits():
    limits()
    resource.setrlimit(resource.RLIMIT_AS, (536870912, 536870912))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))

def offline_tests(workspace, guard):
    process = subprocess.Popen(command(workspace, Path(__file__).with_name('coding_test.py')),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, close_fds=True,
        start_new_session=True, preexec_fn=test_limits)
    output = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                guard()
                for key, _ in selector.select(0.05):
                    chunk = os.read(key.fd, 4096)
                    if not chunk: selector.unregister(key.fd)
                    else:
                        output.extend(chunk)
                        if len(output) > 4096: raise CodingFailure('tests_failed')
                if process.poll() is not None and not selector.get_map(): break
        guard()
        if process.returncode != 0: raise CodingFailure('tests_failed')
        try: report = json.loads(output)
        except ValueError: raise CodingFailure('tests_failed') from None
        if report != {'schema_version': '0.1', 'profile': 'normalize-label-v1', 'passed': 13}:
            raise CodingFailure('tests_failed')
        return report
    finally:
        kill_tree(process)
        process.stdout.close()

def execute(task, root, artifacts, guard, agent=None, tester=offline_tests):
    agent = agent or BrokerAgent()
    value = {'schema_version': '0.1', 'status': 'running', 'usage': None,
             'profile': 'normalize-label-v1', 'model_declares_success': False,
             'provider': 'openai-responses-v1', 'model': MODEL, 'started_at': timestamp()}
    workspace = None
    def progress(usage):
        value['usage'] = usage
        atomic_json(artifacts / 'agent-result.json', value)
    atomic_json(artifacts / 'agent-result.json', value)
    atomic_bytes(artifacts / 'agent.log', b'model_phase_started\n')
    try:
        guard()
        workspace = Workspace(root)
        agent.run(task, workspace, guard, progress)
        guard()
        changed, patch = workspace.validate()
        atomic_bytes(artifacts / 'patch.diff', patch.encode())
        before = workspace.snapshot()
        report = tester(root, guard)
        guard()
        if workspace.snapshot() != before:
            raise CodingFailure('deterministic_validation_failed')
        atomic_json(artifacts / 'test-result.json', {'status': 'passed', **report})
        import hashlib
        value.update(status='completed', code='deterministically_verified', finished_at=timestamp(),
                     changed_files=changed, patch_sha256=hashlib.sha256(patch.encode()).hexdigest())
        atomic_json(artifacts / 'agent-result.json', value)
        atomic_bytes(artifacts / 'agent.log', b'model_phase_ended\ndeterministic_validation_passed\noffline_tests_passed\n')
        return 'succeeded', 'coding_completed'
    except BaseException as error:
        from .work_runner import Abort
        if isinstance(error, Abort):
            status, code = error.status, error.code
        elif isinstance(error, CodingFailure):
            status, code = 'failed', str(error)
        elif isinstance(error, (OSError, KeyError)):
            status, code = 'failed', 'model_network_failed'
        else:
            status, code = 'failed', 'deterministic_validation_failed'
        value.update(status=status, code=code, finished_at=timestamp())
        atomic_json(artifacts / 'agent-result.json', value)
        atomic_json(artifacts / 'test-result.json', {'status': 'not_completed', 'code': code})
        atomic_bytes(artifacts / 'agent.log', (code + '\n').encode())
        return status, code
    finally:
        if workspace is not None: workspace.close()
