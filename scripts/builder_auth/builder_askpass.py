#!/usr/bin/python3 -I
"""Credential provider for the explicitly allowed HTTPS Git context only."""
import os
import stat
import sys

TOKEN = '/home/az1mutt/.config/personal-ai-brain/builder/github-token'

def read_token():
    parent = os.lstat(os.path.dirname(TOKEN))
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700:
        raise ValueError('credential directory rejected')
    fd = os.open(TOKEN, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError('credential file rejected')
        token = stream.read(1001)
    if not token.startswith('github_pat_') or not 30 < len(token) < 1000 or not all(c.isalnum() or c == '_' for c in token):
        raise ValueError('credential format rejected')
    return token

def main():
    if len(sys.argv) != 2:
        return 1
    prompt = sys.argv[1]
    if prompt == "Username for 'https://github.com/Az1mutt/personal-ai-brain.git': ":
        print('Az1mutt')
    elif prompt == "Password for 'https://Az1mutt@github.com/Az1mutt/personal-ai-brain.git': ":
        print(read_token())
    else:
        return 1
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
