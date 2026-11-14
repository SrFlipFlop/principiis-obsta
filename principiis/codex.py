"""Ordinary Codex subprocess adapter; not a host filesystem sandbox."""
import json
import os
import re
from pathlib import Path
import subprocess
from .execution import execute


class Codex:
    def __init__(self, config_path, output, source):
        self.config = json.loads(Path(config_path).read_text())
        c = self.config
        required = {'executable', 'codex_home', 'model', 'reasoning_effort', 'sandbox',
                    'approval_policy', 'network_access', 'web_search', 'clean_runtime_review'}
        if set(c) != required or any(not c[key] for key in required - {'network_access'}):
            raise ValueError('Codex configuration requires explicit settings and clean runtime review')
        if c['sandbox'] != 'workspace-write' or c['approval_policy'] not in ('never', 'on-request'):
            raise ValueError('ordinary adapter requires workspace-write and explicit approval policy')
        if not isinstance(c['network_access'], bool) or c['web_search'] not in ('live', 'cached', 'disabled'):
            raise ValueError('invalid network or web search setting')
        self.home = Path(c['codex_home']).resolve()
        if not self.home.is_dir():
            raise ValueError('existing separately provisioned clean CODEX_HOME required')
        # Do not inspect credentials. Authentication is owned by the operator.
        forbidden = ['AGENTS.md', 'AGENTS.override.md', 'skills', 'hooks', 'memories', 'memory',
                     'sessions', 'archived_sessions', 'history.jsonl', 'plugins', 'agents']
        if any((self.home / name).exists() for name in forbidden):
            raise ValueError('CODEX_HOME contains instructions, skills, hooks or external session memory')
        output = Path(output).resolve()
        source = Path(source).resolve()
        researcher = Path(__file__).resolve().parents[1]
        if output == researcher or researcher in output.parents or output == source or output in source.parents:
            raise ValueError('development output must be separate from research and task packages')
        for ancestor in (output, *output.parents):
            if any((ancestor / name).exists() for name in ('AGENTS.md', 'AGENTS.override.md')) or any(
                    (ancestor / name).is_dir() and any((ancestor / name).iterdir()) for name in ('.agents', '.codex')):
                raise ValueError('development workspace has researcher instruction/config ancestors')
        self.env = {key: value for key, value in os.environ.items()
                    if key in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'TERM', 'TMPDIR')}
        self.env['CODEX_HOME'] = str(self.home)
        version = subprocess.run([c['executable'], '--version'], env=self.env, capture_output=True, text=True)
        if version.returncode:
            raise ValueError('cannot identify Codex executable version')
        self.version = version.stdout.strip() or None

    def execute(self, workspace, request, stdout, stderr):
        c = self.config
        runtime_home = workspace.parent / 'runtime-home'
        runtime_home.mkdir()
        env = dict(self.env, HOME=str(runtime_home))
        argv = [c['executable'], '--no-daemon', 'exec', '--ephemeral', '--ignore-user-config',
                '--ignore-rules', '--skip-git-repo-check', '--json', '--model', c['model'],
                '--sandbox', c['sandbox'], '--cd', str(workspace)]
        settings = {'model_reasoning_effort': c['reasoning_effort'], 'approval_policy': c['approval_policy'],
                    'sandbox_workspace_write.network_access': c['network_access'], 'web_search': c['web_search'],
                    'model_provider': 'openai',
                    'cli_auth_credentials_store': 'file'}
        for key, value in settings.items():
            argv.extend(['-c', key + '=' + json.dumps(value)])
        argv.append('-')
        evidence = {'argv': argv, 'exit_status': None, 'codex': {
            'harness': 'codex-cli', 'version': self.version,
            'access_mode': 'existing-chatgpt-subscription', 'authentication_verified': None,
            'model': c['model'], 'settings': settings, 'clean_runtime_review': c['clean_runtime_review'],
            'reported_usage': None, 'hosted_model_memory': None,
            'filesystem_boundary': 'normal Codex permissions; host reads are not isolated'}}
        evidence.update(execute(argv, workspace, request, stdout, stderr, env=env, transform=redact))
        return evidence


def redact(value):
    """Remove recognizable credential fields without reading credential stores."""
    value = re.sub(r'(?i)("(?:api_key|access_token|refresh_token|id_token|authorization|password)"\s*:\s*)"[^"\n]*"', r'\1"[REDACTED]"', value)
    value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[REDACTED]', value)
    return re.sub(r'\bsk-[A-Za-z0-9_-]+', '[REDACTED]', value)
