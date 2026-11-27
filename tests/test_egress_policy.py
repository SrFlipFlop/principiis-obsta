import base64
import contextlib
import io
import json
import socket
import threading
import unittest
from unittest.mock import patch

from principiis import egress_proxy
from principiis.egress_proxy import allowed, credential


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


TOKEN = 'per-run-model-token-0123456789abcdef'
POLICY = {'domains': ['pypi.org'], 'model_domains': ['chatgpt.com', 'api.openai.com']}


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
        self.assertTrue(allowed('pypi.org', 443, 'allowlist', POLICY['domains'], POLICY['model_domains']))

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
        with patch.object(egress_proxy.socket, 'create_connection', side_effect=OSError('no route in test')):
            reply, events = self.request('CONNECT chatgpt.com:443 HTTP/1.1\r\n\r\n', mode='log')
        self.assertIn(b' 502 ', reply)
        self.assertEqual((events[0]['decision'], events[0]['credential']), ('allowed', 'absent'))


if __name__ == '__main__':
    unittest.main()
