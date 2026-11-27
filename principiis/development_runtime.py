"""Ordinary subscription Codex in a separately prepared, disposable Docker runtime."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
import uuid

from .codex import redact
from .egress_proxy import MODEL_TOKEN_VARIABLE, normalise_host
from .execution import execute
from .jsonio import write_json
from .snapshot import forbid_foreign_git


CHECKOUT = Path(__file__).resolve().parents[1]
SANDBOX_POLICY = CHECKOUT / 'fixtures/development/seccomp_profile.json'
NETWORK_ALLOWLIST = CHECKOUT / 'fixtures/development/network_allowlist.json'
EGRESS_PROXY = Path(__file__).resolve().with_name('egress_proxy.py')
EGRESS_PORT = 3128
EGRESS_MODES = ('allowlist', 'log')
ADAPTER = 'docker-development-v4'
CODEX_HOME = '/home/developer/.codex'
# Model hosts serve hosted web search, which ignores every network limit. Only the Codex
# process may reach them: each attempt gets a fresh token that the proxy requires for
# `model_domains`; the commands Codex runs get the token-less proxy (#75).
MODEL_CREDENTIAL = ('per-run-token-v1: model_domains need proxy-authorization basic model:<per-run token>; '
                    'only the Codex process has it; commands get the token-less proxy and cannot read CODEX_HOME')
PROXY_VARIABLES = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
NETWORK_DESCRIPTION = {
    'allowlist':'internal Docker network; only route out is the egress proxy, limited to the network allowlist',
    'log':'internal Docker network; only route out is the egress proxy, logging every destination without limits',
}


IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')
IMAGE_ENVIRONMENT = {'PATH', 'LANG', 'LC_ALL', 'TZ', 'HOME', 'NODE_VERSION', 'YARN_VERSION',
                     'PYTHON_VERSION', 'PYTHON_SHA256', 'GPG_KEY', 'PYTHONUNBUFFERED',
                     'PYTHONDONTWRITEBYTECODE', 'PIP_DISABLE_PIP_VERSION_CHECK'}


# A trusted engineering control, executed by the ordinary Codex workspace sandbox.
# The outer tmpfs can be written by this UID; only the inner policy denies it.
SANDBOX_PROBE = r"""
import errno, json, os, pathlib, shutil, subprocess, sys, tempfile, venv
assert os.getuid() != 0
status = pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\t1' in status and 'Seccomp:\t2' in status
pathlib.Path('/workspace/probe.txt').write_text('workspace-write')
try:
    pathlib.Path('/outside-workspace/forbidden').write_text('unexpected')
except OSError as error:
    assert error.errno in (errno.EACCES, errno.EPERM, errno.EROFS), error
else:
    raise AssertionError('Codex workspace sandbox allowed outside write')
assert not pathlib.Path(CHECKOUT_INSTRUCTIONS).exists()
with tempfile.TemporaryDirectory(prefix='po-tool-control-') as temporary:
    tool = pathlib.Path(temporary) / 'tool'
    tool.write_text('#!/bin/sh\nexit 0\n')
    tool.chmod(0o700)
    subprocess.run([str(tool)], check=True)
venv.create('/workspace/.qualification-venv', with_pip=True)
subprocess.run(['/workspace/.qualification-venv/bin/python', '-c', 'import sqlite3; print(sqlite3.sqlite_version)'], check=True, stdout=subprocess.DEVNULL)
subprocess.run(['node','-e','require("fs").writeFileSync("/workspace/node-probe.txt","ok")'], check=True)
subprocess.run(['git','--version'], check=True, stdout=subprocess.DEVNULL)
shutil.rmtree('/workspace/.qualification-venv')
paths = set()
for name in ('python', 'python3', 'python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor)):
    p=pathlib.Path('/usr/local/bin')/name
    assert p.is_file() and os.access(p,os.X_OK) and p.resolve() == pathlib.Path(sys.executable).resolve()
    paths.add(str(p))
    while p.is_symlink():
        target=os.readlink(p)
        p=pathlib.Path(os.path.normpath(str(p.parent/target)))
        assert str(p).startswith('/usr/local/bin/') and p.is_file() and os.access(p,os.X_OK)
        paths.add(str(p))
# Commands must not recover the model token (#75): not from their environment, not
# from another process (bubblewrap gives them a fresh PID namespace and /proc), and
# not from the Codex home (login, shell snapshots), which the profile denies.
assert 'PO_MODEL_TOKEN' not in os.environ
for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy'):
    assert '@' not in os.environ.get(name, ''), name + ' carries a credential'
for entry in pathlib.Path('/proc').iterdir():
    if entry.name.isdigit():
        try:
            data = (entry / 'environ').read_bytes()
        except OSError:
            continue
        assert b'PO_MODEL_TOKEN=' not in data and b'://model:' not in data, 'model token visible in /proc'
home = os.environ.get('CODEX_HOME', '/home/developer/.codex')
for attempt in (lambda: os.listdir(home), lambda: open(os.path.join(home, 'auth.json')).close()):
    try:
        attempt()
    except PermissionError:
        continue
    raise AssertionError('CODEX_HOME or its auth.json is readable from commands')
print(json.dumps({'sandbox':'workspace-write','symlink_targets':sorted(paths)}))
""".replace('CHECKOUT_INSTRUCTIONS', repr(str(CHECKOUT / 'AGENTS.md')))


# Hosted search bypasses every network limit and could find later requests in the
# public repository (#75, ADR 0003).
WEB_SEARCH = 'disabled'


def workspace_permission_settings():
    # Explicit profile selection and legacy network overrides do not compose in
    # Codex 0.169.0. Use one supported workspace-derived profile in every path.
    # Commands must not read the Codex home: it holds the login and shell snapshots
    # of the Codex process environment, which carries the model token.
    return {'default_permissions':'development',
            'permissions.development.extends':':workspace',
            'permissions.development.network.enabled':True,
            'permissions.development.filesystem':{CODEX_HOME:'none'}}


def command_environment(address):
    """Environment policy for the commands Codex runs: the proxy without the model token."""
    url = f'http://{address}:{EGRESS_PORT}'
    return {'set': {name: url for name in PROXY_VARIABLES}, 'exclude': [MODEL_TOKEN_VARIABLE]}


def command_settings(address):
    policy = command_environment(address)
    return {'shell_environment_policy.set': policy['set'], 'shell_environment_policy.exclude': policy['exclude']}


# The Codex process alone gets the credentialed proxy; the token variable is dropped first.
MODEL_PROXY_BOOT = ('model_proxy="http://model:${PO_MODEL_TOKEN}@${HTTPS_PROXY#http://}"; unset PO_MODEL_TOKEN; '
                    'export HTTPS_PROXY="$model_proxy" HTTP_PROXY="$model_proxy" '
                    'https_proxy="$model_proxy" http_proxy="$model_proxy"; unset model_proxy; ')


def toml_value(value):
    """A `-c` value: TOML inline tables for mappings, JSON-compatible scalars and arrays otherwise."""
    if isinstance(value, dict):
        return '{' + ','.join((k if re.fullmatch(r'[A-Za-z0-9_-]+', k) else json.dumps(k)) + '=' + toml_value(v)
                              for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(toml_value(v) for v in value) + ']'
    return json.dumps(value)


def configuration_args(settings):
    return [item for key,value in settings.items() for item in ('-c',key+'='+toml_value(value))]


def local_path(value, label, *, executable=False):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(v in value for v in (',', '\n', '\r', '\x00')):
        raise ValueError(f'{label} must be an absolute path without commas/newlines')
    path = Path(value)
    if (path.is_symlink() and not executable) or not path.is_file() or (executable and not os.access(path, os.X_OK)):
        raise ValueError(f'{label} must be an existing regular {"executable" if executable else "file"}, not a symlink')
    # Snap launchers depend on their invocation basename; retain executable symlinks.
    return str(path.absolute() if executable else path.resolve())


def load_config(path):
    config = json.loads(Path(path).read_text())
    keys = {'version', 'docker', 'image', 'auth_file', 'clean_runtime_review'}
    if not isinstance(config, dict) or set(config) != keys or config.get('version') != '1':
        raise ValueError('development runtime requires version 1 and explicit docker/image/auth_file/clean_runtime_review')
    if not isinstance(config['image'], str) or not IMAGE_ID.fullmatch(config['image']):
        raise ValueError('development image must be pinned by a full local sha256 image ID')
    if not isinstance(config['clean_runtime_review'], str) or not config['clean_runtime_review'].strip():
        raise ValueError('a clean runtime review record is required')
    config['docker'] = local_path(config['docker'], 'docker', executable=True)
    config['auth_file'] = local_path(config['auth_file'], 'auth_file')
    return config


def docker_environment():
    # No inherited Docker context, API key, cloud credentials, HOME or CLI config.
    return {key: value for key, value in os.environ.items() if key in ('PATH', 'LANG', 'LC_ALL', 'TZ')}


def docker_command(docker, args):
    # Never select a remote daemon or a user-configured Docker context implicitly.
    return [docker, '--host', 'unix:///var/run/docker.sock', *args]


def docker_run(docker, args, *, timeout=20, env=None):
    try:
        result = subprocess.run(docker_command(docker, args), capture_output=True, text=True,
                                env=env or docker_environment(), timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'Docker {args[0]} exceeded its {timeout}s diagnostic timeout') from error
    if result.returncode:
        raise ValueError(f'Docker {args[0]} failed: {redact(result.stderr[-2000:])}')
    return result.stdout


def preflight_run(docker, args, *, timeout=20, env=None):
    """Named no-auth controls always remove their container, including CLI timeout."""
    name = 'po-development-preflight-' + uuid.uuid4().hex
    failure = None
    try:
        return docker_run(docker, ['run', '--name', name, *args], timeout=timeout, env=env)
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            result = subprocess.run(docker_command(docker, ['rm', '-f', name]),
                capture_output=True, text=True, env=docker_environment(), timeout=20)
            missing = bool(re.fullmatch(r'(?:Error response from daemon: )?No such container: ' + re.escape(name), result.stderr.strip()))
            if result.returncode and not missing:
                raise ValueError('preflight cleanup failed for ' + name + ': ' + redact(result.stderr[-2000:]))
        except (OSError, ValueError, subprocess.TimeoutExpired) as cleanup_error:
            message = 'preflight cleanup required for ' + name + ': ' + str(cleanup_error)
            if failure is not None:
                raise ValueError(str(failure) + '; ' + message) from failure
            raise ValueError(message) from cleanup_error


def inspect_image(docker, image):
    result = json.loads(docker_run(docker, ['image', 'inspect', image]))
    if not isinstance(result, list) or len(result) != 1 or result[0].get('Id') != image:
        raise ValueError('prepared image identity does not match the configured image')
    config = result[0].get('Config') or {}
    if config.get('Volumes') or config.get('OnBuild'):
        raise ValueError('prepared image must not declare volumes or build hooks')
    for value in config.get('Env') or []:
        name = value.split('=', 1)[0]
        if name not in IMAGE_ENVIRONMENT:
            raise ValueError(f'prepared image has unreviewed environment name: {name}')
    return {'id': image, 'environment_names': sorted(v.split('=', 1)[0] for v in config.get('Env') or [])}


def load_allowlist(path=NETWORK_ALLOWLIST):
    raw = Path(path).read_text()
    # `network_measurement draft-allowlist` leaves TODO markers; enforcement must
    # refuse a draft until the owner has reviewed and removed every one.
    if 'TODO' in raw:
        raise ValueError(f'network allowlist {path} still contains a TODO marker; the owner must review and remove it')
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise ValueError('network allowlist must be a JSON object')
    domains = document.get('domains')
    if (document.get('version') != '1' or not isinstance(domains, list)
            or any(not isinstance(v, str) or normalise_host(v.removeprefix('*.')) != v.removeprefix('*.') for v in domains)):
        raise ValueError('network allowlist must be version 1 with lowercase domain names')
    return {'domains': domains, 'model_domains': model_domains(document, domains)}


def model_domains(document, domains):
    """Hosts only the Codex process may reach (with the per-run proxy token); never commands."""
    models = document.get('model_domains')
    if (not isinstance(models, list) or not models
            or any(not isinstance(v, str) or normalise_host(v) != v for v in models)):
        raise ValueError('network allowlist needs model_domains: exact lowercase domain names, no wildcards')
    for entry in domains:
        parent = entry.removeprefix('*.')
        if any(m == entry or (entry.startswith('*.') and (m == parent or m.endswith('.' + parent))) for m in models):
            raise ValueError(f'{entry} in domains would let commands reach a model domain')
    return models


def egress_summary(log):
    """Hosts the proxy allowed and refused, from its JSON-lines decision log."""
    # `allowed` is the policy decision; `connected` means the upstream connection opened.
    hosts = {'allowed': set(), 'refused': set(), 'connected': set(), 'credentialed': set()}
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('decision') in hosts and isinstance(event.get('host'), str):
            hosts[event['decision']].add(event['host'])
            # Requested with this run's model token, so by the Codex process itself.
            if event.get('credential') == 'valid':
                hosts['credentialed'].add(event['host'])
    return {key + '_hosts': sorted(value) for key, value in hosts.items()}


def runtime_user():
    uid, gid = os.getuid(), os.getgid()
    if uid == 0:
        uid = gid = 1000
    return f'{uid}:{gid}'


def restrictions(*, nested_sandbox=False):
    uid, gid = runtime_user().split(':')
    policy = ['--security-opt', 'seccomp=' + str(SANDBOX_POLICY)] if nested_sandbox else []
    executable = 'exec,' if nested_sandbox else ''
    return [*policy, '--pull', 'never', '--init', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--user', f'{uid}:{gid}',
            '--pids-limit', '512', '--memory', '4g', '--memory-swap', '4g',
            '--cpus', '2', '--tmpfs', f'/tmp:rw,{executable}nosuid,nodev,size=1g,mode=1777',
            '--tmpfs', f'/home/developer:rw,{executable}nosuid,nodev,size=1g,uid={uid},gid={gid},mode=700',
            '--env', 'HOME=/home/developer', '--env', 'CODEX_HOME=/home/developer/.codex',
            '--workdir', '/workspace']


def memory_bytes(value):
    match = re.fullmatch(r'\s*([\d.]+)\s*(B|KiB|MiB|GiB|TiB|kB|MB|GB)\s*/.*', value)
    factors = {'B':1, 'KiB':1024, 'MiB':1024**2, 'GiB':1024**3, 'TiB':1024**4,
               'kB':1000, 'MB':1000**2, 'GB':1000**3}
    return int(float(match[1]) * factors[match[2]]) if match else None


def cleanup_runtime(allocation_path, config_path, output):
    """Explicit orphan cleanup; append evidence without changing the original attempt."""
    allocation_path = Path(allocation_path)
    if allocation_path.is_symlink() or not allocation_path.is_file():
        raise ValueError('runtime allocation must be a retained regular file')
    allocation_path = allocation_path.resolve()
    raw = allocation_path.read_bytes()
    allocation = json.loads(raw)
    config = json.loads(Path(config_path).read_text())
    # Authentication is intentionally irrelevant to removal of a retained container.
    if (not isinstance(config, dict) or config.get('version') != '1'
            or not isinstance(config.get('image'), str) or not IMAGE_ID.fullmatch(config['image'])):
        raise ValueError('cleanup requires frozen version 1 Docker/image configuration')
    docker = local_path(config.get('docker'), 'docker', executable=True)
    name = allocation.get('container') if isinstance(allocation, dict) else None
    if not isinstance(name,str) or not re.fullmatch(r'po-development-[0-9a-f]{32}',name):
        raise ValueError('runtime allocation has an invalid development container identity')
    argv = docker_command(docker,['rm','-f',name])
    if allocation.get('image') != config['image'] or allocation.get('cleanup_argv') != argv:
        raise ValueError('runtime allocation image/cleanup command differs from frozen configuration')
    # Allocations before #75 have no egress proxy or network.
    token = name.removeprefix('po-development-')
    egress = allocation.get('egress')
    if egress is not None and egress != {'container':'po-development-egress-'+token, 'network':'po-development-net-'+token}:
        raise ValueError('runtime allocation has an invalid egress identity')
    egress_argvs = [['rm','-f',egress['container']], ['network','rm',egress['network']]] if egress else []
    output = Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    record = {'schema_version':1,'outcome':'cleanup_error','allocation':str(allocation_path),
              'allocation_sha256':hashlib.sha256(raw).hexdigest(),'container':name,
              'image':config['image'],'argv':argv,'exit_status':None,'absent_before_cleanup':None,
              'stdout_path':str(output/'docker.stdout'),'stderr_path':str(output/'docker.stderr'),
              'started_at':time.time()}
    started = time.monotonic()
    write_json(output/'cleanup.json',record)
    stdout, stderr = '', ''
    try:
        result = subprocess.run(argv,capture_output=True,text=True,env=docker_environment(),timeout=20)
        stdout, stderr = result.stdout,result.stderr
        record['exit_status'] = result.returncode
        missing = bool(re.fullmatch(r'(?:Error response from daemon: )?No such container: '+re.escape(name),stderr.strip()))
        if result.returncode == 0 or missing:
            record['egress_argvs'] = [docker_command(docker, v) for v in egress_argvs]
            for egress_argv in egress_argvs:
                remove(docker, egress_argv)
            record.update(outcome='removed',absent_before_cleanup=missing)
        else:
            record['error'] = 'Docker cleanup failed; see retained docker.stderr'
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ''
        stderr = error.stderr or ''
        record['error'] = 'Docker cleanup exceeded its 20s diagnostic timeout'
    except (OSError,ValueError,KeyboardInterrupt) as error:
        record['error'] = str(error) or 'cleanup controller interrupted'
    finally:
        for path, data in ((output/'docker.stdout',stdout),(output/'docker.stderr',stderr)):
            path.write_text(redact(data.decode(errors='replace') if isinstance(data,bytes) else data))
        record.update(finished_at=time.time(),elapsed_seconds=time.monotonic()-started)
        write_json(output/'cleanup.json',record)
    return record


class DevelopmentRuntime:
    def __init__(self, config_path, output, source, *, egress='allowlist'):
        if egress not in EGRESS_MODES:
            raise ValueError(f'egress mode must be one of {EGRESS_MODES}')
        self.egress = egress
        self.allowlist = load_allowlist() if egress == 'allowlist' else {'domains': [], 'model_domains': []}
        self.config = load_config(config_path)
        c = self.config
        output, source = Path(output).resolve(), Path(source).resolve()
        if any(v in str(output) for v in (',', '\n', '\r', '\x00')):
            raise ValueError('development output path cannot contain commas/newlines')
        researcher = Path(__file__).resolve().parents[1]
        if (output == researcher or output.is_relative_to(researcher) or researcher.is_relative_to(output)
                or output == source or source.is_relative_to(output)):
            raise ValueError('development output must be separate from research and task packages')
        self.image = inspect_image(c['docker'], c['image'])
        # This probe runs tools, never a model. Fresh tmpfs home and no credentials.
        probe = ('test ! -e /AGENTS.md; test ! -e /AGENTS.override.md; '
                 'test ! -e /workspace/AGENTS.md; '
                 'command -v python; command -v node; command -v git; '
                 'python -c "import sqlite3, venv"; exec "$@"')
        version = preflight_run(c['docker'], ['--network', 'none', *restrictions(nested_sandbox=True),
                            '--entrypoint', '/bin/sh', c['image'], '-eu', '-c', probe, '--', 'codex', '--version'])
        codex_version = version.strip().splitlines()[-1] if version.strip() else None
        if not codex_version or not codex_version.startswith('codex-cli '):
            raise ValueError('prepared runtime did not report a Codex CLI version')
        # No authentication or candidate files are mounted. Failure is detected before
        # allocating a development attempt or contacting the model.
        # A stand-in model token reaches the Codex process exactly as in `execute`; the
        # probe, run as a command, must not find it (#75). No network, so it goes nowhere.
        attest = preflight_run(c['docker'], ['--network', 'none',
            *restrictions(nested_sandbox=True), *proxy_environment('preflight.invalid'),
            '--env', MODEL_TOKEN_VARIABLE,
            '--tmpfs', '/workspace:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--tmpfs', '/outside-workspace:rw,nosuid,nodev,size=1m,mode=1777',
            '--entrypoint', '/bin/sh', c['image'], '-eu', '-c',
            'mkdir -p "$CODEX_HOME"; echo preflight-login > "$CODEX_HOME/auth.json"; '
            'touch /outside-workspace/outer-write; rm /outside-workspace/outer-write; ' + MODEL_PROXY_BOOT + 'exec "$@"',
            'po-runtime-preflight-v1',
            'codex', '--no-daemon', 'sandbox', '--permission-profile', 'development',
            *configuration_args({**workspace_permission_settings(), **command_settings('preflight.invalid')}),
            '--cd', '/workspace', '--', 'python', '-c', SANDBOX_PROBE], timeout=60,
            env={**docker_environment(), MODEL_TOKEN_VARIABLE: secrets.token_hex(32)})
        try:
            attestation = json.loads(attest)
        except (TypeError, ValueError) as error:
            raise ValueError('nested Codex sandbox preflight did not report valid evidence') from error
        paths = attestation.get('symlink_targets') if isinstance(attestation,dict) else None
        if (not isinstance(attestation,dict) or attestation.get('sandbox') != 'workspace-write' or not isinstance(paths,list)
                or not paths or any(not isinstance(v,str) or not re.fullmatch(r'/usr/local/bin/python(?:3(?:\.[0-9]+)?)?',v) for v in paths)):
            raise ValueError('nested Codex sandbox preflight returned invalid runtime interpreter paths')
        self.snapshot_binding = {'image':c['image'],'symlink_targets':sorted(set(paths))}
        self.version = {'sandbox_policy_sha256':hashlib.sha256(SANDBOX_POLICY.read_bytes()).hexdigest(),
                        'temporary_filesystems':'exec,nosuid,nodev',
                        'snapshot_binding':self.snapshot_binding, 'permission_settings':workspace_permission_settings(), 'codex':codex_version, 'runtime_user':runtime_user(),
                        'command_environment':command_environment('<egress proxy>'),
                        'image':c['image'], 'adapter':ADAPTER, 'web_search':WEB_SEARCH,
                        'egress':{'mode':egress, 'port':EGRESS_PORT,
                                  'allowlist_sha256':hashlib.sha256(NETWORK_ALLOWLIST.read_bytes()).hexdigest() if egress == 'allowlist' else None,
                                  'proxy_sha256':hashlib.sha256(EGRESS_PROXY.read_bytes()).hexdigest(),
                                  'model_credential':MODEL_CREDENTIAL}}

    def execute(self, workspace, request, stdout, stderr):
        c = self.config
        workspace = Path(workspace).resolve()
        if any(v in str(workspace) for v in (',', '\n', '\r')):
            raise ValueError('workspace path cannot contain commas/newlines')
        if not workspace.is_dir():
            raise ValueError(f'development workspace does not exist: {workspace}')
        forbid_foreign_git(workspace)
        # The controller and Docker daemon can have different mount namespaces
        # (notably Snap Docker's private /tmp). Probe this exact bind without
        # credentials or a model request before allocating an attempt.
        try:
            preflight_run(c['docker'], ['--network', 'none', *restrictions(nested_sandbox=True),
                '--mount', f'type=bind,src={workspace},dst=/workspace,readonly',
                '--entrypoint', '/bin/sh', c['image'], '-eu', '-c', 'test -d /workspace'])
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(f'Docker daemon cannot mount workspace {workspace}: {error}. '
                             'Choose a run root visible to the Docker daemon.') from error
        token = uuid.uuid4().hex
        name = 'po-development-' + token
        egress = {'container':'po-development-egress-' + token, 'network':'po-development-net-' + token}
        boot = ('mkdir -p "$CODEX_HOME"; cp /run/subscription-auth.json "$CODEX_HOME/auth.json"; '
                'chmod 600 "$CODEX_HOME/auth.json"; '
                'login_status="$(codex login status 2>&1)" || '
                '{ echo "Subscription login status unavailable" >&2; exit 1; }; '
                'case "$login_status" in *"Logged in using ChatGPT"*) ;; '
                '*) echo "ChatGPT subscription authentication required" >&2; exit 1 ;; esac; '
                'unset login_status; ' + MODEL_PROXY_BOOT + 'exec "$@"')
        codex = ['codex', '--no-daemon', 'exec', '--ephemeral', '--ignore-user-config',
                 '--ignore-rules', '--skip-git-repo-check', '--json',
                 '--cd', '/workspace']
        settings = {**workspace_permission_settings(), 'approval_policy':'never',
                    'web_search':WEB_SEARCH, 'model_provider':'openai', 'cli_auth_credentials_store':'file'}
        codex.extend(configuration_args(settings))
        codex.append('-')
        allocation_path = workspace.parent / 'runtime.json'
        egress_log = workspace.parent / 'egress.jsonl'
        removals = [['rm', '-f', name], ['rm', '-f', egress['container']], ['network', 'rm', egress['network']]]
        allocation = {'schema_version':1,'adapter':ADAPTER,'container':name,'egress':egress,
                      'image':c['image'],'sandbox_policy_sha256':self.version['sandbox_policy_sha256'],'state':'allocated','allocated_at':time.time(),
                      'cleanup_argv':docker_command(c['docker'],['rm','-f',name]),
                      'egress_cleanup_argvs':[docker_command(c['docker'],argv) for argv in removals[1:]],
                      'note':'If the controller dies, remove these containers and network before retrying; original workspace/logs must remain.'}
        # Outside the only writable bind mount, durable before creating any Docker resource.
        write_json(allocation_path,allocation)
        done, samples = threading.Event(), []

        def sample():
            while not done.is_set():
                try:
                    value = memory_bytes(docker_run(c['docker'], ['stats', '--no-stream', '--format', '{{.MemUsage}}', name], timeout=3).strip())
                    if value is not None:
                        samples.append(value)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
                done.wait(.5)

        sampler = threading.Thread(target=sample)
        evidence = {'argv': None, 'exit_status': None, 'memory': {}}
        # Never on a command line, in a log or in evidence: Docker reads it from its own environment.
        model_token = secrets.token_hex(32)
        try:
            try:
                proxy = self.start_egress(egress, model_token)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                evidence['error'] = 'egress setup failed before authentication or model: ' + str(error)
                proxy = None
            if proxy is not None:
                settings.update(command_settings(proxy))
                argv = docker_command(c['docker'], ['run', '-i', '--name', name, '--network', egress['network'],
                            *restrictions(nested_sandbox=True), *proxy_environment(proxy), '--env', MODEL_TOKEN_VARIABLE,
                            '--mount', f'type=bind,src={workspace},dst=/workspace',
                            '--mount', f'type=bind,src={c["auth_file"]},dst=/run/subscription-auth.json,readonly',
                            '--entrypoint', '/bin/sh', c['image'], '-eu', '-c', boot, '--',
                            *codex[:-1], *configuration_args(command_settings(proxy)), codex[-1]])
                sampler.start()
                evidence = execute(argv, workspace, request, stdout, stderr,
                                   env={**docker_environment(), MODEL_TOKEN_VARIABLE: model_token}, transform=redact)
        finally:
            done.set()
            if sampler.is_alive():
                sampler.join()
            try:
                egress_log.write_text(redact(docker_run(c['docker'], ['logs', egress['container']])))
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                evidence['egress_log_error'] = str(error)
            errors = []
            for argv in removals:
                try:
                    remove(c['docker'], argv)
                except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                    errors.append(str(error))
            if errors:
                evidence['cleanup_error'] = '; '.join(errors)
                allocation.update(state='cleanup_error',error=evidence['cleanup_error'])
            else:
                allocation.update(state='removed',removed_at=time.time())
            allocation['execution_exit_status'] = evidence.get('exit_status')
            write_json(allocation_path,allocation)
        evidence['memory']['scope'] = 'host Docker client process group only; excludes container agent/tools'
        evidence['container_memory'] = {'peak_sampled_bytes':max(samples) if samples else None,
            'method':'docker stats --no-stream MemUsage, sampled with a 0.5s pause between calls',
            'scope':'development container working set reported by Docker; all processes',
            'limitations':'formatted/rounded sampled values, not RSS or a guaranteed peak; brief processes may be missed'}
        evidence['codex'] = {'harness':'codex-cli', 'version':self.version['codex'],
            'access_mode':'existing-chatgpt-subscription', 'authentication_verified':None,
            'authentication_guard':'before exec, require Codex login status to report Logged in using ChatGPT; raw status discarded',
            'model':None, 'reasoning_effort':None, 'requested_model':'default',
            'requested_reasoning_effort':'default', 'settings':settings, 'hosted_model_memory':None,
            'clean_runtime_review':c['clean_runtime_review'],
            'filesystem_boundary':'disposable container; only workspace and subscription auth file are mounted'}
        log = egress_log.read_text() if egress_log.is_file() else ''
        evidence['egress'] = {'mode':self.egress, 'log':str(egress_log), **self.version['egress'],
                              **egress_summary(log)}
        evidence['runtime'] = {'image':self.image, 'container':name, 'adapter':ADAPTER,
                               'temporary_filesystems':self.version['temporary_filesystems'],
                               'user':runtime_user(),'sandbox_policy_sha256':self.version['sandbox_policy_sha256'],
                               'allocation':str(allocation_path),'cleanup_state':allocation['state'],
                               'network':NETWORK_DESCRIPTION[self.egress]}
        return evidence

    def start_egress(self, egress, model_token=''):
        """Create the internal network and the proxy that is its only route out; return the proxy address.

        The proxy reads `model_token` from its environment: it is the credential that
        `model_domains` require, and never appears on a command line.
        """
        c = self.config
        docker_run(c['docker'], ['network', 'create', '--driver', 'bridge', '--internal', '--ipv6=false',
                                 egress['network']])
        network = json.loads(docker_run(c['docker'], ['network', 'inspect', egress['network']]))[0]
        if network.get('Internal') is not True:
            raise ValueError('development network is not internal')
        docker_run(c['docker'], ['run', '--detach', '--name', egress['container'], '--network', 'bridge',
                                 *restrictions(), '--env', MODEL_TOKEN_VARIABLE, '--entrypoint', 'python', c['image'],
                                 '-I', '-S', '-c', EGRESS_PROXY.read_text(), self.egress,
                                 json.dumps(self.allowlist), str(EGRESS_PORT)],
                   env={**docker_environment(), MODEL_TOKEN_VARIABLE: model_token})
        docker_run(c['docker'], ['network', 'connect', egress['network'], egress['container']])
        status = json.loads(docker_run(c['docker'], ['inspect', egress['container']]))[0]
        return status['NetworkSettings']['Networks'][egress['network']]['IPAddress']



def proxy_environment(address):
    url = f'http://{address}:{EGRESS_PORT}'
    values = {'HTTPS_PROXY':url, 'HTTP_PROXY':url, 'https_proxy':url, 'http_proxy':url,
              'NO_PROXY':'localhost,127.0.0.1,::1', 'no_proxy':'localhost,127.0.0.1,::1'}
    return [item for key, value in values.items() for item in ('--env', f'{key}={value}')]


def remove(docker, argv):
    """Remove a container or network, treating one that is already gone as removed."""
    result = subprocess.run(docker_command(docker, argv), capture_output=True, text=True,
                            env=docker_environment(), timeout=20)
    name = re.escape(argv[-1])
    missing = re.fullmatch(rf'(?:Error response from daemon: )?(?:No such (?:container|network): {name}|network {name} not found)',
                           result.stderr.strip())
    if result.returncode and not missing:
        raise ValueError(f'Docker {" ".join(argv[:2])} failed: {redact(result.stderr[-2000:])}')
