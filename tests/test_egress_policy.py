import base64
import contextlib
import io
import json
from pathlib import Path
import socket
import ssl
import threading
import unittest
from unittest.mock import patch

from support import temporary_directory
from principiis import egress_proxy
from principiis.development_runtime import load_allowlist
from principiis.egress_proxy import MODEL_PROVIDER, allowed, client_hello, credential, model_provider, never_allowed, unsafe_entry


ALLOWLIST = ['registry.npmjs.org', '*.nuget.org', 'docs.example.net']


class EgressPolicyTests(unittest.TestCase):
    def test_allowlist_mode_admits_listed_hosts_on_web_ports(self):
        for host, port in (('registry.npmjs.org', 443), ('Registry.NPMjs.org.', 443), ('api.nuget.org', 443),
                           ('docs.example.net', 80)):
            self.assertTrue(allowed(host, port, 'allowlist', ALLOWLIST), (host, port))

    def test_allowlist_mode_refuses_everything_else(self):
        for host, port in (('github.com', 443), ('registry.npmjs.org.attacker.example', 443),
                           ('evilregistry.npmjs.org', 443), ('nuget.org', 443), ('registry.npmjs.org', 22),
                           ('140.82.112.3', 443), ('', 443), ('registry.npmjs.org\r\nX: y', 443)):
            self.assertFalse(allowed(host, port, 'allowlist', ALLOWLIST), (host, port))

    def test_log_mode_admits_ordinary_destinations_on_any_port(self):
        self.assertTrue(allowed('registry.npmjs.org', 443, 'log', []))
        self.assertTrue(allowed('docs.python.org', 8443, 'log', []))
        self.assertTrue(allowed('140.82.112.3', 22, 'log', []))  # addresses are checked after resolution
        self.assertFalse(allowed('bad host', 443, 'log', []))

    def test_log_mode_refuses_github_its_mirrors_and_gateway_only_hosts(self):
        # The measurement must never reach GitHub, directly or by Host fronting through Fastly.
        for host in (*GITHUB, 'pypi.org', 'files.pythonhosted.org', 'test.pypi.org', 'Raw.GitHubUserContent.com.'):
            with self.subTest(host=host):
                self.assertFalse(allowed(host, 443, 'log', []))
                self.assertFalse(allowed(host, 443, 'log', [host], [host], credential=True))

    def test_unknown_mode_refuses(self):
        self.assertFalse(allowed('registry.npmjs.org', 443, 'open', ALLOWLIST))


def hello(server_hostname):
    """The first bytes an ordinary TLS client sends, with or without SNI."""
    context = ssl.create_default_context()
    if server_hostname is None:
        context.check_hostname = False
    incoming, outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
    tls = context.wrap_bio(incoming, outgoing, server_hostname=server_hostname)
    try:
        tls.do_handshake()
    except ssl.SSLWantReadError:
        pass
    return outgoing.read()


GITHUB = ('github.com', 'api.github.com', 'codeload.github.com', 'gist.github.com', 'raw.githubusercontent.com',
          'objects.githubusercontent.com', 'avatars.githubusercontent.com', 'githubusercontent.com', 'pages.github.io',
          'github.io', 'github.githubassets.com', 'ghcr.io', 'pkg-containers.ghcr.io', 'github.dev',
          'api.githubcopilot.com', 'githubapp.com', 'proxy.golang.org', 'goproxy.io', 'goproxy.cn',
          'cdn.jsdelivr.net', 'raw.githack.com', 'cdn.statically.io', 'gitpod.io', 'sourcegraph.com',
          'gitee.com', 'web.archive.org', 'archive.org', 'archive.softwareheritage.org', 'gitlab.com',
          'bitbucket.org', 'codeberg.org')


class NeverAllowTests(unittest.TestCase):
    def test_github_and_its_mirrors_are_never_allowed(self):
        for host in GITHUB:
            self.assertTrue(never_allowed(host), host)
        for host in ('pypi.org', 'sum.golang.org', 'golang.org', 'registry.npmjs.org', 'notgithub.com',
                     'github.com.example', 'api.openai.com'):
            self.assertFalse(never_allowed(host), host)

    def test_the_proxy_refuses_them_even_when_listed(self):
        for host in GITHUB:
            self.assertFalse(allowed(host, 443, 'allowlist', [host, '*.' + host]), host)

    def test_entries_that_name_or_cover_them_or_are_too_broad_are_unsafe(self):
        for entry in ('raw.githubusercontent.com', '*.githubusercontent.com', '*.github.com', '*.golang.org',
                      '*.archive.org', '*.io', '*.com', '*.org', '*', '*.dev', 'proxy.golang.org'):
            self.assertTrue(unsafe_entry(entry), entry)
        for entry in ('registry.npmjs.org', '*.nuget.org', 'sum.golang.org', '*.npmjs.org'):
            self.assertIsNone(unsafe_entry(entry), entry)

    def test_the_proxy_ignores_unsafe_wildcards(self):
        self.assertFalse(allowed('example.com', 443, 'allowlist', ['*.com']))
        self.assertTrue(allowed('api.nuget.org', 443, 'allowlist', ['*.com', '*.nuget.org']))


class AllowlistLoaderTests(unittest.TestCase):
    def load(self, domains, model_domains=('chatgpt.com',)):
        with temporary_directory() as directory:
            path = Path(directory) / 'allowlist.json'
            path.write_text(json.dumps({'version': '1', 'domains': domains, 'model_domains': list(model_domains)}))
            return load_allowlist(path)

    def test_loader_refuses_github_mirrors_and_broad_wildcards(self):
        for entry in ('github.com', 'raw.githubusercontent.com', '*.githubusercontent.com', '*.golang.org',
                      'cdn.jsdelivr.net', 'gitlab.com', '*.org', '*.com', '*'):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, 'never|broad|domain'):
                self.load(['registry.npmjs.org', entry])

    def test_loader_accepts_ordinary_registries(self):
        self.assertEqual(self.load(['registry.npmjs.org', '*.nuget.org', 'sum.golang.org']),
                         {'domains': ['registry.npmjs.org', '*.nuget.org', 'sum.golang.org'],
                          'model_domains': ['chatgpt.com']})

    def test_loader_applies_the_never_allow_list_to_model_domains_too(self):
        for entry in ('github.com', 'raw.githubusercontent.com', 'gitlab.com', 'cdn.jsdelivr.net', '10.0.0.1'):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, 'model domain .* is refused'):
                self.load(['registry.npmjs.org'], ['chatgpt.com', entry])

    def test_the_proxy_refuses_never_allowed_model_domains_even_with_the_credential(self):
        self.assertFalse(allowed('raw.githubusercontent.com', 443, 'allowlist', [], ['raw.githubusercontent.com'],
                                 credential=True))
        self.assertFalse(allowed('github.com', 443, 'allowlist', [], ['github.com'], credential=True))


def synthetic_hello(*extensions, record=16384):
    """A minimal ClientHello with the given (type, value) extensions, split into records of `record` bytes."""
    def vector(width, data):
        return len(data).to_bytes(width, 'big') + data
    body = (b'\x03\x03' + bytes(32) + vector(1, b'') + vector(2, b'\x13\x01') + vector(1, b'\x00')
            + vector(2, b''.join(kind.to_bytes(2, 'big') + vector(2, value) for kind, value in extensions)))
    message = b'\x01' + vector(3, body)
    return b''.join(b'\x16\x03\x01' + vector(2, message[i:i + record]) for i in range(0, len(message), record))


def server_name(host):
    name = b'\x00' + len(host).to_bytes(2, 'big') + host
    return 0, len(name).to_bytes(2, 'big') + name


class ClientHelloTests(unittest.TestCase):
    def test_encrypted_client_hello_is_reported(self):
        self.assertEqual(client_hello(synthetic_hello(server_name(b'pypi.org'), (0xfe0d, b'\x00'))),
                         {'sni': 'pypi.org', 'ech': True})

    def test_a_hello_split_across_records_is_reassembled(self):
        self.assertEqual(client_hello(synthetic_hello(server_name(b'pypi.org'), record=7))['sni'], 'pypi.org')

    def test_duplicate_extensions_are_rejected(self):
        with self.assertRaises(ValueError):
            client_hello(synthetic_hello(server_name(b'pypi.org'), server_name(b'github.com')))

    def test_reads_the_server_name_of_a_real_client_hello(self):
        self.assertEqual(client_hello(hello('Raw.GitHubUserContent.com'))['sni'], 'raw.githubusercontent.com')
        self.assertEqual(client_hello(hello('pypi.org')), {'sni': 'pypi.org', 'ech': False})

    def test_no_server_name(self):
        self.assertIsNone(client_hello(hello(None))['sni'])

    def test_rejects_anything_else(self):
        data = hello('pypi.org')
        for value in (b'GET / HTTP/1.1\r\nHost: pypi.org\r\n\r\n', b'', b'\x16\x03\x01\x00', data[:40],
                      b'\x17' + data[1:]):
            with self.assertRaises(ValueError):
                client_hello(value)


class Upstream:
    """A stand-in for the remote server: records what the proxy forwarded."""
    def __init__(self):
        self.received = b''
        self.connections = []

    def connect(self, address, timeout=None):
        self.connections.append(address)
        proxy_side, server_side = socket.socketpair()

        def drain():
            while data := server_side.recv(65536):
                self.received += data
            server_side.close()
        self.thread = threading.Thread(target=drain, daemon=True)
        self.thread.start()
        return proxy_side


PUBLIC = '104.16.1.34'  # what a public name resolves to in these tests: no DNS lookup


class HandleTests(unittest.TestCase):
    def exchange(self, mode, head, payload=b'', policy=None, token='', addresses=(PUBLIC,)):
        policy = policy or {'domains': ['registry.npmjs.org'], 'model_domains': []}
        upstream, events = Upstream(), []
        client, proxy_side = socket.socketpair()
        with patch.object(egress_proxy.socket, 'create_connection', upstream.connect), \
                patch.object(egress_proxy, 'resolve', lambda name, port: list(addresses)), \
                patch.object(egress_proxy, 'log', lambda **event: events.append(event)):
            worker = threading.Thread(target=egress_proxy.handle, args=(proxy_side, mode, policy, token))
            worker.start()
            client.sendall(head)
            reply = b''
            if head.startswith(b'CONNECT'):
                while b'\r\n\r\n' not in reply:
                    reply += client.recv(4096)
            try:
                client.sendall(payload)
                client.shutdown(socket.SHUT_WR)
            except OSError:  # a refusal closes the connection after its 403
                pass
            client.settimeout(10)
            while data := client.recv(65536):
                reply += data
            worker.join(10)
            client.close()
        if upstream.connections:
            upstream.thread.join(10)
        return reply, upstream.received, events

    CONNECT = b'CONNECT registry.npmjs.org:443 HTTP/1.1\r\nHost: registry.npmjs.org:443\r\n\r\n'

    def test_a_tunnel_whose_sni_names_another_host_is_closed_before_any_byte_is_forwarded(self):
        for name, reason in (('raw.githubusercontent.com', 'sni-mismatch'), (None, 'no-sni')):
            with self.subTest(sni=name):
                reply, forwarded, events = self.exchange('allowlist', self.CONNECT, hello(name))
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual(refused[-1]['reason'], reason)

    def test_a_tunnel_offering_encrypted_client_hello_is_closed(self):
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT,
                                                 synthetic_hello(server_name(b'registry.npmjs.org'), (0xfe0d, b'\x00')))
        self.assertEqual(forwarded, b'')
        self.assertEqual([e for e in events if e.get('decision') == 'refused'][-1]['reason'], 'ech')

    def test_a_tunnel_that_is_not_tls_is_closed(self):
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT,
                                                 b'GET / HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n')
        self.assertEqual(forwarded, b'')
        self.assertEqual([e for e in events if e.get('decision') == 'refused'][-1]['reason'], 'not-tls')

    def test_a_tunnel_with_the_matching_sni_forwards_the_hello_unchanged(self):
        data = hello('registry.npmjs.org')
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT, data + b'rest')
        self.assertIn(b' 200 ', reply)
        self.assertEqual(forwarded, data + b'rest')
        self.assertIn('registry.npmjs.org', [e.get('sni') for e in events])

    def test_log_mode_forwards_a_mismatch_and_records_the_sni(self):
        data = hello('raw.githubusercontent.com')
        reply, forwarded, events = self.exchange('log', self.CONNECT, data)
        self.assertEqual(forwarded, data)
        self.assertIn('raw.githubusercontent.com', [e.get('sni') for e in events])

    def test_log_mode_refuses_a_tunnel_to_gateway_only_and_never_allowed_hosts_and_logs_it(self):
        for host, reason in (('pypi.org', 'gateway-only host: use the PyPI gateway'),
                             ('files.pythonhosted.org', 'gateway-only host: use the PyPI gateway'),
                             ('raw.githubusercontent.com', 'never-allowed host'), ('github.com', 'never-allowed host'),
                             ('cdn.jsdelivr.net', 'never-allowed host')):
            with self.subTest(host=host):
                head = f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode()
                reply, forwarded, events = self.exchange('log', head, hello(host))
                self.assertIn(b' 403 ', reply)
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual([(e['host'], e['port']) for e in refused], [(host, 443)])
                self.assertTrue(refused[0]['reason'].startswith(reason), refused[0])
                self.assertNotIn('connected', [e.get('decision') for e in events])

    def test_log_mode_refuses_plain_http_to_them_too(self):
        reply, forwarded, events = self.exchange(
            'log', b'GET http://raw.githubusercontent.com/SrFlipFlop/x HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n')
        self.assertIn(b' 403 ', reply)
        self.assertEqual(forwarded, b'')

    def test_log_mode_refuses_destinations_that_resolve_to_non_public_addresses(self):
        for addresses in (['127.0.0.1'], ['10.0.0.1'], ['172.17.0.1'], ['192.168.65.254'], ['169.254.169.254'],
                          ['100.100.100.200'], ['0.0.0.0'], ['::1'], ['fe80::1%eth0'], ['fd00::1'],
                          ['::ffff:127.0.0.1'], ['224.0.0.1'], [PUBLIC, '10.0.0.1'], []):
            with self.subTest(addresses=addresses):
                reply, forwarded, events = self.exchange('log', self.CONNECT, hello('registry.npmjs.org'),
                                                         addresses=addresses)
                self.assertIn(b' 403 ', reply)
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual(refused[-1]['reason'], 'non-public address')
                self.assertEqual(refused[-1]['host'], 'registry.npmjs.org')
                self.assertNotIn('connected', [e.get('decision') for e in events])

    def test_log_mode_resolves_literal_and_odd_forms_of_private_addresses_itself(self):
        # Real resolution, all local: literals and the shorthand forms getaddrinfo accepts.
        for host in ('127.0.0.1', '169.254.169.254', '10.0.0.1', 'localhost', '2130706433', '127.1'):
            with self.subTest(host=host):
                upstream = Upstream()
                with patch.object(egress_proxy.socket, 'create_connection', upstream.connect):
                    reply, events = ModelCredentialTests.request(
                        self, f'CONNECT {host}:443 HTTP/1.1\r\n\r\n', mode='log', policy={'domains': [], 'model_domains': []})
                self.assertEqual(upstream.connections, [])
                self.assertNotIn(b' 200 ', reply)
                self.assertEqual([e.get('reason') for e in events if e.get('decision') == 'refused'], ['non-public address'])

    def test_log_mode_connects_to_the_address_it_checked(self):
        upstream = Upstream()
        with patch.object(egress_proxy.socket, 'create_connection', upstream.connect), \
                patch.object(egress_proxy, 'resolve', lambda name, port: [PUBLIC]), \
                patch.object(egress_proxy, 'log', lambda **event: None):
            client, proxy_side = socket.socketpair()
            worker = threading.Thread(target=egress_proxy.handle, args=(proxy_side, 'log', {}, ''))
            worker.start()
            client.sendall(self.CONNECT)
            client.recv(4096)
            client.close()
            worker.join(10)
        self.assertEqual(upstream.connections, [(PUBLIC, 443)])

    def test_plain_http_whose_host_header_names_another_host_is_refused(self):
        for host in (b'raw.githubusercontent.com', b'registry.npmjs.org\r\nHost: github.com', None):
            with self.subTest(host=host):
                header = b'Host: ' + host + b'\r\n' if host else b''
                reply, forwarded, events = self.exchange(
                    'allowlist', b'GET http://registry.npmjs.org/six HTTP/1.1\r\n' + header + b'\r\n')
                self.assertIn(b' 403 ', reply)
                self.assertEqual(forwarded, b'')

    def test_plain_http_forwards_one_request_and_nothing_after_it(self):
        smuggled = b'GET /x HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n'
        reply, forwarded, events = self.exchange(
            'allowlist', b'POST http://registry.npmjs.org/six HTTP/1.1\r\nHost: registry.npmjs.org:80\r\nContent-Length: 2\r\n'
                         b'Connection: keep-alive\r\n\r\nok' + smuggled)
        self.assertTrue(forwarded.startswith(b'POST /six HTTP/1.1\r\n'), forwarded)
        self.assertTrue(forwarded.endswith(b'\r\n\r\nok'), forwarded)
        self.assertIn(b'Connection: close', forwarded)
        self.assertNotIn(b'keep-alive', forwarded)
        self.assertNotIn(b'githubusercontent', forwarded)


TOKEN = 'per-run-model-token-0123456789abcdef'
POLICY = {'domains': ['registry.npmjs.org'], 'model_domains': ['chatgpt.com', 'api.openai.com']}


def basic(user, password):
    return 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()


class ModelCredentialTests(unittest.TestCase):
    """Model hosts are reachable only by the Codex process, which alone holds the per-run proxy token."""

    def test_credential_is_valid_only_for_the_model_user_and_this_runs_token(self):
        self.assertEqual(credential([f'Proxy-Authorization: {basic("model", TOKEN)}'], TOKEN), 'valid')
        self.assertEqual(credential([f'proxy-authorization:{basic("model", TOKEN)}'], TOKEN), 'valid')
        for header in (basic('model', 'wrong'), basic('other', TOKEN), 'Bearer ' + TOKEN, 'Basic !!!', basic('model', '')):
            self.assertEqual(credential(['Proxy-Authorization: ' + header], TOKEN), 'invalid', header)
        self.assertEqual(credential(['Host: chatgpt.com:443'], TOKEN), 'absent')
        # Without a configured token nothing is ever valid.
        self.assertEqual(credential([f'Proxy-Authorization: {basic("model", "")}'], ''), 'invalid')

    def test_model_hosts_need_the_credential_even_if_also_listed_as_ordinary_domains(self):
        for host in ('chatgpt.com', 'api.openai.com', 'API.OpenAI.com.'):
            self.assertFalse(allowed(host, 443, 'allowlist', POLICY['domains'], POLICY['model_domains']), host)
            self.assertTrue(allowed(host, 443, 'allowlist', POLICY['domains'], POLICY['model_domains'], credential=True), host)
        self.assertFalse(allowed('chatgpt.com', 443, 'allowlist', ['chatgpt.com'], ['chatgpt.com']))
        self.assertFalse(allowed('chatgpt.com', 22, 'allowlist', [], ['chatgpt.com'], credential=True))
        # The credential never widens the ordinary allowlist.
        self.assertFalse(allowed('github.com', 443, 'allowlist', POLICY['domains'], POLICY['model_domains'], credential=True))
        self.assertTrue(allowed('registry.npmjs.org', 443, 'allowlist', POLICY['domains'], POLICY['model_domains']))

    def request(self, head, *, policy=POLICY, mode='allowlist', token=TOKEN):
        """Drive one proxy connection over a socket pair; return (reply, log events)."""
        ours, theirs = socket.socketpair()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            worker = threading.Thread(target=egress_proxy.handle, args=(theirs, mode, policy, token))
            worker.start()
            ours.sendall(head.encode())
            reply = ours.recv(4096)
            ours.close()
            worker.join(5)
        return reply, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_command_without_the_credential_gets_403_and_the_refusal_says_why(self):
        reply, events = self.request('CONNECT chatgpt.com:443 HTTP/1.1\r\nHost: chatgpt.com:443\r\n\r\n')
        self.assertIn(b' 403 ', reply)
        self.assertEqual(events[0]['decision'], 'refused')
        self.assertEqual(events[0]['credential'], 'absent')
        self.assertEqual(events[0]['reason'], 'model host without the model credential')
        reply, events = self.request('CONNECT api.openai.com:443 HTTP/1.1\r\n'
                                     f'Proxy-Authorization: {basic("model", "guess")}\r\n\r\n')
        self.assertIn(b' 403 ', reply)
        self.assertEqual((events[0]['decision'], events[0]['credential']), ('refused', 'invalid'))

    def test_the_credential_opens_model_hosts_and_is_never_logged_or_forwarded(self):
        sent = []

        class Upstream:
            def settimeout(self, value): pass
            def sendall(self, data): sent.append(data)
            def recv(self, size): return b''
            def shutdown(self, how): pass
            def close(self): pass

        head = (f'GET http://chatgpt.com/backend-api HTTP/1.1\r\nHost: chatgpt.com\r\n'
                f'Proxy-Authorization: {basic("model", TOKEN)}\r\nConnection: close\r\n\r\n')
        with patch.object(egress_proxy.socket, 'create_connection', return_value=Upstream()) as connect:
            reply, events = self.request(head)
        connect.assert_called_once_with(('chatgpt.com', 80), timeout=30)
        self.assertEqual([e['decision'] for e in events if 'decision' in e], ['allowed', 'connected'])
        self.assertEqual(events[0]['credential'], 'valid')
        forwarded = b''.join(sent).decode()
        self.assertNotIn('Proxy-Authorization', forwarded)
        encoded = base64.b64encode(f'model:{TOKEN}'.encode()).decode()
        for secret in (TOKEN, encoded):
            self.assertNotIn(secret, forwarded)
            self.assertNotIn(secret, json.dumps(events))

    def test_log_mode_forwards_everything_but_records_whether_the_credential_came(self):
        with patch.object(egress_proxy.socket, 'create_connection', side_effect=OSError('no route in test')), \
                patch.object(egress_proxy, 'resolve', lambda name, port: [PUBLIC]):
            reply, events = self.request('CONNECT registry.npmjs.org:443 HTTP/1.1\r\n\r\n', mode='log')
        self.assertIn(b' 502 ', reply)
        self.assertEqual((events[0]['decision'], events[0]['credential']), ('allowed', 'absent'))


class CredentialedTunnelTests(unittest.TestCase):
    """The model credential is checked at CONNECT; the SNI check still applies after it."""
    MODEL = {'domains': ['registry.npmjs.org'], 'model_domains': ['chatgpt.com']}
    exchange = HandleTests.exchange

    def connect(self, credential_header=True):
        auth = f'Proxy-Authorization: {basic("model", TOKEN)}\r\n' if credential_header else ''
        return ('CONNECT chatgpt.com:443 HTTP/1.1\r\nHost: chatgpt.com:443\r\n' + auth + '\r\n').encode()

    def test_a_credentialed_tunnel_whose_sni_names_another_host_is_closed(self):
        for name, reason in (('raw.githubusercontent.com', 'sni-mismatch'), ('pypi.org', 'sni-mismatch'),
                             (None, 'no-sni')):
            with self.subTest(sni=name):
                reply, forwarded, events = self.exchange('allowlist', self.connect(), hello(name),
                                                         policy=self.MODEL, token=TOKEN)
                self.assertIn(b' 200 ', reply)
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual((refused[-1]['reason'], refused[-1]['credential']), (reason, 'valid'))

    def test_a_credentialed_tunnel_with_the_matching_sni_is_forwarded(self):
        data = hello('chatgpt.com')
        reply, forwarded, events = self.exchange('allowlist', self.connect(), data, policy=self.MODEL, token=TOKEN)
        self.assertEqual(forwarded, data)
        self.assertEqual(events[0]['credential'], 'valid')
        self.assertIn('chatgpt.com', [e.get('sni') for e in events if e.get('event') == 'tls'])
        self.assertNotIn(TOKEN, json.dumps(events))


class GatewayOnlyTests(unittest.TestCase):
    """PyPI shares Fastly with raw.githubusercontent.com: a tunnel to it can front GitHub with
    the Host header inside TLS. It is reached only through the proxy's PyPI gateway."""

    def test_pypi_hosts_and_wildcards_covering_them_are_unsafe_entries(self):
        for entry in ('pypi.org', 'files.pythonhosted.org', '*.pythonhosted.org', '*.pypi.org', 'test.pypi.org',
                      'pythonhosted.org'):
            with self.subTest(entry=entry):
                self.assertIn('gateway', unsafe_entry(entry) or '')
                self.assertIn('Fastly', unsafe_entry(entry) or '')

    def test_the_loader_refuses_them_in_domains_and_model_domains(self):
        for entry in ('pypi.org', 'files.pythonhosted.org', '*.pythonhosted.org'):
            with self.subTest(entry=entry):
                with self.assertRaisesRegex(ValueError, 'gateway'):
                    AllowlistLoaderTests.load(self, ['registry.npmjs.org', entry])
                if not entry.startswith('*.'):  # model domains refuse every wildcard anyway
                    with self.assertRaisesRegex(ValueError, 'gateway'):
                        AllowlistLoaderTests.load(self, ['registry.npmjs.org'], ['chatgpt.com', entry])

    def test_the_proxy_never_tunnels_to_them_even_when_listed(self):
        for host in ('pypi.org', 'files.pythonhosted.org'):
            self.assertFalse(allowed(host, 443, 'allowlist', [host, '*.pythonhosted.org']), host)
            self.assertFalse(allowed(host, 443, 'allowlist', [], [host], credential=True), host)

    def test_the_gateway_only_hosts_are_kept_in_one_place(self):
        self.assertEqual(set(egress_proxy.GATEWAY_UPSTREAMS), {'pypi.org', 'files.pythonhosted.org'})
        for host in egress_proxy.GATEWAY_UPSTREAMS:
            self.assertTrue(egress_proxy.gateway_only(host), host)
        self.assertFalse(egress_proxy.gateway_only('registry.npmjs.org'))

    def test_a_tunnel_to_pypi_gets_403_and_says_to_use_the_gateway(self):
        with patch.object(egress_proxy.socket, 'create_connection', side_effect=AssertionError('no tunnel')):
            reply, events = ModelCredentialTests.request(
                self, 'CONNECT pypi.org:443 HTTP/1.1\r\nHost: pypi.org:443\r\n\r\n',
                policy={'domains': ['pypi.org', 'registry.npmjs.org'], 'model_domains': []})
        self.assertIn(b' 403 ', reply)
        self.assertIn('gateway', [e for e in events if e.get('decision') == 'refused'][-1]['reason'])

    def test_never_allowed_refusals_say_why_in_allowlist_mode_too(self):
        with patch.object(egress_proxy.socket, 'create_connection', side_effect=AssertionError('no tunnel')):
            reply, events = ModelCredentialTests.request(
                self, 'CONNECT github.com:443 HTTP/1.1\r\n\r\n', policy={'domains': ['github.com'], 'model_domains': []})
        self.assertIn(b' 403 ', reply)
        self.assertTrue(events[0]['reason'].startswith('never-allowed host'), events)

    def test_the_shipped_allowlist_has_no_gateway_only_host(self):
        domains = load_allowlist()['domains']
        self.assertNotIn('pypi.org', domains)
        self.assertNotIn('files.pythonhosted.org', domains)


HASH = 'ab/cd/' + 'e' * 60
WHEEL = f'/pypi/files/packages/{HASH}/six-1.16.0-py2.py3-none-any.whl'
JSON_TYPE = 'application/vnd.pypi.simple.v1+json'


class GatewayRouteTests(unittest.TestCase):
    def test_simple_index_paths_are_normalised_to_pypi(self):
        for target, path in (('/pypi/simple/six/', '/simple/six/'), ('/pypi/simple/six', '/simple/six/'),
                             ('/pypi/simple/Zope.Interface/', '/simple/zope-interface/'),
                             ('/pypi/simple/typing_extensions/', '/simple/typing-extensions/'),
                             ('/pypi/simple/a/', '/simple/a/')):
            with self.subTest(target=target):
                self.assertEqual(egress_proxy.gateway_route('GET', target), ('simple', 'pypi.org', path))

    def test_file_paths_go_to_files_pythonhosted_org_unchanged(self):
        for name in ('six-1.16.0-py2.py3-none-any.whl', 'six-1.16.0.tar.gz', 'six-1.16.0-py2.py3-none-any.whl.metadata',
                     'Flask-3.0.0.zip', 'pkg-1.0.tar.bz2'):
            target = f'/pypi/files/packages/{HASH}/{name}'
            with self.subTest(name=name):
                self.assertEqual(egress_proxy.gateway_route('GET', target),
                                 ('files', 'files.pythonhosted.org', f'/packages/{HASH}/{name}'))

    def test_everything_else_is_refused(self):
        refused = ['/pypi/simple/', '/pypi/simple/../', '/pypi/simple/six/../../x/', '/pypi/simple/..',
                   '/pypi/simple/six/?q=1', '/pypi/simple/six/#x', '/pypi/simple/%2e%2e/', '/pypi/simple/six%2F/',
                   '/pypi/simple/-six/', '/pypi/simple/six/extra/', '/pypi/simple/' + 'a' * 300 + '/',
                   '/pypi/files/packages/../../x', '/pypi/files/packages/' + HASH + '/../six.whl',
                   '/pypi/files/packages/' + HASH + '/README.md', '/pypi/files/packages/' + HASH + '/.whl',
                   '/pypi/files/packages/ab/cd/short/six-1.16.0.tar.gz', '/pypi/files/packages/AB/cd/' + 'e' * 60 + '/x.whl',
                   '/pypi/files/SrFlipFlop/principiis-obsta/main/README.md', WHEEL + '?x=1', WHEEL + '/',
                   '/pypi/pypi/six/json', '/pypi/', '/simple/six/', '/', '', 'six', '//pypi/simple/six/',
                   '/pypi/simple/six/\\', '/pypi/simple/si x/']
        for target in refused:
            with self.subTest(target=target), self.assertRaises(egress_proxy.Refused):
                egress_proxy.gateway_route('GET', target)
        for method in ('POST', 'PUT', 'HEAD', 'DELETE', 'CONNECT', 'OPTIONS'):
            with self.subTest(method=method), self.assertRaises(egress_proxy.Refused):
                egress_proxy.gateway_route(method, '/pypi/simple/six/')

    def test_only_simple_api_media_types_are_forwarded_in_accept(self):
        pip = 'application/vnd.pypi.simple.v1+json, application/vnd.pypi.simple.v1+html; q=0.1, text/html; q=0.01'
        self.assertEqual(egress_proxy.gateway_accept(pip), pip)
        self.assertEqual(egress_proxy.gateway_accept('text/html'), 'text/html')
        for value in (None, '', '*/*', 'application/json', 'text/html, application/x-evil',
                      'text/html; charset=x\r\nHost: raw.githubusercontent.com', 'text/html;q=1;evil=1'):
            with self.subTest(value=value):
                self.assertEqual(egress_proxy.gateway_accept(value), egress_proxy.DEFAULT_ACCEPT)


class GatewayRewriteTests(unittest.TestCase):
    FILE = 'https://files.pythonhosted.org/packages/' + HASH + '/six-1.16.0-py2.py3-none-any.whl'

    def test_html_hrefs_point_at_the_gateway_and_keep_their_hash(self):
        body = (f'<a href="{self.FILE}#sha256={"0" * 64}" data-requires-python="&gt;=2.7" '
                f'data-dist-info-metadata="sha256={"1" * 64}">six</a>\n'
                '<a href="https://raw.githubusercontent.com/x/y/main/z.whl#sha256=00">bad</a>').encode()
        out = egress_proxy.rewrite_index(body, 'application/vnd.pypi.simple.v1+html').decode()
        self.assertIn(f'href="/pypi/files/packages/{HASH}/six-1.16.0-py2.py3-none-any.whl#sha256={"0" * 64}"', out)
        self.assertIn('data-dist-info-metadata="sha256=' + '1' * 64, out)
        self.assertNotIn('files.pythonhosted.org', out)
        self.assertNotIn('githubusercontent', out)

    def test_json_urls_point_at_the_gateway_and_hashes_are_kept(self):
        document = {'meta': {'api-version': '1.1'}, 'name': 'six', 'versions': ['1.16.0'],
                    'files': [{'filename': 'six-1.16.0-py2.py3-none-any.whl', 'url': self.FILE,
                               'hashes': {'sha256': '0' * 64}, 'core-metadata': {'sha256': '1' * 64}},
                              {'filename': 'evil.whl', 'url': 'https://raw.githubusercontent.com/x/y/main/evil.whl',
                               'hashes': {'sha256': '2' * 64}}]}
        out = json.loads(egress_proxy.rewrite_index(json.dumps(document).encode(), JSON_TYPE))
        self.assertEqual([f['url'] for f in out['files']],
                         [f'/pypi/files/packages/{HASH}/six-1.16.0-py2.py3-none-any.whl'])
        self.assertEqual(out['files'][0]['hashes'], {'sha256': '0' * 64})
        self.assertEqual(out['files'][0]['core-metadata'], {'sha256': '1' * 64})
        self.assertEqual(out['meta'], {'api-version': '1.1'})

    def test_other_content_types_and_malformed_json_are_refused(self):
        for body, kind in ((b'{}', 'application/json'), (b'not json', JSON_TYPE), (b'[]', JSON_TYPE)):
            with self.subTest(kind=kind, body=body), self.assertRaises(egress_proxy.Refused):
                egress_proxy.rewrite_index(body, kind)


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b''):
        self.status, self.headers, self.stream = status, headers or {}, io.BytesIO(body)

    def getheader(self, name, default=None):
        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), default)

    def getheaders(self):
        return list(self.headers.items())

    def read(self, size=-1):
        return self.stream.read(size)

    def close(self):
        pass


class GatewayHandleTests(unittest.TestCase):
    """The gateway on the proxy's own port: origin-form `/pypi/...` requests."""

    def serve(self, head, response=None, *, mode='allowlist', address=None):
        calls, events = [], []

        def fetch(host, path, accept):
            calls.append((host, path, accept))
            return response or FakeResponse()
        client, proxy_side = socket.socketpair()
        with patch.object(egress_proxy, 'open_upstream', fetch), \
                patch.object(egress_proxy.socket, 'create_connection', side_effect=AssertionError('no tunnel')), \
                patch.object(egress_proxy, 'log', lambda **event: events.append(event)):
            worker = threading.Thread(target=egress_proxy.handle,
                                      args=(proxy_side, mode, {'domains': [], 'model_domains': []}, ''),
                                      kwargs={'address': address})
            worker.start()
            client.sendall(head)
            client.shutdown(socket.SHUT_WR)
            client.settimeout(10)
            reply = b''
            while data := client.recv(65536):
                reply += data
            worker.join(10)
            client.close()
        status = reply.split(b'\r\n', 1)[0]
        return status, reply.partition(b'\r\n\r\n')[2], calls, events

    def test_an_index_request_is_fetched_from_pypi_rewritten_and_logged_without_its_path(self):
        body = json.dumps({'meta': {'api-version': '1.1'}, 'name': 'six', 'files': [
            {'filename': 'six.whl', 'url': GatewayRewriteTests.FILE, 'hashes': {'sha256': '0' * 64}}]}).encode()
        status, _, calls, events = self.serve(b'GET /pypi/simple/Six/?secret-query HTTP/1.1\r\n\r\n')
        self.assertIn(b' 403 ', status)
        self.assertEqual(calls, [])
        self.assertNotIn('secret-query', json.dumps(events))
        head = (b'GET /pypi/simple/Six/ HTTP/1.1\r\nHost: raw.githubusercontent.com\r\nAccept: ' + JSON_TYPE.encode()
                + b'\r\nAuthorization: Bearer header-value-sentinel\r\nX-Sentinel: header-value-sentinel\r\n\r\n')
        status, reply, calls, events = self.serve(head, FakeResponse(200, {'Content-Type': JSON_TYPE}, body))
        self.assertIn(b' 200 ', status)
        self.assertEqual(calls, [('pypi.org', '/simple/six/', JSON_TYPE)])
        self.assertEqual(json.loads(reply)['files'][0]['url'],
                         f'/pypi/files/packages/{HASH}/six-1.16.0-py2.py3-none-any.whl')
        decisions = [(e.get('host'), e.get('route'), e.get('decision')) for e in events]
        self.assertIn(('pypi.org', 'simple', 'allowed'), decisions)
        self.assertIn(('pypi.org', 'simple', 'connected'), decisions)
        text = json.dumps(events)
        for sentinel in ('six', 'Six', 'header-value-sentinel', 'githubusercontent'):
            self.assertNotIn(sentinel, text)

    def test_a_file_is_streamed_from_files_pythonhosted_org(self):
        data = b'PK' + bytes(range(256)) * 400
        status, reply, calls, events = self.serve(
            b'GET ' + WHEEL.encode() + b' HTTP/1.1\r\nHost: x\r\nRange: bytes=0-1\r\n\r\n',
            FakeResponse(200, {'Content-Type': 'application/octet-stream', 'Content-Length': str(len(data))}, data))
        self.assertIn(b' 200 ', status)
        self.assertEqual(reply, data)
        self.assertEqual(calls, [('files.pythonhosted.org', WHEEL.removeprefix('/pypi/files'), None)])

    def test_refused_requests_never_reach_upstream(self):
        for head in (b'GET /pypi/files/SrFlipFlop/principiis-obsta/main/README.md HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n',
                     b'GET /pypi/simple/../../ HTTP/1.1\r\n\r\n', b'POST /pypi/simple/six/ HTTP/1.1\r\nContent-Length: 0\r\n\r\n',
                     b'GET /pypi/simple/six/ HTTP/1.1\r\nContent-Length: 3\r\n\r\nabc',
                     b'GET /pypi/simple/six/ HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n',
                     b'GET /SrFlipFlop/principiis-obsta/main/README.md HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n'):
            with self.subTest(head=head):
                status, reply, calls, events = self.serve(head)
                self.assertIn(b' 403 ', status)
                self.assertEqual(calls, [])
                self.assertEqual([e['decision'] for e in events if 'decision' in e], ['refused'])
                self.assertNotIn('README', json.dumps(events))

    def test_upstream_redirects_errors_and_github_answers_are_not_relayed(self):
        cases = ((FakeResponse(301, {'Location': 'https://raw.githubusercontent.com/x'}), 'upstream-redirect'),
                 (FakeResponse(200, {'Content-Type': JSON_TYPE, 'X-GitHub-Request-Id': 'A:B'}, b'{"files": []}'), 'github-response'),
                 (FakeResponse(500), 'upstream-status'),
                 (FakeResponse(200, {'Content-Type': 'text/plain'}, b'# principiis-obsta'), 'content-type'))
        for response, reason in cases:
            with self.subTest(reason=reason):
                status, reply, calls, events = self.serve(b'GET /pypi/simple/six/ HTTP/1.1\r\n\r\n', response)
                self.assertIn(b' 502 ', status)
                self.assertNotIn(b'githubusercontent', reply)
                self.assertNotIn(b'principiis', reply)
                self.assertEqual([e.get('reason') for e in events if e.get('decision') == 'refused'], [reason])

    def test_not_found_is_relayed_as_not_found(self):
        status, reply, calls, events = self.serve(b'GET /pypi/simple/no-such-project/ HTTP/1.1\r\n\r\n',
                                                  FakeResponse(404, {'Content-Type': 'text/html'}, b'gone'))
        self.assertIn(b' 404 ', status)
        self.assertEqual(reply, b'')

    def test_oversized_answers_are_refused_or_cut(self):
        with patch.object(egress_proxy, 'INDEX_LIMIT', 10):
            status, reply, calls, events = self.serve(b'GET /pypi/simple/six/ HTTP/1.1\r\n\r\n',
                                                      FakeResponse(200, {'Content-Type': JSON_TYPE}, b'{"files": [] }'))
        self.assertIn(b' 502 ', status)
        self.assertIn('too-large', [e.get('reason') for e in events])
        with patch.object(egress_proxy, 'FILE_LIMIT', 10):
            status, reply, calls, events = self.serve(b'GET ' + WHEEL.encode() + b' HTTP/1.1\r\n\r\n',
                                                      FakeResponse(200, {'Content-Length': '20'}, b'x' * 20))
            self.assertIn(b' 502 ', status)
            status, reply, calls, events = self.serve(b'GET ' + WHEEL.encode() + b' HTTP/1.1\r\n\r\n',
                                                      FakeResponse(200, {}, b'x' * 20))
            self.assertLessEqual(len(reply), 10)
            self.assertIn('too-large', [e.get('reason') for e in events])

    def test_absolute_form_to_the_proxys_own_address_is_the_gateway(self):
        response = FakeResponse(200, {'Content-Type': JSON_TYPE}, b'{"files": []}')
        status, reply, calls, events = self.serve(
            b'GET http://172.30.0.2:3128/pypi/simple/six/ HTTP/1.1\r\nHost: 172.30.0.2:3128\r\n\r\n',
            response, address='172.30.0.2')
        self.assertIn(b' 200 ', status)
        self.assertEqual(calls[0][:2], ('pypi.org', '/simple/six/'))
        # Absolute-form to PyPI itself is not the gateway, and PyPI is gateway-only.
        status, reply, calls, events = self.serve(
            b'GET http://pypi.org/simple/six/ HTTP/1.1\r\nHost: pypi.org\r\n\r\n', address='172.30.0.2')
        self.assertIn(b' 403 ', status)
        self.assertEqual(calls, [])

    def test_the_gateway_also_serves_in_log_mode(self):
        status, reply, calls, events = self.serve(b'GET /pypi/simple/six/ HTTP/1.1\r\n\r\n',
                                                  FakeResponse(200, {'Content-Type': JSON_TYPE}, b'{"files": []}'),
                                                  mode='log')
        self.assertIn(b' 200 ', status)
        self.assertEqual(calls[0][0], 'pypi.org')


class GatewayUpstreamTests(unittest.TestCase):
    def test_upstream_is_verified_https_to_the_fixed_host_with_fixed_headers(self):
        connections = []

        class Connection:
            def __init__(self, host, port=None, *, context=None, timeout=None):
                connections.append(self)
                self.host, self.port, self.context, self.timeout = host, port, context, timeout

            def request(self, method, path, headers=None):
                self.sent = (method, path, headers)

            def getresponse(self):
                return FakeResponse()

            def close(self):
                self.closed = True

        with patch.object(egress_proxy.http.client, 'HTTPSConnection', Connection):
            egress_proxy.open_upstream('pypi.org', '/simple/six/', JSON_TYPE)
            egress_proxy.open_upstream('files.pythonhosted.org', f'/packages/{HASH}/six.whl', None)
        first, second = connections
        self.assertEqual((first.host, first.port), ('pypi.org', 443))
        self.assertEqual(first.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(first.context.check_hostname)
        method, path, headers = first.sent
        self.assertEqual((method, path), ('GET', '/simple/six/'))
        self.assertEqual({k.lower() for k in headers}, {'accept', 'accept-encoding', 'user-agent', 'connection'})
        self.assertEqual(headers['Accept'], JSON_TYPE)
        self.assertEqual(headers['Accept-Encoding'], 'identity')
        self.assertEqual(headers['Connection'], 'close')
        self.assertEqual(second.host, 'files.pythonhosted.org')
        for host, path in (('raw.githubusercontent.com', '/x'), ('pypi.org', '/../x'), ('pypi.org', 'http://x/')):
            with self.subTest(host=host, path=path), self.assertRaises(egress_proxy.Refused):
                egress_proxy.open_upstream(host, path, None)


if __name__ == '__main__':
    unittest.main()


# Hosts of the model provider that a command must never reach, in either mode (#75).
PROVIDER_HOSTS = ('chatgpt.com', 'api.openai.com', 'auth.openai.com', 'ab.chatgpt.com', 'platform.openai.com',
                  'cdn.openai.com', 'cdn.oaistatic.com', 'files.oaiusercontent.com', 'chat.com', 'API.OpenAI.com.')
SHIPPED = {'domains': [], 'model_domains': ['api.openai.com', 'auth.openai.com', 'chatgpt.com']}


class ModelProviderTests(unittest.TestCase):
    """Commands must not reach any model-provider host, also in the measurement's log mode."""

    def test_the_model_provider_hosts_are_kept_in_one_place(self):
        for suffix in ('openai.com', 'chatgpt.com', 'oaistatic.com', 'oaiusercontent.com'):
            self.assertIn(suffix, MODEL_PROVIDER)
        for host in PROVIDER_HOSTS:
            self.assertTrue(model_provider(host), host)
        for host in ('registry.npmjs.org', 'notopenai.com', 'openai.com.attacker.example', 'chatgpt.co'):
            self.assertFalse(model_provider(host), host)

    def test_log_mode_forwards_model_provider_hosts_only_with_the_credential(self):
        for host in PROVIDER_HOSTS:
            with self.subTest(host=host):
                self.assertFalse(allowed(host, 443, 'log', [], SHIPPED['model_domains']))
                self.assertTrue(allowed(host, 443, 'log', [], SHIPPED['model_domains'], credential=True))
                # Even with no model_domains at all.
                self.assertFalse(allowed(host, 443, 'log', []))
        self.assertTrue(allowed('registry.npmjs.org', 443, 'log', [], SHIPPED['model_domains']))

    def test_allowlist_mode_never_forwards_a_provider_host_outside_model_domains(self):
        for host in ('ab.chatgpt.com', 'cdn.oaistatic.com', 'platform.openai.com'):
            with self.subTest(host=host):
                self.assertFalse(allowed(host, 443, 'allowlist', [host], SHIPPED['model_domains'], credential=True))
                self.assertFalse(allowed(host, 443, 'allowlist', [host], SHIPPED['model_domains']))
        self.assertTrue(allowed('chatgpt.com', 443, 'allowlist', [], SHIPPED['model_domains'], credential=True))

    def test_the_loader_refuses_provider_hosts_in_domains(self):
        for entry in ('ab.chatgpt.com', 'cdn.oaistatic.com', '*.openai.com', 'files.oaiusercontent.com'):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, 'model'):
                AllowlistLoaderTests.load(self, ['registry.npmjs.org', entry])

    exchange = HandleTests.exchange

    def test_a_command_gets_403_for_any_provider_host_in_log_mode(self):
        for host in ('chatgpt.com', 'ab.chatgpt.com', 'cdn.oaistatic.com'):
            with self.subTest(host=host):
                head = f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode()
                reply, forwarded, events = self.exchange('log', head, hello(host), policy=SHIPPED, token=TOKEN)
                self.assertIn(b' 403 ', reply)
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual((refused[0]['reason'], refused[0]['credential']),
                                 ('model host without the model credential', 'absent'))
        reply, forwarded, events = self.exchange(
            'log', b'GET http://chatgpt.com/ HTTP/1.1\r\nHost: chatgpt.com\r\n\r\n', policy=SHIPPED, token=TOKEN)
        self.assertIn(b' 403 ', reply)
        self.assertEqual(forwarded, b'')

    def test_the_codex_process_reaches_any_provider_host_in_log_mode_and_it_is_logged(self):
        for host in ('chatgpt.com', 'ab.chatgpt.com'):
            with self.subTest(host=host):
                head = (f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n'
                        f'Proxy-Authorization: {basic("model", TOKEN)}\r\n\r\n').encode()
                data = hello(host)
                reply, forwarded, events = self.exchange('log', head, data, policy=SHIPPED, token=TOKEN)
                self.assertIn(b' 200 ', reply)
                self.assertEqual(forwarded, data)
                self.assertEqual([(e['decision'], e.get('credential')) for e in events if 'decision' in e],
                                 [('allowed', 'valid'), ('connected', None)])

    def test_log_mode_closes_a_tunnel_whose_sni_names_a_provider_host_without_the_credential(self):
        # Fronting by SNI: CONNECT to an ordinary host on the same CDN, SNI of the model API.
        for name in ('api.openai.com', 'chatgpt.com', 'cdn.oaistatic.com'):
            with self.subTest(sni=name):
                reply, forwarded, events = self.exchange('log', HandleTests.CONNECT, hello(name), policy=SHIPPED,
                                                         token=TOKEN)
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual(refused[-1]['reason'], 'model host in SNI without the model credential')
        # Any other SNI is still only recorded (log mode measures, it does not enforce SNI).
        data = hello('docs.example.net')
        reply, forwarded, events = self.exchange('log', HandleTests.CONNECT, data, policy=SHIPPED, token=TOKEN)
        self.assertEqual(forwarded, data)

    def test_log_mode_closes_a_tunnel_offering_encrypted_client_hello(self):
        # ECH would hide a provider host behind an outer SNI.
        reply, forwarded, events = self.exchange(
            'log', HandleTests.CONNECT, synthetic_hello(server_name(b'registry.npmjs.org'), (0xfe0d, b'\x00')),
            policy=SHIPPED, token=TOKEN)
        self.assertEqual(forwarded, b'')
        self.assertEqual([e for e in events if e.get('decision') == 'refused'][-1]['reason'], 'ech')

    def test_log_mode_refuses_plain_http_whose_host_header_names_a_provider_host(self):
        reply, forwarded, events = self.exchange(
            'log', b'GET http://registry.npmjs.org/v1/responses HTTP/1.1\r\nHost: api.openai.com\r\n\r\n',
            policy=SHIPPED, token=TOKEN)
        self.assertIn(b' 403 ', reply)
        self.assertEqual(forwarded, b'')
        refused = [e for e in events if e.get('decision') == 'refused']
        self.assertEqual(refused[-1]['reason'], 'model host in Host header without the model credential')


class GatewayAliasTests(unittest.TestCase):
    serve = GatewayHandleTests.serve

    def test_absolute_form_to_the_proxys_stable_alias_is_the_gateway(self):
        response = FakeResponse(200, {'Content-Type': JSON_TYPE}, b'{"files": []}')
        status, reply, calls, events = self.serve(
            b'GET http://egress-proxy:3128/pypi/simple/six/ HTTP/1.1\r\nHost: egress-proxy:3128\r\n\r\n',
            response, address='172.30.0.2')
        self.assertIn(b' 200 ', status)
        self.assertEqual(calls[0][:2], ('pypi.org', '/simple/six/'))
        self.assertEqual(egress_proxy.GATEWAY_NAME, 'egress-proxy')


class LogModeResolutionTests(unittest.TestCase):
    def test_a_name_that_does_not_resolve_is_still_a_logged_decision_with_its_credential(self):
        # The measurement must record every request, also one whose name does not resolve.
        def unresolvable(name, port):
            raise socket.gaierror('no such name')
        head = (f'CONNECT chatgpt.com:443 HTTP/1.1\r\nProxy-Authorization: {basic("model", TOKEN)}\r\n\r\n').encode()
        upstream, events = Upstream(), []
        client, proxy_side = socket.socketpair()
        with patch.object(egress_proxy.socket, 'create_connection', upstream.connect), \
                patch.object(egress_proxy, 'resolve', unresolvable), \
                patch.object(egress_proxy, 'log', lambda **event: events.append(event)):
            worker = threading.Thread(target=egress_proxy.handle, args=(proxy_side, 'log', SHIPPED, TOKEN))
            worker.start()
            client.sendall(head)
            reply = client.recv(4096)
            client.close()
            worker.join(10)
        self.assertIn(b' 502 ', reply)
        self.assertEqual(upstream.connections, [])
        decisions = [(e['host'], e['decision'], e['credential'], e.get('reason')) for e in events if 'decision' in e]
        self.assertEqual(decisions, [('chatgpt.com', 'refused', 'valid', 'name does not resolve')])
