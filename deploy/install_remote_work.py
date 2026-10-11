"""One-time administrative installation; never callable from the control bridge."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

SOURCE = Path('/tmp/pab-remote-work-v01')
RELEASE = Path('/opt/personal-ai-brain/builder')
SURFACE = Path('/var/lib/personal-ai-brain/work-transport')
UNIT = 'personal-ai-brain-builder.service'

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180).stdout.strip()

def install():
    assert os.geteuid() == 0
    assert (RELEASE / 'work-runner-v01.json').is_file()
    builder, control = pwd.getpwnam('pab-builder'), pwd.getpwnam('az1mutt')
    assert (builder.pw_uid, builder.pw_gid) == (999, 982)
    assert (control.pw_uid, control.pw_gid) == (1000, 1000)
    assert run('/usr/bin/id', '-G', 'pab-builder') == '982'
    # Refuse to interrupt unrelated submitted/running work at installation.
    tasks = Path('/var/lib/personal-ai-brain/builder/state/tasks')
    assert all(json.loads(p.read_text())['status'] in
               {'succeeded', 'failed', 'blocked', 'cancelled', 'interrupted'} for p in tasks.glob('*.json'))
    assert not SURFACE.is_symlink()
    SURFACE.mkdir(mode=0o755, exist_ok=True)
    os.chown(SURFACE, 0, 0)
    SURFACE.chmod(0o755)
    for name, uid, gid in [('inbox', 1000, 982), ('outbox', 999, 1000)]:
        path = SURFACE / name
        assert not path.is_symlink()
        path.mkdir(mode=0o2750, exist_ok=True)
        os.chown(path, uid, gid)
        path.chmod(0o2750)
    run('/usr/bin/systemctl', 'stop', UNIT)
    for name in ['work_runner.py', 'work_handoff.py', 'work_fixture.py', 'work_sandbox.py']:
        source = SOURCE / 'src/personal_ai_brain' / name
        assert source.is_file() and not source.is_symlink()
        target = RELEASE / 'src/personal_ai_brain' / name
        shutil.copyfile(source, target)
        os.chown(target, 0, 0)
        target.chmod(0o644)
    dropin = Path('/etc/systemd/system') / (UNIT + '.d')
    dropin.mkdir(mode=0o755, exist_ok=True)
    (dropin / 'remote-work.conf').write_text(
        '[Service]\nReadOnlyPaths=/var/lib/personal-ai-brain/work-transport/inbox\n'
        'ReadWritePaths=/var/lib/personal-ai-brain/work-transport/outbox\n')
    run('/usr/bin/systemctl', 'daemon-reload')
    run('/usr/bin/systemctl', 'start', UNIT)
    assert run('/usr/bin/systemctl', 'is-active', UNIT) == 'active'
    print('REMOTE_WORK_BUILDER_INSTALLED', flush=True)
    run('/usr/sbin/runuser', '-u', 'az1mutt', '--', '/bin/sh', str(SOURCE / 'scripts/control.sh'), 'up')
    print('REMOTE_WORK_CONTROL_DEPLOYED', flush=True)
    run('/usr/bin/python3', str(SOURCE / 'scripts/remote_work_acceptance.py'))
    print('REMOTE_WORK_ADMIN_ACCEPTANCE_PASSED', flush=True)

if __name__ == '__main__':
    try:
        install()
    except Exception:
        print('REMOTE_WORK_INSTALL_STOPPED', flush=True)
        raise SystemExit(1)
