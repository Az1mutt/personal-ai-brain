"""Administrative stdin-only installer. Never invoke with a key argument."""
import os
import pwd
import stat
import sys
import uuid

DIRECTORY = '/etc/personal-ai-brain/inference/credentials'

def directory(path, owner):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        parts = path.strip('/').split('/')
        for index, part in enumerate(parts):
            if part in ('', '.', '..'): raise ValueError('unsafe_parent')
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = nxt
            info = os.fstat(fd)
            expected = owner if index == len(parts) - 1 else 0
            if info.st_uid != expected or stat.S_IMODE(info.st_mode) & 0o022:
                raise ValueError('unsafe_parent')
        return fd
    except BaseException:
        os.close(fd)
        raise

def install_at(fd, raw, owner, group):
    info = os.fstat(fd)
    if info.st_uid != owner or info.st_gid != group or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('unsafe_credential_directory')
    value = raw.rstrip(b'\r\n')
    if not 16 <= len(value) <= 1024 or any(c < 33 or c > 126 for c in value):
        raise ValueError('invalid_input')
    name = 'openai-api-key'
    try:
        old = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(old.st_mode) or old.st_nlink != 1 or old.st_uid != owner or old.st_gid != group or stat.S_IMODE(old.st_mode) != 0o600:
            raise ValueError('unsafe_existing_file')
    except FileNotFoundError: pass
    temporary = '.' + uuid.uuid4().hex
    file = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(file, 'wb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), owner, group)
            stream.write(value + b'\n'); stream.flush(); os.fsync(stream.fileno())
        os.rename(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), info.st_nlink) != (owner, group, 0o600, 1):
            raise ValueError('installation_validation_failed')
    finally:
        try: os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError: pass

def main():
    if os.geteuid() != 0 or len(sys.argv) != 1: raise ValueError('administrative_stdin_only')
    account = pwd.getpwnam('pab-inference')
    fd = directory(DIRECTORY, account.pw_uid)
    try:
        print('INFERENCE_KEY_READY', flush=True)
        raw = sys.stdin.buffer.read(1050)
        prefix = b'PAB-INFERENCE-KEY-V1\n'
        if not raw.startswith(prefix): raise ValueError('invalid_input_frame')
        install_at(fd, raw[len(prefix):], account.pw_uid, account.pw_gid)
    finally: os.close(fd)
    print('INFERENCE_KEY_INSTALLED')

if __name__ == '__main__':
    try: main()
    except Exception: raise SystemExit('INFERENCE_KEY_INSTALL_FAILED') from None
