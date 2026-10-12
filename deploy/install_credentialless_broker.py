"""Owner-operated fixed bootstrap and acceptance; no API key or paid request."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import time

SOURCE = Path('/tmp/pab-coding-agent-preflight')
RUNTIME = Path('/opt/personal-ai-brain/builder')
CONFIG = Path('/etc/personal-ai-brain/inference')
STATE = Path('/var/lib/personal-ai-brain/inference')
BUILDER = 'personal-ai-brain-builder.service'
BROKER = 'personal-ai-brain-inference-broker.service'
RECEIPT = Path('/var/lib/personal-ai-brain/credentialless-broker-evidence.json')
phase = 'preflight'

def run(*args, input=None, timeout=60):
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)
    if result.returncode: raise RuntimeError('administrative_step_failed')
    return result.stdout.strip()

def owned_directory(path, uid=0, gid=0, mode=0o755):
    assert not path.is_symlink()
    path.mkdir(parents=True, exist_ok=True)
    os.chown(path, uid, gid); path.chmod(mode)

def copy(source, target):
    assert source.is_file() and not source.is_symlink() and not target.is_symlink()
    shutil.copyfile(source, target); os.chown(target, 0, 0); target.chmod(0o644)

def install():
    global phase
    assert os.geteuid() == 0
    assert run('/usr/bin/git', '-c', 'safe.directory='+str(SOURCE), '-C', str(SOURCE), 'branch', '--show-current') == 'feat/coding-agent-broker-v01'
    run('/usr/bin/git', '-c', 'safe.directory='+str(SOURCE), '-C', str(SOURCE), 'merge-base', '--is-ancestor', '83a54fe', 'HEAD')
    builder = pwd.getpwnam('pab-builder')
    assert (builder.pw_uid, builder.pw_gid) == (999, 982)
    assert run('/usr/bin/id', '-G', 'pab-builder') == '982'
    tasks = Path('/var/lib/personal-ai-brain/builder/state/tasks')
    assert all(json.loads(p.read_bytes())['status'] in {'succeeded','failed','blocked','cancelled','interrupted'} for p in tasks.glob('*.json'))
    phase = 'identity'
    try: account = pwd.getpwnam('pab-inference')
    except KeyError:
        run('/usr/sbin/useradd', '--system', '--no-create-home', '--home-dir', '/nonexistent',
            '--shell', '/usr/sbin/nologin', '--gid', 'pab-builder', 'pab-inference')
        account = pwd.getpwnam('pab-inference')
    assert account.pw_uid not in (0, 999, 1000) and account.pw_gid == 982
    assert account.pw_shell == '/usr/sbin/nologin' and run('/usr/bin/id', '-G', 'pab-inference') == '982'
    owned_directory(CONFIG)
    owned_directory(CONFIG/'credentials', account.pw_uid, 982, 0o700)
    assert not (CONFIG/'credentials/openai-api-key').exists()
    owned_directory(STATE, account.pw_uid, 982, 0o700)
    (CONFIG/'operator.json').write_text(json.dumps({'schema_version':'0.1','provider':'acceptance','scenario':'success'}))
    (CONFIG/'operator.json').chmod(0o644)
    phase = 'runtime'
    backup = Path('/var/lib/personal-ai-brain/credentialless-bootstrap-backup')
    owned_directory(backup, mode=0o700)
    profile = Path('/etc/personal-ai-brain/builder/profile.json')
    if not (backup/'profile.json').exists(): copy(profile, backup/'profile.json')
    run('/usr/bin/systemctl', 'stop', BUILDER)
    for pattern in ('coding_*.py', 'inference_*.py', 'work_contract.py', 'work_store.py', 'work_runner.py', 'work_handoff.py'):
        for source in (SOURCE/'src/personal_ai_brain').glob(pattern):
            target = RUNTIME/'src/personal_ai_brain'/source.name
            if target.exists() and not (backup/source.name).exists(): copy(target, backup/source.name)
            copy(source, target)
    seed = RUNTIME/'coding-repository.git'
    if not seed.exists():
        run('/usr/bin/git', '-c', 'safe.directory='+str(SOURCE), 'clone', '--bare', '--no-hardlinks', '--no-local', str(SOURCE), str(seed))
        run('/usr/bin/git', '--git-dir='+str(seed), 'remote', 'remove', 'origin')
    assert run('/usr/bin/git', '--git-dir='+str(seed), 'rev-parse', 'cde8c424b687c3ef99b98e4764da4a67c973d8b2^{commit}') == 'cde8c424b687c3ef99b98e4764da4a67c973d8b2'
    copy(SOURCE/'deploy'/BROKER, Path('/etc/systemd/system')/BROKER)
    dropin = Path('/etc/systemd/system')/(BROKER+'.d')
    owned_directory(dropin)
    (dropin/'credentialless.conf').write_text('[Service]\nPrivateNetwork=yes\nIPAddressDeny=any\n')
    (dropin/'credentialless.conf').chmod(0o644)
    value = json.loads(profile.read_bytes()); value['coding_enabled'] = True
    profile.write_text(json.dumps(value)+'\n'); profile.chmod(0o644)
    run('/usr/bin/systemctl', 'daemon-reload')
    phase = 'broker_start'
    run('/usr/bin/systemctl', 'enable', '--now', BROKER)
    run('/usr/bin/systemctl', 'restart', BROKER)
    run('/usr/bin/systemctl', 'start', BUILDER)
    time.sleep(1)
    assert run('/usr/bin/systemctl', 'is-active', BROKER) == 'active'
    phase = 'live_acceptance'
    sys.path.insert(0, str(SOURCE/'deploy'))
    from credentialless_acceptance import accept
    evidence = accept()
    evidence.update(phase='complete', credential_present=False, paid_requests=0)
    RECEIPT.write_text(json.dumps(evidence, indent=2)+'\n'); RECEIPT.chmod(0o644)
    print('BROKER_CREDENTIALLESS_ACCEPTANCE_PASSED', flush=True)

if __name__ == '__main__':
    try: install()
    except Exception as error:
        # Fail closed for new coding work while restoring fixture availability.
        try:
            profile = Path('/etc/personal-ai-brain/builder/profile.json')
            value = json.loads(profile.read_bytes()); value['coding_enabled'] = False
            profile.write_text(json.dumps(value)+'\n')
            if CONFIG.exists():
                (CONFIG/'operator.json').write_text(json.dumps({'schema_version':'0.1','provider':'disabled','scenario':'success'})+'\n')
            run('/usr/bin/systemctl', 'start', BUILDER)
        except Exception: pass
        import traceback
        frames = [{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)]
        evidence = {'phase':phase,'completed':False,'paid_requests':0,'error_type':type(error).__name__,'frames':frames}
        if 'credentialless_acceptance' in sys.modules:
            evidence['partial_acceptance']=sys.modules['credentialless_acceptance'].progress
        try:
            records = [json.loads(p.read_bytes()) for p in Path('/var/lib/personal-ai-brain/builder/state/tasks').glob('*.json')]
            coding = sorted([r for r in records if r['request']['task_type']=='coding.patch-test.v1'],key=lambda r:r['history'][0]['at'])
            evidence['recent_tasks'] = [{'task_id':r['task_id'],'status':r['status'],'code':r['history'][-1]['code']} for r in coding[-3:]]
            for item in evidence['recent_tasks']:
                ledger = STATE/(item['task_id']+'.json')
                if ledger.exists():
                    entry=json.loads(ledger.read_bytes())
                    item['broker_status']=entry['status']; item['broker_turn_count']=len(entry['turns'])
            security = STATE/'security-evidence'
            if security.exists(): evidence['broker_security']=json.loads(security.read_bytes())
        except Exception: pass
        RECEIPT.write_text(json.dumps(evidence)+'\n')
        RECEIPT.chmod(0o644)
        print('BROKER_CREDENTIALLESS_STOPPED_'+phase.upper(), flush=True)
        raise SystemExit(1)
