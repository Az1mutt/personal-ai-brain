"""Fixed Responses adapter. No retries, redirects, proxy configuration or raw logs."""
import json
import os
from pathlib import Path
import socket
import stat
import urllib.error
import urllib.request
from . import coding_policy as policy
from .coding_protocol import CodingFailure, encoded
from .work_contract import unique_object

CREDENTIAL = Path('/etc/personal-ai-brain/inference/credentials/openai-api-key')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def credential(path=CREDENTIAL):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid() or info.st_size > 1024):
            raise CodingFailure('model_auth_failed')
        value = stream.read(1025).strip()
    if not value or any(c < 33 or c > 126 for c in value):
        raise CodingFailure('model_auth_failed')
    return value.decode('ascii')

def failure(status, raw):
    if status in (401, 403):
        return 'model_auth_failed'
    if status == 429:
        try: code = json.loads(raw)['error']['code']
        except (ValueError, KeyError, TypeError): code = None
        if code in {'insufficient_quota', 'project_spend_limit_exceeded', 'organization_spend_limit_exceeded', 'credit_balance_exhausted'}:
            return 'model_quota_or_spend_limit'
        return 'model_rate_limited'
    return 'model_network_failed'

def request(history):
    body = {'model': policy.MODEL, 'instructions': policy.POLICY, 'input': history,
            'tools': policy.tools(), 'parallel_tool_calls': False, 'store': False,
            'include': ['reasoning.encrypted_content'],
            'reasoning': {'effort': 'medium'}, 'max_output_tokens': policy.MAX_OUTPUT_TOKENS,
            'service_tier': 'default', 'text': {'format': {'type': 'json_schema', 'name': 'coding_summary',
            'strict': True, 'schema': {'type': 'object', 'properties': {'summary': {'type': 'string'}},
                                     'required': ['summary'], 'additionalProperties': False}}}}
    raw = encoded(body)
    if len(raw) > policy.MAX_REQUEST_BYTES:
        raise CodingFailure('model_budget_exceeded')
    return raw

def respond(raw):
    try: key = credential()
    except (OSError, CodingFailure): raise CodingFailure('model_auth_failed') from None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        req = urllib.request.Request(policy.ENDPOINT, data=raw, method='POST',
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with opener.open(req, timeout=20) as response:
            data = response.read(policy.MAX_RESPONSE_BYTES + 1)
        if len(data) > policy.MAX_RESPONSE_BYTES:
            raise CodingFailure('model_invalid_response')
        result = json.loads(data, object_pairs_hook=unique_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(result, dict) or result.get('status') != 'completed' or not isinstance(result.get('output'), list):
            raise CodingFailure('model_invalid_response')
        return result
    except urllib.error.HTTPError as error:
        raise CodingFailure(failure(error.code, error.read(4096))) from None
    except (TimeoutError, socket.timeout):
        raise CodingFailure('model_timeout') from None
    except urllib.error.URLError as error:
        raise CodingFailure('model_timeout' if isinstance(error.reason, TimeoutError) else 'model_network_failed') from None
    except (ValueError, TypeError, KeyError):
        raise CodingFailure('model_invalid_response') from None
    except OSError:
        raise CodingFailure('model_network_failed') from None
