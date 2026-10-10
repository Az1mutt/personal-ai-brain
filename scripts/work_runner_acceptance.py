"""Administrator-only live acceptance for the fixed local service, not a runtime API."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
import uuid

ROOT = Path('/var/lib/personal-ai-brain/builder')
RELEASE = Path('/opt/personal-ai-brain/builder')
SOURCE = Path('/tmp/pab-work-runner-v01')
PROFILE = Path('/etc/personal-ai-brain/builder/profile.json')
UNIT = 'personal-ai-brain-builder.service'
BASE = '71f0d82516d059ba2d65e028742cd73b2b9ee6bc'
REPORT = SOURCE / '.work-runner-acceptance.json'
TERMINAL = {'succeeded','failed','blocked','cancelled','interrupted'}

def service(*args):
    return subprocess.check_output(['/usr/bin/systemctl', *args, UNIT], text=True, timeout=20).strip()

def cli(action, payload=None, identifier=None):
    args = ['/usr/sbin/runuser', '-u', 'pab-builder', '--', '/usr/bin/env',
            'PYTHONPATH=' + str(RELEASE / 'src'), str(RELEASE / 'venv/bin/python'),
            '-B', '-m', 'personal_ai_brain.work_runner', action]
    if identifier: args.append(identifier)
    result = subprocess.run(args, input=json.dumps(payload).encode() if payload else None,
                            capture_output=True, timeout=15)
    return result.returncode, json.loads(result.stdout)

def task(seconds=20):
    from datetime import datetime, timezone
    return {'schema_version':'0.1', 'task_id':str(uuid.uuid4()), 'task_type':'fixture.patch-test.v1',
            'repository':'Az1mutt/personal-ai-brain', 'base_ref':BASE,
            'goal':'Create the deterministic Work Runner fixture artifact.',
            'acceptance_criteria':['fixture content matches','isolation checks pass'],
            'requested_at':datetime.now(timezone.utc).isoformat(), 'deadline_seconds':seconds}

def load(identifier):
    return json.loads((ROOT / 'state/tasks' / (identifier + '.json')).read_text())

def wait(identifier, target=None, seconds=25):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        record = load(identifier)
        if (target and record['status'] == target) or (not target and record['status'] in TERMINAL):
            return record
        if target and record['status'] in TERMINAL:
            raise RuntimeError('terminal_before_expected_state:' + record['status'])
        time.sleep(0.05)
    raise RuntimeError('acceptance_timeout')

def submit(payload):
    code, response = cli('submit', payload=payload)
    assert code == 0 and response['created']
    return payload['task_id']

def clean_cgroup():
    end = time.monotonic() + 4
    while time.monotonic() < end:
        main = int(service('show', '--property=MainPID', '--value'))
        cgroup = service('show', '--property=ControlGroup', '--value')
        pids = {int(x) for x in (Path('/sys/fs/cgroup') / cgroup.lstrip('/') / 'cgroup.procs').read_text().split()}
        if pids == {main}: return True
        time.sleep(0.05)
    raise RuntimeError('sandbox_descendants_remain')

def save_report(value):
    REPORT.write_text(json.dumps(value, indent=2) + '\n')
    REPORT.chmod(0o600)
    owner = pwd.getpwnam('az1mutt')
    os.chown(REPORT, owner.pw_uid, owner.pw_gid)

def observe(identifier):
    # One short-lived read-only observer exports the final result after the
    # originating SSH has ended. It does not execute or keep the task alive.
    time.sleep(8)
    report = json.loads(REPORT.read_text())
    try:
        record = wait(identifier)
        assert record['status'] == 'succeeded'
        clean_cgroup()
        report['session_disconnect'] = {'status':'passed', 'task_id':identifier,
            'finished_at':record['finished_at'], 'service_main_pid':service('show','--property=MainPID','--value')}
        report['acceptance'] = 'passed_reboot_pending'
    except Exception as error:
        report['session_disconnect'] = {'status':'failed', 'code':type(error).__name__}
    save_report(report)

def acceptance():
    checks = {}
    report = {'acceptance':'running', 'checks':checks, 'reboot':'pending_not_performed_on_shared_host'}
    identifier = None
    try:
        assert os.geteuid() == 0
        # The canary represents a different private workspace; its content is not a secret.
        (ROOT / 'workspaces').mkdir(mode=0o700, exist_ok=True)
        (ROOT / 'workspaces/isolation-canary').write_text('private other-task canary\n')
        owner = pwd.getpwnam('pab-builder')
        os.chown(ROOT / 'workspaces', owner.pw_uid, owner.pw_gid)
        payload = task()
        identifier = submit(payload)
        record = wait(identifier)
        assert record['status'] == 'succeeded'
        audit = ROOT / 'audit' / identifier
        assert all((audit / name).is_file() for name in ['execution.log','patch.diff','test-result.json','result.json'])
        tests = json.loads((audit / 'test-result.json').read_text())
        assert tests['status'] == 'passed' and all(tests['checks'].values())
        applied = subprocess.run(['/usr/sbin/runuser', '-u', 'pab-builder', '--',
            '/usr/bin/git', '-C', str(ROOT / 'workspaces' / identifier / 'repo'),
            'apply', '--reverse', '--check', str(audit / 'patch.diff')], capture_output=True)
        assert applied.returncode == 0
        checks['success_and_isolation'] = {'task_id':identifier, 'checks':tests['checks']}
        clean_cgroup()
        checks['normal_background_cleanup'] = True
        code, same = cli('submit', payload=payload)
        assert code == 0 and same['created'] is False and load(identifier)['attempts'] == 1
        code, conflict = cli('submit', payload={**payload, 'deadline_seconds':19})
        assert code == 2 and conflict['error'] == 'task_id_payload_conflict'
        checks['duplicate_and_conflict'] = True
        identifier = submit(task(1))
        assert wait(identifier)['history'][-1]['code'] == 'deadline_exceeded'
        clean_cgroup()
        checks['deadline'] = identifier
        identifier = submit(task())
        wait(identifier, 'running')
        assert cli('cancel', identifier=identifier)[0] == 0
        assert wait(identifier)['status'] == 'cancelled'
        clean_cgroup()
        checks['cancellation'] = identifier
        identifier = submit(task())
        wait(identifier, 'running')
        time.sleep(0.3)
        service('restart')
        assert wait(identifier)['status'] == 'interrupted'
        clean_cgroup()
        checks['restart_preserves_truth'] = identifier
        identifier = submit(task())
        wait(identifier, 'running')
        time.sleep(0.3)
        old_main = service('show', '--property=MainPID', '--value')
        service('kill', '--kill-whom=main', '--signal=KILL')
        assert wait(identifier, seconds=15)['status'] == 'interrupted'
        assert service('show', '--property=MainPID', '--value') != old_main
        clean_cgroup()
        checks['abrupt_interrupt_cleanup'] = identifier
        # Deterministic fixture error injection by the acceptance administrator,
        # not a new payload capability. All resulting evidence is retained.
        identifier = submit(task())
        wait(identifier, 'running')
        (ROOT / 'workspaces' / identifier / 'repo/builder-fixture.txt').mkdir()
        assert wait(identifier)['status'] == 'failed'
        assert (ROOT / 'audit' / identifier / 'execution.log').stat().st_size > 0
        assert (ROOT / 'workspaces' / identifier).is_dir()
        clean_cgroup()
        checks['fixture_error_retains_evidence'] = identifier
        original = PROFILE.read_text()
        try:
            policy = json.loads(original)
            policy['min_free_bytes'] = 2 ** 63
            PROFILE.write_text(json.dumps(policy) + '\n')
            service('restart')
            identifier = submit(task())
            assert wait(identifier)['history'][-1]['code'] == 'insufficient_storage'
            assert not (ROOT / 'workspaces' / identifier).exists()
            checks['low_space_admission_blocked'] = identifier
        finally:
            PROFILE.write_text(original)
            service('restart')
        checks['enabled_at_boot'] = service('is-enabled') == 'enabled'
        checks['service_identity'] = {'uid':owner.pw_uid,'gid':owner.pw_gid,
            'groups':subprocess.check_output(['/usr/bin/id','-G','pab-builder'],text=True).strip()}
        # Final task is deliberately still running when this SSH command returns.
        identifier = submit(task())
        wait(identifier, 'running')
        report['session_disconnect'] = {'status':'running_at_ssh_exit','task_id':identifier}
        save_report(report)
        subprocess.Popen(['/usr/bin/python3', __file__, 'observe', identifier],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, start_new_session=True)
        print(json.dumps({'acceptance':'awaiting_fresh_session_check','task_id':identifier}), flush=True)
    except Exception as error:
        report['acceptance'] = 'failed'
        report['error'] = type(error).__name__
        if identifier:
            report['last_task_id'] = identifier
            try:
                report['last_task_state'] = load(identifier)['status']
                report['last_task_code'] = load(identifier)['history'][-1]['code']
                report['bounded_log'] = (ROOT / 'audit' / identifier / 'execution.log').read_text()[:2048]
            except Exception:
                pass
        save_report(report)
        print(json.dumps({'acceptance':'failed','error':type(error).__name__}), flush=True)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'observe': observe(sys.argv[2])
    elif len(sys.argv) == 1: acceptance()
    else: sys.exit(2)
