"""Root-owned operator gate. Task input cannot select providers or scenarios."""
import json
import os
from pathlib import Path
import stat

PATH = Path('/etc/personal-ai-brain/inference/operator.json')
SCENARIOS = {'success', 'failure', 'malformed', 'timeout', 'budget', 'escape', 'ipc_drop', 'tests_failed'}

def read(path=PATH):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o022 or info.st_size > 1024):
            raise ValueError('invalid_operator_config')
        value = json.loads(stream.read(1025))
    if (set(value) != {'schema_version', 'provider', 'scenario'} or value['schema_version'] != '0.1'
            or value['provider'] not in {'disabled', 'acceptance', 'openai'}
            or value['scenario'] not in SCENARIOS
            or value['provider'] != 'acceptance' and value['scenario'] != 'success'):
        raise ValueError('invalid_operator_config')
    return value
