"""Fixed boolean-only probes, executed by the broker itself in acceptance mode."""
import os
from pathlib import Path
import socket

PATHS = {
    'core_denied': '/home/az1mutt/.config/personal-ai-brain/github-token',
    'control_denied': '/home/az1mutt/.config/personal-ai-brain/github-control-token',
    'publication_denied': '/home/az1mutt/.config/personal-ai-brain/builder/github-token',
    'ssh_denied': '/home/az1mutt/.ssh/id_ed25519',
    'workspace_denied': '/var/lib/personal-ai-brain/builder/workspaces/isolation-canary',
    'runner_state_denied': '/var/lib/personal-ai-brain/builder/state/state.lock',
    'host_shadow_denied': '/etc/shadow',
}

def denied(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        os.close(fd)
        return False
    except OSError: return True

def checks():
    result = {name: denied(path) for name, path in PATHS.items()}
    result['docker_absent'] = not Path('/run/docker.sock').exists() and not Path('/var/run/docker.sock').exists()
    result['home_hidden'] = denied('/home/az1mutt')
    result['non_root'] = os.getuid() not in (0, 999, 1000) and os.geteuid() == os.getuid()
    result['only_ipc_group'] = os.getgid() == 982 and all(g == 982 for g in os.getgroups())
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    result['no_capabilities'] = int(status['CapEff'].strip(), 16) == 0
    result['no_new_privileges'] = status['NoNewPrivs'].strip() == '1'
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: s.bind(('127.0.0.1', 0))
        result['tcp_bind_denied'] = False
    except OSError: result['tcp_bind_denied'] = True
    try: os.setuid(0); result['root_denied'] = False
    except OSError: result['root_denied'] = True
    return result
