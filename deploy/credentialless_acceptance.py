"""Fixed administrative live harness. No network API, arbitrary task or secret output."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
import uuid

RUNTIME = '/opt/personal-ai-brain/builder/src'
PYTHON = '/opt/personal-ai-brain/builder/venv/bin/python'
CONFIG = Path('/etc/personal-ai-brain/inference/operator.json')
ROOT = Path('/var/lib/personal-ai-brain/builder')
LEDGER = Path('/var/lib/personal-ai-brain/inference')
BROKER = 'personal-ai-brain-inference-broker.service'
BUILDER = 'personal-ai-brain-builder.service'
sys.path.insert(0, RUNTIME)
from personal_ai_brain import coding_policy as policy
from personal_ai_brain.work_contract import timestamp
from personal_ai_brain.work_store import atomic_json
progress = {}

def command(*args, input=None):
    r = subprocess.run(args, input=input, text=True, capture_output=True, timeout=30)
    if r.returncode: raise RuntimeError('acceptance_command_failed')
    return r.stdout.strip()

def as_user(user, code, data=None):
    return command('/usr/sbin/runuser', '-u', user, '--', '/usr/bin/env', 'PYTHONPATH='+RUNTIME,
                   PYTHON, '-B', '-c', code, input=None if data is None else json.dumps(data))

def scenario(name):
    CONFIG.write_text(json.dumps({'schema_version':'0.1','provider':'acceptance','scenario':name})+'\n')
    CONFIG.chmod(0o644)

def request(deadline=60):
    return {'schema_version':'0.1','task_id':str(uuid.uuid4()),'task_type':policy.TYPE,
            'repository':'Az1mutt/personal-ai-brain','base_ref':policy.BASE,
            'goal':policy.GOAL,'acceptance_criteria':policy.CRITERIA,
            'requested_at':timestamp(),'deadline_seconds':deadline}

def submit(task, remote=False):
    if remote:
        code = ('import json,sys,uuid; from pathlib import Path; from personal_ai_brain.work_handoff import Client; '
                'print(json.dumps(Client(Path("/var/lib/personal-ai-brain/work-transport")).invoke('
                '"work.submit", {"contract":json.load(sys.stdin)}, str(uuid.uuid4()))))')
        return json.loads(as_user('az1mutt', code, task))
    result = command('/usr/sbin/runuser','-u','pab-builder','--','/usr/bin/env','PYTHONPATH='+RUNTIME,
                     PYTHON,'-B','-m','personal_ai_brain.work_runner','submit', input=json.dumps(task))
    return json.loads(result)

def record(task):
    return json.loads((ROOT/'state/tasks'/(task['task_id']+'.json')).read_bytes())

def wait(task, active=False, seconds=70):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        value = record(task)
        ledger = LEDGER/(task['task_id']+'.json')
        if active:
            if value['status']=='running' and ledger.exists() and json.loads(ledger.read_bytes())['turns']: return value
        elif value['status'] in {'succeeded','failed','blocked','cancelled','interrupted'}: return value
        time.sleep(0.05)
    raise RuntimeError('acceptance_wait_failed')

def accept():
    results = progress
    security = json.loads((LEDGER/'security-evidence').read_bytes())
    assert all(security.values()); results['broker_security'] = security
    assert pwd.getpwnam('pab-inference').pw_shell == '/usr/sbin/nologin'
    # Install a synthetic sentinel through the production installer, never a real key.
    from personal_ai_brain.inference_install_key import directory, install_at, DIRECTORY
    broker = pwd.getpwnam('pab-inference')
    fd = directory(DIRECTORY, broker.pw_uid)
    try: install_at(fd, b'synthetic-acceptance-sentinel-not-a-real-key', broker.pw_uid, broker.pw_gid)
    finally: os.close(fd)
    key = Path(DIRECTORY)/'openai-api-key'
    try:
        checks = json.loads(as_user('pab-builder',
            'import json; from personal_ai_brain.inference_probe import denied; '
            'print(json.dumps({"key_denied":denied("/etc/personal-ai-brain/inference/credentials/openai-api-key")}))'))
        assert all(checks.values()); results['builder_credential_denied'] = True
        results['synthetic_installer_validated'] = (key.stat().st_uid==broker.pw_uid and key.stat().st_gid==982 and key.stat().st_mode & 0o777==0o600)
        scenario('success'); first=request(); assert submit(first, remote=True)['outcome'] in {'completed','handoff_pending'}
        assert wait(first)['status']=='succeeded'
        audit = ROOT/'audit'/first['task_id']
        agent = json.loads((audit/'agent-result.json').read_bytes())
        assert agent['provider']=='acceptance-stub' and agent['model'] is None
        assert agent['operations']==['list_files','read_file','search_text','apply_patch']
        tests = json.loads((audit/'test-result.json').read_bytes())
        assert tests['passed']==13 and all(tests['isolation'].values())
        assert (audit/'patch.diff').stat().st_size>0
        results['success']={'task_id':first['task_id'],'status':'succeeded','operations':agent['operations'],'sandbox':tests['isolation']}
        before=(LEDGER/(first['task_id']+'.json')).read_bytes()
        assert submit(first)['created'] is False
        assert (LEDGER/(first['task_id']+'.json')).read_bytes()==before
        results['duplicate_no_provider_replay']=True
        conflict=submit({**first,'deadline_seconds':59}, remote=True)
        assert conflict.get('error')=='task_id_payload_conflict'; results['conflict_rejected']=True
    finally: key.unlink(missing_ok=True)
    for name, expected in [('failure','model_rate_limited'),('malformed','model_invalid_response'),
                           ('escape','patch_rejected'),('tests_failed','tests_failed'),
                           ('budget','model_budget_exceeded'),('ipc_drop','interrupted')]:
        scenario(name); task=request(); submit(task); value=wait(task)
        assert value['history'][-1]['code']==expected
        results[name]={'task_id':task['task_id'],'status':value['status'],'code':expected}
    scenario('timeout'); task=request(4); submit(task); wait(task, active=True); value=wait(task)
    assert value['history'][-1]['code'] in {'deadline_exceeded','model_timeout','interrupted'}
    results['timeout']={'task_id':task['task_id'],'status':value['status'],'code':value['history'][-1]['code']}
    for action, status in [('cancel','cancelled'),('broker_restart','interrupted'),('runner_restart','interrupted')]:
        scenario('timeout'); task=request(); submit(task); wait(task, active=True)
        if action=='cancel':
            command('/usr/sbin/runuser','-u','pab-builder','--','/usr/bin/env','PYTHONPATH='+RUNTIME,
                    PYTHON,'-B','-m','personal_ai_brain.work_runner','cancel',task['task_id'])
        else: command('/usr/bin/systemctl','restart',BROKER if action=='broker_restart' else BUILDER)
        value=wait(task); assert value['status']==status
        assert submit(task)['created'] is False
        results[action]={'task_id':task['task_id'],'status':status,'attempts':value['attempts']}
    command('/usr/bin/systemctl','stop',BROKER)
    try:
        task=request(); submit(task); value=wait(task)
        assert value['status']=='failed' and value['history'][-1]['code']=='model_network_failed'
        results['broker_unavailable']=True
    finally: command('/usr/bin/systemctl','start',BROKER)
    time.sleep(0.5)
    denial_code = '''import json,socket
s=socket.socket(socket.AF_UNIX); s.settimeout(1)
try:
 s.connect('/run/personal-ai-brain-inference/broker.sock'); s.sendall(b'xxxx'); denied=s.recv(1)==b''
except OSError: denied=True
finally: s.close()
print(json.dumps({'denied':denied}))'''
    for user in ('az1mutt','nobody','pab-inference'):
        assert json.loads(as_user(user,denial_code))['denied']
    results['unrelated_identities_denied']=True
    from personal_ai_brain import work_contract
    fixture=request(20)
    fixture.update(task_type=work_contract.TASK_TYPE,goal=work_contract.GOAL,
                   acceptance_criteria=work_contract.CRITERIA,
                   base_ref=json.loads(Path('/etc/personal-ai-brain/builder/profile.json').read_bytes())['base_ref'])
    submit(fixture); assert wait(fixture)['status']=='succeeded'
    fixture_report=json.loads((ROOT/'audit'/fixture['task_id']/'test-result.json').read_bytes())
    assert all(fixture_report['checks'].values())
    results['fixture_regression']={'task_id':fixture['task_id'],'status':'succeeded','isolation_checks':len(fixture_report['checks'])}
    for unit in (BROKER, BUILDER):
        cgroup=command('/usr/bin/systemctl','show',unit,'-p','ControlGroup','--value')
        pids=(Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cgroup.procs').read_text().split()
        # Only supervisors / receiver / multiprocessing tracker may remain.
        assert all(b'/usr/bin/sleep' not in Path('/proc',pid,'cmdline').read_bytes() and b'time.sleep(120)' not in Path('/proc',pid,'cmdline').read_bytes() for pid in pids)
    results['descendants_cleaned']=True
    # Leave service persistent but no provider enabled; network denial remains.
    CONFIG.write_text(json.dumps({'schema_version':'0.1','provider':'disabled','scenario':'success'})+'\n')
    profile=Path('/etc/personal-ai-brain/builder/profile.json')
    value=json.loads(profile.read_bytes()); value['coding_enabled']=False; profile.write_text(json.dumps(value)+'\n')
    command('/usr/bin/systemctl','restart',BROKER)
    command('/usr/bin/systemctl','restart',BUILDER)
    results['broker_active']=command('/usr/bin/systemctl','is-active',BROKER)=='active'
    results['broker_enabled']=command('/usr/bin/systemctl','is-enabled',BROKER)=='enabled'
    results['no_real_credential']=not key.exists()
    results['completed']=True
    return results
