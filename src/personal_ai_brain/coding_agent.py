"""Provider-neutral runner interface; filesystem authority stays in the runner."""
import pwd
import socket
from typing import Protocol
from . import coding_policy as policy
from .coding_protocol import CodingFailure, receive, send, require_peer, CODES

class CodingAgent(Protocol):
    def run(self, task, workspace, guard, progress): ...

class BrokerAgent:
    def run(self, task, workspace, guard, progress):
        self.operations = []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.2)
            connection.connect(policy.SOCKET)
            require_peer(connection, pwd.getpwnam('pab-inference').pw_uid)
            send(connection, {'schema_version': '0.1', 'task': task})
            for _ in range(policy.MAX_TURNS * 3 + 1):
                guard()
                message = receive(connection, guard)
                kind = message.get('kind')
                if kind == 'usage':
                    progress(message['usage'])
                elif kind == 'tool':
                    self.operations.append(message['name'])
                    try: result = workspace.invoke(message['name'], message['arguments'])
                    except (OSError, UnicodeError, ValueError): raise CodingFailure('patch_rejected') from None
                    guard()
                    send(connection, {'kind': 'tool_result', 'result': result})
                elif kind == 'complete':
                    progress(message['usage'])
                    return
                elif kind == 'failure' and message.get('code') in CODES:
                    if message.get('usage') is not None: progress(message['usage'])
                    raise CodingFailure(message['code'])
                else:
                    raise CodingFailure('model_invalid_response')
            raise CodingFailure('model_budget_exceeded')
