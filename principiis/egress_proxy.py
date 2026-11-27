"""The development container's only way out: a logging HTTP(S) forward proxy.

This file is also the program the trusted egress container runs, as
`python -I -S -c <this source> MODE POLICY_JSON PORT [BIND]`, so it imports only the
standard library. POLICY_JSON is `{"domains": [...], "model_domains": [...]}`.
`log` mode forwards every well-formed destination and records it (the measurement
that builds the allowlist); `allowlist` mode forwards `domains` on web ports, and
`model_domains` only for requests carrying the per-run model credential
(`Proxy-Authorization: Basic base64("model:<token>")`, token from the environment
variable named by MODEL_TOKEN_VARIABLE). Only the Codex process holds that token;
the commands it runs get the token-less proxy. Every decision is printed as one JSON
line on stdout; the token and the header are never printed or forwarded.

HTTPS is tunnelled with CONNECT, so the proxy sees the domain, never the path. In
`allowlist` mode a tunnel is forwarded only if the client's TLS ClientHello names the
same server (SNI) as the CONNECT line, and a plain-HTTP request only if its `Host`
header names the request-line host; this stops domain fronting by SNI or Host.
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

# Hosts that are never allowed, whatever the allowlist says (the loader refuses such an
# allowlist, and the proxy refuses them again in case it was edited). The repository is
# public, so anything that serves GitHub content or mirrors arbitrary public
# repositories would hand the evaluated agent later requests and evaluator material
# (ADR 0003). A suffix also covers its subdomains. Not exhaustive: allowlist mode is
# default-deny; this list only guards against a careless allowlist edit.
NEVER_ALLOW = (
    # GitHub itself: web, API, codeload, gists, raw content, pages, assets, packages.
    'github.com', 'githubusercontent.com', 'github.io', 'githubassets.com', 'ghcr.io',
    'githubapp.com', 'github.dev', 'githubcopilot.com', 'git.io',
    # Go module proxies serve any public repository as a module (sum.golang.org does not).
    'proxy.golang.org', 'goproxy.io', 'goproxy.cn',
    # CDNs and services that serve files from arbitrary GitHub repositories.
    'jsdelivr.net', 'githack.com', 'statically.io', 'esm.sh', 'gitpod.io', 'sourcegraph.com',
    # Code hosts and archives where anyone can mirror the repository.
    'gitlab.com', 'bitbucket.org', 'codeberg.org', 'gitee.com', 'archive.org', 'softwareheritage.org',
)


def never_allowed(host):
    host = normalise_host(host)
    return host is None or any(host == suffix or host.endswith('.' + suffix) for suffix in NEVER_ALLOW)


def unsafe_entry(entry):
    """Why an allowlist entry must not be used, or None. Shared by the loader and the proxy."""
    if not isinstance(entry, str) or entry in ('*', '*.'):
        return 'too broad'
    wildcard = entry.startswith('*.')
    base = entry.removeprefix('*.')
    if normalise_host(base) != base:
        return 'not a lowercase domain name'
    if all(label.isdigit() for label in base.split('.')):
        return 'an IP literal, not a domain name'
    if wildcard and '.' not in base:
        return 'too broad: a wildcard needs at least two labels after "*."'
    for suffix in NEVER_ALLOW:
        if base == suffix or base.endswith('.' + suffix) or (wildcard and suffix.endswith('.' + base)):
            return f'never allowed: {suffix} serves GitHub content or mirrors arbitrary repositories'
    return None


def normalise_host(host):
    host = host.lower().rstrip('.') if isinstance(host, str) else ''
    return host if HOST.match(host) else None


def listed(host, domains):
    """Whether `host` matches a usable entry; entries `unsafe_entry` refuses never match."""
    for entry in domains:
        if unsafe_entry(entry):
            continue
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
    if mode != 'allowlist' or port not in WEB_PORTS or never_allowed(host):
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
            if target is not None:
                target.sendall(data)
    except OSError:
        pass
    finally:
        # Half-close: the other direction may still be carrying a response.
        try:
            if target is not None:
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


class Incomplete(ValueError):
    """More bytes are needed before the ClientHello can be judged."""


def handshake_message(data):
    """The first handshake message carried by the TLS records at the start of `data`."""
    message, offset = b'', 0
    while True:
        if len(data) < offset + 5:
            raise Incomplete('incomplete TLS record header')
        length = int.from_bytes(data[offset + 3:offset + 5], 'big')
        if data[offset] != 0x16 or data[offset + 1] != 3 or not 0 < length <= 16384:
            raise ValueError('not a TLS handshake record')
        if len(data) < offset + 5 + length:
            raise Incomplete('incomplete TLS record')
        message += data[offset + 5:offset + 5 + length]
        offset += 5 + length
        if len(message) >= 4:
            if message[0] != 1:
                raise ValueError('not a ClientHello')
            size = 4 + int.from_bytes(message[1:4], 'big')
            if len(message) >= size:
                return message[4:size]


def client_hello(data):
    """{'sni': lower-case server name or None, 'ech': whether Encrypted Client Hello is offered}."""
    body = handshake_message(data)
    position = 0

    def take(count):
        nonlocal position
        if position + count > len(body):
            raise ValueError('truncated ClientHello')
        position += count
        return body[position - count:position]

    def vector(width):
        return take(int.from_bytes(take(width), 'big'))

    take(2 + 32)  # legacy_version, random
    vector(1), vector(2), vector(1)  # session id, cipher suites, compression methods
    sni, ech, seen = None, False, set()
    extensions = vector(2) if position < len(body) else b''
    while extensions:
        if len(extensions) < 4:
            raise ValueError('truncated extension')
        kind, length = int.from_bytes(extensions[:2], 'big'), int.from_bytes(extensions[2:4], 'big')
        value, extensions = extensions[4:4 + length], extensions[4 + length:]
        if len(value) != length or kind in seen:
            raise ValueError('malformed extensions')
        seen.add(kind)
        if kind in (0xfe0d, 0xffce):  # encrypted_client_hello, draft encrypted_server_name
            ech = True
        if kind == 0:
            names = value[2:]
            if int.from_bytes(value[:2], 'big') != len(names) or len(names) < 3 or names[0] != 0:
                raise ValueError('malformed server_name')
            name = names[3:3 + int.from_bytes(names[1:3], 'big')]
            try:
                sni = name.decode('ascii').lower().rstrip('.')
            except UnicodeDecodeError as error:
                raise ValueError('server_name is not ASCII') from error
    return {'sni': sni, 'ech': ech}


def read_client_hello(client, timeout, data=b''):
    """(`data` plus the bytes read, parsed ClientHello or None). Every byte must still be forwarded."""
    client.settimeout(timeout)
    try:
        while True:
            try:
                return data, client_hello(data)
            except Incomplete:
                chunk = client.recv(65536)
                if not chunk or len(data) > 65536:
                    return data, None
                data += chunk
            except ValueError:
                return data, None
    except OSError:  # includes the timeout: a client that waits for the server first
        return data, None
    finally:
        client.settimeout(None)


def tunnel_refusal(host, hello):
    """Why an allowlist-mode tunnel to `host` must not carry this ClientHello, or None."""
    if hello is None:
        return 'not-tls'
    if hello['ech']:
        return 'ech'
    if hello['sni'] is None:
        return 'no-sni'
    if normalise_host(hello['sni']) != host:
        return 'sni-mismatch'
    return None


def plain_refusal(host, port, headers):
    """Why an allowlist-mode plain-HTTP request must not be forwarded, or None."""
    names = [line.split(':', 1)[0].strip().lower() for line in headers]
    values = [line.split(':', 1)[1].strip() if ':' in line else '' for line in headers]
    hosts = [v for n, v in zip(names, values) if n == 'host']
    if len(hosts) != 1:
        return 'host-mismatch'
    match = re.fullmatch(r'([^:]+)(?::(\d+))?', hosts[0])
    if not match or normalise_host(match[1]) != host or int(match[2] or 80) != port:
        return 'host-mismatch'
    lengths = [v for n, v in zip(names, values) if n == 'content-length']
    if 'transfer-encoding' in names or len(lengths) > 1 or (lengths and not lengths[0].isdigit()):
        return 'unsupported-body'
    return None


def discard(source, target):
    """Read `source` to its end without forwarding it, then half-close `target`."""
    pipe(source, None)
    try:
        target.shutdown(socket.SHUT_WR)
    except OSError:
        pass


def handle(client, mode, policy, token=''):
    upstream = None
    answered = False
    try:
        lines, rest = read_head(client)
        if not lines:
            return
        method, target, version = lines[0].split(' ')
        host, port, path = destination(method, target)
        name = normalise_host(host)
        presented = credential(lines[1:], token)
        model = listed(name or '', policy.get('model_domains', ()))
        decision = allowed(host, port, mode, policy.get('domains', ()), policy.get('model_domains', ()),
                           credential=presented == 'valid')
        reason = None
        if not decision and model and presented != 'valid':
            reason = 'model host without the model credential'
        if decision and mode == 'allowlist' and method != 'CONNECT':
            reason = plain_refusal(name, port, lines[1:])
            decision = reason is None
        log(method=method, host=name or host, port=port, decision='allowed' if decision else 'refused',
            credential=presented, **({'reason': reason} if reason else {}))
        if not decision:
            answered = True
            client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            return
        upstream = socket.create_connection((name, port), timeout=30)
        upstream.settimeout(None)
        log(method=method, host=name, port=port, decision='connected')
        answered = True
        reply = threading.Thread(target=pipe, args=(upstream, client), daemon=True)
        if method == 'CONNECT':
            client.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
            if mode == 'log':
                reply.start()  # never delay a protocol in which the server speaks first
            data, hello = read_client_hello(client, 30 if mode == 'allowlist' else 5, rest)
            sni = hello and hello['sni']
            if mode == 'allowlist' and (refusal := tunnel_refusal(name, hello)):
                log(method=method, host=name, port=port, decision='refused', reason=refusal, sni=sni,
                    credential=presented)
                return
            log(event='tls', method=method, host=name, port=port, sni=sni)
            upstream.sendall(data)
        elif mode == 'allowlist':
            headers = [line for line in lines[1:] if not line.lower().startswith(('proxy-', 'connection:', 'keep-alive:'))]
            upstream.sendall(('\r\n'.join([f'{method} {path} {version}', *headers, 'Connection: close'])
                              + '\r\n\r\n').encode('latin-1'))
            length = next((int(line.split(':', 1)[1]) for line in headers if line.lower().startswith('content-length:')), 0)
            while len(rest) < length and (data := client.recv(65536)):
                rest += data
            upstream.sendall(rest[:length])
            reply.start()
            # One request per connection: nothing after its body reaches the server.
            discard(client, upstream)
            reply.join()
            return
        else:
            headers = [line for line in lines[1:] if not line.lower().startswith('proxy-')]
            upstream.sendall(('\r\n'.join([f'{method} {path} {version}', *headers]) + '\r\n\r\n').encode('latin-1'))
            if rest:
                upstream.sendall(rest)
        if not reply.is_alive():
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


def serve(mode, policy, port, token='', bind='0.0.0.0'):
    # `own-address`: the container's address on the only network it has at start, the
    # internal development network. Networks joined later (the way out) cannot reach it.
    address = socket.gethostbyname(socket.gethostname()) if bind == 'own-address' else bind
    listener = socket.create_server((address, port))
    log(event='listening', mode=mode, address=address, port=port, allowlist=policy.get('domains'),
        model_domains=policy.get('model_domains'), model_token='set' if token else 'missing')
    while True:
        client, _ = listener.accept()
        threading.Thread(target=handle, args=(client, mode, policy, token), daemon=True).start()


if __name__ == '__main__':
    serve(sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]), os.environ.pop(MODEL_TOKEN_VARIABLE, ''),
          *sys.argv[4:5])
