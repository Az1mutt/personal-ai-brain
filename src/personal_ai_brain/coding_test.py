"""Root-owned offline acceptance harness, mounted read-only by the supervisor."""
import json
import runpy

def main():
    try:
        fn = runpy.run_path('/workspace/src/personal_ai_brain/coding_exercise.py')['normalize_label']
        cases = [('', ''), (' A  B ', 'a b'), ('Straße', 'strasse'),
                 ('\tHELLO\nworld\r', 'hello world'), ('A\u2003B\u00a0C', 'a b c'),
                 ('  MiXeD  ', 'mixed'), ('one', 'one')]
        for value, expected in cases:
            if fn(value) != expected: raise ValueError()
        for value in (None, 1, True, [], {}, b'text'):
            try: fn(value)
            except TypeError: continue
            raise ValueError()
        print(json.dumps({'schema_version': '0.1', 'profile': 'normalize-label-v1', 'passed': 13}))
        return 0
    except BaseException:
        print('{"status":"failed"}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
