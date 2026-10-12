"""Deterministic acceptance adapter. Selected only by root-owned operator config."""
import json
import os
import subprocess
import time
from .coding_policy import TARGET
from .coding_protocol import CodingFailure

CODE = ('def normalize_label(value):\n'
        '    if not isinstance(value, str):\n'
        '        raise TypeError("string required")\n'
        '    return " ".join(value.split()).casefold()\n')

class Provider:
    def __init__(self, scenario):
        self.scenario = scenario

    def __call__(self, raw):
        body = json.loads(raw)
        step = sum(item.get('type') == 'function_call_output' for item in body['input'])
        if self.scenario == 'failure': raise CodingFailure('model_rate_limited')
        if self.scenario == 'malformed': return {'usage': {'input_tokens': 1, 'output_tokens': 1}, 'output': [42]}
        if self.scenario == 'timeout':
            # A trusted test-only child verifies group cleanup; no caller command.
            subprocess.Popen(['/usr/bin/sleep', '300'], close_fds=True)
            time.sleep(300)
        if self.scenario == 'ipc_drop': os._exit(0)
        operations = [('list_files', {}), ('read_file', {'path': 'AGENTS.md'}),
                      ('search_text', {'text': 'Python'}), ('apply_patch', {'path': TARGET, 'old': '',
                       'new': CODE if self.scenario != 'tests_failed' else 'def normalize_label(value):\n    return value\n'})]
        if self.scenario == 'budget': name, args = 'list_files', {}
        elif self.scenario == 'escape': name, args = 'read_file', {'path': '../other-task/secret'}
        elif step < len(operations): name, args = operations[step]
        else:
            return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"summary":"acceptance adapter completed"}'}]}],
                    'usage': {'input_tokens': 100, 'output_tokens': 20}}
        return {'output': [{'type': 'function_call', 'name': name, 'call_id': 'acceptance_' + str(step),
                            'arguments': json.dumps(args)}], 'usage': {'input_tokens': 100, 'output_tokens': 20}}
