import io
import json
from pathlib import Path
from support import temporary_directory
import unittest
from unittest.mock import patch
import subprocess

from principiis.development_runtime import ADAPTER, CODEX_HOME, MODEL_CREDENTIAL, PYPI_GATEWAY, SANDBOX_PROBE, DevelopmentRuntime, cleanup_runtime, docker_command, load_config, preflight_run, configuration_args, workspace_permission_settings, restrictions


IMAGE = 'sha256:' + 'a' * 64


def docker_fixture(base):
    executable = base / 'docker'
    executable.write_text('''#!/usr/bin/env python3
import json,pathlib,sys
args=sys.argv[1:]
assert args[:2] == ['--host','unix:///var/run/docker.sock']
args=args[2:]
with pathlib.Path(''' + repr(str(base / 'commands.jsonl')) + ''').open('a') as f: f.write(json.dumps(args)+'\\n')
import os
if args[0] == 'run' and os.environ.get('PO_MODEL_TOKEN'):
    # What the Docker client would hand a container for a bare `--env PO_MODEL_TOKEN`.
    with pathlib.Path(''' + repr(str(base / 'tokens.jsonl')) + ''').open('a') as f:
        f.write(json.dumps({'argv':args,'token':os.environ['PO_MODEL_TOKEN']})+'\\n')
if args[:2] == ['image','inspect']:
    print(json.dumps([{'Id':''' + repr(IMAGE) + ''','Config':{'Env':['PATH=/usr/bin:/bin'],'Volumes':None}}])); sys.exit()
if args[0] == 'run' and '--version' in args:
    print('codex-cli fixture-container');sys.exit()
if args[0] == 'run' and 'po-runtime-preflight-v1' in args:
    print(json.dumps({'sandbox':'workspace-write','symlink_targets':['/usr/local/bin/python','/usr/local/bin/python3','/usr/local/bin/python3.12']}));sys.exit()
if args[0] == 'run' and 'test -d /workspace' in args:
    mounts=[args[i+1] for i,v in enumerate(args) if v=='--mount']
    workspace=next(v.split('src=',1)[1].split(',')[0] for v in mounts if 'dst=/workspace' in v)
    assert pathlib.Path(workspace).is_dir()
    sys.exit()
if args[0] == 'run' and '--detach' in args:
    print('preview-container');sys.exit()
if args[0] == 'run':
    mounts=[args[i+1] for i,v in enumerate(args) if v=='--mount']
    workspace=next(v.split('src=',1)[1].split(',')[0] for v in mounts if 'dst=/workspace' in v)
    assert pathlib.Path(workspace).parent.joinpath('runtime.json').is_file()
    pathlib.Path(workspace,'app.py').write_text(sys.stdin.read())
    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':3}}));sys.exit()
if args[0] == 'inspect':
    records=[json.loads(v) for v in pathlib.Path(''' + repr(str(base / 'commands.jsonl')) + ''').read_text().splitlines()]
    network=next((c[-1] for c in reversed(records) if c[:2]==['network','create']),'fixture-network')
    networks={network:{'IPAddress':'172.30.0.2'}}
    if args[-1].startswith('po-development-egress-'):
        networks={c[-1]:{'IPAddress':'172.30.0.2' if '--internal' in c else '172.31.0.2'} for c in records if c[:2]==['network','create']}
    ports={'8123/tcp':[{'HostIp':'127.0.0.1','HostPort':'58123'}]} if args[-1].startswith('po-preview-relay-') else {'8123/tcp':None}
    print(json.dumps([{'State':{'Running':True},'NetworkSettings':{'Ports':ports,'Networks':networks}}]));sys.exit()
if args[0] == 'logs' and args[-1].startswith('po-development-egress-'):
    print(json.dumps({'event':'listening','mode':'allowlist','address':'172.30.0.2','port':3128}))
    print(json.dumps({'method':'CONNECT','host':'registry.npmjs.org','port':443,'decision':'allowed'}))
    print(json.dumps({'method':'CONNECT','host':'registry.npmjs.org','port':443,'decision':'connected'}))
    print(json.dumps({'method':'CONNECT','host':'github.com','port':443,'decision':'refused'}))
    print(json.dumps({'method':'CONNECT','host':'chatgpt.com','port':443,'decision':'allowed','credential':'valid'}))
    print(json.dumps({'method':'CONNECT','host':'api.openai.com','port':443,'decision':'refused','credential':'absent','reason':'model host without the model credential'}));sys.exit()
if args[0] == 'logs':
    print('application startup');sys.exit()
if args[0] == 'stats':
    print('12MiB / 2GiB');sys.exit()
if args[:2] == ['network','create']: print('network-id')
if args[:2] == ['network','inspect']:
    print(json.dumps([{'Internal':True,'EnableIPv6':False,'Options':{'com.docker.network.bridge.gateway_mode_ipv4':'isolated'}}]))
''')
    executable.chmod(0o755)
    return executable


class DevelopmentRuntimeTests(unittest.TestCase):
    def test_sandbox_probe_checks_this_checkout_is_invisible_without_host_specific_paths(self):
        checkout_instructions = Path(__file__).resolve().parents[1] / 'AGENTS.md'
        self.assertIn(repr(str(checkout_instructions)), SANDBOX_PROBE)
        # The probe must name this checkout (derived at import) and nothing else host
        # specific. Remove that derived path first, so a checkout that itself lives
        # under /home/srflipflop is not mistaken for a hardcoded host path.
        self.assertNotIn('/home/srflipflop', SANDBOX_PROBE.replace(str(checkout_instructions), ''))

    def test_temporary_tool_execution_is_enabled_only_for_development(self):
        for development in (False, True):
            args = restrictions(nested_sandbox=development)
            mounts = [args[index + 1] for index, value in enumerate(args) if value == '--tmpfs']
            for mount in mounts:
                flags = mount.split(':', 1)[1].split(',')
                self.assertEqual('exec' in flags, development)
                self.assertIn('nosuid', flags)
                self.assertIn('nodev', flags)

    def configuration(self, base):
        auth = base / 'auth.json'
        auth.write_text('opaque-test-auth-not-read-by-controller')
        config = {'version':'1','docker':str(docker_fixture(base)), 'image':IMAGE,
                  'auth_file':str(auth),'clean_runtime_review':'fixture review'}
        path = base / 'runtime.json'
        path.write_text(json.dumps(config))
        return path, config

    def test_isolated_attempt_delivers_only_workspace_and_auth_and_retains_usage(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            source = base / 'tasks'; source.mkdir()
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, source)
            workspace = output / 'steps/one/workspace'; workspace.mkdir(parents=True)
            stdout, stderr = io.StringIO(), io.StringIO()
            evidence = runtime.execute(workspace, 'released request only', stdout, stderr)
            self.assertEqual(evidence['exit_status'], 0)
            self.assertEqual((workspace / 'app.py').read_text(), 'released request only')
            self.assertIn('turn.completed', stdout.getvalue())
            self.assertIsNone(evidence['codex']['model'])
            self.assertIsNone(evidence['codex']['reasoning_effort'])
            commands = [json.loads(v) for v in (base/'commands.jsonl').read_text().splitlines()]
            launch = next(c for c in commands if c[0] == 'run' and '-i' in c)
            mounts = [launch[i+1] for i,v in enumerate(launch) if v == '--mount']
            self.assertEqual(len(mounts), 2)
            self.assertTrue(any('src='+str(workspace) in m and 'dst=/workspace' in m for m in mounts))
            self.assertTrue(any('dst=/run/subscription-auth.json,readonly' in m for m in mounts))
            self.assertNotIn(str(source), repr(launch))
            for value in configuration_args(workspace_permission_settings()):
                self.assertIn(value,launch)
            self.assertNotIn('--sandbox',launch)
            self.assertNotIn('--model', launch)
            self.assertNotIn('model_reasoning_effort', repr(launch))
            self.assertIn('--ephemeral', launch)
            self.assertIn('--read-only', launch)
            self.assertIn('--cap-drop', launch)
            self.assertTrue(launch[launch.index('--network')+1].startswith('po-development-net-'))
            self.assertTrue(any(c[:2] == ['rm','-f'] for c in commands))
            self.assertFalse((output / 'runtime-home').exists())
            self.assertIn('Docker client', evidence['memory']['scope'])

    def launch(self, base):
        commands = [json.loads(v) for v in (base/'commands.jsonl').read_text().splitlines()]
        return next(c for c in commands if c[0] == 'run' and '-i' in c)

    def test_live_web_search_is_disabled_and_part_of_the_runtime_version(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, base / 'tasks')
            workspace = output / 'workspace'; workspace.mkdir(parents=True)
            evidence = runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            self.assertIn('web_search="disabled"', self.launch(base))
            self.assertNotIn('live', repr(self.launch(base)))
            self.assertEqual(evidence['codex']['settings']['web_search'], 'disabled')
            self.assertEqual(runtime.version['web_search'], 'disabled')

    def commands(self, base):
        return [json.loads(v) for v in (base/'commands.jsonl').read_text().splitlines()]

    def test_development_reaches_the_network_only_through_the_allowlist_proxy(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, base / 'tasks')
            workspace = output / 'workspace'; workspace.mkdir(parents=True)
            evidence = runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            commands = self.commands(base)
            internal, outside = [c for c in commands if c[:2] == ['network', 'create']]
            network, outside_network = internal[-1], outside[-1]
            self.assertIn('--internal', internal)
            self.assertNotIn('--internal', outside)
            self.assertIn('--ipv6=false', internal)
            self.assertIn('--ipv6=false', outside)
            self.assertRegex(network, r'^po-development-net-[0-9a-f]{32}$')
            self.assertEqual(outside_network, network.replace('-net-', '-out-'))
            proxy = next(c for c in commands if c[0] == 'run' and '--detach' in c)
            proxy_name = proxy[proxy.index('--name') + 1]
            # The proxy starts on the internal network only and binds to its address
            # there; the per-run outside network is connected afterwards. Never the
            # default bridge, where other containers could reach it.
            self.assertEqual(proxy[proxy.index('--network') + 1], network)
            self.assertEqual(proxy[-1], 'own-address')
            self.assertNotIn('bridge', [c[2] for c in commands if c[:2] == ['network', 'connect']])
            self.assertEqual([c for c in commands if c[:2] == ['network', 'connect']],
                             [['network', 'connect', outside_network, proxy_name]])
            self.assertLess(commands.index(proxy), commands.index(['network', 'connect', outside_network, proxy_name]))
            self.assertNotIn('--mount', proxy)
            self.assertNotIn(config['auth_file'], repr(proxy))
            self.assertIn('allowlist', proxy)
            self.assertIn('registry.npmjs.org', proxy[proxy.index('allowlist') + 1])
            self.assertNotIn('pypi.org', proxy[proxy.index('allowlist') + 1])
            self.assertNotIn('github.com', proxy[proxy.index('allowlist') + 1])
            launch = self.launch(base)
            self.assertEqual(launch[launch.index('--network') + 1], network)
            self.assertIn('HTTPS_PROXY=http://172.30.0.2:3128', launch)
            self.assertIn('HTTP_PROXY=http://172.30.0.2:3128', launch)
            self.assertIn('PIP_INDEX_URL=http://172.30.0.2:3128/pypi/simple/', launch)
            self.assertIn('NO_PROXY=localhost,127.0.0.1,::1,172.30.0.2', launch)
            self.assertIn(['rm', '-f', proxy_name], commands)
            self.assertIn(['network', 'rm', network], commands)
            self.assertLess(commands.index(['rm', '-f', proxy_name]), commands.index(['network', 'rm', network]))
            self.assertLess(commands.index(['rm', '-f', proxy_name]), commands.index(['network', 'rm', outside_network]))
            log = Path(evidence['egress']['log'])
            self.assertEqual(log, output / 'egress.jsonl')
            self.assertIn('"decision": "refused"', log.read_text())
            self.assertEqual(evidence['egress']['mode'], 'allowlist')
            self.assertEqual(evidence['egress']['refused_hosts'], ['api.openai.com', 'github.com'])
            self.assertEqual(evidence['egress']['connected_hosts'], ['registry.npmjs.org'])
            self.assertIn('allowlist', evidence['runtime']['network'])
            allocation = json.loads((output / 'runtime.json').read_text())
            self.assertEqual(allocation['egress'], {'container': proxy_name, 'network': network,
                                                    'outside_network': outside_network})
            self.assertEqual([v[-3:] for v in allocation['egress_cleanup_argvs']],
                             [['rm', '-f', proxy_name], ['network', 'rm', network], ['network', 'rm', outside_network]])
            self.assertEqual(allocation['state'], 'removed')
            self.assertEqual(runtime.version['adapter'], 'docker-development-v6')

    def egress_failure(self, replace):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            docker = Path(config['docker'])
            text = docker.read_text()
            for old, new in replace:
                assert old in text, old
                text = text.replace(old, new)
            docker.write_text(text)
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, base / 'tasks')
            workspace = output / 'workspace'; workspace.mkdir(parents=True)
            evidence = runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            commands = self.commands(base)
            self.assertIsNone(evidence['exit_status'])
            self.assertFalse(any(c[0] == 'run' and '-i' in c for c in commands))
            for created in (c[-1] for c in commands if c[:2] == ['network', 'create']):
                self.assertIn(['network', 'rm', created], commands)
            self.assertEqual(json.loads((output / 'runtime.json').read_text())['state'], 'removed')
            return evidence['error']

    def test_an_internal_network_with_ipv6_stops_before_auth_or_model(self):
        self.assertIn('IPv6', self.egress_failure([("'EnableIPv6':False", "'EnableIPv6':True")]))

    def test_a_proxy_listening_anywhere_but_its_internal_address_stops_before_auth_or_model(self):
        self.assertIn('listen', self.egress_failure([("'address':'172.30.0.2'", "'address':'0.0.0.0'")]))

    def tokens(self, base):
        path = base / 'tokens.jsonl'
        return [json.loads(v) for v in path.read_text().splitlines()] if path.exists() else []

    def test_model_hosts_get_a_per_run_token_that_only_codex_holds_and_nothing_logs(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, base / 'tasks')
            workspace = output / 'workspace'; workspace.mkdir(parents=True)
            stdout, stderr = io.StringIO(), io.StringIO()
            evidence = runtime.execute(workspace, 'request', stdout, stderr)
            launch = self.launch(base)
            proxy = next(c for c in self.commands(base) if c[0] == 'run' and '--detach' in c)
            received = {('proxy' if '--detach' in v['argv'] else 'codex' if '-i' in v['argv'] else 'preflight'): v['token']
                        for v in self.tokens(base)}
            token = received['proxy']
            self.assertRegex(token, r'^[0-9a-f]{64}$')
            self.assertEqual(received['codex'], token)
            # Both containers get it by name only, from the Docker client's environment.
            for argv in (proxy, launch):
                self.assertEqual(argv[argv.index('PO_MODEL_TOKEN') - 1], '--env')
            policy = json.loads(proxy[proxy.index('allowlist') + 1])
            self.assertEqual(sorted(policy['model_domains']), ['api.openai.com', 'auth.openai.com', 'chatgpt.com'])
            self.assertNotIn('chatgpt.com', policy['domains'])
            # The Codex process gets the credentialed proxy; the token variable itself is dropped.
            boot = launch[launch.index('-c') + 1]
            self.assertIn('http://model:${PO_MODEL_TOKEN}@', boot)
            self.assertIn('unset PO_MODEL_TOKEN', boot)
            self.assertLess(boot.index('unset PO_MODEL_TOKEN'), boot.index('exec "$@"'))
            # Commands get the token-less proxy and cannot read the Codex home (login, shell snapshots).
            plain = 'http://172.30.0.2:3128'
            policy_arg = next(v for v in launch if v.startswith('shell_environment_policy.set='))
            for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
                self.assertIn(f'{name}="{plain}"', policy_arg)
            self.assertIn(f'PIP_INDEX_URL="{plain}/pypi/simple/"', policy_arg)
            self.assertIn('PIP_TRUSTED_HOST="172.30.0.2:3128"', policy_arg)
            self.assertIn('shell_environment_policy.exclude=["PO_MODEL_TOKEN"]', launch)
            self.assertIn('permissions.development.filesystem={"' + CODEX_HOME + '"="none"}', launch)
            retained = [json.dumps(self.commands(base)), json.dumps(evidence), stdout.getvalue(), stderr.getvalue(),
                        (output / 'runtime.json').read_text(), (output / 'egress.jsonl').read_text()]
            for text in retained:
                self.assertNotIn(token, text)
            self.assertEqual(evidence['egress']['credentialed_hosts'], ['chatgpt.com'])
            self.assertEqual(evidence['egress']['model_credential'], MODEL_CREDENTIAL)
            runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            self.assertNotEqual(self.tokens(base)[-1]['token'], token)

    def test_preflight_proves_commands_cannot_see_a_model_token(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            DevelopmentRuntime(config_path, base / 'run', base / 'tasks')
            attest = next(c for c in self.commands(base) if 'po-runtime-preflight-v1' in c)
            self.assertEqual(attest[attest.index('PO_MODEL_TOKEN') - 1], '--env')
            self.assertTrue(any(v.startswith('shell_environment_policy.set=') for v in attest))
            self.assertIn('permissions.development.filesystem={"' + CODEX_HOME + '"="none"}', attest)
            sentinel = next(v['token'] for v in self.tokens(base) if 'po-runtime-preflight-v1' in v['argv'])
            self.assertNotIn(sentinel, json.dumps(self.commands(base)))
            for check in ('PO_MODEL_TOKEN', '://model:', 'auth.json', 'CODEX_HOME'):
                self.assertIn(check, SANDBOX_PROBE)

    def test_runtime_version_names_the_model_credential_scheme_not_the_token(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            runtime = DevelopmentRuntime(config_path, base / 'run', base / 'tasks')
            self.assertEqual(ADAPTER, 'docker-development-v6')
            self.assertEqual(runtime.version['adapter'], ADAPTER)
            self.assertEqual(runtime.version['egress']['model_credential'], MODEL_CREDENTIAL)
            self.assertIn('proxy-authorization', MODEL_CREDENTIAL)
            commands = runtime.version['command_environment']
            self.assertEqual(commands['exclude'], ['PO_MODEL_TOKEN'])
            self.assertEqual(commands['set']['HTTPS_PROXY'], 'http://<egress proxy>:3128')
            # Python package installs go through the proxy's PyPI gateway, never a tunnel to PyPI.
            self.assertEqual(commands['set']['PIP_INDEX_URL'], 'http://<egress proxy>:3128/pypi/simple/')
            self.assertEqual(commands['set']['PIP_TRUSTED_HOST'], '<egress proxy>:3128')
            self.assertEqual(commands['set']['UV_DEFAULT_INDEX'], 'http://<egress proxy>:3128/pypi/simple/')
            self.assertEqual(commands['set']['NO_PROXY'], 'localhost,127.0.0.1,::1,<egress proxy>')
            self.assertEqual(runtime.version['egress']['pypi_gateway'], PYPI_GATEWAY)
            for needle in ('pypi.org', 'files.pythonhosted.org', '/pypi/simple/', 'Fastly'):
                self.assertIn(needle, PYPI_GATEWAY)
            self.assertEqual(runtime.version['permission_settings']['permissions.development.filesystem'],
                             {CODEX_HOME: 'none'})
            for value in self.tokens(base):
                self.assertNotIn(value['token'], json.dumps(runtime.version))

    def test_log_mode_is_a_different_runtime_version(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            enforced = DevelopmentRuntime(config_path, base / 'run', base / 'tasks')
            measured = DevelopmentRuntime(config_path, base / 'run', base / 'tasks', egress='log')
            self.assertEqual(enforced.version['egress']['mode'], 'allowlist')
            self.assertRegex(enforced.version['egress']['allowlist_sha256'], r'^[0-9a-f]{64}$')
            self.assertRegex(enforced.version['egress']['proxy_sha256'], r'^[0-9a-f]{64}$')
            self.assertNotEqual(enforced.version, measured.version)
            with self.assertRaises(ValueError):
                DevelopmentRuntime(config_path, base / 'run', base / 'tasks', egress='open')

    def test_a_non_internal_network_stops_before_auth_or_model_and_is_removed(self):
        with temporary_directory() as directory:
            base = Path(directory)
            config_path, config = self.configuration(base)
            docker = Path(config['docker'])
            docker.write_text(docker.read_text().replace("'Internal':True", "'Internal':False"))
            output = base / 'run'
            runtime = DevelopmentRuntime(config_path, output, base / 'tasks')
            workspace = output / 'workspace'; workspace.mkdir(parents=True)
            evidence = runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            self.assertIsNone(evidence['exit_status'])
            self.assertIn('internal', evidence['error'])
            commands = self.commands(base)
            self.assertFalse(any(c[0] == 'run' and '-i' in c for c in commands))
            network = next(c for c in commands if c[:2] == ['network', 'create'])[-1]
            self.assertIn(['network', 'rm', network], commands)
            self.assertEqual(json.loads((output / 'runtime.json').read_text())['state'], 'removed')

    def test_sandbox_failure_is_detected_without_auth_mount_or_attempt_allocation(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            docker=Path(config['docker'])
            docker.write_text(docker.read_text().replace("if args[0] == 'run' and 'po-runtime-preflight-v1' in args:",
                "if args[0] == 'run' and 'po-runtime-preflight-v1' in args: print('nested sandbox denied',file=sys.stderr);sys.exit(1)\nif False:"))
            with self.assertRaisesRegex(ValueError,'nested sandbox denied'):
                DevelopmentRuntime(path,base/'run',base/'tasks')
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            probe=next(c for c in commands if 'po-runtime-preflight-v1' in c)
            self.assertNotIn('--mount',probe)
            self.assertNotIn(config['auth_file'],repr(probe))
            self.assertFalse((base/'run').exists())

    def test_invisible_workspace_bind_fails_before_auth_or_model(self):
        with temporary_directory() as directory:
            base = Path(directory)
            path, config = self.configuration(base)
            docker = Path(config['docker'])
            docker.write_text(docker.read_text().replace(
                "    assert pathlib.Path(workspace).is_dir()\n    sys.exit()\n",
                "    print('bind source path does not exist',file=sys.stderr);sys.exit(125)\n"))
            output = base/'run'
            runtime = DevelopmentRuntime(path, output, base/'tasks')
            workspace = output/'workspace'; workspace.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'Docker daemon cannot mount workspace'):
                runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            commands = [json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            probe = next(c for c in commands if 'test -d /workspace' in c)
            self.assertIn('src='+str(workspace), repr(probe))
            self.assertNotIn(config['auth_file'], repr(probe))
            self.assertFalse(any(c[0] == 'run' and '-i' in c for c in commands))
            self.assertFalse((output/'runtime.json').exists())

    def test_sandbox_policy_and_runtime_interpreters_enter_provenance(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            runtime=DevelopmentRuntime(path,base/'run',base/'tasks')
            self.assertEqual(runtime.snapshot_binding['image'],IMAGE)
            self.assertIn('/usr/local/bin/python3.12',runtime.snapshot_binding['symlink_targets'])
            self.assertRegex(runtime.version['sandbox_policy_sha256'],r'^[0-9a-f]{64}$')
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            for command in (c for c in commands if c[0]=='run'):
                self.assertTrue(any(v.startswith('seccomp=') for v in command))
                self.assertNotIn('unconfined',repr(command))
                self.assertNotIn('--cap-add',command)

    def test_successful_preflight_rejects_malformed_runtime_attestation(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            docker=Path(config['docker']); original=docker.read_text()
            normal="print(json.dumps({'sandbox':'workspace-write','symlink_targets':['/usr/local/bin/python','/usr/local/bin/python3','/usr/local/bin/python3.12']}));sys.exit()"
            for value in ('null','[]','{"sandbox":"workspace-write","symlink_targets":["/etc/passwd"]}'):
                docker.write_text(original.replace(normal,'print('+repr(value)+');sys.exit()'))
                with self.assertRaisesRegex(ValueError,'invalid runtime interpreter paths'):
                    DevelopmentRuntime(path,base/'run',base/'tasks')
                self.assertFalse((base/'run').exists())

    def test_preflight_timeout_removes_named_container_and_keeps_original_error(self):
        calls=[]
        def execute(argv, **kwargs):
            calls.append(argv)
            if 'run' in argv:
                raise subprocess.TimeoutExpired(argv,20)
            return subprocess.CompletedProcess(argv,0,stdout='',stderr='')
        with patch('principiis.development_runtime.subprocess.run',side_effect=execute):
            with self.assertRaisesRegex(ValueError,'Docker run exceeded'):
                preflight_run('/docker',['--network','none','image','trusted-control'])
        launch=next(c for c in calls if 'run' in c)
        name=launch[launch.index('--name')+1]
        self.assertTrue(name.startswith('po-development-preflight-'))
        self.assertEqual(calls[-1],docker_command('/docker',['rm','-f',name]))

    def test_invalid_configuration_never_contacts_docker_or_allocates_attempt(self):
        with temporary_directory() as directory:
            base = Path(directory)
            path, config = self.configuration(base)
            for changes in ({'image':'latest'}, {'model':'some-other-model'}, {'auth_file':str(base)},
                            {'docker':'docker'}, {'clean_runtime_review':''}):
                path.write_text(json.dumps(dict(config, **changes)))
                with self.assertRaises(ValueError):
                    load_config(path)
                self.assertFalse((base/'commands.jsonl').exists())
                self.assertFalse((base/'run').exists())

    def test_preflight_rejects_image_credentials(self):
        with temporary_directory() as directory:
            base = Path(directory)
            path, config = self.configuration(base)
            executable = Path(config['docker'])
            executable.write_text(executable.read_text().replace("'PATH=/usr/bin:/bin'", "'OPENAI_API_KEY=do-not-log'"))
            with self.assertRaisesRegex(ValueError, 'environment'):
                DevelopmentRuntime(path, base/'run', base/'tasks')
            self.assertFalse((base/'run').exists())

    def test_diagnostic_timeout_is_a_clear_preallocation_error(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path, config=self.configuration(base)
            with patch('principiis.development_runtime.subprocess.run',side_effect=subprocess.TimeoutExpired(['docker'],20)):
                with self.assertRaisesRegex(ValueError,'Docker image exceeded'):
                    DevelopmentRuntime(path,base/'run',base/'tasks')
            self.assertFalse((base/'run').exists())

    def test_unsupported_mount_path_is_rejected_before_preflight(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path, config=self.configuration(base)
            with self.assertRaisesRegex(ValueError,'commas'):
                DevelopmentRuntime(path,base/'run,broken',base/'tasks')
            self.assertFalse((base/'commands.jsonl').exists())

    def test_failed_container_preserves_partial_application_and_original_exit(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path, config=self.configuration(base)
            docker=Path(config['docker'])
            docker.write_text(docker.read_text().replace("print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':3}}));sys.exit()",
                "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':7,'output_tokens':3}}));sys.exit(7)"))
            output=base/'run';runtime=DevelopmentRuntime(path,output,base/'tasks')
            workspace=output/'workspace';workspace.mkdir(parents=True)
            stdout,stderr=io.StringIO(),io.StringIO()
            evidence=runtime.execute(workspace,'partial',stdout,stderr)
            self.assertEqual(evidence['exit_status'],7)
            self.assertEqual((workspace/'app.py').read_text(),'partial')
            self.assertIn('turn.completed',stdout.getvalue())
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            self.assertTrue(any(c[:2]==['rm','-f'] for c in commands))

    def test_cleanup_failure_does_not_erase_execution_status_and_retains_cleanup_identity(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            docker=Path(config['docker'])
            docker.write_text(docker.read_text().replace("if args[:2] == ['network','create']:",
                "if args[:2] == ['rm','-f'] and not args[-1].startswith('po-development-preflight-'): sys.exit(9)\nif args[:2] == ['network','create']:"))
            output=base/'run';runtime=DevelopmentRuntime(path,output,base/'tasks')
            workspace=output/'workspace';workspace.mkdir(parents=True)
            evidence=runtime.execute(workspace,'complete source',io.StringIO(),io.StringIO())
            self.assertEqual(evidence['exit_status'],0)
            self.assertIn('cleanup_error',evidence)
            allocation=json.loads((output/'runtime.json').read_text())
            self.assertEqual(allocation['state'],'cleanup_error')
            self.assertEqual(allocation['container'],evidence['runtime']['container'])
            self.assertEqual(allocation['execution_exit_status'],0)
            self.assertEqual(allocation['cleanup_argv'][-3:],['rm','-f',allocation['container']])

    def cleanup_allocation(self, base, config):
        allocation=base/'retained-runtime.json'
        name='po-development-'+'b'*32
        allocation.write_text(json.dumps({'schema_version':1,'container':name,'image':IMAGE,
            'state':'allocated','cleanup_argv':docker_command(config['docker'],['rm','-f',name])}))
        return allocation

    def egress_allocation(self, base, config, egress):
        allocation = self.cleanup_allocation(base, config)
        allocation.write_text(json.dumps(dict(json.loads(allocation.read_text()), egress=egress)))
        return allocation

    def test_explicit_cleanup_removes_the_proxy_before_both_networks(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            token='b'*32
            egress={'container':'po-development-egress-'+token,'network':'po-development-net-'+token,
                    'outside_network':'po-development-out-'+token}
            record=cleanup_runtime(self.egress_allocation(base,config,egress),path,base/'cleanup')
            self.assertEqual(record['outcome'],'removed')
            self.assertEqual(self.commands(base),[['rm','-f','po-development-'+token],['rm','-f',egress['container']],
                                                  ['network','rm',egress['network']],['network','rm',egress['outside_network']]])

    def test_explicit_cleanup_accepts_allocations_made_before_the_outside_network(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            token='b'*32
            egress={'container':'po-development-egress-'+token,'network':'po-development-net-'+token}
            record=cleanup_runtime(self.egress_allocation(base,config,egress),path,base/'cleanup')
            self.assertEqual(record['outcome'],'removed')
            self.assertEqual(self.commands(base),[['rm','-f','po-development-'+token],['rm','-f',egress['container']],
                                                  ['network','rm',egress['network']]])

    def test_explicit_cleanup_refuses_a_foreign_egress_identity(self):
        token='b'*32
        good={'container':'po-development-egress-'+token,'network':'po-development-net-'+token,
              'outside_network':'po-development-out-'+token}
        for egress in (dict(good,outside_network='bridge'), dict(good,outside_network='po-development-out-'+'c'*32),
                       dict(good,extra='x'), {'container':good['container']}, dict(good,outside_network=None)):
            with temporary_directory() as directory, self.subTest(egress=egress):
                base=Path(directory)
                path,config=self.configuration(base)
                with self.assertRaisesRegex(ValueError,'egress identity'):
                    cleanup_runtime(self.egress_allocation(base,config,egress),path,base/'cleanup')
                self.assertFalse((base/'commands.jsonl').exists())

    def test_explicit_cleanup_keeps_original_evidence_and_does_not_need_auth_file(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            allocation=self.cleanup_allocation(base,config)
            before=allocation.read_bytes()
            result=base/'result.json';result.write_text('{"outcome":"incomplete"}')
            result_before=result.read_bytes()
            Path(config['auth_file']).unlink()
            record=cleanup_runtime(allocation,path,base/'cleanup-1')
            self.assertEqual(record['outcome'],'removed')
            self.assertEqual(record['exit_status'],0)
            self.assertEqual(allocation.read_bytes(),before)
            self.assertEqual(result.read_bytes(),result_before)
            self.assertTrue((base/'cleanup-1/cleanup.json').is_file())
            self.assertEqual(record['argv'],json.loads(before)['cleanup_argv'])
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            self.assertEqual(commands,[['rm','-f','po-development-'+'b'*32]])

    def test_explicit_cleanup_only_accepts_saved_canonical_container_command(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            allocation=self.cleanup_allocation(base,config)
            original=json.loads(allocation.read_text())
            for changes in ({'container':'unrelated-container'}, {'image':'sha256:'+'c'*64},
                            {'cleanup_argv':['rm','-rf','/']}, {'cleanup_argv':['sh','-c','touch /tmp/forbidden']}):
                allocation.write_text(json.dumps(dict(original,**changes)))
                with self.assertRaises(ValueError):
                    cleanup_runtime(allocation,path,base/'cleanup')
                self.assertFalse((base/'commands.jsonl').exists())
                self.assertFalse((base/'cleanup').exists())

    def test_explicit_cleanup_retains_daemon_failure_and_accepts_only_exact_missing_container(self):
        with temporary_directory() as directory:
            base=Path(directory)
            path,config=self.configuration(base)
            allocation=self.cleanup_allocation(base,config)
            before=allocation.read_bytes()
            docker=Path(config['docker'])
            original=docker.read_text()
            docker.write_text(original+"\nprint('Cannot connect to the Docker daemon',file=sys.stderr);sys.exit(1)\n")
            failed=cleanup_runtime(allocation,path,base/'cleanup-failed')
            self.assertEqual(failed['outcome'],'cleanup_error')
            self.assertEqual(failed['exit_status'],1)
            self.assertIn('Cannot connect',(base/'cleanup-failed/docker.stderr').read_text())
            docker.write_text(original+"\nprint('Error response from daemon: No such container: '+args[-1],file=sys.stderr);sys.exit(1)\n")
            missing=cleanup_runtime(allocation,path,base/'cleanup-missing')
            self.assertEqual(missing['outcome'],'removed')
            self.assertTrue(missing['absent_before_cleanup'])
            self.assertEqual(missing['exit_status'],1)
            self.assertEqual(allocation.read_bytes(),before)
            self.assertEqual(json.loads((base/'cleanup-failed/cleanup.json').read_text())['outcome'],'cleanup_error')


if __name__ == '__main__':
    unittest.main()
