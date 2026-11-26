"""Trusted stdlib process fixture at approved executor seam, not a candidate app run."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
from support import temporary_directory
import time
import unittest
import urllib.request
import json

ROOT=Path(__file__).resolve().parents[1]
LIFECYCLE=ROOT/'benchmarks/document-portal/executor/lifecycle.py'

class TrustedLifecycle(unittest.TestCase):
    def test_restart_retains_data_and_does_not_forward_fixture_metadata(self):
        # The sandbox may prohibit local listeners; report that limitation honestly.
        # The hashed benchmark supervisor fixes ports 8123/8124, so they cannot be
        # OS-assigned. Probe them as its servers bind (SO_REUSEADDR), so sockets from
        # a previous run still in TIME_WAIT do not fail this test.
        for port in [8123,8124]:
            try:
                with socket.socket() as probe:
                    probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                    probe.bind(('127.0.0.1',port))
            except PermissionError:
                self.skipTest('sandbox prohibits loopback listeners; process contract runtime pending')
        with temporary_directory() as temp:
            root=Path(temp)
            child=root/'app.py'
            child.write_text('''import http.server,pathlib,sys
assert len(sys.argv)==1, 'fixture metadata leaked to candidate argv'
p=pathlib.Path('starts');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
class H(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  raw=p.read_bytes();self.send_response(200);self.end_headers();self.wfile.write(raw)
http.server.HTTPServer.allow_reuse_address=True
http.server.HTTPServer(('127.0.0.1',8123),H).serve_forever()
''')
            log=(root/'log').open('w+')
            p=subprocess.Popen([sys.executable,str(LIFECYCLE),sys.executable,str(child),'safe'],cwd=root,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:8124/lifecycle',timeout=.3) as r: before=json.load(r)
                        break
                    except OSError:
                        if p.poll() is not None:
                            log.seek(0);self.fail(log.read())
                        time.sleep(.05)
                else:self.fail('trusted fixture lifecycle did not become ready')
                with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8124/restart',method='POST'),timeout=20) as r:after=json.load(r)
                self.assertGreater(after['generation'],before['generation'])
                with urllib.request.urlopen('http://127.0.0.1:8123/ready',timeout=2) as r:self.assertEqual(r.read(),b'2')
            finally:
                p.terminate();p.wait(timeout=10);log.close()
