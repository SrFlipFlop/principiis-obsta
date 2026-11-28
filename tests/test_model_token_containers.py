"""Opt-in, model-free control: only the Codex process can reach the model hosts (#75).

Nothing here can reach OpenAI. Every proxy started here has its outside network
removed right after it starts, so it can decide and log but never connect out; the
`codex exec` controls also run the proxy with a refuse-everything policy. The one
exception, the PyPI gateway control, keeps its way out but gets no model token (so the
model hosts are always refused) and no `domains`. The login is a FAKE file with dummy
tokens, and the one model that answers is a loopback stand-in inside the container.

    PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=/var/tmp/po-scratch PO_EGRESS_CONTROL=1 \\
        python3 -m unittest discover -s tests -p test_model_token_containers.py

Docker Desktop: set the runtime.json host settings these controls write into their
config (see `support.runtime_host_settings`):

    PO_DOCKER=/usr/local/bin/docker PO_DOCKER_SOCKET=$HOME/.docker/run/docker.sock \\
    PO_RUNTIME_PROC=unmasked-for-nested-sandbox PO_RUNTIME_WORKSPACE_MOUNT=volume
"""
import base64
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import time
import unittest
from unittest.mock import patch
import uuid

from support import runtime_host_settings

from principiis import development_runtime as runtime_module
from principiis.development_runtime import (MODEL_PROXY_BOOT, MODEL_TOKEN_VARIABLE, DevelopmentRuntime,
                                            command_settings, configuration_args, docker_environment, docker_run,
                                            load_allowlist, proxy_environment, remove, workspace_permission_settings)

ENABLED = (os.environ.get('PO_RUNTIME_IMAGE') and os.environ.get('PO_RUNTIME_ROOT')
           and os.environ.get('PO_EGRESS_CONTROL') == '1')
MODEL_HOSTS = ('chatgpt.com', 'api.openai.com', 'auth.openai.com')
REFUSE_EVERYTHING = {'domains': [], 'model_domains': []}

# CONNECT through whatever proxy this process's environment names, with the
# credential in its URL if there is one (as reqwest does). Prints the status lines.
CONNECT_PROBE = r'''
import base64, json, os, socket, sys, urllib.parse
proxy = urllib.parse.urlsplit(os.environ['HTTPS_PROXY'])
status = {}
for host in sys.argv[1:]:
    head = f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n'
    if proxy.username:
        pair = urllib.parse.unquote(proxy.username) + ':' + urllib.parse.unquote(proxy.password or '')
        head += 'Proxy-Authorization: Basic ' + base64.b64encode(pair.encode()).decode() + '\r\n'
    with socket.create_connection((proxy.hostname, proxy.port), timeout=30) as sock:
        sock.sendall((head + '\r\n').encode())
        status[host] = sock.recv(4096).split(b'\r\n')[0].decode()
print(json.dumps(status))
'''
# Run as a command inside Codex's sandbox: try the model hosts, then dump everything a
# command could read that might hold the token. The test, not the probe, looks for it.
COMMAND_PROBE = r'''
import json, os, pathlib, re, socket, urllib.parse
proxy = urllib.parse.urlsplit(os.environ['HTTPS_PROXY'])
result = {'proxy_has_userinfo': bool(proxy.username), 'connect': {}, 'environ': {}, 'files': {}, 'unreadable': []}
for host in ('chatgpt.com', 'api.openai.com', 'auth.openai.com'):
    with socket.create_connection((proxy.hostname, proxy.port), timeout=30) as sock:
        sock.sendall(f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode())
        result['connect'][host] = sock.recv(4096).split(b'\r\n')[0].decode()
result['env'] = dict(os.environ)
for entry in pathlib.Path('/proc').iterdir():
    if re.fullmatch('[0-9]+', entry.name):
        try:
            result['environ'][entry.name] = (entry / 'environ').read_bytes().decode(errors='replace')
        except OSError as error:
            result['environ'][entry.name] = type(error).__name__
home = os.environ.get('CODEX_HOME', '/home/developer/.codex')
try:
    result['auth_json'] = pathlib.Path(home, 'auth.json').read_text()
except OSError as error:
    result['auth_json'] = type(error).__name__
for root in ('/home', '/tmp', '/run', '/workspace', '/etc'):
    for directory, _, names in os.walk(root, onerror=lambda error: result['unreadable'].append(error.filename)):
        for name in names:
            path = os.path.join(directory, name)
            try:
                if os.path.getsize(path) < 1_000_000:
                    result['files'][path] = pathlib.Path(path).read_bytes().decode(errors='replace')
            except OSError:
                result['unreadable'].append(path)
print('PO-COMMAND-PROBE ' + json.dumps(result))
'''
# A TCP sink that stands in for chatgpt.com on the internal network (a Docker network
# alias): it records what the proxy forwarded and never answers.
SINK = r'''
import socket, sys, threading
def take(conn):
    conn.settimeout(10)
    data = b''
    try:
        while chunk := conn.recv(65536):
            data += chunk
    except OSError:
        pass
    conn.close()
    print('PO-SINK', len(data), data[:1].hex(), b'chatgpt.com' in data, b'pypi.org' in data, flush=True)
server = socket.create_server(('0.0.0.0', 443))
print('PO-SINK-READY', flush=True)
while True:
    threading.Thread(target=take, args=(server.accept()[0],), daemon=True).start()
'''
# The Codex process's credentialed CONNECT to chatgpt.com, then a TLS ClientHello with
# the given SNI (empty: no CONNECT credential). Prints the CONNECT status per case.
SNI_PROBE = r'''
import base64, json, os, socket, ssl, sys
token = os.environ.pop('PO_MODEL_TOKEN')
proxy = os.environ['PROXY_ADDRESS']
result = {}
for case in sys.argv[1:]:
    sni, credentialed = case.split(':')
    head = 'CONNECT chatgpt.com:443 HTTP/1.1\r\nHost: chatgpt.com:443\r\n'
    if credentialed == 'yes':
        head += 'Proxy-Authorization: Basic ' + base64.b64encode(('model:' + token).encode()).decode() + '\r\n'
    sock = socket.create_connection((proxy, 3128), timeout=15)
    sock.sendall((head + '\r\n').encode())
    reply = b''
    while b'\r\n\r\n' not in reply and (chunk := sock.recv(4096)):
        reply += chunk
    status = reply.split(b'\r\n')[0].decode()
    if ' 200 ' in status:
        context = ssl.create_default_context()
        try:
            context.wrap_socket(sock, server_hostname=sni).close()
            status += ' | handshake completed'
        except (OSError, ssl.SSLError) as error:
            status += ' | ' + type(error).__name__
    sock.close()
    result[case] = status
print('PO-SNI-PROBE ' + json.dumps(result))
'''
# A loopback stand-in for the Responses API. The first turn asks for one command; the
# next prints that command's output to stderr and ends the session.
MOCK_MODEL = r'''
import http.server, json, sys
COMMAND = sys.argv[2]
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        self.reply(b'{"data": [], "models": []}', 'application/json')
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        outputs = [i for i in request.get('input', []) if isinstance(i, dict) and i.get('type') == 'function_call_output']
        tools = [t.get('name') for t in request.get('tools', []) if isinstance(t, dict)]
        if outputs:
            sys.stderr.write('PO-MOCK-OUTPUT ' + json.dumps(outputs[-1].get('output')) + '\n'); sys.stderr.flush()
            item = {'type': 'message', 'role': 'assistant', 'id': 'msg_1', 'content': [{'type': 'output_text', 'text': 'done'}]}
        else:
            name, arguments = ('exec_command', {'cmd': COMMAND, 'yield_time_ms': 30000}) if 'exec_command' in tools \
                else ('shell', {'command': ['bash', '-lc', COMMAND]})
            item = {'type': 'function_call', 'id': 'fc_1', 'call_id': 'call_1', 'name': name, 'arguments': json.dumps(arguments)}
        events = [{'type': 'response.created', 'response': {'id': 'resp'}},
                  {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                  {'type': 'response.completed', 'response': {'id': 'resp', 'usage': {
                      'input_tokens': 1, 'input_tokens_details': None, 'output_tokens': 1,
                      'output_tokens_details': None, 'total_tokens': 2}}}]
        self.reply(''.join(f'event: {e["type"]}\ndata: {json.dumps(e)}\n\n' for e in events).encode(), 'text/event-stream')
    def reply(self, body, kind):
        self.send_response(200); self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
'''


def fake_login(path):
    """Dummy, unsigned ChatGPT tokens: enough for `codex login status`, useless to any server."""
    def encode(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()
    claims = {'email': 'fake@example.invalid', 'exp': 4102444800, 'iat': 1700000000,
              'https://api.openai.com/auth': {'chatgpt_account_id': 'fake-account', 'chatgpt_plan_type': 'plus'}}
    jwt = encode({'alg': 'none', 'typ': 'JWT'}) + '.' + encode(claims) + '.fake-signature'
    path.write_text(json.dumps({'OPENAI_API_KEY': None, 'auth_mode': 'chatgpt', 'last_refresh': '2026-11-27T00:00:00Z',
                                'tokens': {'id_token': jwt, 'access_token': jwt, 'refresh_token': 'fake-refresh',
                                           'account_id': 'fake-account'}}))


def secrets_of(token):
    return (token, base64.b64encode(f'model:{token}'.encode()).decode())


@unittest.skipUnless(ENABLED, 'set PO_RUNTIME_IMAGE, PO_RUNTIME_ROOT and PO_EGRESS_CONTROL=1 for the model-free token control')
class ModelTokenContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = os.environ['PO_RUNTIME_IMAGE']
        cls.scratch = Path(os.environ['PO_RUNTIME_ROOT']).resolve() / ('model-token-control-' + uuid.uuid4().hex)
        cls.scratch.mkdir(parents=True)
        cls.resources = []
        login = cls.scratch / 'fake-login.json'
        fake_login(login)
        (cls.scratch / 'mock_model.py').write_text(MOCK_MODEL)
        (cls.scratch / 'command_probe.py').write_text(COMMAND_PROBE)
        cls.config = cls.scratch / 'runtime-config.json'
        cls.config.write_text(json.dumps({'version': '1', 'docker': os.environ.get('PO_DOCKER', '/snap/bin/docker'),
                                          'image': cls.image, 'auth_file': str(login),
                                          'clean_runtime_review': 'trusted no-model control only',
                                          **runtime_host_settings()}))
        # The configured CLI, bound to the configured daemon socket.
        loaded = runtime_module.load_config(cls.config)
        cls.docker, cls.proc = loaded['docker'], loaded['proc']
        try:
            # The constructor's preflight runs the token probe inside the nested sandbox.
            cls.runtime = DevelopmentRuntime(cls.config, cls.scratch / 'output', cls.scratch / 'source')
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        errors = []
        for argv in cls.resources:
            try:
                remove(cls.docker, argv)
            except Exception as error:
                errors.append(str(error))
        shutil.rmtree(cls.scratch, ignore_errors=True)
        if errors:
            raise RuntimeError('model token control cleanup failed: ' + '; '.join(errors))

    def isolate(self, container, keep):
        """Remove every network but `keep` from the proxy: it can decide and log, never connect out."""
        networks = json.loads(docker_run(self.docker, ['inspect', container]))[0]['NetworkSettings']['Networks']
        for name in networks:
            if name != keep:
                docker_run(self.docker, ['network', 'disconnect', '--force', name, container])
        left = json.loads(docker_run(self.docker, ['inspect', container]))[0]['NetworkSettings']['Networks']
        self.assertEqual(list(left), [keep])

    def egress(self, policy, token):
        suffix = uuid.uuid4().hex
        egress = {'container': 'po-development-egress-' + suffix, 'network': 'po-development-net-' + suffix,
                  'outside_network': 'po-development-out-' + suffix}
        self.resources[:0] = [['rm', '-f', egress['container']], ['network', 'rm', egress['network']],
                              ['network', 'rm', egress['outside_network']]]
        self.runtime.allowlist = policy
        proxy = self.runtime.start_egress(egress, token)
        self.isolate(egress['container'], egress['network'])
        return egress, proxy

    def log(self, container):
        return [json.loads(line) for line in docker_run(self.docker, ['logs', container]).splitlines() if line.strip()]

    def test_commands_get_403_for_model_hosts_and_cannot_recover_the_token(self):
        token = secrets.token_hex(32)
        egress, proxy = self.egress(load_allowlist(), token)
        boot = ('mkdir -p "$CODEX_HOME"; echo FAKE-LOGIN > "$CODEX_HOME/auth.json"; ' + MODEL_PROXY_BOOT
                + 'echo "PO-CODEX-PROCESS $(python -c "$1" ' + ' '.join(MODEL_HOSTS) + ')"; shift; exec "$@"')
        output = docker_run(self.docker, [
            'run', '--rm', '--network', egress['network'], *runtime_module.restrictions(nested_sandbox=True, proc=self.proc),
            *proxy_environment(proxy), '--env', MODEL_TOKEN_VARIABLE,
            '--tmpfs', '/workspace:rw,exec,nosuid,nodev,size=64m,mode=1777',
            '--entrypoint', '/bin/sh', self.image, '-eu', '-c', boot, 'po-model-token-control', CONNECT_PROBE,
            'codex', '--no-daemon', 'sandbox', '--permission-profile', 'development',
            *configuration_args({**workspace_permission_settings(), **command_settings(proxy)}),
            '--cd', '/workspace', '--', 'python', '-c', COMMAND_PROBE],
            timeout=180, env={**docker_environment(), MODEL_TOKEN_VARIABLE: token})
        lines = {line.split(' ', 1)[0]: line.split(' ', 1)[1] for line in output.splitlines() if line.startswith('PO-')}
        codex_process = json.loads(lines['PO-CODEX-PROCESS'])
        command = json.loads(lines['PO-COMMAND-PROBE'])
        (self.scratch / 'command-probe.json').write_text(json.dumps(command, indent=1))
        print('\nCodex process (credentialed proxy):', codex_process)
        print('Command in the nested sandbox:', command['connect'], '| auth.json:', command['auth_json'],
              '| visible pids:', sorted(command['environ']), '| proxy has userinfo:', command['proxy_has_userinfo'])
        # (a) Commands are refused; the Codex process's credential is accepted (then no route out).
        for host in MODEL_HOSTS:
            self.assertIn(' 403 ', command['connect'][host])
            self.assertNotIn(' 403 ', codex_process[host])
        # (b) Nothing a command can read holds the token.
        for value in secrets_of(token):
            self.assertNotIn(value, output)
        self.assertFalse(command['proxy_has_userinfo'])
        # (c) The login is not readable from commands.
        self.assertEqual(command['auth_json'], 'PermissionError')
        events = [e for e in self.log(egress['container']) if 'decision' in e]
        print('Proxy decisions:', [(e['host'], e['decision'], e['credential'], e.get('reason')) for e in events])
        for host in MODEL_HOSTS:
            self.assertIn((host, 'refused', 'absent'), [(e['host'], e['decision'], e['credential']) for e in events])
            self.assertIn((host, 'allowed', 'valid'), [(e['host'], e['decision'], e['credential']) for e in events])
        self.assertNotIn('connected', {e['decision'] for e in events})
        for value in secrets_of(token):
            self.assertNotIn(value, json.dumps(self.log(egress['container'])))

    def test_a_command_in_the_codex_sandbox_installs_from_pypi_through_the_gateway(self):
        # The one proxy here that keeps its way out, so the gateway can reach PyPI. It still
        # cannot reach OpenAI: it gets no model token (so no credential is ever valid, and
        # model hosts are refused), `domains` is empty, and the container gets no token either.
        suffix = uuid.uuid4().hex
        egress = {'container': 'po-development-egress-' + suffix, 'network': 'po-development-net-' + suffix,
                  'outside_network': 'po-development-out-' + suffix}
        self.resources[:0] = [['rm', '-f', egress['container']], ['network', 'rm', egress['network']],
                              ['network', 'rm', egress['outside_network']]]
        self.runtime.allowlist = {'domains': [], 'model_domains': list(MODEL_HOSTS)}
        proxy = self.runtime.start_egress(egress, '')
        install = ('python -m venv /workspace/venv && /workspace/venv/bin/pip install --no-cache-dir '
                   'six==1.16.0 requests==2.32.3 2>&1 | grep -E "Successfully|ERROR" ; '
                   'env | grep -E "^(PIP_INDEX_URL|PIP_TRUSTED_HOST|UV_DEFAULT_INDEX)=" | sort')
        output = docker_run(self.docker, [
            'run', '--rm', '--network', egress['network'], *runtime_module.restrictions(nested_sandbox=True, proc=self.proc),
            '--tmpfs', '/workspace:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--entrypoint', '/bin/sh', self.image, '-eu', '-c', 'mkdir -p "$CODEX_HOME"; exec "$@"', 'po-gateway-control',
            'codex', '--no-daemon', 'sandbox', '--permission-profile', 'development',
            *configuration_args({**workspace_permission_settings(), **command_settings(proxy)}),
            '--cd', '/workspace', '--', '/bin/sh', '-c', install], timeout=300)
        print('\ncommand in the Codex sandbox (command environment only):', output.strip())
        self.assertIn('Successfully installed', output)
        for package in ('six-1.16.0', 'requests-2.32.3', 'urllib3-'):
            self.assertIn(package, output)
        self.assertIn(f'PIP_INDEX_URL=http://{proxy}:3128/pypi/simple/', output)
        events = self.log(egress['container'])
        print('proxy decisions:', sorted({(e.get('event'), e.get('host'), e.get('route'), e['decision'])
                                          for e in events if 'decision' in e}))
        routes = {(e['host'], e['route']) for e in events if e.get('event') == 'gateway' and e['decision'] == 'connected'}
        self.assertEqual(routes, {('pypi.org', 'simple'), ('files.pythonhosted.org', 'files')})
        self.assertFalse({e.get('host') for e in events if e.get('method') == 'CONNECT'} & {'pypi.org', 'files.pythonhosted.org'})
        self.assertNotIn('connected', {e['decision'] for e in events if e.get('host') in MODEL_HOSTS})

    def test_the_codex_process_credentialed_tunnel_still_passes_the_sni_check(self):
        # chatgpt.com resolves, for the isolated proxy only, to a sink on the internal
        # network (Docker DNS alias). The proxy has no outside network, so nothing here
        # can reach OpenAI even if the alias did not resolve.
        token = secrets.token_hex(32)
        egress, proxy = self.egress(load_allowlist(), token)
        sink = 'po-development-sink-' + uuid.uuid4().hex
        self.resources[:0] = [['rm', '-f', sink]]
        docker_run(self.docker, ['run', '--detach', '--name', sink, '--network', egress['network'],
                                 '--network-alias', 'chatgpt.com', *runtime_module.restrictions(),
                                 '--entrypoint', 'python', self.image, '-c', SINK])
        for _ in range(50):
            if 'PO-SINK-READY' in docker_run(self.docker, ['logs', sink]):
                break
            time.sleep(.2)
        cases = ('chatgpt.com:yes', 'pypi.org:yes', 'raw.githubusercontent.com:yes', 'chatgpt.com:no')
        output = docker_run(self.docker, [
            'run', '--rm', '--network', egress['network'], *runtime_module.restrictions(),
            '--env', 'PROXY_ADDRESS=' + proxy, '--env', MODEL_TOKEN_VARIABLE,
            '--entrypoint', 'python', self.image, '-c', SNI_PROBE, *cases],
            timeout=120, env={**docker_environment(), MODEL_TOKEN_VARIABLE: token})
        statuses = json.loads(next(v for v in output.splitlines() if v.startswith('PO-SNI-PROBE ')).split(' ', 1)[1])
        events = self.log(egress['container'])
        print('\ncredentialed tunnels:', statuses)
        print('proxy events:', [(e.get('event'), e.get('host'), e.get('decision'), e.get('credential'),
                                 e.get('reason'), e.get('sni')) for e in events if e.get('host') == 'chatgpt.com'])
        time.sleep(1)
        received = [line.split()[1:] for line in docker_run(self.docker, ['logs', sink]).splitlines()
                    if line.startswith('PO-SINK ')]
        print('sink received (bytes, first byte, chatgpt.com, pypi.org):', received)
        for case in cases[:3]:
            self.assertIn(' 200 ', statuses[case])
        self.assertIn(' 403 ', statuses['chatgpt.com:no'])
        refusals = [(e.get('reason'), e.get('sni'), e.get('credential')) for e in events
                    if e.get('host') == 'chatgpt.com' and e.get('decision') == 'refused']
        self.assertIn(('sni-mismatch', 'pypi.org', 'valid'), refusals)
        self.assertIn(('sni-mismatch', 'raw.githubusercontent.com', 'valid'), refusals)
        self.assertIn(('model host without the model credential', None, 'absent'), refusals)
        self.assertIn('chatgpt.com', [e.get('sni') for e in events if e.get('event') == 'tls'])
        # Only the hello whose SNI is the CONNECT host reached the (stand-in) server.
        forwarded = [r for r in received if r[0] != '0']
        self.assertEqual(forwarded, [[forwarded[0][0], '16', 'True', 'False']] if forwarded else [])
        self.assertEqual(len(forwarded), 1)
        for value in secrets_of(token):
            self.assertNotIn(value, json.dumps(events) + output)

    def run_exec(self, policy, *, mock):
        """`DevelopmentRuntime.execute` as is, with the proxy isolated (and the stand-in model if `mock`)."""
        seen = {}
        start = self.runtime.start_egress
        real_execute = runtime_module.execute

        def isolated_start(egress, model_token=''):
            # `execute` removes this proxy and network itself.
            seen['token'] = model_token
            self.runtime.allowlist = policy
            proxy = start(egress, model_token)
            self.isolate(egress['container'], egress['network'])
            seen['egress'] = egress
            return proxy

        def control_execute(argv, *args, **kwargs):
            seen['argv'] = list(argv)
            argv = list(argv)
            if mock:
                entry = argv.index('--entrypoint')
                argv[entry:entry] = ['--mount', f'type=bind,src={self.scratch / "mock_model.py"},dst=/run/po-mock.py,readonly',
                                     '--mount', f'type=bind,src={self.scratch / "command_probe.py"},dst=/run/po-probe.py,readonly']
                boot = argv.index('-eu') + 2
                argv[boot] = "python /run/po-mock.py 8765 'python /run/po-probe.py' & " + argv[boot]
                argv[argv.index('model_provider="openai"')] = 'model_provider="mock"'
                argv[-1:-1] = ['-c', 'model="mock-model"', '-c',
                               'model_providers.mock={name="mock",base_url="http://127.0.0.1:8765/v1",wire_api="responses"}']
            return real_execute(argv, *args, **dict(kwargs, timeout=180))

        workspace = self.scratch / ('exec-' + uuid.uuid4().hex) / 'workspace'
        workspace.mkdir(parents=True)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(self.runtime, 'start_egress', isolated_start), \
                patch.object(runtime_module, 'execute', control_execute):
            evidence = self.runtime.execute(workspace, 'model-free control request', stdout, stderr)
        retained = [json.dumps(evidence), json.dumps(seen['argv']), stdout.getvalue(), stderr.getvalue()]
        retained += [p.read_text() for p in workspace.parent.glob('*.json*')]
        for text in retained:
            for value in secrets_of(seen['token']):
                self.assertNotIn(value, text)
        events = [json.loads(line) for line in (workspace.parent / 'egress.jsonl').read_text().splitlines() if line.strip()]
        return evidence, events, stderr.getvalue()

    def test_codex_exec_presents_the_model_credential_to_a_refusing_proxy(self):
        # (d) The real Codex process, a FAKE login, and a proxy that refuses everything
        # and has no way out: it only records whether the credential came.
        evidence, events, stderr = self.run_exec(REFUSE_EVERYTHING, mock=False)
        decisions = [(e['host'], e['decision'], e['credential']) for e in events if 'decision' in e]
        print('\ncodex exec against the refusing proxy:', sorted(set(decisions)))
        print('exit status:', evidence['exit_status'], '| stderr tail:', stderr[-300:].replace('\n', ' | '))
        self.assertTrue(decisions, 'Codex sent nothing through the proxy')
        self.assertEqual({d for _, d, _ in decisions}, {'refused'})
        model_requests = [c for host, _, c in decisions if host in MODEL_HOSTS]
        self.assertTrue(model_requests)
        self.assertEqual(set(model_requests), {'valid'})
        self.assertEqual(evidence['egress']['credentialed_hosts'], sorted({h for h, _, c in decisions if c == 'valid'}))

    def test_commands_run_by_codex_exec_get_the_token_less_proxy(self):
        # The real `codex exec` command path (shell snapshot, exec_command) with a loopback
        # stand-in model that asks for one probe command.
        evidence, events, stderr = self.run_exec(load_allowlist(), mock=True)
        line = next(v for v in stderr.splitlines() if v.startswith('PO-MOCK-OUTPUT '))
        output = json.loads(line.split(' ', 1)[1])
        command = json.loads(output[output.index('PO-COMMAND-PROBE ') + len('PO-COMMAND-PROBE '):].splitlines()[0])
        print('\ncodex exec command:', command['connect'], '| auth.json:', command['auth_json'],
              '| visible pids:', sorted(command['environ']), '| proxy has userinfo:', command['proxy_has_userinfo'])
        print('proxy decisions:', sorted({(e['host'], e['decision'], e['credential']) for e in events if 'decision' in e}))
        self.assertEqual(evidence['exit_status'], 0)
        for host in MODEL_HOSTS:
            self.assertIn(' 403 ', command['connect'][host])
        self.assertFalse(command['proxy_has_userinfo'])
        self.assertEqual(command['auth_json'], 'PermissionError')
        refused = {(e['host'], e['credential']) for e in events if e.get('decision') == 'refused'}
        for host in MODEL_HOSTS:
            self.assertIn((host, 'absent'), refused)
        self.assertNotIn('connected', {e.get('decision') for e in events})


if __name__ == '__main__':
    unittest.main()
