"""Ordinary subscription Codex in a separately prepared, disposable Docker runtime."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid

from .codex import redact
from .execution import execute
from .resume import write_json


CHECKOUT = Path(__file__).resolve().parents[1]
SANDBOX_POLICY = CHECKOUT / 'fixtures/development/seccomp_profile.json'


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
print(json.dumps({'sandbox':'workspace-write','symlink_targets':sorted(paths)}))
""".replace('CHECKOUT_INSTRUCTIONS', repr(str(CHECKOUT / 'AGENTS.md')))


def workspace_permission_settings():
    # Explicit profile selection and legacy network overrides do not compose in
    # Codex 0.169.0. Use one supported workspace-derived profile in every path.
    return {'default_permissions':'development',
            'permissions.development.extends':':workspace',
            'permissions.development.network.enabled':True}


def configuration_args(settings):
    return [item for key,value in settings.items() for item in ('-c',key+'='+json.dumps(value))]


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


def docker_run(docker, args, *, timeout=20):
    try:
        result = subprocess.run(docker_command(docker, args), capture_output=True, text=True,
                                env=docker_environment(), timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'Docker {args[0]} exceeded its {timeout}s diagnostic timeout') from error
    if result.returncode:
        raise ValueError(f'Docker {args[0]} failed: {redact(result.stderr[-2000:])}')
    return result.stdout


def preflight_run(docker, args, *, timeout=20):
    """Named no-auth controls always remove their container, including CLI timeout."""
    name = 'po-development-preflight-' + uuid.uuid4().hex
    failure = None
    try:
        return docker_run(docker, ['run', '--name', name, *args], timeout=timeout)
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
            record.update(outcome='removed',absent_before_cleanup=missing)
        else:
            record['error'] = 'Docker cleanup failed; see retained docker.stderr'
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ''
        stderr = error.stderr or ''
        record['error'] = 'Docker cleanup exceeded its 20s diagnostic timeout'
    except (OSError,KeyboardInterrupt) as error:
        record['error'] = str(error) or 'cleanup controller interrupted'
    finally:
        for path, data in ((output/'docker.stdout',stdout),(output/'docker.stderr',stderr)):
            path.write_text(redact(data.decode(errors='replace') if isinstance(data,bytes) else data))
        record.update(finished_at=time.time(),elapsed_seconds=time.monotonic()-started)
        write_json(output/'cleanup.json',record)
    return record


class DevelopmentRuntime:
    def __init__(self, config_path, output, source):
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
        attest = preflight_run(c['docker'], ['--network', 'none',
            *restrictions(nested_sandbox=True),
            '--tmpfs', '/workspace:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--tmpfs', '/outside-workspace:rw,nosuid,nodev,size=1m,mode=1777',
            '--entrypoint', '/bin/sh', c['image'], '-eu', '-c',
            'mkdir -p "$CODEX_HOME"; touch /outside-workspace/outer-write; rm /outside-workspace/outer-write; exec "$@"', 'po-runtime-preflight-v1',
            'codex', '--no-daemon', 'sandbox', '--permission-profile', 'development',
            *configuration_args(workspace_permission_settings()), '--cd', '/workspace', '--', 'python', '-c', SANDBOX_PROBE], timeout=60)
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
                        'image':c['image'], 'adapter':'docker-development-v2'}

    def execute(self, workspace, request, stdout, stderr):
        c = self.config
        workspace = Path(workspace).resolve()
        if any(v in str(workspace) for v in (',', '\n', '\r')):
            raise ValueError('workspace path cannot contain commas/newlines')
        if not workspace.is_dir():
            raise ValueError(f'development workspace does not exist: {workspace}')
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
        name = 'po-development-' + uuid.uuid4().hex
        boot = ('mkdir -p "$CODEX_HOME"; cp /run/subscription-auth.json "$CODEX_HOME/auth.json"; '
                'chmod 600 "$CODEX_HOME/auth.json"; '
                'login_status="$(codex login status 2>&1)" || '
                '{ echo "Subscription login status unavailable" >&2; exit 1; }; '
                'case "$login_status" in *"Logged in using ChatGPT"*) ;; '
                '*) echo "ChatGPT subscription authentication required" >&2; exit 1 ;; esac; '
                'unset login_status; exec "$@"')
        codex = ['codex', '--no-daemon', 'exec', '--ephemeral', '--ignore-user-config',
                 '--ignore-rules', '--skip-git-repo-check', '--json',
                 '--cd', '/workspace']
        settings = {**workspace_permission_settings(), 'approval_policy':'never',
                    'web_search':'live', 'model_provider':'openai', 'cli_auth_credentials_store':'file'}
        codex.extend(configuration_args(settings))
        codex.append('-')
        argv = docker_command(c['docker'], ['run', '-i', '--name', name, '--network', 'bridge',
                    *restrictions(nested_sandbox=True), '--mount', f'type=bind,src={workspace},dst=/workspace',
                    '--mount', f'type=bind,src={c["auth_file"]},dst=/run/subscription-auth.json,readonly',
                    '--entrypoint', '/bin/sh', c['image'], '-eu', '-c', boot, '--', *codex])
        allocation_path = workspace.parent / 'runtime.json'
        allocation = {'schema_version':1,'adapter':'docker-development-v2','container':name,
                      'image':c['image'],'sandbox_policy_sha256':self.version['sandbox_policy_sha256'],'state':'allocated','allocated_at':time.time(),
                      'cleanup_argv':docker_command(c['docker'],['rm','-f',name]),
                      'note':'If the controller dies, remove this container before retrying; original workspace/logs must remain.'}
        # Outside the only writable bind mount, durable before starting Docker.
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
        sampler.start()
        evidence = {}
        try:
            evidence = execute(argv, workspace, request, stdout, stderr,
                               env=docker_environment(), transform=redact)
        finally:
            done.set()
            sampler.join()
            try:
                docker_run(c['docker'], ['rm', '-f', name])
                allocation.update(state='removed',removed_at=time.time())
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                evidence['cleanup_error'] = str(error)
                allocation.update(state='cleanup_error',error=str(error))
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
        evidence['runtime'] = {'image':self.image, 'container':name, 'adapter':'docker-development-v2',
                               'temporary_filesystems':self.version['temporary_filesystems'],
                               'user':runtime_user(),'sandbox_policy_sha256':self.version['sandbox_policy_sha256'],
                               'allocation':str(allocation_path),'cleanup_state':allocation['state'],
                               'network':'bridge; ordinary development network access'}
        return evidence
