"""Operator progress that does not echo candidate or evaluator content."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import threading
import time


EVENT_FILE = 'operator-events.jsonl'
LOG_PATTERNS = (
    'development/steps/*/executor.stdout',
    'development/attempts/*/*/executor.stdout',
    'development/evaluations/*/*/evaluator.stdout',
    'investigations/*/*/agent.stdout',
)


def read_events(root):
    path = Path(root) / EVENT_FILE
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class Progress:
    def __init__(self, root, stage, step=None, *, verbose=False, interval=10):
        self.root = Path(root)
        self.stage = stage
        self.step = step
        self.verbose = verbose
        self.interval = interval
        self.started = time.monotonic()
        self.stop = threading.Event()
        self.thread = None
        self.offsets = {}
        self.lock = threading.Lock()
        self.scan_lock = threading.Lock()
        self.result_details = {}

    def emit(self, event, **fields):
        record = {'time': datetime.now(timezone.utc).isoformat(), 'stage': self.stage,
                  'step': self.step, 'event': event, 'elapsed_seconds': round(time.monotonic() - self.started, 1),
                  **fields}
        line = json.dumps(record, sort_keys=True) + '\n'
        with self.lock:
            fd = os.open(self.root / EVENT_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line.encode())
            finally:
                os.close(fd)
            if event != 'codex-event' or self.verbose:
                detail = f" {fields.get('type', '')}/{fields.get('item_type', '')}" if event == 'codex-event' else ''
                if fields.get('outcome'):
                    detail += f" outcome={fields['outcome']}"
                if fields.get('artifact'):
                    detail += f" artifact={fields['artifact']}"
                label = 'still running' if event == 'heartbeat' else event
                print(f"[{self.stage} {self.step or ''} {record['elapsed_seconds']:.1f}s] {label}{detail}",
                      file=sys.stderr, flush=True)

    def scan(self):
        with self.scan_lock:
            for pattern in LOG_PATTERNS:
                for path in sorted(self.root.glob(pattern)):
                    self._scan_file(path)

    def _scan_file(self, path):
        if path.is_symlink() or not path.is_file():
            return
        offset = self.offsets.get(path, 0)
        try:
            with path.open() as stream:
                stream.seek(offset)
                while True:
                    position = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    if not line.endswith('\n'):
                        stream.seek(position)
                        break
                    try:
                        data = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(data, dict):
                        continue
                    event_type = data.get('type')
                    item = data.get('item')
                    item_type = item.get('type') if isinstance(item, dict) else None
                    if isinstance(event_type, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', event_type):
                        self.emit('codex-event', type=event_type,
                                  item_type=item_type if isinstance(item_type, str)
                                  and re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', item_type) else None,
                                  source=str(path.relative_to(self.root)))
                self.offsets[path] = stream.tell()
        except OSError:
            return

    def _watch(self):
        next_heartbeat = time.monotonic() + self.interval
        while not self.stop.wait(min(1, self.interval)):
            self.scan()
            if time.monotonic() >= next_heartbeat:
                self.emit('heartbeat')
                next_heartbeat = time.monotonic() + self.interval

    def __enter__(self):
        for pattern in LOG_PATTERNS:
            for path in self.root.glob(pattern):
                if path.is_file() and not path.is_symlink():
                    self.offsets[path] = path.stat().st_size
        self.emit('started')
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, error_type, error, traceback):
        self.stop.set()
        self.thread.join()
        self.scan()
        self.emit('failed' if error_type else 'completed',
                  error_type=error_type.__name__ if error_type else None,
                  **self.result_details)
        return False
