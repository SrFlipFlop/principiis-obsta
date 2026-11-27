"""Logging-only network measurement that builds the development allowlist (#75).

    python3 -m principiis.network_measurement --config RUNTIME_JSON --output NEW_DIR

Runs one ordinary Codex development session on a disposable fixture request, with
the egress proxy in `log` mode: every destination is forwarded and recorded. The
output keeps the workspace, Codex logs, `egress.jsonl` and `measurement.json`, whose
`connected_hosts` (destinations that actually answered) are the candidate allowlist. This is a live subscription run; it
needs the owner's approval (AGENTS.md hard rule 3) and never uses a benchmark request.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from .development_runtime import (CHECKOUT, NETWORK_ALLOWLIST, DevelopmentRuntime, docker_run, inspect_image,
                                  load_allowlist, load_config, preflight_run, remove, restrictions)
from .egress_proxy import gateway_only, never_allowed, unsafe_entry
from .jsonio import write_json

REQUEST = CHECKOUT / 'fixtures/development/network_measurement_request.txt'


def measure(config, output, request=REQUEST):
    output = Path(output).resolve()
    runtime = DevelopmentRuntime(config, output, Path(request).resolve().parent, egress='log')
    workspace = output / 'workspace'
    workspace.mkdir(parents=True)
    with (output / 'codex.stdout').open('w') as stdout, (output / 'codex.stderr').open('w') as stderr:
        evidence = runtime.execute(workspace, Path(request).read_text(), stdout, stderr)
    record = {'schema_version': 1, 'request': str(request), 'runtime_version': runtime.version,
              'connected_hosts': evidence['egress']['connected_hosts'],
              'allowed_hosts': evidence['egress']['allowed_hosts'],
              'refused_hosts': evidence['egress']['refused_hosts'], 'execution': evidence}
    write_json(output / 'measurement.json', record)
    return record


# Hosts the draft never contains: they serve arbitrary public repositories (the
# reason #78 excludes them) or bypass the domain check. Each needs an owner decision.
EXCLUDED = (
    ('github.com', 'code hosting serves the public research repository'),
    ('githubusercontent.com', 'code hosting serves the public research repository'),
    ('gitlab.com', 'code hosting'),
    ('bitbucket.org', 'code hosting'),
    ('golang.org', 'proxy.golang.org serves any public GitHub repository as a Go module'),
)


def exclusion(host):
    if re.fullmatch(r'[0-9.]+|.*:.*', host):
        return 'IP literal: the allowlist is by domain name'
    if never_allowed(host):
        return 'never allowed (egress_proxy.NEVER_ALLOW): serves GitHub content or mirrors arbitrary repositories'
    if gateway_only(host):
        return ('gateway-only (egress_proxy.GATEWAY_ONLY): shares Fastly with raw.githubusercontent.com; '
                'commands reach it through the PyPI gateway, never a tunnel')
    for suffix, reason in EXCLUDED:
        if host == suffix or host.endswith('.' + suffix):
            return reason


# Measured hosts of these families go to the owner as model hosts, never into `domains`:
# commands must not reach the model API (it offers hosted web search).
MODEL_FAMILIES = ('openai.com', 'chatgpt.com')


def model_host(host):
    return any(host == suffix or host.endswith('.' + suffix) for suffix in MODEL_FAMILIES)


def draft_allowlist(measurement, output):
    """Write a DRAFT allowlist from measured hosts. It carries TODO markers, so the loader refuses it."""
    measurement, output = Path(measurement), Path(output)
    if output.exists():
        raise ValueError(f'refusing to overwrite {output}')
    raw = measurement.read_bytes()
    document = json.loads(raw)
    hosts = document.get('connected_hosts') if isinstance(document, dict) else None
    if not isinstance(hosts, list) or any(not isinstance(v, str) for v in hosts):
        raise ValueError('measurement has no connected_hosts list')
    models = sorted({v for v in hosts if model_host(v)})
    kept = sorted({v for v in hosts if not exclusion(v) and not model_host(v)})
    excluded = {v: exclusion(v) for v in sorted(set(hosts)) if exclusion(v)}
    draft = {'version': '1',
             'status': 'TODO-OWNER: DRAFT from a measurement (sha256 %s). Review each host, then replace this '
                       'status with the approval note. The runtime refuses this file while any marker remains.'
                       % hashlib.sha256(raw).hexdigest(),
             'measured_from': 'TODO-OWNER: describe the measurement run (request fixture, date, who approved)',
             'model_domains': load_allowlist()['model_domains'],
             'model_domains_measured': models,
             'domains': kept}
    output.write_text(json.dumps(draft, indent=2) + '\n')
    return {'draft': str(output), 'hosts': kept, 'model_hosts': models, 'excluded': excluded}


def check(report, name, function):
    try:
        report.append({'check': name, 'status': 'PASS', 'detail': function() or ''})
        return True
    except (OSError, ValueError, KeyError) as error:
        report.append({'check': name, 'status': 'FAIL', 'detail': str(error)})
        return False


def dedicated_login(path):
    """Stat only: the file is never opened."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('login file must be a regular file, not a symlink')
    default = Path(os.path.expanduser('~/.codex/auth.json'))
    if default.exists() and os.path.samefile(path, default):
        raise ValueError('login file is the default ~/.codex/auth.json; use a dedicated login for this runtime')
    if '.codex' in path.resolve().parts[:-1]:
        raise ValueError('login file lives under a .codex directory; use a dedicated login file elsewhere')
    return 'content not read'


def visible_to_daemon(config, directory, label):
    """A no-network, no-credential container must see a marker the controller just wrote."""
    marker = directory / ('.po-visible-' + uuid.uuid4().hex)
    marker.write_text('x')
    try:
        preflight_run(config['docker'], ['--network', 'none', *restrictions(),
                      '--mount', f'type=bind,src={directory},dst=/probe,readonly', '--entrypoint', '/bin/sh',
                      config['image'], '-eu', '-c', f'test -f /probe/{marker.name}'])
    except ValueError as error:
        raise ValueError(f'Docker daemon cannot see {label} {directory}: {error}') from error
    finally:
        marker.unlink()
    return str(directory)


def preflight(runtime_config, runs_root):
    """Ordered PASS/FAIL checks before the owner-approved measurement. No model, no network, no login read."""
    report, state = [], {}

    def load():
        state['config'] = load_config(runtime_config)
        return 'image ' + state['config']['image']

    if not check(report, 'runtime config valid and placeholders replaced', load):
        return report
    config = state['config']
    check(report, 'login file is a dedicated regular file, not ~/.codex/auth.json', lambda: dedicated_login(config['auth_file']))
    if not check(report, 'docker daemon reachable',
                 lambda: 'server ' + docker_run(config['docker'], ['version', '--format', '{{.Server.Version}}']).strip()):
        return report
    check(report, 'image id matches the configured pin', lambda: inspect_image(config['docker'], config['image'])['id'])
    check(report, 'runs-root is visible to the docker daemon',
          lambda: visible_to_daemon(config, Path(runs_root).resolve(), 'the runs-root'))
    # The proxy program is passed as an argument, not mounted, so only the image must run it.
    check(report, 'proxy imports work under python -I -S in the image',
          lambda: preflight_run(config['docker'], ['--network', 'none', *restrictions(), '--entrypoint', 'python',
                                config['image'], '-I', '-S', '-c',
                                'import base64, hmac, http.client, json, os, re, socket, ssl, sys, threading, time; '
                                'ssl.create_default_context()']) and '')
    return report


# Host-header fronting control (#75). The proxy checks the SNI of a tunnel but cannot see
# the HTTP Host header inside TLS, so a host on a CDN shared with GitHub can serve GitHub
# content through a tunnel addressed to it. PyPI on Fastly did (now gateway-only). Run this
# before approving any allowlist: every `domains` host must PASS.
FRONTING_PATH = '/SrFlipFlop/principiis-obsta/main/README.md'
# Executed in a client container on the internal network: `python -c PROBE PROXY HOST...`.
FRONTING_PROBE = r'''
import json, socket, ssl, sys
proxy, results = sys.argv[1], {}
for host in sys.argv[2:]:
    result = {}
    try:
        sock = socket.create_connection((proxy, 3128), timeout=20)
        sock.sendall(f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode())
        reply = b''
        while b'\r\n\r\n' not in reply and (chunk := sock.recv(4096)):
            reply += chunk
        result['connect'] = reply.split(b'\r\n')[0].decode(errors='replace')
        if ' 200 ' in result['connect']:
            context = ssl.create_default_context()
            context.check_hostname = False   # about what answers, not whose certificate
            context.verify_mode = ssl.CERT_NONE
            tls = context.wrap_socket(sock, server_hostname=host)
            result['tls'] = 'established'
            tls.sendall(('GET PATH HTTP/1.1\r\nHost: raw.githubusercontent.com\r\n'
                         'User-Agent: po-fronting-check\r\nConnection: close\r\n\r\n').encode())
            data = b''
            while len(data) < 65536 and (chunk := tls.recv(65536)):
                data += chunk
            head, _, body = data.partition(b'\r\n\r\n')
            lines = head.split(b'\r\n')
            result['status'] = lines[0].decode(errors='replace')
            result['github_header'] = any(v.lower().startswith(b'x-github-request-id') for v in lines[1:])
            result['body'] = body[:300].decode(errors='replace')
    except (OSError, ssl.SSLError) as error:
        result.setdefault('tls', 'failed: ' + type(error).__name__)
    results[host] = result
print(json.dumps(results))
'''.replace('PATH', FRONTING_PATH)


def fronting_verdict(result):
    """(status, detail) for one host's probe: FAIL if GitHub answered, PASS if something else did."""
    status = result.get('status', '')
    if result.get('github_header') or 'principiis-obsta' in result.get('body', ''):
        return 'FAIL', f'GitHub content through this host ({status}): Host-header fronting works; do not allow it'
    if result.get('tls') != 'established' or not status:
        return 'INCONCLUSIVE', 'no answer to judge: ' + '; '.join(
            f'{k} {result[k]}' for k in ('connect', 'tls') if result.get(k))
    return 'PASS', 'no GitHub content: ' + status


def fronting_check(config, allowlist):
    """Probe each `domains` host of an allowlist (draft or approved) for Host-header fronting to GitHub.

    Starts the egress proxy as `execute` does, with `model_domains` empty and no model token,
    so nothing can reach the model hosts. Calls no model and reads no login.
    """
    document = json.loads(Path(allowlist).read_text())
    domains = document.get('domains') if isinstance(document, dict) else None
    if not isinstance(domains, list) or any(not isinstance(v, str) for v in domains):
        raise ValueError('allowlist has no domains list')
    report, probed = [], []
    for entry in domains:
        reason = unsafe_entry(entry)
        if reason:
            report.append({'host': entry, 'status': 'REFUSED', 'detail': reason})
        elif entry.startswith('*.'):
            report.append({'host': entry, 'status': 'UNCHECKED',
                           'detail': 'a wildcard cannot be probed; list each concrete host instead'})
        else:
            probed.append(entry)
    runtime = DevelopmentRuntime.__new__(DevelopmentRuntime)
    runtime.config, runtime.egress = load_config(config), 'allowlist'
    runtime.allowlist = {'domains': probed, 'model_domains': []}
    token = uuid.uuid4().hex
    egress = {'container': 'po-development-egress-' + token, 'network': 'po-development-net-' + token,
              'outside_network': 'po-development-out-' + token}
    output = '{}'
    try:
        if probed:
            proxy = runtime.start_egress(egress)
            output = docker_run(runtime.config['docker'], [
                'run', '--rm', '--network', egress['network'], *restrictions(), '--entrypoint', 'python',
                runtime.config['image'], '-c', FRONTING_PROBE, proxy, *probed], timeout=60 + 30 * len(probed))
    finally:
        if probed:
            for argv in (['rm', '-f', egress['container']], ['network', 'rm', egress['network']],
                         ['network', 'rm', egress['outside_network']]):
                remove(runtime.config['docker'], argv)
    results = json.loads(output.strip().splitlines()[-1])
    for host in probed:
        status, detail = fronting_verdict(results.get(host, {}))
        report.append({'host': host, 'status': status, 'detail': detail})
    order = {entry: index for index, entry in enumerate(domains)}
    return sorted(report, key=lambda item: order[item['host']])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] in ('preflight', 'draft-allowlist', 'fronting-check'):
        return helper(argv)
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--config', required=True, help='development runtime JSON')
    parser.add_argument('--output', required=True, help='new directory outside the checkout')
    parser.add_argument('--request', default=str(REQUEST), help='disposable fixture request')
    args = parser.parse_args(argv)
    record = measure(args.config, args.output, args.request)
    print('\n'.join(record['connected_hosts']))


def helper(argv):
    parser = argparse.ArgumentParser(prog='python3 -m principiis.network_measurement')
    commands = parser.add_subparsers(dest='command', required=True)
    pre = commands.add_parser('preflight', help='check the setup before the live measurement; calls no model')
    pre.add_argument('--config', required=True)
    pre.add_argument('--runs-root', required=True)
    draft = commands.add_parser('draft-allowlist', help='write a draft allowlist from measurement.json')
    draft.add_argument('--measurement', required=True)
    draft.add_argument('--output', required=True)
    fronting = commands.add_parser('fronting-check', help='probe every allowlist domain for Host-header fronting '
                                   'to GitHub (real Docker, host internet; no model, no login)')
    fronting.add_argument('--config', required=True)
    fronting.add_argument('--allowlist', default=str(NETWORK_ALLOWLIST), help='draft or approved allowlist JSON')
    args = parser.parse_args(argv)
    if args.command == 'fronting-check':
        report = fronting_check(args.config, args.allowlist)
        for item in report:
            print(f"{item['status']}  {item['host']}: {item['detail']}")
        failed = [item for item in report if item['status'] != 'PASS']
        print('FRONTING CHECK ' + ('FAILED: do not approve this allowlist' if failed else 'OK'))
        if failed:
            sys.exit(1)
        return
    if args.command == 'preflight':
        report = preflight(args.config, args.runs_root)
        for item in report:
            print(f"{item['status']}  {item['check']}" + (f": {item['detail']}" if item['detail'] else ''))
        failed = [item for item in report if item['status'] != 'PASS']
        print('PREFLIGHT ' + ('FAILED: do not start the run' if failed else 'OK'))
        if failed:
            sys.exit(1)
        return
    try:
        summary = draft_allowlist(args.measurement, args.output)
    except (OSError, ValueError) as error:
        sys.exit(f'error: {error}')
    print(f"Draft written to {summary['draft']} ({len(summary['hosts'])} hosts). It is REJECTED until you edit it.")
    for host, reason in summary['excluded'].items():
        print(f'NOT drafted, decide consciously: {host} ({reason})')


if __name__ == '__main__':
    main()
