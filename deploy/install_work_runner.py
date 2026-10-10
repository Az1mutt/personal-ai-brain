"""Explicit administrator bootstrap for the one local runner; never task code."""
import grp
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import venv

SOURCE = Path('/tmp/pab-work-runner-v01')
RELEASE = Path('/opt/personal-ai-brain/builder')
CONFIG = Path('/etc/personal-ai-brain/builder')
STATE = Path('/var/lib/personal-ai-brain/builder')
BASE = '71f0d82516d059ba2d65e028742cd73b2b9ee6bc'
UNIT = 'personal-ai-brain-builder.service'

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('bootstrap_command_failed:' + args[0])
    return result.stdout.strip()

def install():
    if os.geteuid() != 0:
        raise RuntimeError('administrator_bootstrap_required')
    os.umask(0o022)
    if RELEASE.exists() and not (RELEASE / 'work-runner-v01.json').is_file():
        raise RuntimeError('unrecognized_existing_release')
    try:
        user = pwd.getpwnam('pab-builder')
    except KeyError:
        run('/usr/sbin/useradd', '--system', '--user-group', '--home-dir', '/nonexistent',
            '--shell', '/usr/sbin/nologin', 'pab-builder')
        user = pwd.getpwnam('pab-builder')
    if user.pw_uid == 0 or user.pw_shell != '/usr/sbin/nologin' or user.pw_dir != '/nonexistent':
        raise RuntimeError('unexpected_builder_identity')
    groups = set(map(int, run('/usr/bin/id', '-G', 'pab-builder').split()))
    if groups != {user.pw_gid} or grp.getgrgid(user.pw_gid).gr_name != 'pab-builder':
        raise RuntimeError('unexpected_builder_groups')
    subprocess.run(['/usr/bin/systemctl', 'stop', UNIT], capture_output=True, timeout=15)
    package = RELEASE / 'src/personal_ai_brain'
    package.mkdir(parents=True, mode=0o755, exist_ok=True)
    (package / '__init__.py').write_text('')
    for name in ['work_contract.py', 'work_store.py', 'work_fixture.py', 'work_sandbox.py', 'work_runner.py']:
        source = SOURCE / 'src/personal_ai_brain' / name
        if source.is_symlink() or not source.is_file():
            raise RuntimeError('unexpected_source')
        shutil.copyfile(source, package / name)
        (package / name).chmod(0o644)
    if not (RELEASE / 'venv/bin/python').exists():
        venv.EnvBuilder(with_pip=False).create(RELEASE / 'venv')
    seed = RELEASE / 'repository.git'
    if not seed.exists():
        run('/usr/bin/git', 'init', '--bare', str(seed))
        run('/usr/bin/git', '-C', str(seed), 'fetch', str(SOURCE / '.work-runner-base.bundle'),
            'refs/remotes/origin/main:refs/heads/fixture-base')
        run('/usr/bin/git', '-C', str(seed), 'symbolic-ref', 'HEAD', 'refs/heads/fixture-base')
    if run('/usr/bin/git', '-C', str(seed), 'rev-parse', 'HEAD') != BASE:
        raise RuntimeError('seed_base_mismatch')
    CONFIG.mkdir(mode=0o755, parents=True, exist_ok=True)
    (CONFIG / 'profile.json').write_text(json.dumps({'schema_version':'0.1',
        'repository':'Az1mutt/personal-ai-brain', 'base_ref':BASE,
        'seed':str(seed), 'min_free_bytes':16777216}) + '\n')
    (CONFIG / 'profile.json').chmod(0o644)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    STATE.chmod(0o700)
    os.chown(STATE, user.pw_uid, user.pw_gid)
    marker = {'milestone':'work-runner-v0.1', 'base_sha':BASE, 'uid':user.pw_uid, 'gid':user.pw_gid}
    (RELEASE / 'work-runner-v01.json').write_text(json.dumps(marker) + '\n')
    shutil.copyfile(SOURCE / 'deploy' / UNIT, Path('/etc/systemd/system') / UNIT)
    run('/usr/bin/systemctl', 'daemon-reload')
    run('/usr/bin/systemctl', 'enable', '--now', UNIT)
    return marker

if __name__ == '__main__':
    try:
        marker = install()
        print(json.dumps({'bootstrap':'installed', **marker}), flush=True)
        result = subprocess.run(['/usr/bin/python3', str(SOURCE / 'scripts/work_runner_acceptance.py')], timeout=180)
        sys.exit(result.returncode)
    except Exception as error:
        print(json.dumps({'bootstrap':'stopped', 'error_type':type(error).__name__, 'code':str(error) if isinstance(error, RuntimeError) else 'bootstrap_failed'}), flush=True)
        sys.exit(1)
