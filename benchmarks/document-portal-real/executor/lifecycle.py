"""Trusted evaluator image entrypoint: restart an app child without restarting its container.

Public launch instrumentation; contains no tasks, assertions or evaluator secrets.
It keeps the existing UID, cgroup, read-only root, network and capability boundaries.
Port 8124 belongs to this supervisor; application port is 8123. Never use in production.
"""
import http.server
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request

# Existing #6 runner supplies: PYTHON APPLICATION_SCRIPT FIXTURE_METADATA.
# Consume the metadata here; the application sees exactly python app.py.
if len(sys.argv) != 4:
    raise SystemExit('usage: lifecycle.py PYTHON APPLICATION_SCRIPT FIXTURE_METADATA')
command = sys.argv[1:3]
fixture_metadata = sys.argv[3]
child = None
generation = 0
lock = threading.Lock()


def stop():
    global child
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def start():
    global child, generation
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL)
    generation += 1
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('application process exited before ready')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8123/ready', timeout=.3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(.1)
    raise RuntimeError('application readiness timed out')


class Lifecycle(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, value):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path != '/lifecycle':
            return self.respond(404, {'error':'unknown lifecycle operation'})
        self.respond(200, {'generation':generation,'pid':child.pid,'running':child.poll() is None})

    def do_POST(self):
        if self.path != '/restart':
            return self.respond(404, {'error':'unknown lifecycle operation'})
        with lock:
            try:
                stop()
                start()
                self.respond(200, {'generation':generation,'pid':child.pid,'running':True})
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                self.respond(503, {'error':str(exc),'generation':generation})


def shutdown(_signum, _frame):
    stop()
    raise SystemExit(0)


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
try:
    start()
    http.server.HTTPServer(('127.0.0.1', 8124), Lifecycle).serve_forever()
finally:
    stop()
