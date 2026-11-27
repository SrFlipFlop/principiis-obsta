"""The development container's only way out: a logging HTTP(S) forward proxy.

This file is also the program the trusted egress container runs, as
`python -I -S -c <this source> MODE POLICY_JSON PORT`, so it imports only the
standard library. POLICY_JSON is `{"domains": [...], "model_domains": [...]}`.
`log` mode forwards every well-formed destination and records it (the measurement
that builds the allowlist); `allowlist` mode forwards `domains` on web ports, and
`model_domains` only for requests carrying the per-run model credential
(`Proxy-Authorization: Basic base64("model:<token>")`, token from the environment
variable named by MODEL_TOKEN_VARIABLE). Only the Codex process holds that token;
the commands it runs get the token-less proxy. Every decision is printed as one JSON
line on stdout; the token and the header are never printed or forwarded.

HTTPS is tunnelled with CONNECT, so the proxy sees the domain, never the path.
"""
import base64
import hmac
import json
import os
import re
import socket
import sys
import threading
import time

WEB_PORTS = (80, 443)
MODEL_TOKEN_VARIABLE = 'PO_MODEL_TOKEN'
MODEL_USER = 'model'
HOST = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z')


def normalise_host(host):
    host = host.lower().rstrip('.') if isinstance(host, str) else ''
    return host if HOST.match(host) else None


def listed(host, domains):
    for entry in domains:
        if entry.startswith('*.'):
            if host.endswith(entry[1:]):
                return True
        elif host == entry:
            return True
    return False


def allowed(host, port, mode, allowlist, model_domains=(), credential=False):
    """Whether the proxy may open a connection to `host:port`.

    A model host needs the model credential even if it is also in `allowlist`.
    """
    host = normalise_host(host)
    if host is None or not isinstance(port, int) or not 0 < port < 65536:
        return False
    if mode == 'log':
        return True
    if mode != 'allowlist' or port not in WEB_PORTS:
        return False
    if listed(host, model_domains):
        return credential is True
    return listed(host, allowlist)


def credential(lines, token):
    """'valid', 'invalid' or 'absent': the request's model credential. Never returns the value."""
    values = [line.split(':', 1)[1].strip() for line in lines
              if line.split(':', 1)[0].strip().lower() == 'proxy-authorization' and ':' in line]
    if not values:
        return 'absent'
    scheme, _, encoded = values[0].partition(' ')
    try:
        user, _, password = base64.b64decode(encoded.strip(), validate=True).decode().partition(':')
    except ValueError:
        return 'invalid'
    expected = (MODEL_USER + ':' + token).encode()
    given = (user + ':' + password).encode()
    ok = (len(values) == 1 and scheme.lower() == 'basic' and bool(token)
          and hmac.compare_digest(given, expected))
    return 'valid' if ok else 'invalid'


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
        # Half-close: the other direction may still be carrying a response.
        try:
            target.shutdown(socket.SHUT_WR)
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


def handle(client, mode, policy, token=''):
    upstream = None
    answered = False
    try:
        lines, rest = read_head(client)
        if not lines:
            return
        method, target, version = lines[0].split(' ')
        host, port, path = destination(method, target)
        presented = credential(lines[1:], token)
        model = listed(normalise_host(host) or '', policy.get('model_domains', ()))
        decision = allowed(host, port, mode, policy.get('domains', ()), policy.get('model_domains', ()),
                           credential=presented == 'valid')
        event = dict(method=method, host=normalise_host(host) or host, port=port,
                     decision='allowed' if decision else 'refused', credential=presented)
        if not decision and model and presented != 'valid':
            event['reason'] = 'model host without the model credential'
        log(**event)
        if not decision:
            answered = True
            client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            return
        upstream = socket.create_connection((normalise_host(host), port), timeout=30)
        upstream.settimeout(None)
        log(method=method, host=normalise_host(host), port=port, decision='connected')
        answered = True
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
        if answered:
            return
        try:
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except OSError:
            pass
    finally:
        for end in (client, upstream):
            if end is not None:
                end.close()


def serve(mode, policy, port, token):
    listener = socket.create_server(('0.0.0.0', port))
    log(event='listening', mode=mode, port=port, allowlist=policy.get('domains'),
        model_domains=policy.get('model_domains'), model_token='set' if token else 'missing')
    while True:
        client, _ = listener.accept()
        threading.Thread(target=handle, args=(client, mode, policy, token), daemon=True).start()


if __name__ == '__main__':
    serve(sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]), os.environ.pop(MODEL_TOKEN_VARIABLE, ''))
