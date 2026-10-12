import json
import os
import socket
import threading
import multiprocessing
import time
from pathlib import Path
import pytest
from personal_ai_brain import coding_policy as policy
from personal_ai_brain.inference_acceptance import Provider
from personal_ai_brain.inference_broker import loop
from personal_ai_brain.inference_usage import Ledger
from personal_ai_brain.inference_install_key import install_at, directory
from personal_ai_brain.coding_protocol import receive, send, CodingFailure
from personal_ai_brain.coding_workspace import Workspace
from test_coding_broker import task, workspace

def spawned_stub(connection, value, root):
    from personal_ai_brain import inference_broker
    inference_broker.STATE=Path(root)
    policy.PRICE_REVIEW_UNTIL='2099-01-01'
    inference_broker.child(connection,value,{'provider':'acceptance','scenario':'success'})

def test_spawned_broker_socket_restores_timeout(tmp_path):
    w=Workspace(workspace(tmp_path))
    left,right=socket.socketpair(); left.settimeout(0.2); right.settimeout(0.2)
    process=multiprocessing.get_context('spawn').Process(target=spawned_stub,args=(right,task(),str(tmp_path/'ledger')))
    process.start(); right.close()
    deadline=time.monotonic()+10
    def guard():
        if time.monotonic()>deadline: raise CodingFailure('interrupted')
    seen=[]
    try:
        while True:
            message=receive(left,guard)
            if message['kind']=='tool':
                seen.append(message['name'])
                send(left,{'kind':'tool_result','result':w.invoke(message['name'],message['arguments'])})
            elif message['kind']=='complete': break
            elif message['kind']=='failure': pytest.fail(message['code'])
        assert seen==['list_files','read_file','search_text','apply_patch']
        process.join(2); assert process.exitcode==0
    finally:
        if process.is_alive(): process.kill(); process.join()
        left.close(); w.close()

def test_acceptance_uses_all_mediated_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, 'PRICE_REVIEW_UNTIL', '2099-01-01')
    w = Workspace(workspace(tmp_path))
    left, right = socket.socketpair()
    thread = threading.Thread(target=loop, args=(right, task(), Ledger(tmp_path/'ledger', 'acceptance'), Provider('success')))
    thread.start(); seen = []
    try:
        while True:
            message = receive(left)
            if message['kind'] == 'tool':
                seen.append(message['name'])
                send(left, {'kind': 'tool_result', 'result': w.invoke(message['name'], message['arguments'])})
            elif message['kind'] == 'complete': break
        assert seen == ['list_files', 'read_file', 'search_text', 'apply_patch']
        assert w.validate()[0] == [policy.TARGET]
    finally:
        left.close(); right.close(); thread.join(2); w.close()
    assert not thread.is_alive()

def test_synthetic_installer_modes_and_symlink_rejection(tmp_path):
    tmp_path.chmod(0o700)
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        install_at(fd, b'synthetic-only-not-an-api-key', os.getuid(), os.getgid())
        key = tmp_path/'openai-api-key'
        assert key.stat().st_mode & 0o777 == 0o600
        key.unlink(); key.symlink_to(tmp_path/'outside')
        with pytest.raises(ValueError): install_at(fd, b'synthetic-only-not-an-api-key', os.getuid(), os.getgid())
        assert not (tmp_path/'outside').exists()
        tmp_path.chmod(0o755)
        with pytest.raises(ValueError): install_at(fd, b'synthetic-only-not-an-api-key', os.getuid(), os.getgid())
    finally: os.close(fd)

def test_installer_rejects_writable_ancestor(tmp_path):
    with pytest.raises(ValueError): directory(str(tmp_path), os.getuid())

def test_acceptance_budget_does_not_consume_real_budget_or_allow_uuid_reuse(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, 'PRICE_REVIEW_UNTIL', '2099-01-01')
    monkeypatch.setattr(policy, 'MONTH_BUDGET_MICRO_USD', 250000)
    fake, real = Ledger(tmp_path, 'acceptance'), Ledger(tmp_path, 'openai')
    first, second = task(), task()
    fake.start(first); fake.reserve(first['task_id'])
    real.start(second); real.reserve(second['task_id'])
    with pytest.raises(CodingFailure): real.start(first)

@pytest.mark.parametrize('status,body,expected', [(401,b'{}','model_auth_failed'),
    (403,b'{}','model_auth_failed'), (429,b'{}','model_rate_limited'),
    (429,b'{"error":{"code":"project_spend_limit_exceeded"}}','model_quota_or_spend_limit')])
def test_http_failures_through_real_adapter(monkeypatch,status,body,expected):
    import io
    import urllib.error
    from personal_ai_brain import inference_provider as p
    monkeypatch.setattr(p,'credential',lambda:'synthetic-only-test-key')
    class Opener:
        def open(self,*args,**kwargs): raise urllib.error.HTTPError(p.policy.ENDPOINT,status,'private message',{},io.BytesIO(body))
    monkeypatch.setattr(p.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(CodingFailure,match='^'+expected+'$'): p.respond(p.request([]))

def test_actual_adapter_timeout_and_bounded_response(monkeypatch):
    from personal_ai_brain import inference_provider as p
    monkeypatch.setattr(p,'credential',lambda:'synthetic-only-test-key')
    class Timeout:
        def open(self,*a,**k): raise TimeoutError('private details')
    monkeypatch.setattr(p.urllib.request,'build_opener',lambda *a:Timeout())
    with pytest.raises(CodingFailure,match='^model_timeout$'): p.respond(p.request([]))
    class Oversize:
        def open(self,*a,**k): return self
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self,n): return b'x'*n
    monkeypatch.setattr(p.urllib.request,'build_opener',lambda *a:Oversize())
    with pytest.raises(CodingFailure,match='^model_invalid_response$'): p.respond(p.request([]))

def test_module_entrypoint_uses_shared_abort(tmp_path):
    import runpy
    from personal_ai_brain.work_contract import Abort
    from personal_ai_brain.coding_execute import execute
    with pytest.warns(RuntimeWarning, match='found in sys.modules'):
        namespace=runpy.run_module('personal_ai_brain.work_runner',run_name='entrypoint_regression')
    assert namespace['Abort'] is Abort
    root=workspace(tmp_path); audit=tmp_path/'audit'; audit.mkdir()
    def guard(): raise namespace['Abort']('failed','deadline_exceeded')
    assert execute(task(),root,audit,guard)==('failed','deadline_exceeded')

@pytest.mark.parametrize('framed',[True,False])
def test_key_installer_ready_handshake_and_framing(tmp_path,monkeypatch,capsys,framed):
    import io
    import types
    from personal_ai_brain import inference_install_key as installer
    uid,gid=os.getuid(),os.getgid(); tmp_path.chmod(0o700)
    monkeypatch.setattr(installer.os,'geteuid',lambda:0)
    monkeypatch.setattr(installer.pwd,'getpwnam',lambda _:types.SimpleNamespace(pw_uid=uid,pw_gid=gid))
    monkeypatch.setattr(installer,'directory',lambda *a:os.open(tmp_path,os.O_RDONLY|os.O_DIRECTORY))
    monkeypatch.setattr(installer.sys,'argv',['installer'])
    raw=(b'PAB-INFERENCE-KEY-V1\n' if framed else b'wrong-frame\n')+b'synthetic-installer-key\n'
    monkeypatch.setattr(installer.sys,'stdin',types.SimpleNamespace(buffer=io.BytesIO(raw)))
    if framed:
        installer.main()
        assert capsys.readouterr().out=='INFERENCE_KEY_READY\nINFERENCE_KEY_INSTALLED\n'
        assert (tmp_path/'openai-api-key').stat().st_mode & 0o777==0o600
    else:
        with pytest.raises(ValueError,match='invalid_input_frame'): installer.main()
        assert capsys.readouterr().out=='INFERENCE_KEY_READY\n'
        assert not (tmp_path/'openai-api-key').exists()
