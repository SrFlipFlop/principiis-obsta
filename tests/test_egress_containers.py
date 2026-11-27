"""Opt-in, model-free, credential-free control of the real egress network and proxy (#75).

Starts the internal Docker network, the proxy's outside network and the proxy sidecar
through `DevelopmentRuntime.start_egress`, exactly as `execute` does, then probes them
from client containers that run in the same network with the same restrictions as the
agent container. No auth file is mounted, no model is called. The Codex preflight is
skipped, so any local image with `python` works (the proxy needs only the standard
library); the pip check needs `pip`, the npm check is skipped without `npm`. Needs
Docker and outbound internet from the host.

    PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=/var/tmp/po-scratch PO_EGRESS_CONTROL=1 \
        python3 -m unittest discover -s tests -p test_egress_containers.py

`PO_DOCKER` names the Docker CLI (default `/snap/bin/docker`).
"""
import json
import os
from pathlib import Path
import shutil
import socket
import unittest
import uuid

from principiis.development_runtime import (DevelopmentRuntime, docker_run, load_allowlist, load_config,
                                            proxy_environment, remove, restrictions)

# Executed inside a client container; prints one JSON result.
CONNECT_PROBE = r'''
import json, socket, sys
host, port = sys.argv[1], int(sys.argv[2])
sock = socket.create_connection((sys.argv[3], 3128), timeout=15)
sock.sendall(f'CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n'.encode())
print(json.dumps({'status': sock.recv(4096).split(b'\r\n')[0].decode()}))
'''
# CONNECT to `host`, then TLS with `server_name` as SNI and an HTTP/1.1 GET with `http_host`.
TLS_PROBE = r'''
import json, socket, ssl, sys
proxy, host, server_name, http_host, path = sys.argv[1:6]
sock = socket.create_connection((proxy, 3128), timeout=20)
sock.sendall(f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode())
reply = b''
while b'\r\n\r\n' not in reply:
    reply += sock.recv(4096)
result = {'connect': reply.split(b'\r\n')[0].decode()}
context = ssl.create_default_context()
context.check_hostname = False   # the certificate is for `host`; this probe is about SNI routing
context.verify_mode = ssl.CERT_NONE
try:
    tls = context.wrap_socket(sock, server_hostname=server_name)
    result['tls'] = 'established'
    tls.sendall(f'GET {path} HTTP/1.1\r\nHost: {http_host}\r\nUser-Agent: po-egress-control\r\nConnection: close\r\n\r\n'.encode())
    data = b''
    while len(data) < 65536 and (chunk := tls.recv(65536)):
        data += chunk
    head, _, body = data.partition(b'\r\n\r\n')
    result['status'] = head.split(b'\r\n')[0].decode(errors='replace')
    result['server'] = [line.decode(errors='replace') for line in head.split(b'\r\n')[1:]
                        if line.lower().startswith((b'server:', b'x-github-request-id', b'via:'))]
    result['body'] = body[:200].decode(errors='replace')
except (OSError, ssl.SSLError) as error:
    result['tls'] = 'failed: ' + type(error).__name__
print(json.dumps(result))
'''
DIRECT_PROBE = r'''
import json, socket, sys
result = {}
for label, address, family in (('tcp', '1.1.1.1', socket.AF_INET), ('tcp_github', sys.argv[1], socket.AF_INET),
                               ('tcp_ipv6', '2606:4700:4700::1111', socket.AF_INET6)):
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((address, 443))
        sock.close()
        result[label] = 'connected'
    except OSError:
        result[label] = 'failed'
for label, name in (('dns', 'pypi.org'), ('dns_github', 'github.com')):
    try:
        socket.getaddrinfo(name, 443)
        result[label] = 'resolved'
    except OSError:
        result[label] = 'failed'
try:
    lines = open('/proc/net/if_inet6').read().split()
except OSError:
    lines = []
# Only link-local (fe80::/10, scope 0x20) or loopback IPv6 addresses are acceptable.
result['global_ipv6'] = [v for v in lines[::6] if not v.startswith(('fe80', '00000000000000000000000000000001'))]
print(json.dumps(result))
'''
REACH_PROBE = r'''
import json, socket, sys
try:
    socket.create_connection((sys.argv[1], 3128), timeout=5).close()
    print(json.dumps('connected'))
except OSError:
    print(json.dumps('failed'))
'''
PLAIN_HTTP_PROBE = r'''
import socket, sys
sock = socket.create_connection((sys.argv[1], 3128), timeout=15)
sock.sendall(b'GET http://pypi.org/secret-path-sentinel?q=query-sentinel HTTP/1.1\r\nHost: ' + sys.argv[2].encode() + b'\r\n'
             b'X-Header-Sentinel: header-value-sentinel\r\nConnection: close\r\n\r\n')
print(sock.recv(4096).split(b'\r\n')[0].decode())
'''
LOG_KEYS = {'method', 'host', 'port', 'decision', 'time', 'event', 'mode', 'allowlist', 'error', 'address',
            'reason', 'sni'}
GITHUB = ('github.com', 'api.github.com', 'raw.githubusercontent.com', 'codeload.github.com',
          'objects.githubusercontent.com', 'gist.github.com')


@unittest.skipUnless(os.environ.get('PO_RUNTIME_IMAGE') and os.environ.get('PO_RUNTIME_ROOT')
                     and os.environ.get('PO_EGRESS_CONTROL') == '1',
                     'set PO_RUNTIME_IMAGE, PO_RUNTIME_ROOT and PO_EGRESS_CONTROL=1 for the model-free egress control')
class EgressContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = os.environ['PO_RUNTIME_IMAGE']
        cls.docker = os.environ.get('PO_DOCKER', '/snap/bin/docker')
        cls.scratch = Path(os.environ['PO_RUNTIME_ROOT']).resolve() / ('egress-control-' + uuid.uuid4().hex)
        cls.scratch.mkdir(parents=True)
        auth = cls.scratch / 'not-authentication.fixture'
        auth.write_text('never mounted by this control')
        config = cls.scratch / 'runtime-config.json'
        config.write_text(json.dumps({'version': '1', 'docker': cls.docker, 'image': cls.image,
                                      'auth_file': str(auth), 'clean_runtime_review': 'trusted no-model control only'}))
        token = uuid.uuid4().hex
        cls.egress = {'container': 'po-development-egress-' + token, 'network': 'po-development-net-' + token,
                      'outside_network': 'po-development-out-' + token}
        # The same `start_egress` that `execute` uses, without the Codex preflight.
        cls.runtime = DevelopmentRuntime.__new__(DevelopmentRuntime)
        cls.runtime.config, cls.runtime.egress, cls.runtime.allowlist = load_config(config), 'allowlist', load_allowlist()
        cls.github_ip = socket.gethostbyname('github.com')
        try:
            cls.proxy = cls.runtime.start_egress(cls.egress)
        except BaseException:
            cls.cleanup()
            raise

    @classmethod
    def cleanup(cls):
        errors = []
        for argv in (['rm', '-f', cls.egress['container']], ['network', 'rm', cls.egress['network']],
                     ['network', 'rm', cls.egress['outside_network']]):
            try:
                remove(cls.docker, argv)
            except Exception as error:
                errors.append(str(error))
        shutil.rmtree(cls.scratch, ignore_errors=True)
        if errors:
            raise RuntimeError('egress control cleanup failed: ' + '; '.join(errors))

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()

    def client(self, *command, proxied=True, timeout=120, network=None):
        argv = ['run', '--rm', '--network', network or self.egress['network'], *restrictions(nested_sandbox=True),
                *(proxy_environment(self.proxy) if proxied else []), '--entrypoint', command[0], self.image, *command[1:]]
        return docker_run(self.docker, argv, timeout=timeout)

    def python(self, code, *args, **options):
        return json.loads(self.client('python', '-c', code, *args, **options))

    def log(self):
        lines = docker_run(self.docker, ['logs', self.egress['container']]).splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def connect(self, host, port):
        return self.python(CONNECT_PROBE, host, str(port), self.proxy)['status']

    def tls(self, host, server_name, http_host=None, path='/'):
        return self.python(TLS_PROBE, self.proxy, host, server_name, http_host or server_name, path)

    def test_network_is_internal_without_ipv6_and_a_client_without_the_proxy_has_no_route(self):
        network = json.loads(docker_run(self.docker, ['network', 'inspect', self.egress['network']]))[0]
        self.assertTrue(network['Internal'])
        self.assertFalse(network['EnableIPv6'])
        result = self.python(DIRECT_PROBE, self.github_ip, proxied=False)
        self.assertEqual(result, {'tcp': 'failed', 'tcp_github': 'failed', 'tcp_ipv6': 'failed',
                                  'dns': 'failed', 'dns_github': 'failed', 'global_ipv6': []})

    def test_the_proxy_is_on_its_own_networks_only_and_listens_only_on_its_internal_address(self):
        proxy = json.loads(docker_run(self.docker, ['inspect', self.egress['container']]))[0]
        networks = proxy['NetworkSettings']['Networks']
        self.assertEqual(set(networks), {self.egress['network'], self.egress['outside_network']})
        outside = json.loads(docker_run(self.docker, ['network', 'inspect', self.egress['outside_network']]))[0]
        self.assertFalse(outside['Internal'])
        self.assertFalse(outside['EnableIPv6'])
        listening = [e for e in self.log() if e.get('event') == 'listening']
        self.assertEqual([e['address'] for e in listening], [self.proxy])
        # A container on the default bridge cannot reach it at all, and one on the
        # outside network reaches nothing on the proxy's address there.
        self.assertEqual(self.python(REACH_PROBE, self.proxy, proxied=False, network='bridge'), 'failed')
        self.assertEqual(self.python(REACH_PROBE, networks[self.egress['outside_network']]['IPAddress'],
                                     proxied=False, network=self.egress['outside_network']), 'failed')

    def test_allowed_hosts_connect_and_everything_else_is_refused(self):
        self.assertIn(' 200 ', self.connect('pypi.org', 443))
        self.assertIn(' 200 ', self.connect('files.pythonhosted.org', 443))
        refused = [*((host, 443) for host in GITHUB), ('github.com', 80), ('pypi.org', 22), ('pypi.org', 8443),
                   ('127.0.0.1', 443), ('localhost', 443), ('10.0.0.1', 443), ('172.17.0.1', 80),
                   ('192.168.1.1', 443), ('169.254.169.254', 80), ('1.1.1.1', 443), (self.github_ip, 443)]
        for host, port in refused:
            with self.subTest(host=host, port=port):
                self.assertIn(' 403 ', self.connect(host, port))
        decisions = {(e['host'], e['port']): e['decision'] for e in self.log() if 'decision' in e and e['decision'] != 'connected'}
        for host, port in refused:
            self.assertEqual(decisions[(host, port)], 'refused')

    def test_tls_to_an_allowed_host_works_only_with_its_own_server_name(self):
        good = self.tls('pypi.org', 'pypi.org', path='/simple/six/')
        self.assertEqual(good['tls'], 'established', good)
        self.assertIn(' 200 ', good['status'])
        for host, server_name in (('pypi.org', 'raw.githubusercontent.com'),
                                  ('files.pythonhosted.org', 'raw.githubusercontent.com'),
                                  ('pypi.org', 'github.com'), ('pypi.org', 'files.pythonhosted.org')):
            with self.subTest(host=host, server_name=server_name):
                result = self.tls(host, server_name, path='/SrFlipFlop/principiis-obsta/main/README.md')
                self.assertIn(' 200 ', result['connect'])
                self.assertTrue(result['tls'].startswith('failed'), result)
        reasons = {(e['host'], e.get('sni')): e.get('reason') for e in self.log() if e.get('decision') == 'refused'}
        self.assertEqual(reasons[('pypi.org', 'raw.githubusercontent.com')], 'sni-mismatch')
        self.assertEqual(reasons[('files.pythonhosted.org', 'raw.githubusercontent.com')], 'sni-mismatch')

    # KNOWN OPEN GAP (#75). The proxy sees SNI but not the HTTP Host header inside TLS.
    # pypi.org and files.pythonhosted.org share Fastly with raw.githubusercontent.com,
    # and on 2026-11-27 Fastly served this repository's README for SNI pypi.org with
    # Host raw.githubusercontent.com. Closing it needs TLS termination or a registry
    # gateway at the proxy, or dropping the Fastly hosts. Expected to fail until then;
    # an unexpected success means Fastly stopped serving it (or the hosts moved).
    @unittest.expectedFailure
    def test_host_header_fronting_through_an_allowed_cdn_does_not_reach_github(self):
        for host in ('pypi.org', 'files.pythonhosted.org'):
            result = self.tls(host, host, 'raw.githubusercontent.com', '/SrFlipFlop/principiis-obsta/main/README.md')
            self.assertNotIn(' 200 ', result.get('status', ''), (host, result))

    def test_plain_http_with_a_foreign_host_header_is_refused(self):
        self.assertIn(' 403 ', self.client('python', '-c', PLAIN_HTTP_PROBE, self.proxy, 'raw.githubusercontent.com'))
        refused = [e for e in self.log() if e.get('reason') == 'host-mismatch']
        self.assertTrue(refused)

    def test_proxy_log_holds_only_destinations_and_decisions(self):
        self.client('python', '-c', PLAIN_HTTP_PROBE, self.proxy, 'pypi.org')
        events = self.log()
        self.assertTrue(events)
        for event in events:
            self.assertLessEqual(set(event), LOG_KEYS, event)
        text = json.dumps(events)
        for sentinel in ('secret-path-sentinel', 'query-sentinel', 'header-value-sentinel'):
            self.assertNotIn(sentinel, text)

    def test_registry_installs_work_through_the_allowlist(self):
        pip = self.client('/bin/sh', '-eu', '-c',
                          'python -m venv /tmp/venv && /tmp/venv/bin/pip install --no-cache-dir six==1.16.0 2>&1 | grep -E "Successfully|added|ERROR|error" || true',
                          timeout=240)
        self.assertIn('Successfully installed six-1.16.0', pip)
        hosts = {e['host'] for e in self.log() if e.get('decision') == 'connected'}
        self.assertLessEqual({'pypi.org', 'files.pythonhosted.org'}, hosts)
        if not self.client('/bin/sh', '-c', 'command -v npm || true').strip():
            self.skipTest('pip verified; this image has no npm')
        npm = self.client('/bin/sh', '-eu', '-c',
                          'cd /tmp && npm install --no-audit --no-fund --cache /tmp/npm-cache left-pad@1.3.0 2>&1 | grep -E "Successfully|added|ERROR|error" || true',
                          timeout=240)
        self.assertIn('added 1 package', npm)
        self.assertIn('registry.npmjs.org', {e['host'] for e in self.log() if e.get('decision') == 'connected'})


if __name__ == '__main__':
    unittest.main()
