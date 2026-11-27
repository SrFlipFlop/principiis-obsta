import unittest

from principiis.egress_proxy import allowed


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


if __name__ == '__main__':
    unittest.main()
