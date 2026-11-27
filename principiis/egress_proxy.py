"""The development container's only way out: a logging HTTP(S) forward proxy.

This file is also the program the trusted egress container runs, as
`python -I -S -c <this source> MODE ALLOWLIST_JSON PORT`, so it imports only the
standard library. `log` mode forwards every well-formed destination and records it
(the measurement that builds the allowlist); `allowlist` mode forwards only listed
domains on web ports. Every decision is printed as one JSON line on stdout.

HTTPS is tunnelled with CONNECT, so the proxy sees the domain, never the path.
"""
import json
import re
import socket
import sys
import threading
import time

WEB_PORTS = (80, 443)
HOST = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z')


def normal(host):
    host = host.lower().rstrip('.') if isinstance(host, str) else ''
    return host if HOST.match(host) else None


def allowed(host, port, mode, allowlist):
    """Whether the proxy may open a connection to `host:port`."""
    host = normal(host)
    if host is None or not isinstance(port, int) or not 0 < port < 65536:
        return False
    if mode == 'log':
        return True
    if mode != 'allowlist' or port not in WEB_PORTS:
        return False
    for entry in allowlist:
        if entry.startswith('*.'):
            if host.endswith(entry[1:]):
                return True
        elif host == entry:
            return True
    return False


def log(**event):
    sys.stdout.write(json.dumps(dict(event, time=time.time()), sort_keys=True) + '\n')
    sys.stdout.flush()


def pipe(source, target):
    try:
        while data := source.recv(65536):
            target.sendall(data)
    except OSError:
        pass
    finally:
        for end in (source, target):
            try:
                end.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def read_head(client):
    head = b''
    while b'\r\n\r\n' not in head:
        data = client.recv(4096)
        if not data or len(head) > 65536:
            return None, b''
        head += data
    head, rest = head.split(b'\r\n\r\n', 1)
    return head.decode('latin-1').split('\r\n'), rest


def destination(method, target):
    """(host, port, origin-form path) of a CONNECT or absolute-form HTTP request."""
    if method == 'CONNECT':
        host, _, port = target.rpartition(':')
        return host, int(port), None
    match = re.fullmatch(r'http://([^/:]+)(?::(\d+))?(/.*)?', target)
    if not match:
        raise ValueError('absolute-form http:// request required')
    return match[1], int(match[2] or 80), match[3] or '/'


def handle(client, mode, allowlist):
    upstream = None
    try:
        lines, rest = read_head(client)
        if not lines:
            return
        method, target, version = lines[0].split(' ')
        host, port, path = destination(method, target)
        decision = allowed(host, port, mode, allowlist)
        log(method=method, host=normal(host) or host, port=port, decision='allowed' if decision else 'refused')
        if not decision:
            client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            return
        upstream = socket.create_connection((normal(host), port), timeout=30)
        upstream.settimeout(None)
        if method == 'CONNECT':
            client.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
        else:
            headers = [line for line in lines[1:] if not line.lower().startswith('proxy-')]
            upstream.sendall(('\r\n'.join([f'{method} {path} {version}', *headers]) + '\r\n\r\n').encode('latin-1'))
        if rest:
            upstream.sendall(rest)
        reply = threading.Thread(target=pipe, args=(upstream, client), daemon=True)
        reply.start()
        pipe(client, upstream)
        reply.join()
    except (OSError, ValueError) as error:
        log(event='error', error=str(error)[:200])
        try:
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except OSError:
            pass
    finally:
        for end in (client, upstream):
            if end is not None:
                end.close()


def serve(mode, allowlist, port):
    listener = socket.create_server(('0.0.0.0', port))
    log(event='listening', mode=mode, port=port, allowlist=allowlist)
    while True:
        client, _ = listener.accept()
        threading.Thread(target=handle, args=(client, mode, allowlist), daemon=True).start()


if __name__ == '__main__':
    serve(sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]))
