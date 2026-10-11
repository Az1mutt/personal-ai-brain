"""The sole v0.1 task program. Runs only in the disposable task namespace."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

CONTENT = 'Personal AI Brain Work Runner v0.1\n'

def denied_read(path):
    try:
        with open(path, 'rb') as stream:
            stream.read(1)
        return False
    except OSError:
        return True

def run():
    checks = {}
    paths = {
        'core_credential_denied': '/home/az1mutt/.config/personal-ai-brain/github-token',
        'control_credential_denied': '/home/az1mutt/.config/personal-ai-brain/github-control-token',
        'builder_credential_denied': '/home/az1mutt/.config/personal-ai-brain/builder/github-token',
        'other_workspace_denied': '/var/lib/personal-ai-brain/builder/workspaces/isolation-canary',
        'production_state_denied': '/home/az1mutt/.local/state/personal-ai-brain/control/status.json',
        'supervisor_state_denied': '/var/lib/personal-ai-brain/builder/state/state.lock',
        'host_shadow_denied': '/etc/shadow',
        'docker_socket_denied': '/run/docker.sock',
    }
    checks.update({name: denied_read(path) for name, path in paths.items()})
    checks['transport_absent'] = (not Path('/var/lib/personal-ai-brain/work-transport').exists()
                                  and not Path('/work-transport').exists())
    checks['docker_socket_absent'] = not Path('/run/docker.sock').exists() and not Path('/var/run/docker.sock').exists()
    checks['non_root'] = os.getuid() != 0 and os.geteuid() != 0
    checks['only_primary_group'] = all(group == os.getgid() for group in os.getgroups())
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    checks['no_capabilities'] = int(status['CapEff'].strip(), 16) == 0
    checks['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
    try:
        os.setuid(0)
        checks['setuid_root_denied'] = False
    except OSError:
        checks['setuid_root_denied'] = True
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.2)
            connection.connect(('1.1.1.1', 443))
        checks['network_denied'] = False
    except OSError:
        checks['network_denied'] = True
    try:
        with open('/workspace/.git/config', 'a') as stream:
            stream.write('unexpected-write')
        checks['git_metadata_readonly'] = False
    except OSError:
        checks['git_metadata_readonly'] = True
    # Deliberately detach a harmless child. PID-namespace teardown must reap it,
    # even though it created its own session. Acceptance observes the host cgroup.
    subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(120)'],
                     start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    target = Path('/workspace/builder-fixture.txt')
    target.write_text(CONTENT)
    checks['fixture_content_matches'] = target.read_text() == CONTENT
    report = {'schema_version': '0.1', 'fixture': 'fixture.patch-test.v1', 'checks': checks,
              'ok': all(checks.values())}
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report['ok'] else 1

if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception:
        print('{"ok":false,"code":"fixture_error"}', flush=True)
        sys.exit(1)
