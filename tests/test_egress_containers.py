"""Opt-in, model-free, credential-free control of the real egress network and proxy (#75).

Starts the internal Docker network and proxy sidecar through `DevelopmentRuntime.start_egress`,
exactly as `execute` does, then probes them from client containers that run in the same
network with the same restrictions as the agent container. No auth file is mounted, no
model is called. Needs Docker, the pinned image and outbound internet from the host.

    PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=/var/tmp/po-scratch PO_EGRESS_CONTROL=1 \
        python3 -m unittest tests.test_egress_containers
"""
import json
import os
from pathlib import Path
import shutil
import unittest
import uuid

from support import temporary_directory
from principiis.development_runtime import (DevelopmentRuntime, docker_run,
                                            proxy_environment, remove, restrictions)

# Executed inside a client container; prints one JSON result.
CONNECT_PROBE = r'''
import json, socket, sys
host, port = sys.argv[1], int(sys.argv[2])
sock = socket.create_connection((sys.argv[3], 3128), timeout=15)
sock.sendall(f'CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n'.encode())
print(json.dumps({'status': sock.recv(4096).split(b'\r\n')[0].decode()}))
'''
DIRECT_PROBE = r'''
import json, socket
result = {}
try:
    socket.create_connection(('1.1.1.1', 443), timeout=5).close()
    result['tcp'] = 'connected'
except OSError as error:
    result['tcp'] = 'failed'
try:
    socket.getaddrinfo('pypi.org', 443)
    result['dns'] = 'resolved'
except OSError:
    result['dns'] = 'failed'
print(json.dumps(result))
'''
PLAIN_HTTP_PROBE = r'''
import socket, sys
sock = socket.create_connection((sys.argv[1], 3128), timeout=15)
sock.sendall(b'GET http://pypi.org/secret-path-sentinel?q=query-sentinel HTTP/1.1\r\nHost: pypi.org\r\n'
             b'X-Header-Sentinel: header-value-sentinel\r\nConnection: close\r\n\r\n')
print(sock.recv(4096).split(b'\r\n')[0].decode())
'''
LOG_KEYS = {'method', 'host', 'port', 'decision', 'time', 'event', 'mode', 'allowlist', 'error'}


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
        cls.egress = {'container': 'po-development-egress-' + token, 'network': 'po-development-net-' + token}
        cls.runtime = DevelopmentRuntime(config, cls.scratch / 'output', cls.scratch / 'source')
        try:
            cls.proxy = cls.runtime.start_egress(cls.egress)
        except BaseException:
            cls.cleanup()
            raise

    @classmethod
    def cleanup(cls):
        errors = []
        for argv in (['rm', '-f', cls.egress['container']], ['network', 'rm', cls.egress['network']]):
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

    def client(self, *command, proxied=True, timeout=120):
        argv = ['run', '--rm', '--network', self.egress['network'], *restrictions(nested_sandbox=True),
                *(proxy_environment(self.proxy) if proxied else []), '--entrypoint', command[0], self.image, *command[1:]]
        return docker_run(self.docker, argv, timeout=timeout)

    def python(self, code, *args, **options):
        return self.client('python', '-c', code, *args, **options)

    def log(self):
        lines = docker_run(self.docker, ['logs', self.egress['container']]).splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def connect(self, host, port):
        return json.loads(self.python(CONNECT_PROBE, host, str(port), self.proxy))['status']

    def test_network_is_internal_and_a_client_without_the_proxy_has_no_route(self):
        network = json.loads(docker_run(self.docker, ['network', 'inspect', self.egress['network']]))[0]
        self.assertTrue(network['Internal'])
        self.assertEqual(json.loads(self.python(DIRECT_PROBE, proxied=False)), {'tcp': 'failed', 'dns': 'failed'})

    def test_allowed_hosts_connect_and_everything_else_is_refused(self):
        self.assertIn(' 200 ', self.connect('pypi.org', 443))
        self.assertIn(' 200 ', self.connect('files.pythonhosted.org', 443))
        refused = [('github.com', 443), ('pypi.org', 22), ('pypi.org', 8443), ('127.0.0.1', 443),
                   ('localhost', 443), ('10.0.0.1', 443), ('172.17.0.1', 80), ('192.168.1.1', 443),
                   ('169.254.169.254', 80), ('1.1.1.1', 443)]
        for host, port in refused:
            with self.subTest(host=host, port=port):
                self.assertIn(' 403 ', self.connect(host, port))
        decisions = {(e['host'], e['port']): e['decision'] for e in self.log() if 'decision' in e and e['decision'] != 'connected'}
        for host, port in refused:
            self.assertEqual(decisions[(host, port)], 'refused')

    def test_proxy_log_holds_only_destinations_and_decisions(self):
        self.assertIn(' ', self.python(PLAIN_HTTP_PROBE, self.proxy))
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
        npm = self.client('/bin/sh', '-eu', '-c',
                          'cd /tmp && npm install --no-audit --no-fund --cache /tmp/npm-cache left-pad@1.3.0 2>&1 | grep -E "Successfully|added|ERROR|error" || true',
                          timeout=240)
        self.assertIn('added 1 package', npm)
        hosts = {e['host'] for e in self.log() if e.get('decision') == 'connected'}
        self.assertLessEqual({'pypi.org', 'files.pythonhosted.org', 'registry.npmjs.org'}, hosts)


if __name__ == '__main__':
    unittest.main()
