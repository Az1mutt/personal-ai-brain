"""Credential-owning AF_UNIX service. Only the trusted runner UID may call it."""
import json
import multiprocessing
import os
from pathlib import Path
import pwd
import select
import signal
import socket
import time
from . import coding_policy as policy
from .coding_protocol import CodingFailure, encoded, receive, send, require_peer, CODES
from .inference_provider import request, respond
from .inference_usage import Ledger
from .work_contract import parse, unique_object
from .work_store import locked, atomic_json

STATE = Path('/var/lib/personal-ai-brain/inference')
def loop(connection, task, ledger, provider=respond):
    identifier = task['task_id']
    started = False
    until = time.monotonic() + task['deadline_seconds']
    def guard():
        if time.monotonic() >= until:
            raise CodingFailure('model_timeout')
    try:
        ledger.start(task)
        started = True
        history = [{'role': 'user', 'content': json.dumps({'goal': task['goal'],
                   'acceptance_criteria': task['acceptance_criteria'], 'repository': task['repository'],
                   'base_ref': task['base_ref']}, ensure_ascii=True)}]
        for _ in range(policy.MAX_TURNS):
            guard()
            raw = request(history)  # Size/budget admission before reservation/API.
            usage = ledger.reserve(identifier)
            send(connection, {'kind': 'usage', 'usage': usage})
            response = provider(raw)  # Exactly one attempt, never automatic retry.
            usage = ledger.usage(identifier, response.get('usage'))
            send(connection, {'kind': 'usage', 'usage': usage})
            output = response['output']
            calls = [item for item in output if isinstance(item, dict) and item.get('type') == 'function_call']
            if len(calls) > 1 or any(not isinstance(item, dict) or item.get('type') not in {'reasoning', 'message', 'function_call'} for item in output):
                raise CodingFailure('model_invalid_response')
            # Reasoning items may be necessary on the next turn; RAM only, never logs/artifacts.
            history.extend(output)
            if calls:
                call = calls[0]
                if call.get('name') not in {t['name'] for t in policy.tools()} or not isinstance(call.get('call_id'), str):
                    raise CodingFailure('model_invalid_response')
                args = json.loads(call['arguments'], object_pairs_hook=unique_object)
                send(connection, {'kind': 'tool', 'name': call['name'], 'arguments': args})
                answer = receive(connection, guard)
                if set(answer) != {'kind', 'result'} or answer['kind'] != 'tool_result':
                    raise CodingFailure('model_invalid_response')
                history.append({'type': 'function_call_output', 'call_id': call['call_id'],
                                'output': encoded(answer['result']).decode()})
                continue
            texts = [c['text'] for item in output if item.get('type') == 'message'
                     for c in item.get('content', []) if c.get('type') == 'output_text']
            if len(texts) != 1 or len(texts[0]) > 2048:
                raise CodingFailure('model_invalid_response')
            final = json.loads(texts[0], object_pairs_hook=unique_object)
            if set(final) != {'summary'} or not isinstance(final['summary'], str) or len(final['summary']) > 1000:
                raise CodingFailure('model_invalid_response')
            # Do not retain untrusted model prose (could echo secrets/reasoning).
            usage = ledger.finish(identifier, 'reasoning_completed')
            send(connection, {'kind': 'complete', 'usage': usage})
            return
        raise CodingFailure('model_budget_exceeded')
    except Exception as error:
        import traceback
        frames = traceback.extract_tb(error.__traceback__)
        last = frames[-1]
        # Source locations and exception class only; never messages, locals or provider payloads.
        safe_module = Path(last.filename).name
        if not safe_module.startswith(('inference_', 'coding_', 'work_')): safe_module = 'stdlib'
        print('broker_failure ' + type(error).__name__ + ' ' + safe_module + ':' + str(last.lineno), flush=True)
        code = str(error) if isinstance(error, CodingFailure) and str(error) in CODES else 'model_invalid_response'
        usage = ledger.finish(identifier, code) if started else None
        try: send(connection, {'kind': 'failure', 'code': code, 'usage': usage})
        except OSError: pass

def child(connection, task, config):
    os.setsid()
    # SCM_RIGHTS preserves O_NONBLOCK, but multiprocessing rebuilds a Python
    # socket with timeout=None. Restore the timeout in the receiving process.
    connection.settimeout(0.2)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        if config['provider'] == 'acceptance':
            from .inference_acceptance import Provider
            provider = Provider(config['scenario'])
        elif config['provider'] == 'openai': provider = respond
        else:
            send(connection, {'kind': 'failure', 'code': 'model_auth_failed', 'usage': None})
            return
        loop(connection, task, Ledger(STATE, config['provider']), provider)
    finally: connection.close()

def supervise(process, connection, until, stopping):
    try:
        while process.is_alive() and not stopping() and time.monotonic() < until:
            if select.select([connection], [], [], 0.1)[0]:
                try:
                    if connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT) == b'': break
                except (BlockingIOError, socket.timeout):
                    continue
                time.sleep(0.025)
    finally:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        if process.is_alive(): process.terminate()
        process.join(timeout=1)
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        if process.is_alive(): process.kill(); process.join(timeout=1)

def serve():
    os.umask(0o077)
    if os.geteuid() == 0:
        raise RuntimeError('non_root_required')
    expected = pwd.getpwnam('pab-builder').pw_uid
    ledger = Ledger(STATE)
    from .inference_config import read
    if read()['provider'] == 'acceptance':
        from .inference_probe import checks
        evidence = checks()
        atomic_json(STATE / 'security-evidence', evidence)
        if not all(evidence.values()): raise RuntimeError('broker_boundary_failed')
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, stop)
    with locked(STATE / 'service.lock', nonblocking=True):
        ledger.recover()
        path = Path(policy.SOCKET)
        path.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            os.chmod(path, 0o660)
            listener.listen(1)
            listener.settimeout(0.2)
            while not stopped:
                try: connection, _ = listener.accept()
                except socket.timeout: continue
                process = None
                try:
                    require_peer(connection, expected)
                    connection.settimeout(0.2)
                    until = time.monotonic() + 3
                    def admission_guard():
                        if stopped or time.monotonic() >= until: raise CodingFailure('interrupted')
                    message = receive(connection, admission_guard)
                    if set(message) != {'schema_version', 'task'} or message['schema_version'] != '0.1': continue
                    task = parse(encoded(message['task']))
                    if task['task_type'] != policy.TYPE or task['base_ref'] != policy.BASE: continue
                    from .inference_config import read
                    config = read()
                    # Spawn avoids inheriting listener/other connections into the paid worker.
                    process = multiprocessing.get_context('spawn').Process(target=child, args=(connection, task, config))
                    process.start()
                    until = time.monotonic() + task['deadline_seconds']
                    supervise(process, connection, until, lambda: stopped)
                    # EOF/cancel/deadline interrupts an in-flight HTTP worker, not just its wait.
                except (OSError, ValueError, CodingFailure):
                    pass
                finally:
                    if process is not None:
                        if process.is_alive(): process.terminate()
                        process.join(timeout=1)
                        if process.is_alive(): process.kill(); process.join(timeout=1)
                        ledger.recover()
                    connection.close()
        path.unlink(missing_ok=True)

if __name__ == '__main__':
    try: serve()
    except Exception: raise SystemExit('inference_broker_unavailable') from None
