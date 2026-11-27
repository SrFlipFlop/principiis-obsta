"""Operator helpers around the one owner-approved network measurement (#75). No model, no network."""
import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from support import temporary_directory
from principiis import development_runtime, network_measurement

IMAGE = 'sha256:' + 'a' * 64
OTHER = 'sha256:' + 'b' * 64


def write_measurement(path, hosts):
    path.write_text(json.dumps({'schema_version': 1, 'connected_hosts': hosts, 'allowed_hosts': hosts,
                                'refused_hosts': []}))
    return path


class MeasurementRequest(unittest.TestCase):
    def test_request_asks_for_one_pinned_dependency_per_ecosystem_a_docs_page_and_notes(self):
        text = network_measurement.REQUEST.read_text()
        for needle in ('Flask', 'pytest', 'six==1.16.0', 'Express', 'left-pad@1.3.0', 'psr/log:3.0.2',
                       'Newtonsoft.Json --version 13.0.3', 'github.com/google/uuid@v1.6.0',
                       'https://docs.python.org/3/library/json.html', 'NOTES.md'):
            self.assertIn(needle, text)
        self.assertIn('toolchain is missing', text)
        self.assertNotIn('curl', text)


class DraftAllowlist(unittest.TestCase):
    def test_draft_keeps_measured_hosts_and_is_rejected_until_the_owner_edits_it(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'measurement.json',
                                            ['pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org', 'docs.python.org'])
            draft = base / 'draft.json'
            summary = network_measurement.draft_allowlist(measurement, draft)
            self.assertEqual(summary['hosts'], ['docs.python.org', 'files.pythonhosted.org', 'pypi.org', 'registry.npmjs.org'])
            document = json.loads(draft.read_text())
            self.assertEqual(document['version'], '1')
            self.assertEqual(document['domains'], summary['hosts'])
            self.assertIn('TODO', draft.read_text())
            with self.assertRaisesRegex(ValueError, 'TODO'):
                development_runtime.load_allowlist(draft)
            # The owner removes every marker; only then does the loader accept it.
            document['status'] = 'approved by the owner after reviewing the measurement'
            document.pop('measured_from', None)
            draft.write_text(json.dumps(document))
            self.assertEqual(development_runtime.load_allowlist(draft), summary['hosts'])

    def test_code_hosting_and_ip_literals_are_never_drafted(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', [
                'pypi.org', 'github.com', 'codeload.github.com', 'raw.githubusercontent.com',
                'gitlab.com', '140.82.112.3', 'proxy.golang.org'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual(summary['hosts'], ['pypi.org'])
            self.assertEqual(set(summary['excluded']), {
                'github.com', 'codeload.github.com', 'raw.githubusercontent.com', 'gitlab.com',
                '140.82.112.3', 'proxy.golang.org'})
            self.assertNotIn('github', (base / 'draft.json').read_text())

    def test_existing_output_and_malformed_measurement_are_refused(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', ['pypi.org'])
            (base / 'draft.json').write_text('keep')
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual((base / 'draft.json').read_text(), 'keep')
            (base / 'bad.json').write_text('{"connected_hosts": "pypi.org"}')
            with self.assertRaisesRegex(ValueError, 'connected_hosts'):
                network_measurement.draft_allowlist(base / 'bad.json', base / 'new.json')

    def test_the_committed_allowlist_has_no_markers(self):
        self.assertIn('pypi.org', development_runtime.load_allowlist())
        self.assertIn('files.pythonhosted.org', development_runtime.load_allowlist())


def fake_docker(base, *, image=IMAGE, invisible=()):
    executable = base / 'docker'
    executable.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
args = sys.argv[3:]
with pathlib.Path(''' + repr(str(base / 'commands.jsonl')) + ''').open('a') as f:
    f.write(json.dumps(args) + '\\n')
if args[:2] == ['version', '--format']:
    print('27.0.0'); sys.exit()
if args[:2] == ['image', 'inspect']:
    print(json.dumps([{'Id': ''' + repr(image) + ''', 'Config': {'Env': ['PATH=/usr/bin'], 'Volumes': None}}])); sys.exit()
if args[0] == 'run':
    mounts = [args[i + 1] for i, v in enumerate(args) if v == '--mount']
    if mounts:
        source = mounts[0].split('src=', 1)[1].split(',')[0]
        if source in ''' + repr(list(map(str, invisible))) + ''' or not pathlib.Path(source).is_dir():
            print('bind source path does not exist', file=sys.stderr); sys.exit(125)
        marker = args[-1].split('/probe/')[1] if '/probe/' in args[-1] else None
        if marker and not (pathlib.Path(source) / marker).is_file():
            print('marker missing', file=sys.stderr); sys.exit(1)
    sys.exit()
''')
    executable.chmod(0o755)
    return executable


class Preflight(unittest.TestCase):
    def setup(self, base, **options):
        auth = base / 'dedicated' / 'login.json'
        auth.parent.mkdir()
        auth.write_text('opaque-never-read')
        config = base / 'runtime.json'
        config.write_text(json.dumps({'version': '1', 'docker': str(fake_docker(base, **options)), 'image': IMAGE,
                                      'auth_file': str(auth), 'clean_runtime_review': 'fixture review'}))
        runs = base / 'runs'
        runs.mkdir()
        return config, runs, auth

    def statuses(self, report):
        return {item['check']: item['status'] for item in report}

    def test_every_check_passes_for_a_usable_setup_without_reading_the_login(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, auth = self.setup(base)
            auth.chmod(0)
            try:
                report = network_measurement.preflight(config, runs)
            finally:
                auth.chmod(0o600)
            self.assertEqual({item['status'] for item in report}, {'PASS'}, report)
            self.assertGreaterEqual(len(report), 5)
            self.assertEqual(list(runs.iterdir()), [])
            commands = (base / 'commands.jsonl').read_text()
            self.assertNotIn('login.json', commands)
            self.assertNotIn('--network", "bridge', commands)
            for line in commands.splitlines():
                command = json.loads(line)
                if command[0] == 'run':
                    self.assertEqual(command[command.index('--network') + 1], 'none')

    def test_wrong_image_id_and_unreachable_runs_root_fail(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, _ = self.setup(base, image=OTHER)
            self.assertIn('FAIL', self.statuses(network_measurement.preflight(config, runs)).values())
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, _ = self.setup(base)
            report = network_measurement.preflight(config, base / 'missing-runs')
            failed = [item['check'] for item in report if item['status'] == 'FAIL']
            self.assertEqual(len(failed), 1)
            self.assertIn('runs', failed[0])

    def test_login_must_be_a_dedicated_regular_file(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, auth = self.setup(base)
            home = base / 'home'
            (home / '.codex').mkdir(parents=True)
            default = home / '.codex/auth.json'
            default.write_text('default login')
            for label, target in (('default', default), ('under .codex', home / '.codex/other.json')):
                with self.subTest(label), patch.dict(os.environ, {'HOME': str(home)}):
                    target.write_text('x')
                    raw = json.loads(config.read_text())
                    raw['auth_file'] = str(target)
                    config.write_text(json.dumps(raw))
                    report = network_measurement.preflight(config, runs)
                    self.assertEqual(self.statuses(report)['login file is a dedicated regular file, not ~/.codex/auth.json'], 'FAIL')
            # A symlink is refused by the runtime config loader before any Docker call.
            (base / 'commands.jsonl').unlink()
            link = base / 'link.json'
            link.symlink_to(auth)
            raw = json.loads(config.read_text())
            raw['auth_file'] = str(link)
            config.write_text(json.dumps(raw))
            report = network_measurement.preflight(config, runs)
            self.assertEqual(report[0]['status'], 'FAIL')
            self.assertFalse((base / 'commands.jsonl').exists())

    def test_command_line_prints_a_report_and_exits_nonzero_on_failure(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, _ = self.setup(base)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                network_measurement.main(['preflight', '--config', str(config), '--runs-root', str(runs)])
            self.assertIn('PREFLIGHT OK', output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as raised:
                network_measurement.main(['preflight', '--config', str(config), '--runs-root', str(base / 'nope')])
            self.assertEqual(raised.exception.code, 1)
            self.assertIn('PREFLIGHT FAILED', output.getvalue())


if __name__ == '__main__':
    unittest.main()
