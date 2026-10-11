"""Administrative integration probes; no credential reads and no production task API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, '/opt/personal-ai-brain/builder/src')
from personal_ai_brain.work_contract import timestamp, GOAL, CRITERIA, REPOSITORY, TASK_TYPE
from personal_ai_brain.work_handoff import BASE

ROOT = Path('/var/lib/personal-ai-brain/builder')
UNIT = 'personal-ai-brain-builder.service'
CONTROL = 'personal-ai-brain-control-control-1'
RECEIPT = Path('/tmp/pab-remote-work-v01/.remote-work-acceptance.json')

def run(*args, input=None):
    return subprocess.run(args, input=input, check=True, capture_output=True,
                          text=True, timeout=45).stdout.strip()

def call(operation, arguments):
    payload = json.dumps([operation, arguments, str(uuid.uuid4())])
    program = "import json,sys; from pathlib import Path; from personal_ai_brain.work_handoff import Client; print(json.dumps(Client(Path('/var/lib/personal-ai-brain/work-transport'),0).invoke(*json.load(sys.stdin))))"
    return json.loads(run('/usr/sbin/runuser', '-u', 'az1mutt', '--', '/usr/bin/env',
        'PYTHONPATH=/opt/personal-ai-brain/builder/src', '/usr/bin/python3', '-c', program, input=payload))

def task():
    return dict(schema_version='0.1', task_id=str(uuid.uuid4()), task_type=TASK_TYPE,
                repository=REPOSITORY, base_ref=BASE, goal=GOAL,
                acceptance_criteria=CRITERIA, requested_at=timestamp(), deadline_seconds=20)

def wait(identifier, states):
    until = time.monotonic() + 30
    path = ROOT / 'state/tasks' / (identifier + '.json')
    while time.monotonic() < until:
        if path.exists():
            record = json.loads(path.read_text())
            if record['status'] in states:
                return record
        time.sleep(0.05)
    raise RuntimeError('acceptance_timeout')

def main():
    assert os.geteuid() == 0
    receipt = {'schema_version': '0.1', 'checked_at': timestamp(), 'external_chatgpt': 'pending', 'reboot': 'pending_out_of_scope'}
    assert run('/usr/bin/systemctl', 'is-active', UNIT) == 'active'
    assert run('/usr/bin/id', '-G', 'pab-builder') == '982'
    # Actual container boundary: no mount of builder private roots or publication token.
    program = "from pathlib import Path; import os; assert os.getuid()==1000; assert all(not Path(p).exists() for p in ['/var/lib/personal-ai-brain/builder','/home/az1mutt/.config/personal-ai-brain/builder/github-token','/run/docker.sock']); assert os.access('/work-transport/inbox',os.W_OK); assert not os.access('/work-transport/outbox',os.W_OK); print('CONTROL_BOUNDARY_OK')"
    assert run('/usr/bin/docker', 'exec', CONTROL, 'python', '-c', program) == 'CONTROL_BOUNDARY_OK'
    program = "import os; assert os.getuid()==999; assert all(not os.access(p,os.R_OK) for p in ['/home/az1mutt/.config/personal-ai-brain/github-control-token','/home/az1mutt/.local/state/personal-ai-brain/control/status.json','/home/az1mutt/.config/personal-ai-brain/builder/github-token']); assert not os.access('/var/lib/personal-ai-brain/work-transport/inbox',os.W_OK); print('BUILDER_BOUNDARY_OK')"
    assert run('/usr/sbin/runuser', '-u', 'pab-builder', '--', '/usr/bin/python3', '-c', program) == 'BUILDER_BOUNDARY_OK'
    receipt['identity_boundaries'] = True
    # Durable handoff remains pending while builder is down; control restart
    # cannot erase it. The control reservation-crash case is separately unit-tested.
    queued = task()
    run('/usr/bin/systemctl', 'stop', UNIT)
    try:
        assert call('work.submit', {'contract': queued})['outcome'] == 'handoff_pending'
        run('/usr/bin/docker', 'restart', CONTROL)
    finally:
        run('/usr/bin/systemctl', 'start', UNIT)
    completed = wait(queued['task_id'], {'succeeded', 'failed', 'blocked', 'interrupted'})
    assert completed['status'] == 'succeeded' and completed['attempts'] == 1
    call('work.submit', {'contract': queued})
    time.sleep(0.3)
    assert wait(queued['task_id'], {'succeeded'}) == completed
    report = json.loads((ROOT / 'audit' / queued['task_id'] / 'test-result.json').read_text())
    assert report['ok'] and len(report['checks']) == 18 and all(report['checks'].values())
    receipt['control_restart_pending_handoff'] = queued['task_id']
    receipt['sandbox_18_checks'] = True
    interrupted = task()
    call('work.submit', {'contract': interrupted})
    wait(interrupted['task_id'], {'running'})
    run('/usr/bin/systemctl', 'restart', UNIT)
    record = wait(interrupted['task_id'], {'interrupted'})
    assert record['attempts'] == 1
    call('work.submit', {'contract': interrupted})
    time.sleep(0.3)
    assert wait(interrupted['task_id'], {'interrupted'}) == record
    receipt['builder_restart_no_replay'] = interrupted['task_id']
    receipt['internal_admin_checks'] = 'passed'
    RECEIPT.write_text(json.dumps(receipt, indent=2) + '\n')
    RECEIPT.chmod(0o600)
    os.chown(RECEIPT, 1000, 1000)
    print('REMOTE_WORK_ADMIN_ACCEPTANCE_PASSED')

if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('REMOTE_WORK_ADMIN_ACCEPTANCE_STOPPED')
        raise SystemExit(1)
