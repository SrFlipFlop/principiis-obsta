"""Measured subprocess execution and live log retention."""
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


def execute(argv, workspace, request, stdout, stderr, *, env=None, transform=lambda value: value,
            clock=time.monotonic, wall_clock=time.time, timeout=None, termination_grace_seconds=.2):
    """Run one measured stage, retaining logs and killing its process group on interruption."""
    started = clock()
    evidence = {'argv': argv, 'exit_status': None, 'started_at': wall_clock(),
                'memory': {'peak_sampled_rss_bytes': None, 'method': 'Linux /proc process-group RSS sampled every 10ms',
                           'scope': 'local executor and descendants remaining in its process group',
                           'limitations': 'RSS includes shared pages repeatedly; short-lived children and detached groups may be missed; no container or hosted model RAM'}}
    stop = threading.Event()
    peaks = []
    process = None
    readers = []

    def sample():
        while not stop.is_set():
            total = 0
            found = False
            for path in Path('/proc').glob('[0-9]*/stat'):
                try:
                    fields = path.read_text().rsplit(') ', 1)[1].split()
                    if int(fields[2]) == process.pid:
                        total += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
                        found = True
                except (OSError, ValueError, IndexError):
                    continue
            if found:
                peaks.append(total)
            stop.wait(.01)

    def retain(stream, destination):
        try:
            for line in stream:
                destination.write(transform(line))
                destination.flush()
        finally:
            stream.close()

    try:
        process = subprocess.Popen(argv, cwd=workspace, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        readers = [threading.Thread(target=retain, args=(stream, destination))
                   for stream, destination in ((process.stdout, stdout), (process.stderr, stderr))]
        sampler = threading.Thread(target=sample)
        readers.append(sampler)
        for reader in readers:
            reader.start()
        try:
            process.stdin.write(request)
            process.stdin.close()
        except BrokenPipeError:
            process.stdin.close()
        evidence['exit_status'] = process.wait(timeout=timeout)
    except (OSError, KeyboardInterrupt, subprocess.TimeoutExpired) as error:
        evidence['error'] = str(error) or 'controller interrupted'
    finally:
        if process is not None:
            # Also close descendants holding stdout pipes after their parent exits.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                evidence['termination'] = {'signal': 'SIGTERM', 'grace_seconds': termination_grace_seconds, 'forced': False}
                try:
                    process.wait(timeout=termination_grace_seconds)
                except subprocess.TimeoutExpired:
                    evidence['termination']['forced'] = True
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
        stop.set()
        for reader in readers:
            reader.join()
        evidence['finished_at'] = wall_clock()
        evidence['elapsed_seconds'] = clock() - started
        evidence['memory']['peak_sampled_rss_bytes'] = max(peaks) if peaks else None
    return evidence

