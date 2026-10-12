"""FUTURE owner-operated paid acceptance. Never run during credentialless slice."""
import json
import os
from pathlib import Path
import pwd
import stat
import sys
from datetime import date

def main():
    if os.geteuid()!=0 or sys.argv[1:]!=['--owner-confirmed-project-hard-cap']:
        raise ValueError('owner_gate_required')
    from credentialless_acceptance import CONFIG, BROKER, BUILDER, request, submit, wait, command
    from personal_ai_brain import coding_policy as policy
    from personal_ai_brain.work_store import atomic_json
    from personal_ai_brain.inference_install_key import DIRECTORY, directory
    if date.today().isoformat()>policy.PRICE_REVIEW_UNTIL: raise ValueError('pricing_review_required')
    account=pwd.getpwnam('pab-inference')
    fd=directory(DIRECTORY,account.pw_uid)
    try: info=os.stat('openai-api-key',dir_fd=fd,follow_symlinks=False)
    finally: os.close(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=account.pw_uid or info.st_gid!=982
            or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1): raise ValueError('credential_not_ready')
    evidence=Path('/var/lib/personal-ai-brain/credentialless-broker-evidence.json')
    if json.loads(evidence.read_bytes()).get('completed') is not True: raise ValueError('credentialless_acceptance_required')
    record=Path('/var/lib/personal-ai-brain/broker-live-acceptance-task.json')
    # Re-invoking this administrative procedure reuses the exact task, never pays twice.
    if record.exists(): task=json.loads(record.read_bytes())
    else:
        task=request(180); atomic_json(record,task)
    dropin=Path('/etc/systemd/system')/(BROKER+'.d')/'credentialless.conf'
    if dropin.is_symlink(): raise ValueError('unsafe_dropin')
    profile=Path('/etc/personal-ai-brain/builder/profile.json')
    try:
        CONFIG.write_text(json.dumps({'schema_version':'0.1','provider':'openai','scenario':'success'})+'\n')
        dropin.unlink(missing_ok=True)
        value=json.loads(profile.read_bytes()); value['coding_enabled']=True; profile.write_text(json.dumps(value)+'\n')
        command('/usr/bin/systemctl','daemon-reload')
        command('/usr/bin/systemctl','restart',BROKER)
        command('/usr/bin/systemctl','restart',BUILDER)
        submit(task)
        result=wait(task, seconds=200)
        print(json.dumps({'task_id':task['task_id'],'status':result['status'],'code':result['history'][-1]['code']}))
    finally:
        CONFIG.write_text(json.dumps({'schema_version':'0.1','provider':'disabled','scenario':'success'})+'\n')
        dropin.write_text('[Service]\nPrivateNetwork=yes\nIPAddressDeny=any\n')
        value=json.loads(profile.read_bytes()); value['coding_enabled']=False; profile.write_text(json.dumps(value)+'\n')
        command('/usr/bin/systemctl','daemon-reload')
        command('/usr/bin/systemctl','restart',BROKER)
        command('/usr/bin/systemctl','restart',BUILDER)

if __name__=='__main__':
    try: main()
    except Exception: raise SystemExit('REAL_ACCEPTANCE_STOPPED_REVIEW_DURABLE_TASK') from None
