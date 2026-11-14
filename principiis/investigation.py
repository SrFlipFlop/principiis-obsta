"""Independent supplemental investigation; trusted controller commands only.

Untrusted application probes must use the restricted evaluation runner, never host
execution. This orchestration subprocess boundary is not an OS sandbox.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from .execution import execute as measured_execute
from .resource import token_usage


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(argv, cwd, payload, timeout, output, prefix):
    stdout_path = output / (prefix + '.stdout')
    stderr_path = output / (prefix + '.stderr')
    with stdout_path.open('w') as stdout, stderr_path.open('w') as stderr:
        record = measured_execute(argv, cwd, payload, stdout, stderr,
                                  env={'PATH': '/usr/local/bin:/usr/bin:/bin'}, timeout=timeout)
    record.update(stdout_ref=stdout_path.name, stderr_ref=stderr_path.name,
                  tokens=token_usage(stdout_path))
    return record, stdout_path.read_text()


def investigate(args):
    snapshot, primary = Path(args.snapshot).resolve(), Path(args.primary).resolve()
    output = Path(args.output).resolve()
    if not snapshot.is_dir() or not primary.is_file():
        raise ValueError('retained snapshot and primary results are required')
    if output == snapshot or snapshot in output.parents or output in snapshot.parents:
        raise ValueError('investigation output must be outside retained snapshot')
    config_path, prompt_path = Path(args.config).resolve(), Path(args.prompt).resolve()
    config = json.loads(config_path.read_text())
    for field in ('version', 'model', 'settings', 'agent', 'timeout_seconds', 'evidence'):
        if field not in config:
            raise ValueError('missing evaluator configuration: ' + field)
    if not isinstance(config['evidence'], dict) or any(
            not isinstance(v, dict) or not isinstance(v.get('root_cause'), str) or not v['root_cause']
            or not isinstance(v.get('scope'), str) or not v['scope'] or 'argv' not in v
            for v in config['evidence'].values()):
        raise ValueError('evidence requires operator-declared root cause, scope and argv')
    commands = [config['agent'], *[v['argv'] for v in config['evidence'].values()]]
    if any(not isinstance(c, list) or not c or any(not isinstance(v, str) or not v for v in c) for c in commands):
        raise ValueError('commands must be nonempty argv arrays')
    if not isinstance(config['timeout_seconds'], (int, float)) or config['timeout_seconds'] <= 0:
        raise ValueError('positive timeout required')
    prompt = prompt_path.read_text()
    original = digest(primary)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(config_path, output / 'config.json')
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
        with tempfile.TemporaryDirectory(prefix='principiis-investigation-') as temporary:
            workspace = Path(temporary) / 'checkpoint'
            shutil.copytree(snapshot, workspace, symlinks=True)
            agent, response = execute(config['agent'], workspace,
                json.dumps({'prompt': prompt, 'prompt_version': args.prompt_version,
                            'checkpoint': str(workspace)}), config['timeout_seconds'], output, 'agent')
            report['agent'] = agent
            if agent['exit_status'] != 0:
                raise ValueError('evaluator agent failed')
            claims = json.loads(response)['claims']
            if not isinstance(claims, list):
                raise ValueError('claims must be an array')
            for number, claim in enumerate(claims):
                if not isinstance(claim, dict) or any(not isinstance(claim.get(k), str) or not claim[k] for k in ('id', 'root_cause')):
                    raise ValueError('claims require nonempty id and root_cause')
                finding = {'id': claim['id'], 'root_cause': claim['root_cause'],
                           'claim': claim, 'status': 'unresolved', 'evidence_ref': None}
                proof = config['evidence'].get(claim.get('evidence'))
                if proof and proof['root_cause'] == claim['root_cause']:
                    command = proof['argv']
                    finding['verification_scope'] = proof['scope']
                    prefix = 'evidence-' + str(number)
                    proof_workspace = Path(temporary) / prefix
                    shutil.copytree(snapshot, proof_workspace, symlinks=True)
                    evidence, text = execute(command, proof_workspace, json.dumps(claim),
                        config['timeout_seconds'], output, prefix)
                    evidence_path = output / (prefix + '.json')
                    evidence['stdout_sha256'] = digest(output / evidence['stdout_ref'])
                    evidence['stderr_sha256'] = digest(output / evidence['stderr_ref'])
                    evidence_path.write_text(json.dumps(evidence, indent=2))
                    finding['evidence_ref'] = evidence_path.name
                    report['tools'].append(evidence_path.name)
                    report['resources']['measurement_refs'].append(evidence_path.name)
                    if evidence['exit_status'] == 0:
                        try:
                            reproduced = json.loads(text)['reproduced']
                            if type(reproduced) is bool:
                                finding['status'] = 'verified' if reproduced else 'rejected'
                        except (ValueError, KeyError, TypeError):
                            pass
                report['claims'].append(finding)
            report['verified_root_causes'] = sorted({c['root_cause'] for c in report['claims'] if c['status'] == 'verified'})
            report['status'] = 'completed'
    except (ValueError, KeyError, TypeError) as error:
        report['status'] = 'evaluator_error'
        report['error'] = str(error)
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
