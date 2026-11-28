"""The development container's only way out: a logging HTTP(S) forward proxy.

This file is also the program the trusted egress container runs, as
`python -I -S -c <this source> MODE POLICY_JSON PORT [BIND]`, so it imports only the
standard library. POLICY_JSON is `{"domains": [...], "model_domains": [...]}`.
`log` mode forwards and records every well-formed destination (the measurement that
builds the allowlist) except GitHub and its mirrors (`NEVER_ALLOW`), the gateway-only
PyPI hosts (`GATEWAY_ONLY`) and names that resolve to a non-public address (loopback,
private, link-local, metadata, ...), which it refuses and logs; `allowlist` mode
forwards `domains` on web ports, and
`model_domains` only for requests carrying the per-run model credential
(`Proxy-Authorization: Basic base64("model:<token>")`, token from the environment
variable named by MODEL_TOKEN_VARIABLE). Only the Codex process holds that token;
the commands it runs get the token-less proxy. Every decision is printed as one JSON
line on stdout; the token and the header are never printed or forwarded.

HTTPS is tunnelled with CONNECT, so the proxy sees the domain, never the path. In
`allowlist` mode a tunnel is forwarded only if the client's TLS ClientHello names the
same server (SNI) as the CONNECT line, and a plain-HTTP request only if its `Host`
header names the request-line host; this stops domain fronting by SNI or Host.

It cannot see the `Host` header inside TLS, so a host that shares a CDN with GitHub can
front it (`GATEWAY_ONLY`). PyPI is such a host and is never tunnelled: the same port
also serves a read-only PyPI gateway over plain HTTP (`/pypi/simple/<project>/`,
`/pypi/files/packages/...`, origin-form). The gateway itself makes the HTTPS request,
with certificate verification and a fixed host, path shape and header set, and points
the index's file URLs back at itself. It serves in both modes.
"""
import base64
import hmac
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
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
    # Found by the 2026-11-28 measurement. pkg.go.dev renders the GitHub README of any Go
    # module. docs.python.org is on Fastly and failed `fronting-check`: a tunnel to it with
    # `Host: raw.githubusercontent.com` returned this repository's README.
    'pkg.go.dev', 'docs.python.org',
)


# Hosts reached only through the PyPI gateway, never through a CONNECT tunnel: the loader
# refuses them (and wildcards covering them) in either list, and the proxy ignores them
# if listed. They share the Fastly CDN with raw.githubusercontent.com, and the proxy
# cannot see the HTTP Host header inside TLS: on 2026-11-27 and 2026-11-28 a tunnel to
# pypi.org with SNI pypi.org and `Host: raw.githubusercontent.com` returned this
# repository's README. A suffix also covers its subdomains. Before allowing any other
# host, run `python3 -m principiis.network_measurement fronting-check`.
GATEWAY_ONLY = ('pypi.org', 'pythonhosted.org')
# The only upstreams the gateway contacts, and the route each serves.
GATEWAY_UPSTREAMS = ('pypi.org', 'files.pythonhosted.org')
# The proxy's stable name on the internal network (a Docker network alias, resolved by
# Docker's embedded DNS there). Commands use it for the proxy and the PyPI gateway, so
# lockfiles that record the index URL (uv.lock, poetry.lock) stay valid across attempts.
GATEWAY_NAME = 'egress-proxy'

# Model-provider hosts: the registrable domains OpenAI serves Codex, ChatGPT and the API
# from (api/auth/platform/cdn.openai.com, chatgpt.com and its subdomains such as
# ab.chatgpt.com, the chat.com alias, oaistatic.com static assets, oaiusercontent.com
# user files). Any of them may lead to the model, and the model offers hosted web search,
# which ignores every network limit. So in every mode they are forwarded only with the
# per-run model credential, which only the Codex process holds; in `allowlist` mode only
# if also listed in `model_domains`. The loader refuses them in `domains`. A suffix also
# covers its subdomains. Not exhaustive (other providers or resellers would need their own
# key, which commands do not have); `allowlist` mode is default-deny regardless.
MODEL_PROVIDER = ('openai.com', 'chatgpt.com', 'chat.com', 'oaistatic.com', 'oaiusercontent.com')


def never_allowed(host):
    host = normalise_host(host)
    return host is None or any(host == suffix or host.endswith('.' + suffix) for suffix in NEVER_ALLOW)


def gateway_only(host):
    host = normalise_host(host)
    return host is not None and any(host == suffix or host.endswith('.' + suffix) for suffix in GATEWAY_ONLY)


def model_provider(host):
    host = normalise_host(host)
    return host is not None and any(host == suffix or host.endswith('.' + suffix) for suffix in MODEL_PROVIDER)


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
    for suffix in GATEWAY_ONLY:
        if base == suffix or base.endswith('.' + suffix) or (wildcard and suffix.endswith('.' + base)):
            return (f'gateway-only: {suffix} shares the Fastly CDN with raw.githubusercontent.com, so a tunnel '
                    'to it can front GitHub with the Host header inside TLS; commands reach PyPI through the '
                    "proxy's PyPI gateway")
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

    A model host (`model_domains` or any `MODEL_PROVIDER` host) needs the model
    credential in every mode, even if it is also in `allowlist`; in `allowlist` mode a
    provider host must also be a model domain.
    """
    host = normalise_host(host)
    if host is None or not isinstance(port, int) or not 0 < port < 65536:
        return False
    model = listed(host, model_domains) or model_provider(host)
    if mode == 'log':
        # Addresses are checked after resolution (`public_address`).
        return not never_allowed(host) and not gateway_only(host) and (not model or credential is True)
    if mode != 'allowlist' or port not in WEB_PORTS or never_allowed(host):
        return False
    if listed(host, model_domains):
        return credential is True
    return not model and listed(host, allowlist)


def refusal_reason(host):
    """Why `host` is refused in every mode, or None."""
    if never_allowed(host):
        return 'never-allowed host: serves GitHub content or mirrors arbitrary repositories'
    if gateway_only(host):
        return 'gateway-only host: use the PyPI gateway'
    return None


def resolve(name, port):
    """Every address `name` resolves to (literals and shorthand forms such as `127.1` included)."""
    return [info[4][0] for info in socket.getaddrinfo(name, port, type=socket.SOCK_STREAM)]


def public(address):
    try:
        ip = ipaddress.ip_address(address.split('%', 1)[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def public_address(name, port):
    """The address to connect to if every address `name` resolves to is public, else None.

    `log` mode connects to this address, not the name, so a second lookup cannot change it.
    """
    addresses = resolve(name, port)
    return addresses[0] if addresses and all(public(a) for a in addresses) else None


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


def log_tunnel_refusal(hello, presented, model_domains):
    """Why a log-mode tunnel must not carry this ClientHello, or None.

    Log mode records SNI mismatches instead of refusing them, except where they could
    reach the model without the credential: an SNI naming a model host (fronting through
    another host on the same CDN), and Encrypted Client Hello, which hides the real SNI.
    """
    if hello is None:
        return None
    if hello['ech']:
        return 'ech'
    sni = normalise_host(hello['sni'] or '')
    if sni and (model_provider(sni) or listed(sni, model_domains)) and presented != 'valid':
        return 'model host in SNI without the model credential'
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


def host_header_names_model(headers, model_domains):
    """Whether a plain-HTTP request's Host header names a model host (log mode: fronting by Host)."""
    for line in headers:
        name, _, value = line.partition(':')
        if name.strip().lower() == 'host':
            host = normalise_host(value.strip().rsplit(':', 1)[0] if value.strip().count(':') == 1 else value.strip())
            if host and (model_provider(host) or listed(host, model_domains)):
                return True
    return False


def discard(source, target):
    """Read `source` to its end without forwarding it, then half-close `target`."""
    pipe(source, None)
    try:
        target.shutdown(socket.SHUT_WR)
    except OSError:
        pass


class Refused(ValueError):
    """A gateway request or upstream answer that must not be served; `reason` is logged."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# PEP 503 project names (normalised before the upstream request) and PyPI's hashed file
# paths. Nothing else: no `/simple/` root, no JSON API, no query, no percent-encoding.
GATEWAY_PROJECT = re.compile(r'/pypi/simple/([A-Za-z0-9](?:[A-Za-z0-9._-]{0,198}[A-Za-z0-9])?)/?')
GATEWAY_FILE = re.compile(r'/pypi/files(/packages/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}/[A-Za-z0-9_][A-Za-z0-9._+-]{0,250}'
                          r'\.(?:whl|tar\.gz|zip|tar\.bz2|tar\.xz|tgz|egg)(?:\.metadata)?)')
FILES_ORIGIN = 'https://files.pythonhosted.org'
JSON_INDEX = 'application/vnd.pypi.simple.v1+json'
INDEX_TYPES = (JSON_INDEX, 'application/vnd.pypi.simple.v1+html', 'text/html')
DEFAULT_ACCEPT = 'application/vnd.pypi.simple.v1+json, application/vnd.pypi.simple.v1+html; q=0.1, text/html; q=0.01'
USER_AGENT = 'principiis-pypi-gateway/1'
INDEX_LIMIT = 64 * 1024 * 1024   # the largest simple pages are a few MB
FILE_LIMIT = 1024 ** 3           # wheels larger than 1 GiB (some CUDA builds) are refused
UPSTREAM_TIMEOUT = 60
HTTP_METHODS = ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'CONNECT', 'TRACE')


def gateway_route(method, target):
    """(route, upstream host, upstream path) for a gateway request target, or `Refused`."""
    if method != 'GET':
        raise Refused('method')
    if match := GATEWAY_PROJECT.fullmatch(target):
        return 'simple', 'pypi.org', '/simple/' + re.sub(r'[-_.]+', '-', match[1]).lower() + '/'
    if match := GATEWAY_FILE.fullmatch(target):
        return 'files', 'files.pythonhosted.org', match[1]
    raise Refused('path')


def gateway_accept(value):
    """The client's Accept if it names only simple-API media types (with at most a q value); else the default."""
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_ACCEPT
    parts = []
    for part in value.split(','):
        kind, *parameters = [v.strip() for v in part.split(';')]
        if (kind.lower() not in INDEX_TYPES or len(parameters) > 1
                or any(not re.fullmatch(r'q=(?:0(?:\.[0-9]{1,3})?|1(?:\.0{1,3})?)', p) for p in parameters)):
            return DEFAULT_ACCEPT
        parts.append('; '.join([kind.lower(), *parameters]))
    return ', '.join(parts)


def gateway_file_url(url):
    """The gateway path for a files.pythonhosted.org URL (keeping a hash fragment), or None."""
    if not isinstance(url, str) or not url.startswith(FILES_ORIGIN + '/'):
        return None
    base, _, fragment = url.partition('#')
    path = '/pypi/files' + base[len(FILES_ORIGIN):]
    if not GATEWAY_FILE.fullmatch(path):
        return None
    if re.fullmatch(r'(?:md5|sha1|sha224|sha256|sha384|sha512)=[0-9a-f]{32,128}', fragment):
        return path + '#' + fragment
    return path


def index_type(content_type):
    kind = (content_type or '').split(';')[0].strip().lower()
    if kind not in INDEX_TYPES:
        raise Refused('content-type')
    return kind


def rewrite_index(body, content_type):
    """Point every file URL of a simple-API page at the gateway; drop files hosted anywhere else."""
    kind = index_type(content_type)
    if kind == JSON_INDEX:
        try:
            document = json.loads(body)
        except ValueError as error:
            raise Refused('malformed-index') from error
        if not isinstance(document, dict) or not isinstance(document.get('files', []), list):
            raise Refused('malformed-index')
        files = []
        for entry in document.get('files', []):
            local = gateway_file_url(entry.get('url')) if isinstance(entry, dict) else None
            if local:
                files.append(dict(entry, url=local))
        document['files'] = files
        return json.dumps(document).encode()

    def anchor(match):
        local = gateway_file_url(match[1].decode('latin-1').replace('&amp;', '&'))
        return b'href="' + (local or '').encode() + b'"'
    return re.sub(rb'href="([^"]*)"', anchor, body)


def open_upstream(host, path, accept):
    """GET `path` from a gateway upstream over verified HTTPS; SNI and Host are `host`. No client header is sent."""
    if host == 'pypi.org':
        valid = re.fullmatch(r'/simple/[a-z0-9](?:[a-z0-9-]{0,198}[a-z0-9])?/', path)
    elif host == 'files.pythonhosted.org':
        valid = GATEWAY_FILE.fullmatch('/pypi/files' + path)
    else:
        valid = None
    if not valid:
        raise Refused('upstream')
    connection = http.client.HTTPSConnection(host, 443, context=ssl.create_default_context(),
                                             timeout=UPSTREAM_TIMEOUT)
    # `Connection: close` hands the socket to the response (http.client), which the caller closes.
    connection.request('GET', path, headers={'Accept': accept or '*/*', 'Accept-Encoding': 'identity',
                                             'User-Agent': USER_AGENT, 'Connection': 'close'})
    return connection.getresponse()


def send_head(client, status, headers=()):
    reason = {200: 'OK', 403: 'Forbidden', 404: 'Not Found', 502: 'Bad Gateway'}[status]
    lines = [f'HTTP/1.1 {status} {reason}', *headers, 'Connection: close']
    if not any(line.startswith('Content-Length:') for line in headers) and status != 200:
        lines.append('Content-Length: 0')
    client.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1'))


def serve_gateway(client, method, target, headers):
    """Serve one PyPI gateway request. Logs the route and upstream host, never the path or headers."""
    names = [line.split(':', 1)[0].strip().lower() for line in headers]
    values = [line.split(':', 1)[1].strip() if ':' in line else '' for line in headers]
    event = {'event': 'gateway', 'method': method if method in HTTP_METHODS else 'other', 'route': 'invalid'}
    try:
        if 'transfer-encoding' in names or any(v != '0' for n, v in zip(names, values) if n == 'content-length'):
            raise Refused('request-body')
        route, host, path = gateway_route(method, target)
    except Refused as refusal:
        log(**event, decision='refused', reason=refusal.reason)
        send_head(client, 403)
        return
    event.update(route=route, host=host, port=443)
    accept = gateway_accept(next((v for n, v in zip(names, values) if n == 'accept'), None)) if route == 'simple' else None
    log(**event, decision='allowed')
    response, sent = None, False
    try:
        response = open_upstream(host, path, accept)
        status = response.status
        if response.getheader('X-GitHub-Request-Id') is not None:
            raise Refused('github-response')
        if 300 <= status < 400:
            raise Refused('upstream-redirect')
        if status not in (200, 404):
            raise Refused('upstream-status')
        if status == 404:
            log(**event, decision='connected', status=status)
            send_head(client, 404)
            return
        if route == 'simple':
            kind = index_type(response.getheader('Content-Type'))
            body = response.read(INDEX_LIMIT + 1)
            if len(body) > INDEX_LIMIT:
                raise Refused('too-large')
            body = rewrite_index(body, kind)
            log(**event, decision='connected', status=status)
            send_head(client, 200, [f'Content-Type: {kind}' + ('' if kind == JSON_INDEX else '; charset=utf-8'),
                                    f'Content-Length: {len(body)}'])
            sent = True
            client.sendall(body)
            return
        length = response.getheader('Content-Length')
        if length is not None and (not length.isdigit() or int(length) > FILE_LIMIT):
            raise Refused('too-large')
        log(**event, decision='connected', status=status)
        send_head(client, 200, ['Content-Type: application/octet-stream',
                                *([f'Content-Length: {int(length)}'] if length is not None else [])])
        sent, total = True, 0
        while chunk := response.read(65536):
            total += len(chunk)
            if total > FILE_LIMIT:
                log(**event, decision='refused', reason='too-large')
                return
            client.sendall(chunk)
    except Refused as refusal:
        log(**event, decision='refused', reason=refusal.reason)
        if not sent:
            send_head(client, 502)
    except (OSError, http.client.HTTPException, ValueError) as error:
        log(event='error', route=event['route'], host=host, error=type(error).__name__)
        if not sent:
            send_head(client, 502)
    finally:
        if response is not None:
            response.close()


def own_target(target, address):
    """The origin-form target of an absolute-form request to the proxy's own address or alias, or None."""
    match = re.fullmatch(r'http://([^/:]+)(?::\d+)?(/.*)?', target)
    own = match and ((address and match[1] == address) or match[1].lower() == GATEWAY_NAME)
    return (match[2] or '/') if own else None


def handle(client, mode, policy, token='', address=None):
    upstream = None
    answered = False
    try:
        lines, rest = read_head(client)
        if not lines:
            return
        method, target, version = lines[0].split(' ')
        # Origin-form (or absolute-form naming the proxy itself) is the PyPI gateway, in both modes.
        if method != 'CONNECT' and (target.startswith('/') or own_target(target, address)):
            answered = True
            serve_gateway(client, method, target if target.startswith('/') else own_target(target, address), lines[1:])
            return
        host, port, path = destination(method, target)
        name = normalise_host(host)
        presented = credential(lines[1:], token)
        model = listed(name or '', policy.get('model_domains', ())) or model_provider(name or '')
        decision = allowed(host, port, mode, policy.get('domains', ()), policy.get('model_domains', ()),
                           credential=presented == 'valid')
        reason, address = None, name
        if not decision and name and (always := refusal_reason(name)):
            reason = always
        elif not decision and model and presented != 'valid':
            reason = 'model host without the model credential'
        elif not decision and model and mode == 'allowlist' and port in WEB_PORTS:
            reason = 'model-provider host not in model_domains'
        if (decision and mode == 'log' and method != 'CONNECT' and presented != 'valid'
                and host_header_names_model(lines[1:], policy.get('model_domains', ()))):
            decision, reason = False, 'model host in Host header without the model credential'
        if decision and mode == 'allowlist' and method != 'CONNECT':
            reason = plain_refusal(name, port, lines[1:])
            decision = reason is None
        unresolved = False
        if decision and mode == 'log':
            try:
                address = public_address(name, port)
            except OSError:  # still one logged decision, with its credential
                address, unresolved = None, True
            if address is None:
                decision, reason = False, 'name does not resolve' if unresolved else 'non-public address'
        log(method=method, host=name or host, port=port, decision='allowed' if decision else 'refused',
            credential=presented, **({'reason': reason} if reason else {}))
        if not decision:
            answered = True
            client.sendall(b'HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n' if unresolved
                           else b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            return
        upstream = socket.create_connection((address, port), timeout=30)
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
            refusal = tunnel_refusal(name, hello) if mode == 'allowlist' else log_tunnel_refusal(
                hello, presented, policy.get('model_domains', ()))
            if refusal:
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
        threading.Thread(target=handle, args=(client, mode, policy, token), kwargs={'address': address},
                         daemon=True).start()


if __name__ == '__main__':
    serve(sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]), os.environ.pop(MODEL_TOKEN_VARIABLE, ''),
          *sys.argv[4:5])
