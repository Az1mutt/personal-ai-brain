"""Length-framed bounded JSON over a local Unix socket; no object deserialization."""
import json
import socket
import struct
from .work_contract import unique_object

LIMIT = 65536
CODES = {'model_auth_failed', 'model_rate_limited', 'model_quota_or_spend_limit',
         'model_network_failed', 'model_timeout', 'model_invalid_response',
         'model_budget_exceeded', 'patch_rejected', 'deterministic_validation_failed',
         'tests_failed', 'interrupted'}
class CodingFailure(Exception):
    pass

def peer_uid(connection):
    return struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]

def require_peer(connection, expected):
    if peer_uid(connection) != expected:
        raise CodingFailure('model_auth_failed')

def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()

def send(sock, value):
    data = encoded(value)
    if len(data) > LIMIT:
        raise CodingFailure('model_invalid_response')
    sock.sendall(struct.pack('!I', len(data)) + data)

def receive(sock, guard=lambda: None):
    def read(count):
        chunks = bytearray()
        while len(chunks) < count:
            guard()
            try:
                data = sock.recv(count - len(chunks))
            except socket.timeout:
                continue
            if not data:
                raise CodingFailure('interrupted')
            chunks.extend(data)
        return bytes(chunks)
    size = struct.unpack('!I', read(4))[0]
    if not 1 <= size <= LIMIT:
        raise CodingFailure('model_invalid_response')
    try:
        value = json.loads(read(size), object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, RecursionError, UnicodeError):
        raise CodingFailure('model_invalid_response') from None
