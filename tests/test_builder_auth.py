"""Offline security boundary tests; synthetic credentials only."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

def module(name):
    path = Path(__file__).with_name(name + '.py')
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'builder_auth' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj

ask = module('builder_askpass')
publish = module('builder_publish')

class Boundaries(unittest.TestCase):
    def test_unknown_context_never_reads_secret(self):
        prompts = ["Password for 'https://evil.example': ",
                   "Password for 'https://Az1mutt@github.com/Other/repo.git': ",
                   "Password for 'http://Az1mutt@github.com/Az1mutt/personal-ai-brain.git': ",
                   "Password for 'https://Az1mutt@github.com': "]
        with patch.object(ask, 'read_token') as read:
            for prompt in prompts:
                with patch.object(sys, 'argv', ['helper', prompt]), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(ask.main(), 1)
                    self.assertEqual(out.getvalue(), '')
            read.assert_not_called()

    def test_exact_context_only(self):
        prompt = "Password for 'https://Az1mutt@github.com/Az1mutt/personal-ai-brain.git': "
        with patch.object(ask, 'read_token', return_value='synthetic-test-only'), patch.object(sys, 'argv', ['helper', prompt]), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ask.main(), 0)
            self.assertEqual(out.getvalue(), 'synthetic-test-only\n')

    def test_credential_permissions_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / 'private'
            parent.mkdir(mode=0o700)
            token = parent / 'token'
            token.write_text('github_pat_' + 'x' * 40)
            token.chmod(0o600)
            with patch.object(ask, 'TOKEN', str(token)):
                self.assertTrue(ask.read_token().startswith('github_pat_'))
                token.chmod(0o644)
                with self.assertRaises(ValueError): ask.read_token()
                token.chmod(0o600)
                parent.chmod(0o755)
                with self.assertRaises(ValueError): ask.read_token()
                parent.chmod(0o700)
                other = parent / 'other'
                token.rename(other)
                token.symlink_to(other)
                with self.assertRaises(OSError): ask.read_token()

    def test_no_arbitrary_operation(self):
        with patch.object(publish, 'read_token') as read:
            with self.assertRaises(ValueError): publish.main('delete-main')
            read.assert_not_called()

    def test_no_api_redirect(self):
        self.assertIsNone(publish.NoRedirect().redirect_request(None, None, None, None, None))

    def test_push_preserves_hooks_and_bounds_ref(self):
        calls = []
        def git(args, **kwargs):
            calls.append((args, kwargs))
            output = publish.BASE + '\n' if 'rev-parse' in args else ''
            return publish.subprocess.CompletedProcess(args, 0, output, '')
        with patch.object(publish, 'read_token', return_value='synthetic-test-only'), patch.object(publish.urllib.request, 'build_opener') as opener, patch.object(publish.subprocess, 'run', side_effect=git), contextlib.redirect_stdout(io.StringIO()):
            opener.return_value.open.return_value = io.StringIO('{"full_name":"Az1mutt/personal-ai-brain"}')
            self.assertEqual(publish.main('push'), 0)
        pushes = [(args, opts) for args, opts in calls if 'push' in args]
        self.assertEqual(len(pushes), 2)
        self.assertIn('--dry-run', pushes[0][0])
        self.assertNotIn('--dry-run', pushes[1][0])
        for args, opts in pushes:
            self.assertEqual(args[-2], publish.URL)
            self.assertEqual(args[-1], publish.BASE + ':refs/heads/' + publish.BRANCH)
            self.assertNotIn('--no-verify', args)
            self.assertFalse(any('hooksPath' in x or 'force' in x or 'synthetic-test-only' in x for x in args))
            self.assertFalse(any('TRACE' in k or k == 'GITHUB_TOKEN' for k in opts['env']))

    def test_reject_url_rewrite_before_push(self):
        with patch.object(publish, 'read_token', return_value='synthetic-test-only'), patch.object(publish.urllib.request, 'build_opener') as opener, patch.object(publish.subprocess, 'run') as run, contextlib.redirect_stdout(io.StringIO()):
            opener.return_value.open.return_value = io.StringIO('{"full_name":"Az1mutt/personal-ai-brain"}')
            run.return_value = publish.subprocess.CompletedProcess([], 0, 'url.https://other/.insteadof\n', '')
            with self.assertRaises(ValueError): publish.main('push')
            self.assertEqual(run.call_count, 1)

if __name__ == '__main__':
    unittest.main()
