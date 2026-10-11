"""Fsynced reservations precede paid requests; unknown outcomes are never replayed."""
from datetime import datetime, timezone
from pathlib import Path
import json
from . import coding_policy as policy
from .coding_protocol import CodingFailure
from .work_contract import digest, task_id, timestamp
from .work_store import atomic_json, locked

class Ledger:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def path(self, identifier):
        return self.root / (task_id(identifier) + '.json')

    def recover(self):
        with locked(self.root / 'ledger.lock'):
            for path in self.root.glob('*.json'):
                value = json.loads(path.read_bytes())
                if value['status'] == 'reserved':
                    value.update(status='interrupted', finished_at=timestamp())
                    atomic_json(path, value)

    def start(self, task):
        with locked(self.root / 'ledger.lock'):
            path = self.path(task['task_id'])
            if path.exists():
                raise CodingFailure('interrupted')
            if len(list(self.root.glob('*.json'))) >= 256:
                raise CodingFailure('model_budget_exceeded')
            value = {'task_id': task['task_id'], 'payload_hash': digest(task),
                     'status': 'reserved', 'started_at': timestamp(), 'turns': []}
            atomic_json(path, value)
            return value

    def reserve(self, identifier):
        with locked(self.root / 'ledger.lock'):
            now = datetime.now(timezone.utc)
            if now.date().isoformat() > policy.PRICE_REVIEW_UNTIL:
                raise CodingFailure('model_budget_exceeded')
            path = self.path(identifier)
            value = json.loads(path.read_bytes())
            month = now.strftime('%Y-%m')
            total = 0
            for record in self.root.glob('*.json'):
                total += sum(t['reserved_micro_usd'] for t in json.loads(record.read_bytes())['turns'] if t['month'] == month)
            if (len(value['turns']) >= policy.MAX_TURNS or
                    (len(value['turns']) + 1) * policy.TURN_RESERVE_MICRO_USD > policy.TASK_BUDGET_MICRO_USD or
                    total + policy.TURN_RESERVE_MICRO_USD > policy.MONTH_BUDGET_MICRO_USD):
                raise CodingFailure('model_budget_exceeded')
            value['turns'].append({'month': month, 'reserved_at': timestamp(),
                                  'reserved_micro_usd': policy.TURN_RESERVE_MICRO_USD,
                                  'status': 'outcome_unknown'})
            atomic_json(path, value)
            return value

    def usage(self, identifier, usage):
        # Strict integer projection; no provider text/headers/response IDs retained.
        if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or not 0 <= usage[k] <= 1000000
                                             for k in ('input_tokens', 'output_tokens')):
            raise CodingFailure('model_invalid_response')
        with locked(self.root / 'ledger.lock'):
            path = self.path(identifier)
            value = json.loads(path.read_bytes())
            turn = value['turns'][-1]
            turn.update(status='usage_received', input_tokens=usage['input_tokens'], output_tokens=usage['output_tokens'])
            # Conservative estimate includes cache writes/regional headroom; reservation is never refunded.
            turn['estimated_micro_usd'] = usage['input_tokens'] * 3 + usage['output_tokens'] * 11
            atomic_json(path, value)
            if turn['estimated_micro_usd'] > turn['reserved_micro_usd']:
                raise CodingFailure('model_budget_exceeded')
            return value

    def finish(self, identifier, code):
        with locked(self.root / 'ledger.lock'):
            path = self.path(identifier)
            value = json.loads(path.read_bytes())
            value.update(status=code, finished_at=timestamp())
            atomic_json(path, value)
            return value
