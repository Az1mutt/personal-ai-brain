"""Supervisor-owned mediated workspace operations, never a shell or model path API."""
import ast
import difflib
import os
from pathlib import Path
import stat
import uuid
from .coding_policy import TARGET
from .coding_protocol import CodingFailure

class Workspace:
    def __init__(self, root):
        self.root = Path(root)
        self.fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: self.original = self.snapshot()
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        os.close(self.fd)

    def parts(self, name):
        if (not isinstance(name, str) or not 1 <= len(name) <= 200 or '\\' in name
                or ':' in name or name.startswith('/') or any(
                    p in ('', '.', '..') or p.startswith('.') for p in name.split('/'))):
            raise CodingFailure('patch_rejected')
        return name.split('/')

    def parent(self, name):
        parts = self.parts(name)
        fd = os.dup(self.fd)
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            return fd, parts[-1]
        except BaseException:
            os.close(fd)
            raise

    def read(self, name):
        fd, leaf = self.parent(name)
        try:
            file = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(file, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16384:
                    raise CodingFailure('patch_rejected')
                data = stream.read(16385)
                if len(data) > 16384 or b'\0' in data:
                    raise CodingFailure('patch_rejected')
                return data.decode('utf-8')
        finally:
            os.close(fd)

    def files(self):
        names = []
        for parent, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(parent)/d).is_symlink())
            for name in sorted(files):
                path = Path(parent)/name
                if name.startswith('.') or path.is_symlink() or path.suffix not in ('.py', '.md', '.toml', '.yaml'):
                    continue
                names.append(path.relative_to(self.root).as_posix())
                if len(names) > 256:
                    raise CodingFailure('deterministic_validation_failed')
        return names

    def snapshot(self):
        # Hash all files including dotfiles/Git metadata; never follow symlinks.
        import hashlib
        result = {}
        total = 0
        for parent, dirs, files in os.walk(self.root, followlinks=False):
            if any((Path(parent)/d).is_symlink() for d in dirs):
                raise CodingFailure('deterministic_validation_failed')
            for name in files:
                path = Path(parent)/name
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 8388608:
                    raise CodingFailure('deterministic_validation_failed')
                total += info.st_size
                if len(result) >= 4096 or total > 67108864:
                    raise CodingFailure('deterministic_validation_failed')
                result[path.relative_to(self.root).as_posix()] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(info.st_mode))
        return result

    def apply(self, name, old, new):
        if name != TARGET or not all(isinstance(x, str) and len(x.encode()) <= 8192 for x in (old, new)):
            raise CodingFailure('patch_rejected')
        fd, leaf = self.parent(name)
        temporary = '.' + uuid.uuid4().hex
        try:
            try:
                before = self.read(name)
            except FileNotFoundError:
                before = ''
            if old:
                if before.count(old) != 1:
                    raise CodingFailure('patch_rejected')
                after = before.replace(old, new, 1)
            else:
                if before:
                    raise CodingFailure('patch_rejected')
                after = new
            if len(after.encode()) > 8192:
                raise CodingFailure('patch_rejected')
            file = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            with os.fdopen(file, 'w', encoding='utf-8') as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            os.rename(temporary, leaf, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
            return {'changed': before != after}
        finally:
            try: os.unlink(temporary, dir_fd=fd)
            except FileNotFoundError: pass
            os.close(fd)

    def invoke(self, name, args):
        if not isinstance(args, dict):
            raise CodingFailure('patch_rejected')
        if name == 'list_files' and args == {}:
            return {'files': self.files()}
        if name == 'read_file' and set(args) == {'path'}:
            if args['path'] not in self.files():
                raise CodingFailure('patch_rejected')
            return {'text': self.read(args['path'])}
        if name == 'search_text' and set(args) == {'text'}:
            text = args['text']
            if not isinstance(text, str) or not 1 <= len(text) <= 100:
                raise CodingFailure('patch_rejected')
            hits = []
            for path in self.files():
                try: content = self.read(path)
                except (OSError, UnicodeError, CodingFailure): continue
                for number, line in enumerate(content.splitlines(), 1):
                    if text in line:
                        hits.append({'path': path, 'line': number, 'text': line[:200]})
                    if len(hits) == 20: return {'matches': hits, 'bounded': True}
            return {'matches': hits, 'bounded': True}
        if name == 'apply_patch' and set(args) == {'path', 'old', 'new'}:
            return self.apply(args['path'], args['old'], args['new'])
        raise CodingFailure('patch_rejected')

    def validate(self):
        current = self.snapshot()
        changed = sorted(p for p in set(current) | set(self.original) if current.get(p) != self.original.get(p))
        if changed != [TARGET] or TARGET in self.original:
            raise CodingFailure('deterministic_validation_failed')
        content = self.read(TARGET)
        if not content.endswith('\n'):
            raise CodingFailure('deterministic_validation_failed')
        try: tree = ast.parse(content)
        except (SyntaxError, ValueError): raise CodingFailure('deterministic_validation_failed') from None
        # Reviewed acceptance profile is a pure string-normalization function.
        # No executable module initialization/imports or dynamic Python escapes.
        definitions = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if len(definitions) != 1 or not isinstance(definitions[0], ast.FunctionDef):
            raise CodingFailure('deterministic_validation_failed')
        fn = definitions[0]
        if (fn.name != 'normalize_label' or fn.decorator_list or fn.args.defaults or fn.args.kw_defaults
                or fn.returns or fn.args.vararg or fn.args.kwarg or fn.args.posonlyargs or fn.args.kwonlyargs
                or len(fn.args.args) != 1 or fn.args.args[0].arg != 'value' or fn.args.args[0].annotation):
            raise CodingFailure('deterministic_validation_failed')
        allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Expr, ast.Constant,
                   ast.If, ast.UnaryOp, ast.Not, ast.Call, ast.Name, ast.Load, ast.Store,
                   ast.Return, ast.Raise, ast.Attribute, ast.Assign)
        for node in ast.walk(tree):
            if (not isinstance(node, allowed) or (isinstance(node, ast.FunctionDef) and node is not fn)
                    or (isinstance(node, ast.Name) and node.id.startswith('_'))):
                raise CodingFailure('deterministic_validation_failed')
            if isinstance(node, ast.Attribute) and node.attr not in {'strip', 'split', 'join', 'casefold'}:
                raise CodingFailure('deterministic_validation_failed')
            if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Attribute) or
                    isinstance(node.func, ast.Name) and node.func.id in {'isinstance', 'str', 'TypeError'}):
                raise CodingFailure('deterministic_validation_failed')
        patch = 'diff --git a/' + TARGET + ' b/' + TARGET + '\nnew file mode 100644\n'
        patch += ''.join(difflib.unified_diff([], content.splitlines(keepends=True), fromfile='/dev/null', tofile='b/'+TARGET))
        return changed, patch
