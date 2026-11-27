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
from principiis.egress_proxy import allowed, client_hello, never_allowed, unsafe_entry


ALLOWLIST = ['pypi.org', '*.pythonhosted.org', 'chatgpt.com']


class EgressPolicyTests(unittest.TestCase):
    def test_allowlist_mode_admits_listed_hosts_on_web_ports(self):
        for host, port in (('pypi.org', 443), ('PyPI.org.', 443), ('files.pythonhosted.org', 443),
                           ('chatgpt.com', 80)):
            self.assertTrue(allowed(host, port, 'allowlist', ALLOWLIST), (host, port))

    def test_allowlist_mode_refuses_everything_else(self):
        for host, port in (('github.com', 443), ('pypi.org.attacker.example', 443), ('evilpypi.org', 443),
                           ('pythonhosted.org', 443), ('pypi.org', 22), ('140.82.112.3', 443),
                           ('', 443), ('pypi.org\r\nX: y', 443)):
            self.assertFalse(allowed(host, port, 'allowlist', ALLOWLIST), (host, port))

    def test_log_mode_admits_any_well_formed_destination(self):
        self.assertTrue(allowed('github.com', 443, 'log', []))
        self.assertTrue(allowed('140.82.112.3', 22, 'log', []))
        self.assertFalse(allowed('bad host', 443, 'log', []))

    def test_unknown_mode_refuses(self):
        self.assertFalse(allowed('pypi.org', 443, 'open', ALLOWLIST))


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
        for entry in ('pypi.org', '*.pythonhosted.org', 'sum.golang.org', '*.npmjs.org'):
            self.assertIsNone(unsafe_entry(entry), entry)

    def test_the_proxy_ignores_unsafe_wildcards(self):
        self.assertFalse(allowed('example.com', 443, 'allowlist', ['*.com']))
        self.assertTrue(allowed('files.pythonhosted.org', 443, 'allowlist', ['*.com', '*.pythonhosted.org']))


class AllowlistLoaderTests(unittest.TestCase):
    def load(self, domains):
        with temporary_directory() as directory:
            path = Path(directory) / 'allowlist.json'
            path.write_text(json.dumps({'version': '1', 'domains': domains}))
            return load_allowlist(path)

    def test_loader_refuses_github_mirrors_and_broad_wildcards(self):
        for entry in ('github.com', 'raw.githubusercontent.com', '*.githubusercontent.com', '*.golang.org',
                      'cdn.jsdelivr.net', 'gitlab.com', '*.org', '*.com', '*'):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, 'never|broad|domain'):
                self.load(['pypi.org', entry])

    def test_loader_accepts_ordinary_registries(self):
        self.assertEqual(self.load(['pypi.org', '*.pythonhosted.org', 'sum.golang.org']),
                         ['pypi.org', '*.pythonhosted.org', 'sum.golang.org'])


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


class HandleTests(unittest.TestCase):
    def exchange(self, mode, head, payload=b''):
        upstream, events = Upstream(), []
        client, proxy_side = socket.socketpair()
        with patch.object(egress_proxy.socket, 'create_connection', upstream.connect), \
                patch.object(egress_proxy, 'log', lambda **event: events.append(event)):
            worker = threading.Thread(target=egress_proxy.handle, args=(proxy_side, mode, ['pypi.org']))
            worker.start()
            client.sendall(head)
            reply = b''
            if head.startswith(b'CONNECT'):
                while b'\r\n\r\n' not in reply:
                    reply += client.recv(4096)
            client.sendall(payload)
            client.shutdown(socket.SHUT_WR)
            client.settimeout(10)
            while data := client.recv(65536):
                reply += data
            worker.join(10)
            client.close()
        if upstream.connections:
            upstream.thread.join(10)
        return reply, upstream.received, events

    CONNECT = b'CONNECT pypi.org:443 HTTP/1.1\r\nHost: pypi.org:443\r\n\r\n'

    def test_a_tunnel_whose_sni_names_another_host_is_closed_before_any_byte_is_forwarded(self):
        for name, reason in (('raw.githubusercontent.com', 'sni-mismatch'), (None, 'no-sni')):
            with self.subTest(sni=name):
                reply, forwarded, events = self.exchange('allowlist', self.CONNECT, hello(name))
                self.assertEqual(forwarded, b'')
                refused = [e for e in events if e.get('decision') == 'refused']
                self.assertEqual(refused[-1]['reason'], reason)

    def test_a_tunnel_offering_encrypted_client_hello_is_closed(self):
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT,
                                                 synthetic_hello(server_name(b'pypi.org'), (0xfe0d, b'\x00')))
        self.assertEqual(forwarded, b'')
        self.assertEqual([e for e in events if e.get('decision') == 'refused'][-1]['reason'], 'ech')

    def test_a_tunnel_that_is_not_tls_is_closed(self):
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT,
                                                 b'GET / HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n')
        self.assertEqual(forwarded, b'')
        self.assertEqual([e for e in events if e.get('decision') == 'refused'][-1]['reason'], 'not-tls')

    def test_a_tunnel_with_the_matching_sni_forwards_the_hello_unchanged(self):
        data = hello('pypi.org')
        reply, forwarded, events = self.exchange('allowlist', self.CONNECT, data + b'rest')
        self.assertIn(b' 200 ', reply)
        self.assertEqual(forwarded, data + b'rest')
        self.assertIn('pypi.org', [e.get('sni') for e in events])

    def test_log_mode_forwards_a_mismatch_and_records_the_sni(self):
        data = hello('raw.githubusercontent.com')
        reply, forwarded, events = self.exchange('log', self.CONNECT, data)
        self.assertEqual(forwarded, data)
        self.assertIn('raw.githubusercontent.com', [e.get('sni') for e in events])

    def test_plain_http_whose_host_header_names_another_host_is_refused(self):
        for host in (b'raw.githubusercontent.com', b'pypi.org\r\nHost: github.com', None):
            with self.subTest(host=host):
                header = b'Host: ' + host + b'\r\n' if host else b''
                reply, forwarded, events = self.exchange(
                    'allowlist', b'GET http://pypi.org/simple/ HTTP/1.1\r\n' + header + b'\r\n')
                self.assertIn(b' 403 ', reply)
                self.assertEqual(forwarded, b'')

    def test_plain_http_forwards_one_request_and_nothing_after_it(self):
        smuggled = b'GET /x HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n\r\n'
        reply, forwarded, events = self.exchange(
            'allowlist', b'POST http://pypi.org/simple/ HTTP/1.1\r\nHost: pypi.org:80\r\nContent-Length: 2\r\n'
                         b'Connection: keep-alive\r\n\r\nok' + smuggled)
        self.assertTrue(forwarded.startswith(b'POST /simple/ HTTP/1.1\r\n'), forwarded)
        self.assertTrue(forwarded.endswith(b'\r\n\r\nok'), forwarded)
        self.assertIn(b'Connection: close', forwarded)
        self.assertNotIn(b'keep-alive', forwarded)
        self.assertNotIn(b'githubusercontent', forwarded)


if __name__ == '__main__':
    unittest.main()
