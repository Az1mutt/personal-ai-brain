"""Single-host filesystem truth; private atomic records, fsync and flock."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import uuid

from .work_contract import Rejected, digest, fresh, task_id, timestamp

TERMINAL = {'succeeded', 'failed', 'blocked', 'cancelled', 'interrupted'}
EDGES = {'submitted': {'reserved', 'blocked', 'cancelled', 'failed'},
         'reserved': {'running', 'blocked', 'failed', 'cancelled', 'interrupted'},
         'running': TERMINAL}

def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def atomic_bytes(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)

def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, sort_keys=True, ensure_ascii=True) + '\n').encode())

@contextmanager
def locked(path, nonblocking=False):
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'r+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.state = self.root / 'state'
        self.tasks = self.state / 'tasks'
        self.audit = self.root / 'audit'
        self.workspaces = self.root / 'workspaces'
        for path in (self.root, self.state, self.tasks, self.audit, self.workspaces):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            sync_directory(path.parent)

    def lock(self):
        return locked(self.state / 'state.lock')

    def path(self, identifier):
        return self.tasks / (task_id(identifier) + '.json')

    def load(self, identifier):
        path = self.path(identifier)
        # Never treat unreadable/corrupt state as an absent request.
        return json.loads(path.read_bytes()) if path.exists() else None

    def submit(self, request, allowed_base):
        with self.lock():
            existing = self.load(request['task_id'])
            if existing:
                if existing['payload_hash'] != digest(request):
                    raise Rejected('task_id_payload_conflict')
                return existing, False
            fresh(request)
            if request['base_ref'] != allowed_base:
                raise Rejected('base_not_allowlisted')
            if len(list(self.tasks.glob('*.json'))) >= 256:
                raise Rejected('retention_capacity_reached')
            identifier = request['task_id']
            artifacts = self.audit / identifier
            # An orphan directory means interrupted admission, not permission to
            # erase evidence or reuse the ID. An operator must reconcile it.
            artifacts.mkdir(mode=0o700)
            sync_directory(self.audit)
            reserve = artifacts / 'emergency.reserve'
            fd = os.open(reserve, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.posix_fallocate(fd, 0, 131072)
                os.fsync(fd)
            finally:
                os.close(fd)
            record = {'schema_version': '0.1', 'task_id': identifier,
                      'request': request, 'payload_hash': digest(request),
                      'status': 'submitted', 'attempts': 0, 'cancel_requested': False,
                      'history': [{'status': 'submitted', 'at': timestamp(), 'code': 'accepted'}]}
            atomic_bytes(artifacts / 'execution.log', b'submitted\n')
            atomic_bytes(artifacts / 'patch.diff', b'')
            atomic_json(artifacts / 'test-result.json', {'status': 'not_run'})
            atomic_json(artifacts / 'result.json', record)
            atomic_json(self.path(identifier), record)
            return record, True

    def transition_locked(self, record, status, code, **extra):
        if status not in EDGES.get(record['status'], set()):
            raise ValueError('invalid_transition')
        record = {**record, **extra, 'status': status,
                  'history': [*record['history'], {'status': status, 'at': timestamp(), 'code': code}]}
        if status in TERMINAL:
            record['finished_at'] = timestamp()
            # Artifact publication precedes terminal truth. A crash between these
            # writes is recovered as interrupted, never as a second invocation.
            atomic_json(self.audit / record['task_id'] / 'result.json', record)
        atomic_json(self.path(record['task_id']), record)
        return record

    def transition(self, identifier, status, code, **extra):
        with self.lock():
            record = self.load(identifier)
            if record['status'] in TERMINAL:
                return record
            if record['cancel_requested'] and status in {'reserved', 'running', 'succeeded'}:
                status, code = 'cancelled', 'cancellation_requested'
            return self.transition_locked(record, status, code, **extra)

    def cancel(self, identifier):
        with self.lock():
            record = self.load(identifier)
            if not record:
                raise Rejected('unknown_task')
            if record['status'] in TERMINAL:
                return record
            record['cancel_requested'] = True
            record['cancel_requested_at'] = timestamp()
            if record['status'] == 'submitted':
                return self.transition_locked(record, 'cancelled', 'cancelled_before_reservation')
            atomic_json(self.path(identifier), record)
            return record

    def records(self):
        return [json.loads(path.read_bytes()) for path in sorted(self.tasks.glob('*.json'))]

    def storage_failure(self, identifier):
        # Release preallocated headroom before recording ENOSPC/EIO. If storage is
        # still unavailable, the previously fsynced nonterminal record survives;
        # the service exits and recovery marks it interrupted without replay.
        (self.audit / identifier / 'emergency.reserve').unlink(missing_ok=True)
        sync_directory(self.audit / identifier)
        record = self.load(identifier)
        if record['status'] not in TERMINAL:
            atomic_bytes(self.audit / identifier / 'execution.log', b'storage_error; task not retried\n')
            atomic_json(self.audit / identifier / 'test-result.json', {'status': 'not_completed', 'code': 'storage_error'})
            return self.transition(identifier, 'failed', 'storage_error')
        return record
