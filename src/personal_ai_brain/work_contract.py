"""Strict Work Contract v0.1. Text fields describe the one fixed fixture only."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import uuid
from . import coding_policy

REPOSITORY = 'Az1mutt/personal-ai-brain'
TASK_TYPE = 'fixture.patch-test.v1'
GOAL = 'Create the deterministic Work Runner fixture artifact.'
CRITERIA = ['fixture content matches', 'isolation checks pass']
FIELDS = {'schema_version', 'task_id', 'task_type', 'repository', 'base_ref',
          'goal', 'acceptance_criteria', 'requested_at', 'deadline_seconds'}

class Rejected(ValueError):
    pass

def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def task_id(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise Rejected('invalid_task_id') from None
    return value

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected('duplicate_json_key')
        result[key] = value
    return result

def parse(raw):
    if not isinstance(raw, bytes) or len(raw) > 8192:
        raise Rejected('invalid_payload_size')
    try:
        value = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(Rejected('nonfinite_json')))
        if not isinstance(value, dict) or set(value) != FIELDS:
            raise Rejected('invalid_fields')
        task_id(value['task_id'])
        coding = value['task_type'] == coding_policy.TYPE
        if (value['schema_version'] != '0.1' or value['task_type'] not in (TASK_TYPE, coding_policy.TYPE)
                or value['repository'] != REPOSITORY):
            raise Rejected('unsupported_contract')
        if coding:
            texts = value['acceptance_criteria']
            if (not isinstance(texts, list) or not 1 <= len(texts) <= 5 or
                    any(not isinstance(t, str) or not 1 <= len(t) <= 300 for t in texts) or
                    not isinstance(value['goal'], str) or not 1 <= len(value['goal']) <= 2000):
                raise Rejected('invalid_coding_text')
            if any(re.search(r'://|(?:^|\s)(?:/|[A-Za-z]:\\)|[\x00-\x08\x0b-\x1f]', t)
                   for t in [value['goal'], *texts]):
                raise Rejected('invalid_coding_text')
            if value['base_ref'] != coding_policy.BASE:
                raise Rejected('base_not_allowlisted')
            # v0.1 has one reviewed acceptance profile; never claim arbitrary
            # caller goals passed merely because this profile's tests passed.
            if value['goal'] != coding_policy.GOAL or texts != coding_policy.CRITERIA:
                raise Rejected('unsupported_coding_profile')
        elif value['goal'] != GOAL or value['acceptance_criteria'] != CRITERIA:
            raise Rejected('unsupported_contract')
        if not isinstance(value['base_ref'], str) or not re.fullmatch('[0-9a-f]{40}', value['base_ref']):
            raise Rejected('immutable_base_required')
        if type(value['deadline_seconds']) is not int or not 1 <= value['deadline_seconds'] <= (180 if coding else 60):
            raise Rejected('invalid_deadline')
        requested = datetime.fromisoformat(value['requested_at'].replace('Z', '+00:00'))
        if requested.tzinfo is None:
            raise Rejected('timezone_required')
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as error:
        if isinstance(error, Rejected):
            raise
        raise Rejected('invalid_json_or_timestamp') from None
    return value

def allowed_base(request, fixture_base):
    return coding_policy.BASE if request['task_type'] == coding_policy.TYPE else fixture_base

def fresh(request):
    requested = datetime.fromisoformat(request['requested_at'].replace('Z', '+00:00'))
    age = datetime.now(timezone.utc) - requested
    if not -timedelta(minutes=5) <= age <= timedelta(days=7):
        raise Rejected('stale_or_future_request')

def digest(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()
