#!/usr/bin/python3
"""One-repository, one-branch bootstrap publisher. No generic shell/API interface."""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from builder_askpass import read_token

REPO = '/home/az1mutt/projects/personal-ai-brain'
BRANCH = 'docs/builder-execution-reconciliation'
BASE = '8f5c19ec3780f1afdf76538d0363e4632f9308f9'
URL = 'https://github.com/Az1mutt/personal-ai-brain.git'
HELPER = '/home/az1mutt/.local/lib/personal-ai-brain/builder-auth/builder_askpass.py'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main(action):
    if action not in ('verify', 'push'):
        raise ValueError()
    # Read-only authenticated probe; do not print response or authorization headers.
    request = urllib.request.Request('https://api.github.com/repos/Az1mutt/personal-ai-brain', headers={
        'Authorization': 'Bearer ' + read_token(), 'Accept': 'application/vnd.github+json',
        'User-Agent': 'personal-ai-brain-builder-auth'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=20) as response:
        data = json.load(response)
    if data.get('full_name') != 'Az1mutt/personal-ai-brain':
        raise ValueError()
    print('AUTHENTICATED_REPOSITORY_READ_OK', flush=True)
    if action == 'verify':
        return
    # Preserve normal repository/system Git hooks. Clear inherited tracing and
    # credential environment; reject URL rewrites, extra auth headers or proxies.
    env = {'PATH':'/usr/bin:/bin', 'HOME':'/home/az1mutt', 'LC_ALL':'C',
           'GIT_TERMINAL_PROMPT':'0', 'GIT_ASKPASS':HELPER}
    def git(*args):
        return subprocess.run(['/usr/bin/git', '-C', REPO, *args], env=env, capture_output=True, text=True, timeout=90)
    config = git('config', '--name-only', '--list')
    keys = config.stdout.lower().splitlines()
    if config.returncode or any(k.startswith('url.') or 'extraheader' in k or 'proxy' in k for k in keys):
        raise ValueError()
    head_result = git('rev-parse', 'refs/heads/' + BRANCH)
    head = head_result.stdout.strip()
    if head_result.returncode or len(head) != 40 or any(c not in '0123456789abcdef' for c in head):
        raise ValueError()
    if git('merge-base', '--is-ancestor', BASE, head).returncode:
        raise ValueError()
    common = ['-c', 'credential.helper=', '-c', 'credential.useHttpPath=true',
              '-c', 'credential.username=Az1mutt',
              '-c', 'http.followRedirects=false', '-c', 'http.sslVerify=true',
              '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
              'push', '--porcelain']
    for dry in (True, False):
        result = git(*common, *(['--dry-run'] if dry else []), URL, head + ':refs/heads/' + BRANCH)
        if result.returncode:
            print('DRY_RUN_FAILED' if dry else 'PUSH_FAILED_NO_AUTOMATIC_RETRY')
            return 1
        print('DRY_RUN_OK' if dry else 'BRANCH_PUSH_OK ' + head, flush=True)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
    except urllib.error.HTTPError as error:
        print('AUTH_HTTP_' + str(error.code))
        sys.exit(1)
    except Exception:
        print('BOUNDED_OPERATION_FAILED')
        sys.exit(1)
