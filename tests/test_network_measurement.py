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


def write_measurement(path, hosts, refused=(), credentialed=None):
    record = {'schema_version': 1, 'connected_hosts': hosts, 'allowed_hosts': hosts, 'refused_hosts': list(refused)}
    if credentialed is not None:
        record['credentialed_hosts'] = list(credentialed)
    path.write_text(json.dumps(record))
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
                                            ['repo.packagist.org', 'api.nuget.org', 'registry.npmjs.org', 'docs.pytest.org'])
            draft = base / 'draft.json'
            summary = network_measurement.draft_allowlist(measurement, draft)
            self.assertEqual(summary['hosts'], ['api.nuget.org', 'docs.pytest.org', 'registry.npmjs.org', 'repo.packagist.org'])
            document = json.loads(draft.read_text())
            self.assertEqual(document['version'], '1')
            self.assertEqual(document['domains'], summary['hosts'])
            self.assertEqual(document['model_domains'], development_runtime.load_allowlist()['model_domains'])
            self.assertIn('TODO', draft.read_text())
            with self.assertRaisesRegex(ValueError, 'TODO'):
                development_runtime.load_allowlist(draft)
            # The owner removes every marker; only then does the loader accept it.
            document['status'] = 'approved by the owner after reviewing the measurement'
            document.pop('measured_from', None)
            draft.write_text(json.dumps(document))
            self.assertEqual(development_runtime.load_allowlist(draft)['domains'], summary['hosts'])

    def test_measured_model_hosts_stay_out_of_the_ordinary_domains(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', ['registry.npmjs.org', 'chatgpt.com', 'api.openai.com', 'ab.chatgpt.com'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            document = json.loads((base / 'draft.json').read_text())
            self.assertEqual(document['domains'], ['registry.npmjs.org'])
            self.assertEqual(summary['model_hosts'], ['ab.chatgpt.com', 'api.openai.com', 'chatgpt.com'])
            # A measured model host that is not yet a model domain is for the owner to decide.
            self.assertIn('ab.chatgpt.com', document['model_domains_measured'])

    def test_hosts_the_codex_process_reached_with_the_credential_are_model_hosts_for_the_owner(self):
        # In log mode only the Codex process holds the model credential, so whatever it
        # reached with it goes to model_domains_measured, never to the ordinary domains (#75).
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json',
                                            ['registry.npmjs.org', 'chatgpt.com', 'telemetry.example.net'],
                                            credentialed=['chatgpt.com', 'telemetry.example.net', 'github.com'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            document = json.loads((base / 'draft.json').read_text())
            self.assertEqual(document['domains'], ['registry.npmjs.org'])
            self.assertEqual(document['model_domains_measured'], ['chatgpt.com', 'telemetry.example.net'])
            self.assertEqual(summary['model_hosts'], ['chatgpt.com', 'telemetry.example.net'])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                network_measurement.main(['draft-allowlist', '--measurement', str(measurement),
                                          '--output', str(base / 'second.json')])
            self.assertIn('model_domains_measured (Codex process, with the model credential): telemetry.example.net',
                          output.getvalue())

    def test_the_measurement_records_the_credentialed_hosts(self):
        class Runtime:
            version = {'egress': {'mode': 'log'}}

            def __init__(self, config, output, source, *, egress):
                assert egress == 'log'

            def execute(self, workspace, request, stdout, stderr):
                return {'egress': {'connected_hosts': ['chatgpt.com', 'registry.npmjs.org'],
                                   'allowed_hosts': ['chatgpt.com', 'registry.npmjs.org'], 'refused_hosts': ['api.openai.com'],
                                   'credentialed_hosts': ['chatgpt.com']}}
        with temporary_directory() as directory, patch.object(network_measurement, 'DevelopmentRuntime', Runtime):
            record = network_measurement.measure(Path(directory) / 'config.json', Path(directory) / 'out')
        self.assertEqual(record['credentialed_hosts'], ['chatgpt.com'])
        self.assertEqual(record['egress_mode'], 'log')

    def test_the_follow_up_session_reruns_the_request_under_the_enforced_allowlist(self):
        # After the owner approves the allowlist, the same fixture request runs in
        # allowlist mode, so the per-ecosystem NOTES.md shows what the allowlist breaks.
        modes = []

        class Runtime:
            version = {'egress': {'mode': 'allowlist'}}

            def __init__(self, config, output, source, *, egress):
                modes.append(egress)

            def execute(self, workspace, request, stdout, stderr):
                return {'egress': {'connected_hosts': [], 'allowed_hosts': [], 'refused_hosts': [],
                                   'credentialed_hosts': []}}
        with temporary_directory() as directory, patch.object(network_measurement, 'DevelopmentRuntime', Runtime), \
                contextlib.redirect_stdout(io.StringIO()):
            network_measurement.main(['--config', str(Path(directory) / 'c.json'), '--output',
                                      str(Path(directory) / 'out'), '--egress', 'allowlist'])
            record = json.loads((Path(directory) / 'out' / 'measurement.json').read_text())
            with self.assertRaises(SystemExit):
                network_measurement.main(['--config', 'c.json', '--output', 'x', '--egress', 'open'])
        self.assertEqual(modes, ['allowlist'])
        self.assertEqual(record['egress_mode'], 'allowlist')
        with temporary_directory() as directory:
            # A draft only ever comes from a log-mode measurement.
            path = Path(directory) / 'm.json'
            path.write_text(json.dumps(dict(record, connected_hosts=['registry.npmjs.org'])))
            with self.assertRaisesRegex(ValueError, 'log-mode'):
                network_measurement.draft_allowlist(path, Path(directory) / 'draft.json')

    def test_code_hosting_and_ip_literals_are_never_drafted(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', [
                'registry.npmjs.org', 'github.com', 'codeload.github.com', 'raw.githubusercontent.com',
                'gitlab.com', '140.82.112.3', 'proxy.golang.org'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual(summary['hosts'], ['registry.npmjs.org'])
            self.assertEqual(set(summary['excluded']), {
                'github.com', 'codeload.github.com', 'raw.githubusercontent.com', 'gitlab.com',
                '140.82.112.3', 'proxy.golang.org'})
            self.assertNotIn('github', (base / 'draft.json').read_text())

    def test_never_allowed_mirrors_are_never_drafted(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', ['registry.npmjs.org', 'cdn.jsdelivr.net', 'web.archive.org', 'ghcr.io'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual(summary['hosts'], ['registry.npmjs.org'])
            self.assertEqual(set(summary['excluded']), {'cdn.jsdelivr.net', 'web.archive.org', 'ghcr.io'})

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

    def test_pypi_hosts_are_never_drafted_they_are_gateway_only(self):
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', ['registry.npmjs.org', 'pypi.org', 'files.pythonhosted.org'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual(summary['hosts'], ['registry.npmjs.org'])
            self.assertEqual(set(summary['excluded']), {'pypi.org', 'files.pythonhosted.org'})
            self.assertIn('gateway', summary['excluded']['pypi.org'])

    def test_hosts_refused_during_the_measurement_are_reported_not_drafted(self):
        # Log mode refuses GitHub, mirrors, PyPI tunnels and non-public addresses; the
        # owner still sees each attempt.
        with temporary_directory() as directory:
            base = Path(directory)
            measurement = write_measurement(base / 'm.json', ['registry.npmjs.org'],
                                            refused=['github.com', 'pypi.org', 'localhost'])
            summary = network_measurement.draft_allowlist(measurement, base / 'draft.json')
            self.assertEqual(summary['hosts'], ['registry.npmjs.org'])
            self.assertEqual(summary['refused'], ['github.com', 'localhost', 'pypi.org'])
            self.assertNotIn('github', (base / 'draft.json').read_text())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                network_measurement.main(['draft-allowlist', '--measurement', str(measurement),
                                          '--output', str(base / 'second.json')])
            self.assertIn('REFUSED during the measurement: github.com', output.getvalue())

    def test_the_committed_allowlist_has_no_markers(self):
        self.assertIn('registry.npmjs.org', development_runtime.load_allowlist()['domains'])
        self.assertNotIn('pypi.org', development_runtime.load_allowlist()['domains'])

    def test_the_committed_allowlist_keeps_model_hosts_apart(self):
        allowlist = development_runtime.load_allowlist()
        self.assertEqual(sorted(allowlist['model_domains']), ['api.openai.com', 'auth.openai.com', 'chatgpt.com'])
        self.assertFalse(set(allowlist['model_domains']) & set(allowlist['domains']))


class AllowlistLoader(unittest.TestCase):
    def load(self, document):
        with temporary_directory() as directory:
            path = Path(directory) / 'allowlist.json'
            path.write_text(json.dumps(document))
            return development_runtime.load_allowlist(path)

    def test_both_lists_are_required_and_validated(self):
        good = {'version': '1', 'domains': ['registry.npmjs.org'], 'model_domains': ['chatgpt.com']}
        self.assertEqual(self.load(good), {'domains': ['registry.npmjs.org'], 'model_domains': ['chatgpt.com']})
        for changes in ({'model_domains': None}, {'model_domains': []}, {'model_domains': ['ChatGPT.com']},
                        {'model_domains': 'chatgpt.com'}, {'domains': ['chatgpt.com', 'registry.npmjs.org']},
                        {'domains': ['*.chatgpt.com']}, {'model_domains': ['*.openai.com']}):
            document = {k: v for k, v in dict(good, **changes).items() if v is not None}
            with self.subTest(changes), self.assertRaises(ValueError):
                self.load(document)


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

    def test_the_proxy_import_check_covers_the_gateway_modules(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config, runs, _ = self.setup(base)
            network_measurement.preflight(config, runs)
            imports = [c for c in map(json.loads, (base / 'commands.jsonl').read_text().splitlines())
                       if c[0] == 'run' and any(v.startswith('import ') for v in c)]
            self.assertEqual(len(imports), 1)
            for module in ('ssl', 'http.client', 'ipaddress'):
                self.assertIn(module, imports[0][-1])


GITHUB_ANSWER = {'connect': 'HTTP/1.1 200 Connection established', 'tls': 'established',
                 'status': 'HTTP/1.1 200 OK', 'github_header': True, 'body': '# principiis-obsta\n'}
CDN_REFUSAL = {'connect': 'HTTP/1.1 200 Connection established', 'tls': 'established',
               'status': 'HTTP/1.1 403 Forbidden', 'github_header': False, 'body': 'Forbidden'}


class FrontingCheck(unittest.TestCase):
    def test_verdict_flags_any_github_answer(self):
        verdict = network_measurement.fronting_verdict
        self.assertEqual(verdict(GITHUB_ANSWER)[0], 'FAIL')
        self.assertEqual(verdict(dict(GITHUB_ANSWER, github_header=False))[0], 'FAIL')
        self.assertEqual(verdict(dict(GITHUB_ANSWER, status='HTTP/1.1 404 Not Found', body='nope'))[0], 'FAIL')
        self.assertEqual(verdict(CDN_REFUSAL)[0], 'PASS')
        self.assertEqual(verdict(dict(CDN_REFUSAL, status='HTTP/1.1 421 Misdirected Request'))[0], 'PASS')
        # No TLS, no answer: nothing was shown either way.
        self.assertEqual(verdict({'connect': 'HTTP/1.1 502 Bad Gateway'})[0], 'INCONCLUSIVE')
        self.assertEqual(verdict(dict(CDN_REFUSAL, tls='failed: SSLError'))[0], 'INCONCLUSIVE')

    def test_the_probe_sends_the_github_host_inside_a_tunnel_with_the_right_sni(self):
        probe = network_measurement.FRONTING_PROBE
        for needle in ('CONNECT', 'server_hostname=host', 'Host: raw.githubusercontent.com',
                       network_measurement.FRONTING_PATH, 'x-github-request-id'):
            self.assertIn(needle, probe)
        self.assertEqual(network_measurement.FRONTING_PATH, '/SrFlipFlop/principiis-obsta/main/README.md')

    def run_check(self, base, document, answers):
        allowlist = base / 'allowlist.json'
        allowlist.write_text(json.dumps(document))
        config = base / 'runtime.json'
        auth = base / 'login.json'
        auth.write_text('never read')
        config.write_text(json.dumps({'version': '1', 'docker': str(fake_docker(base)), 'image': IMAGE,
                                      'auth_file': str(auth), 'clean_runtime_review': 'fixture review'}))
        seen = {}

        def start(runtime, egress, model_token=''):
            seen['policy'], seen['egress'], seen['token'] = runtime.allowlist, egress, model_token
            return '172.30.0.2'

        def run(docker, argv, **kwargs):
            seen['argv'], seen['env'] = argv, kwargs.get('env') or {}
            hosts = [h.removeprefix('model:') for h in argv[argv.index('172.30.0.2') + 1:]]
            return json.dumps({h: answers[h] for h in hosts}) + '\n'
        removed = []
        with patch.object(network_measurement.DevelopmentRuntime, 'start_egress', start), \
                patch.object(network_measurement, 'docker_run', run), \
                patch.object(network_measurement, 'remove', lambda docker, argv: removed.append(argv)):
            report = network_measurement.fronting_check(config, allowlist)
        return report, seen, removed

    def test_every_domain_is_probed_and_resources_are_removed(self):
        with temporary_directory() as directory:
            base = Path(directory)
            document = {'version': '1', 'status': 'TODO-OWNER: draft', 'model_domains': [],
                        'domains': ['registry.npmjs.org', 'api.nuget.org', '*.example.org', 'github.com', 'pypi.org']}
            report, seen, removed = self.run_check(base, document, {'registry.npmjs.org': CDN_REFUSAL,
                                                                   'api.nuget.org': GITHUB_ANSWER})
            statuses = {item['host']: item['status'] for item in report}
            self.assertEqual(statuses, {'registry.npmjs.org': 'PASS', 'api.nuget.org': 'FAIL',
                                        '*.example.org': 'UNCHECKED', 'github.com': 'REFUSED', 'pypi.org': 'REFUSED'})
            self.assertEqual(seen['policy'], {'domains': ['registry.npmjs.org', 'api.nuget.org'], 'model_domains': []})
            self.assertEqual(seen['token'], '')
            self.assertEqual(seen['argv'][seen['argv'].index('--network') + 1], seen['egress']['network'])
            self.assertEqual(removed, [['rm', '-f', seen['egress']['container']], ['network', 'rm', seen['egress']['network']],
                                       ['network', 'rm', seen['egress']['outside_network']]])

    def test_model_domains_are_probed_with_a_throwaway_credential_kept_out_of_argv(self):
        with temporary_directory() as directory:
            base = Path(directory)
            document = {'version': '1', 'status': 'TODO-OWNER: draft',
                        'model_domains': ['chatgpt.com', 'api.openai.com', 'github.com'],
                        'domains': ['registry.npmjs.org']}
            report, seen, removed = self.run_check(base, document, {
                'registry.npmjs.org': CDN_REFUSAL, 'chatgpt.com': CDN_REFUSAL, 'api.openai.com': GITHUB_ANSWER})
            statuses = {item['host']: item['status'] for item in report}
            self.assertEqual(statuses, {'registry.npmjs.org': 'PASS', 'chatgpt.com': 'PASS',
                                        'api.openai.com': 'FAIL', 'github.com': 'REFUSED'})
            self.assertEqual(seen['policy'], {'domains': ['registry.npmjs.org'],
                                              'model_domains': ['chatgpt.com', 'api.openai.com']})
            token = seen['token']
            self.assertRegex(token, r'^[0-9a-f]{32}$')
            hosts = seen['argv'][seen['argv'].index('172.30.0.2') + 1:]
            self.assertEqual(hosts, ['registry.npmjs.org', 'model:chatgpt.com', 'model:api.openai.com'])
            self.assertNotIn(token, json.dumps(seen['argv']))
            self.assertIn('PO_FRONTING_TOKEN', seen['argv'])  # bare --env: the value comes from the environment
            self.assertEqual(seen['env'].get('PO_FRONTING_TOKEN'), token)
            self.assertEqual(len(removed), 3)

    def test_the_probe_authenticates_only_model_hosts(self):
        probe = network_measurement.FRONTING_PROBE
        self.assertIn("removeprefix('model:')", probe)
        self.assertIn('Proxy-Authorization: Basic', probe)
        self.assertIn("os.environ.get('PO_FRONTING_TOKEN'", probe)

    def test_command_line_reports_and_exits_nonzero_unless_every_domain_passes(self):
        with temporary_directory() as directory:
            base = Path(directory)
            passing = [{'host': 'registry.npmjs.org', 'status': 'PASS', 'detail': 'HTTP/1.1 403'}]
            with patch.object(network_measurement, 'fronting_check', return_value=passing) as check, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                network_measurement.main(['fronting-check', '--config', 'c.json', '--allowlist', 'a.json'])
            check.assert_called_once_with('c.json', 'a.json')
            self.assertIn('FRONTING CHECK OK', output.getvalue())
            failing = passing + [{'host': 'api.nuget.org', 'status': 'FAIL', 'detail': 'GitHub answered'}]
            with patch.object(network_measurement, 'fronting_check', return_value=failing), \
                    contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as raised:
                network_measurement.main(['fronting-check', '--config', 'c.json'])
            self.assertEqual(raised.exception.code, 1)
            self.assertIn('FAIL  api.nuget.org', output.getvalue())
            self.assertIn('FRONTING CHECK FAILED', output.getvalue())


if __name__ == '__main__':
    unittest.main()
