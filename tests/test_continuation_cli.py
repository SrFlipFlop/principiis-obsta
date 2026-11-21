"""Predecessor data reaches only the disposable restricted application copy."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from principiis.snapshot import preserve, validate

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'a' * 64


class ContinuationCLI(unittest.TestCase):
    def test_predecessor_database_is_exercised_without_mutating_either_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            before = base / 'before'
            current = base / 'current'
            before.mkdir()
            current.mkdir()
            for directory, account in ((before, 'prior-account'), (current, 'new-version')):
                (directory / 'app.py').write_text('raise SystemExit("host execution forbidden")')
                with sqlite3.connect(directory / 'data.db') as database:
                    database.execute('CREATE TABLE accounts (name TEXT NOT NULL)')
                    database.execute('INSERT INTO accounts VALUES (?)', (account,))
            old = base / 'old-snapshot'
            new = base / 'new-snapshot'
            preserve(before, old)
            preserve(current, new)
            docker = base / 'docker'
            docker.write_text('''#!/usr/bin/python3
import json,pathlib,sqlite3,sys
args=sys.argv[1:]
if args[:1]==['--host']: args=args[2:]
if args[:2]==['image','inspect']: print(json.dumps([{'Id':args[2]}]))
elif args[:1]==['run'] and '-d' in args:
 mount=next(arg for arg in args if 'dst=/workspace' in arg)
 root=pathlib.Path(mount.split('src=')[1].split(',')[0])
 with sqlite3.connect(root/'data.db') as database:
  if database.execute('SELECT name FROM accounts').fetchone()!=('prior-account',):
   raise SystemExit('prior database row absent')
 print('predecessor data seen by disposable candidate')
else: print('{}')
''')
            docker.chmod(0o755)
            output = base / 'assessment'
            command = [sys.executable, '-m', 'principiis.evaluation', '--snapshot', str(new),
                       '--output', str(output), '--app-image', IMAGE, '--evaluator-image', IMAGE,
                       '--app-command', '["python", "app.py"]', '--docker', str(docker),
                       '--predecessor-snapshot', str(old), '--continuation-path', 'data.db',
                       '--continuation-version', 'control-v1']
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            record = json.loads((output / 'assessment.json').read_text())
            self.assertTrue(record['snapshot_unchanged'])
            self.assertEqual(record['continuation']['version'], 'control-v1')
            self.assertEqual(record['continuation']['paths'], ['data.db'])
            self.assertIn('predecessor data seen', (output / '3.stdout').read_text())
            with sqlite3.connect(old / 'data.db') as database:
                self.assertEqual(database.execute('SELECT name FROM accounts').fetchone(), ('prior-account',))
            with sqlite3.connect(new / 'data.db') as database:
                self.assertEqual(database.execute('SELECT name FROM accounts').fetchone(), ('new-version',))
            validate(old)
            validate(new)

    def test_unsafe_or_missing_predecessor_data_cannot_launch_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            before = base / 'before'
            current = base / 'current'
            before.mkdir()
            current.mkdir()
            (before / 'data.db').write_bytes(b'prior')
            (current / 'app.py').write_text('pass')
            old = base / 'old-snapshot'
            new = base / 'new-snapshot'
            preserve(before, old)
            preserve(current, new)
            for index, path in enumerate(('../data.db', 'absent.db')):
                output = base / f'assessment-{index}'
                process = subprocess.run([sys.executable, '-m', 'principiis.evaluation',
                    '--snapshot', str(new), '--output', str(output), '--app-image', IMAGE,
                    '--evaluator-image', IMAGE, '--app-command', '["python", "app.py"]',
                    '--docker', '/nonexistent/docker', '--predecessor-snapshot', str(old),
                    '--continuation-path', path, '--continuation-version', 'control-v1'],
                    cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(process.returncode, 0, process.stderr)
                record = json.loads((output / 'assessment.json').read_text())
                self.assertEqual(record['outcome'], 'evaluator_error')
                self.assertFalse(any('run' in command for command in record['commands']))


if __name__ == '__main__':
    unittest.main()
