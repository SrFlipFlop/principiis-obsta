"""Independent AI security review in the isolated reviewer runtime.

Untrusted application probes must use the restricted evaluation runner, never host
execution. Reviewer claims are retained unresolved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

from .development_runtime import DevelopmentRuntime, load_config
from .resource import token_usage
from .snapshot import inventory, validate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def investigate(args):
    snapshot, primary = Path(args.snapshot).resolve(), Path(args.primary).resolve()
    output = Path(args.output).resolve()
    if not snapshot.is_dir() or not primary.is_file():
        raise ValueError('retained snapshot and primary results are required')
    if output == snapshot or snapshot in output.parents or output in snapshot.parents:
        raise ValueError('investigation output must be outside retained snapshot')
    config_path, prompt_path = Path(args.config).resolve(), Path(args.prompt).resolve()
    config = json.loads(config_path.read_text())
    for field in ('version', 'model', 'settings', 'timeout_seconds', 'evidence', 'runtime_config'):
        if field not in config:
            raise ValueError('missing evaluator configuration: ' + field)
    if 'agent' in config or 'codex_config' in config:
        raise ValueError('investigation requires the isolated reviewer runtime; host agents are not supported')
    if config['evidence'] != {}:
        raise ValueError('containerized investigation requires reviewed restricted proof support; leave claims unresolved')
    if config['timeout_seconds'] is not None:
        raise ValueError('isolated Codex reviewer uses unlimited timeout; set timeout_seconds null')
    reviewer = load_config(config['runtime_config'])
    if snapshot.with_suffix('.json').exists():
        validate(snapshot, runtime_image=reviewer['image'])
    else:
        # Historical investigation fixtures may lack a retained manifest. They
        # still require self-contained links before any consumer runs.
        inventory(snapshot)
    prompt = prompt_path.read_text()
    original = digest(primary)
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    shutil.copyfile(config_path, output / 'config.json')
    shutil.copyfile(config['runtime_config'], output / 'reviewer-runtime.json')
    (output / 'prompt.txt').write_text(prompt)
    report = {'schema_version': 1, 'stage': 'independent_evaluation', 'status': 'running',
              'primary': {'path': str(primary), 'sha256': original},
              'snapshot': str(snapshot), 'config_sha256': digest(config_path),
              'prompt_version': args.prompt_version, 'prompt_sha256': digest(prompt_path),
              'claims': [], 'verified_root_causes': [], 'tools': [],
              'resources': {'scope': 'independent_evaluation', 'reported_tokens': None,
                            'hosted_model_memory_bytes': None,
                            'measurement_refs': ['agent'], 'elapsed_seconds': None}}
    started = time.monotonic()
    try:
        workspace = output / 'workspace'
        shutil.copytree(snapshot, workspace, symlinks=True)
        adapter = DevelopmentRuntime(output / 'reviewer-runtime.json', output, snapshot)
        with (output / 'agent.stdout').open('w') as stdout, (output / 'agent.stderr').open('w') as stderr:
            agent = adapter.execute(workspace, prompt, stdout, stderr)
        agent.update(stdout_ref='agent.stdout', stderr_ref='agent.stderr',
                     tokens=token_usage(output / 'agent.stdout'))
        messages = []
        for line in (output / 'agent.stdout').read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get('type') == 'item.completed':
                item = event.get('item', {})
                if isinstance(item, dict) and item.get('type') == 'agent_message':
                    messages.append(item.get('text', ''))
        response = messages[-1] if messages else ''
        (output / 'agent.final.txt').write_text(response)
        report['agent'] = agent
        report['resources']['reported_tokens'] = agent.get('tokens')
        if agent.get('cleanup_error'):
            raise ValueError('evaluator runtime cleanup failed; inspect retained allocation')
        if agent['exit_status'] != 0:
            raise ValueError('evaluator agent failed')
        claims = json.loads(response)['claims']
        if not isinstance(claims, list):
            raise ValueError('claims must be an array')
        for claim in claims:
            if not isinstance(claim, dict) or any(not isinstance(claim.get(k), str) or not claim[k] for k in ('id', 'root_cause')):
                raise ValueError('claims require nonempty id and root_cause')
            # Reviewer claims stay unresolved until restricted proof support is reviewed.
            report['claims'].append({'id': claim['id'], 'root_cause': claim['root_cause'],
                                     'claim': claim, 'status': 'unresolved', 'evidence_ref': None})
        report['status'] = 'completed'
    except (ValueError, KeyError, TypeError, OSError, KeyboardInterrupt) as error:
        report['status'] = 'evaluator_error'
        report['error'] = str(error) or 'controller interrupted'
    finally:
        report['resources']['elapsed_seconds'] = time.monotonic() - started
        report['primary']['unchanged'] = digest(primary) == original
        (output / 'investigation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('snapshot', 'primary', 'config', 'prompt', 'prompt-version', 'output'):
        parser.add_argument('--' + option, required=True)
    args = parser.parse_args()
    try:
        investigate(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
