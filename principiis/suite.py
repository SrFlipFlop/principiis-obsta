"""Local suite orchestration and artifact reports. No implicit retries or model runs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import signal
import tempfile
import time
import uuid

from .__main__ import evaluator_scores, run_sequence
from .execution import execute
from .resource import inspect as inspect_resources
from .resume import write_json
from .snapshot import validate
from .task import check_argv


LIMITATIONS = [
    'Checkpoints within an application are dependent; denominators describe progress, not independent samples.',
    'Single runs do not estimate stochastic reliability or intervention efficacy.',
    'Application and stack effects are bundled; no model or harness causal effect is inferred.',
    'Primary scores retain their original evaluator; versioned reruns and supplementary claims are separate.',
    'Unstarted checkpoints and unknown/unassessable security never count as passes.',
    'Missing resource measurements and actual spending remain unknown; hosted model RAM is unobservable.',
]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite(path):
    path = Path(path).resolve()
    manifest = read(path)
    if not manifest.get('id') or not manifest.get('version'):
        raise ValueError('suite id and version required')
    applications = manifest.get('applications')
    if not isinstance(applications, list) or not applications:
        raise ValueError('suite applications required')
    identities = [app.get('id') for app in applications]
    if any(not isinstance(key, str) or not key or Path(key).name != key or key in ('.', '..') for key in identities) or len(set(identities)) != len(identities):
        raise ValueError('missing, unsafe or duplicate application identifiers')
    entries = []
    for app in applications:
        source = (path.parent / app['sequence']).resolve()
        sequence = read(source)
        entries.append({'id': app['id'], 'sequence_path': str(source), 'sequence_sha256': sha(source),
                        'sequence': {'id': sequence['id'], 'version': sequence['version']},
                        'condition': sequence['condition'], 'steps': [step['id'] for step in sequence['steps']]})
    return {'schema_version': 1, 'suite': {'id': manifest['id'], 'version': manifest['version']},
            'manifest_sha256': sha(path), 'applications': entries}


def select(state, requested):
    identities = [app['id'] for app in state['applications']]
    if requested and (len(set(requested)) != len(requested) or set(requested) - set(identities)):
        raise ValueError('unknown or duplicate application selection')
    return [app for app in state['applications'] if not requested or app['id'] in requested]


def run_suite(args, stop_requested=lambda: False):
    state = load_suite(args.suite)
    applications = select(state, args.application)
    output = Path(args.output).resolve()
    if args.retry_incomplete and not args.resume:
        raise ValueError('--retry-incomplete requires --resume')
    if args.resume:
        if read(output / 'suite.json') != state:
            raise ValueError('suite/sequence identity or content changed; create a new suite run')
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / 'suite.json', state)
    failures = []
    for app in applications:
        destination = output / 'applications' / app['id']
        try:
            if args.codex_config:
                from .codex import Codex
                executor = Codex(args.codex_config, destination, Path(app['sequence_path']).parent)
            else:
                executor = json.loads(args.executor)
            run_sequence(app['sequence_path'], executor, destination,
                         resume=(destination / 'sequence.json').exists(), retry_incomplete=args.retry_incomplete,
                         stop_requested=stop_requested)
        except (ValueError, OSError, TypeError, KeyError, KeyboardInterrupt) as error:
            # Controller failures are append-only suite evidence; other applications
            # may still run. Do not turn a rejected resume into an implicit retry.
            directory = output / 'controller-errors'
            directory.mkdir(exist_ok=True)
            write_json(directory / (uuid.uuid4().hex + '.json'), {'application': app['id'], 'error': str(error)})
            failures.append(str(error))
        if stop_requested():
            break
    if failures:
        raise ValueError('; '.join(failures))


def evaluate(args, stop_requested=lambda: False):
    output = Path(args.output).resolve()
    state = read(output / 'suite.json')
    for app in select(state, args.application):
        root = output / 'applications' / app['id']
        if not (root / 'sequence.json').exists():
            continue
        sequence = read(root / 'sequence.json')
        checkpoints = list(sequence['checkpoints'])
        active = sequence.get('active_attempt')
        if active:
            result_path = root / active['artifact'] / 'result.json'
            if result_path.exists() and read(result_path).get('completed'):
                checkpoints.append(active)
        for checkpoint in checkpoints:
            source = root / checkpoint['artifact']
            if checkpoint.get('outcome') == 'incomplete':
                continue
            snapshot = source / 'snapshot'
            destination = root / 'evaluations' / (str(time.time_ns()) + '-' + uuid.uuid4().hex)
            destination.mkdir(parents=True)
            record = {'application': app['id'], 'checkpoint': checkpoint['id'], 'attempt': None,
                      'primary': str(source / 'result.json'), 'primary_sha256': None,
                      'snapshot': str(snapshot), 'evaluator_version': args.evaluator_version,
                      'check': None, 'check_files': {},
                      'outcome': 'evaluator_error', 'functional': 'unassessable', 'security': 'unassessable', 'execution': {}}
            write_json(destination / 'assessment.json', record)
            try:
                result = read(source / 'result.json')
                record['attempt'] = result['attempt']
                if not result.get('completed'):
                    raise ValueError('checkpoint journal lacks a completed primary result')
                record['primary_sha256'] = sha(source / 'result.json')
                task = read(root / 'tasks' / (checkpoint['id'] + '.json'))
                check = check_argv(Path(app['sequence_path']).parent, task['check'])
                record['check'] = check
                record['check_files'] = {arg: sha(Path(arg)) for arg in check if Path(arg).is_file()}
                validate(snapshot)
                # The check is trusted controller code. Generated application code
                # must be launched by its check through the restricted runner.
                with tempfile.TemporaryDirectory(prefix='principiis-suite-evaluation-') as temporary:
                    candidate = Path(temporary) / 'candidate'
                    shutil.copytree(snapshot, candidate, symlinks=True)
                    with (destination / 'stdout').open('w') as stdout, (destination / 'stderr').open('w') as stderr:
                        record['execution'] = execute(check, candidate, '', stdout, stderr)
                if record['execution']['exit_status'] != 0:
                    raise ValueError('evaluator exited unsuccessfully')
                scores = read(destination / 'stdout')
                record.update(evaluator_scores(scores))
                validate(snapshot)
            except (OSError, ValueError, TypeError, KeyError, KeyboardInterrupt) as error:
                record.update(outcome='evaluator_error', functional='unassessable', security='unassessable', error=str(error))
            write_json(destination / 'assessment.json', record)
            if stop_requested():
                return


def report(output):
    output = Path(output).resolve()
    state = read(output / 'suite.json')
    applications, attempts, evaluations, investigations = [], [], [], []
    planned = sum(len(app['steps']) for app in state['applications'])
    completed, started = 0, 0
    primary_paths = []
    for app in state['applications']:
        root = output / 'applications' / app['id']
        summary = read(root / 'sequence.json') if (root / 'sequence.json').exists() else None
        if (root / 'manual.json').exists():
            manual = read(root / 'manual.json')
            summary = dict(manual, status='manual', checkpoints=manual['attempts'])
        entry = dict(app, status=summary['status'] if summary else 'unstarted', run_id=summary['run_id'] if summary else None)
        if summary:
            entry['fingerprint'] = summary['fingerprint']
            records = list(summary['checkpoints'])
            if summary.get('active_attempt'):
                records.append(summary['active_attempt'])
            finished, begun = set(), set()
            for checkpoint in records:
                artifact = root / checkpoint['artifact'] / 'result.json'
                result = read(artifact) if artifact.exists() else {'outcome': 'incomplete', 'functional': 'unknown', 'security': 'unknown', 'completed': False}
                begun.add(checkpoint['id'])
                if result.get('completed'):
                    finished.add(checkpoint['id'])
                if result.get('outcome') == 'pending_evaluation':
                    primary = root / 'evaluations' / checkpoint['id'] / '1' / 'result.json'
                    if primary.exists():
                        assessment = read(primary)
                        if assessment.get('developer_result_sha256') != sha(artifact) and assessment.get('allocation_provenance') != 'unknown_legacy':
                            raise ValueError('manual primary developer provenance mismatch')
                        result = dict(result, developer_outcome=result['outcome'],
                                      primary_assessment_ref=str(primary), primary_provenance=assessment['provenance'],
                                      **{key: assessment[key] for key in ('outcome', 'functional', 'security')})
                        primary_paths.append(primary)
                attempts.append({'application': app['id'], 'checkpoint': checkpoint['id'], 'artifact': str(artifact), **result})
            completed += len(finished)
            started += len(begun)
        applications.append(entry)
        for path in sorted((root / 'evaluations').glob('*/assessment.json')):
            evaluations.append(dict(read(path), artifact=str(path)))
        for path in sorted((root / 'evaluations').glob('*/*/result.json')):
            assessment = read(path)
            if assessment.get('role') == 'rerun':
                evaluations.append(dict(assessment, execution=assessment['evaluation'], artifact=str(path)))
        for path in sorted((root / 'investigations').rglob('investigation.json')):
            investigation = dict(read(path), application=app['id'], artifact=str(path))
            investigation['measurements'] = [dict(read(path.parent / ref), artifact=str(path.parent / ref))
                                             for ref in investigation.get('tools', [])]
            investigations.append(investigation)
    outcomes = Counter(attempt['outcome'] for attempt in attempts)
    claims = Counter()
    verified = set()
    for investigation in investigations:
        for claim in investigation.get('claims', []):
            status = claim['status']
            claims[status] += 1
            if status == 'verified':
                verified.add((investigation['application'], claim['root_cause']))
    controller_errors = [dict(read(path), artifact=str(path)) for path in sorted((output / 'controller-errors').glob('*.json'))]
    return {'schema_version': 1, 'suite': state['suite'], 'manifest_sha256': state['manifest_sha256'],
            'applications': applications, 'attempts': attempts,
            'denominators': {'planned_checkpoints': planned, 'completed_checkpoints': completed,
                             'unstarted_checkpoints': planned - started, 'attempts': len(attempts)},
            'outcomes': dict(outcomes), 'functional': dict(Counter(a.get('functional', 'unknown') for a in attempts)),
            'security': dict(Counter(a.get('security', 'unknown') for a in attempts)),
            'controller_errors': controller_errors, 'evaluations': evaluations,
            'supplementary': {'claims': dict(claims), 'verified_root_causes': [{'application': app, 'root_cause': cause} for app, cause in sorted(verified)],
                              'investigations': investigations},
            'resources': inspect_resources(output / 'applications', result_paths=[Path(a['artifact']) for a in attempts if Path(a['artifact']).is_file()] + primary_paths),
            'supplemental_resources': {'evaluation_reruns': [{'artifact': e['artifact'], **e['execution']} for e in evaluations],
                                       'investigations': [{'artifact': i['artifact'], 'resources': i.get('resources'), 'agent': i.get('agent'), 'tools': i['measurements']} for i in investigations]},
            'limitations': LIMITATIONS}


def markdown(value):
    lines = [f"Suite {value['suite']['id']} @ {value['suite']['version']}", '',
             'Progress: ' + json.dumps(value['denominators']), '',
             '| Application | Status | Sequence | Condition |', '| --- | --- | --- | --- |']
    for app in value['applications']:
        lines.append(f"| {app['id']} | {app['status']} | {app['sequence']['id']} @ {app['sequence']['version']} | {app['condition']['id']} @ {app['condition']['version']} |")
    lines += ['', 'Primary attempt outcomes: ' + json.dumps(value['outcomes']),
              'Security: ' + json.dumps(value['security']), '', '| Application | Checkpoint | Attempt | Outcome | Functional | Security | Developer outcome | Primary assessment | Evaluator version | Developer evidence |',
              '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for a in value['attempts']:
        lines.append(f"| {a['application']} | {a['checkpoint']} | {a.get('attempt', 'unknown')} | {a['outcome']} | {a['functional']} | {a['security']} | {a.get('developer_outcome', a['outcome'])} | {a.get('primary_assessment_ref', 'unknown')} | {a.get('primary_provenance', {}).get('version') or 'unknown'} | {a['artifact']} |")
    lines += ['', 'Controller errors: ' + json.dumps(value['controller_errors']),
              'Separate evaluator reruns: ' + json.dumps(value['evaluations']),
              'Supplementary claims: ' + json.dumps(value['supplementary']['claims']),
              'Verified root causes (per application): ' + json.dumps(value['supplementary']['verified_root_causes']),
              'Supplementary evidence: ' + json.dumps(value['supplementary']['investigations']),
              'Primary resource totals: ' + json.dumps(value['resources']['totals']),
              'Separate stage resources: ' + json.dumps(value['supplemental_resources']),
              'Actual spending: unknown; API-equivalent estimate: unknown.', '', *value['limitations']]
    return '\n'.join(lines) + '\n'


def main():
    stopped = False

    def interrupted(signum, frame):
        nonlocal stopped
        stopped = True
        raise KeyboardInterrupt('controller interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='initialize suite metadata without executing any checkpoint')
    prepare.add_argument('--suite', required=True)
    run = commands.add_parser('run')
    run.add_argument('--suite', required=True)
    executor = run.add_mutually_exclusive_group(required=True)
    executor.add_argument('--executor')
    executor.add_argument('--codex-config')
    run.add_argument('--resume', action='store_true')
    run.add_argument('--retry-incomplete', action='store_true')
    assessment = commands.add_parser('evaluate')
    assessment.add_argument('--evaluator-version', required=True)
    view = commands.add_parser('report')
    view.add_argument('--format', choices=('json', 'markdown'), default='json')
    for command in (prepare, run, assessment, view):
        command.add_argument('--output', required=True)
    for command in (run, assessment):
        command.add_argument('--application', action='append')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            state = load_suite(args.suite)
            output = Path(args.output).resolve()
            output.mkdir(parents=True, exist_ok=False)
            write_json(output / 'suite.json', state)
        elif args.command == 'run':
            run_suite(args, lambda: stopped)
        elif args.command == 'evaluate':
            evaluate(args, lambda: stopped)
        else:
            value = report(args.output)
            print(markdown(value) if args.format == 'markdown' else json.dumps(value, indent=2))
        if stopped:
            raise SystemExit(130)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
