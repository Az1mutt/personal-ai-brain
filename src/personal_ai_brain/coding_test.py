"""Root-owned offline acceptance harness, mounted read-only by the supervisor."""
import json
import runpy
import os
from pathlib import Path
import socket
import subprocess
import sys

CHECKS = {'credentials_absent', 'broker_socket_absent', 'other_workspace_absent',
          'docker_absent', 'non_root', 'no_capabilities', 'no_new_privileges', 'network_denied', 'root_denied'}

def isolation():
    paths = ['/home/az1mutt', '/etc/personal-ai-brain/inference/credentials/openai-api-key']
    result = {'credentials_absent': all(not Path(p).exists() for p in paths),
              'broker_socket_absent': not Path('/run/personal-ai-brain-inference/broker.sock').exists(),
              'other_workspace_absent': not Path('/var/lib/personal-ai-brain/builder').exists(),
              'docker_absent': not Path('/run/docker.sock').exists(), 'non_root': os.geteuid() == 65534}
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    result['no_capabilities'] = int(status['CapEff'].strip(), 16) == 0
    result['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
    try: os.setuid(0); result['root_denied'] = False
    except OSError: result['root_denied'] = True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2); s.connect(('1.1.1.1', 443))
        result['network_denied'] = False
    except OSError: result['network_denied'] = True
    return result

def main():
    try:
        checks = isolation()
        if set(checks) != CHECKS or not all(checks.values()): raise ValueError()
        fn = runpy.run_path('/workspace/src/personal_ai_brain/coding_exercise.py')['normalize_label']
        cases = [('', ''), (' A  B ', 'a b'), ('Straße', 'strasse'),
                 ('\tHELLO\nworld\r', 'hello world'), ('A\u2003B\u00a0C', 'a b c'),
                 ('  MiXeD  ', 'mixed'), ('one', 'one')]
        for value, expected in cases:
            if fn(value) != expected: raise ValueError()
        for value in (None, 1, True, [], {}, b'text'):
            try: fn(value)
            except TypeError: continue
            raise ValueError()
        subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(120)'],
                         start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(json.dumps({'schema_version': '0.1', 'profile': 'normalize-label-v1', 'passed': 13, 'isolation': checks}))
        return 0
    except BaseException:
        print('{"status":"failed"}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
