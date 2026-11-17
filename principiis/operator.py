"""Small operator entry point composing the manual checkpoint controller."""
import argparse
import csv
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
from types import SimpleNamespace
import uuid

from . import resource
from .resume import write_json

REPOSITORY = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def operation(root, name):
    """Serialize operator mutations while permitting read-only status inspection."""
    with (root / '.operation.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('another operator action is active for this run; inspect status and wait') from error
        try:
            write_json(root / '.operation.json', {'active': True, 'operation': name, 'controller_pid': os.getpid()})
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def active_operation(root):
    path = root / '.operation.lock'
    if not path.exists():
        return {'active': False}
    with path.open() as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            metadata = root / '.operation.json'
            try:
                return dict(json.loads(metadata.read_text()), active=True)
            except (OSError, ValueError):
                return {'active': True, 'operation': 'unknown'}
        fcntl.flock(lock, fcntl.LOCK_UN)
    return {'active': False}


def run_directory(args):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run):
        raise ValueError('run must be a single name containing letters, numbers, dots, underscores or hyphens')
    root = Path(args.runs_root).expanduser().resolve() / args.run
    if any(value in str(root) for value in (',', '\n', '\r', '\0')):
        raise ValueError('run directory cannot contain commas/newlines or NUL bytes')
    if root.is_relative_to(REPOSITORY) or REPOSITORY.is_relative_to(root):
        raise ValueError('run directory must be outside the research checkout')
    if root.is_symlink():
        raise ValueError('run directory cannot be a symlink')
    for ancestor in (root, *root.parents):
        if any((ancestor / name).exists() for name in ('AGENTS.md', 'AGENTS.override.md')) or any(
                (ancestor / name).is_dir() and any((ancestor / name).iterdir()) for name in ('.agents', '.codex')):
            raise ValueError('run directory has researcher instructions/configuration in its ancestors')
    return root


def initialize(args):
    from .development_runtime import load_config
    runtime_path = Path(args.runtime_config).resolve()
    load_config(runtime_path)  # Validate configuration without starting Docker or allocating an attempt.
    root = run_directory(args)
    package = REPOSITORY / 'benchmarks' / args.application
    metadata = json.loads((package / 'package.json').read_text())
    count = getattr(args, 'steps', 3)
    if count == 10:
        from .qualification import load_qualified_package
        metadata = load_qualified_package(package, expected_steps=10)
    steps, requests = [], {}
    for number in range(1, count + 1):
        relative = f'requests/{number:02}.txt'
        source = package / relative
        if digest(source) != metadata['files'][relative]:
            raise ValueError('released request differs from package hash')
        requests[relative] = source.read_bytes()
        steps.append({'id': f'step-{number:02}', 'version': metadata['version'],
                      'sequence_version': metadata['version'], 'request': relative})
    sequence = {'id': args.application, 'version': metadata['version'],
                'condition': {'id': 'ordinary', 'version': '1'}, 'steps': steps}
    root.mkdir(parents=True, exist_ok=False)
    os.chmod(root, 0o700)
    (root / 'requests').mkdir()
    for relative, content in requests.items():
        (root / relative).write_bytes(content)
    (root / 'runtime.json').write_bytes(runtime_path.read_bytes())
    os.chmod(root / 'runtime.json', 0o600)
    write_json(root / 'sequence.json', sequence)
    configuration = {
        'schema_version': 1, 'run_name': args.run, 'application': args.application,
        'run_mode': 'qualification' if count == 10 else 'development-rehearsal', 'evaluator_binding': 'unbound',
        'package_version': metadata['version'], 'package_sha256': digest(package / 'package.json'),
        'frozen_files': {name: digest(root / name) for name in ('runtime.json', 'sequence.json', *requests)},
        'qualification': 'pending runtime review and scoped live acceptance; no primary scores',
    }
    write_json(root / 'configuration.json', configuration)
    return build_status(root, configuration)


def load_run(args):
    root = run_directory(args)
    configuration = json.loads((root / 'configuration.json').read_text())
    if configuration.get('run_name') != args.run:
        raise ValueError('run identity differs from its saved configuration')
    for name, expected in configuration['frozen_files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('saved development configuration changed; use a new run')
    return root, configuration


def step_identity(selection):
    choices = {str(number): f'step-{number:02}' for number in range(1, 11)}
    choices.update({value: value for value in choices.values()})
    if selection not in choices:
        raise ValueError('select portal request 1 through 10')
    return choices[selection]


def selected_step(root, selection):
    step = step_identity(selection)
    sequence = json.loads((root / 'sequence.json').read_text())
    if step not in [entry['id'] for entry in sequence['steps']]:
        raise ValueError('selected checkpoint is outside the frozen run; use a new run for a longer sequence')
    return step


def allocations(root, sequence):
    """Read only canonical controller allocations, never candidate-owned JSON files."""
    development = root / 'development'
    journal = development / 'manual.json'
    if not journal.exists():
        if development.exists():
            raise ValueError('development directory exists without its allocation journal')
        return [], None
    from .manual import _journal_attempts
    state = json.loads(journal.read_text())
    loaded, _ = _journal_attempts(development, state, [step['id'] for step in sequence['steps']])
    return [{'allocation': entry, 'directory': directory, 'result': result}
            for entry, directory, result in loaded], state['run_id']


def build_status(root, configuration):
    from .assessment import inspect as inspect_assessments
    active = active_operation(root)
    sequence = json.loads((root / 'sequence.json').read_text())
    records, run_id = allocations(root, sequence)
    selected = [entry['directory'] / 'result.json' for entry in records if entry['result'] is not None]
    resources = resource.inspect(root / 'development', result_paths=selected)
    measured = {attempt['artifact']: attempt for attempt in resources['attempts']}
    ordered = []
    for entry in records:
        if entry['result'] is not None:
            ordered.append(measured[str(entry['directory'] / 'result.json')])
        else:
            allocation = entry['allocation']
            ordered.append({
                'run_id': run_id, 'session_id': None, 'checkpoint': allocation['id'],
                'attempt': allocation['attempt'], 'outcome': 'interrupted_allocation',
                'artifact': str(entry['directory'] / 'result.json'),
                'stages': {'development': {'tokens': resource.token_usage(entry['directory'] / 'executor.stdout')},
                           'evaluation': {}},
            })
    assessment_evidence = inspect_assessments(root, configuration)
    assessments = assessment_evidence['assessments']
    assessment_binding = assessment_evidence['binding']
    resources = resource.summarize(ordered + assessment_evidence['resources']['attempts'])
    cleanups = []
    cleanup_index = root / 'runtime-cleanups/index.json'
    if cleanup_index.exists():
        for relative in json.loads(cleanup_index.read_text()):
            path = root / relative
            if not path.resolve().is_relative_to(root / 'runtime-cleanups'):
                raise ValueError('runtime cleanup evidence must stay within controller artifacts')
            cleanups.append(json.loads(path.read_text()) if path.is_file() else {'outcome': 'interrupted_cleanup'})
    pending_cleanup = []
    for entry in records:
        allocation_path = entry['directory'] / 'runtime.json'
        if allocation_path.is_symlink():
            raise ValueError('runtime allocation cannot be a symlink')
        if allocation_path.is_file():
            allocation = json.loads(allocation_path.read_text())
            reconciled = any(cleanup.get('outcome') == 'removed'
                             and cleanup.get('allocation') == str(allocation_path)
                             and cleanup.get('allocation_sha256') == digest(allocation_path) for cleanup in cleanups)
            if allocation.get('state') != 'removed' and not reconciled:
                pending_cleanup.append({'step': entry['allocation']['id'], 'allocation': str(allocation_path),
                                        'state': allocation.get('state'), 'container': allocation.get('container'),
                                        'cleanup_argv': allocation.get('cleanup_argv')})
    checkpoints = []
    next_action = {'action': 'development-complete', 'step': None, 'retry': False,
                   'explanation': 'All frozen requests retained. Preview/report remain available; evaluator is unbound.'}
    for step in sequence['steps']:
        attempts = [entry for entry in records if entry['allocation']['id'] == step['id']]
        latest = attempts[-1] if attempts else None
        result = latest['result'] if latest else None
        complete = bool(result and result.get('completed'))
        directory = latest['directory'] if latest else None
        status = result['outcome'] if result else 'interrupted_allocation' if latest else 'not-started'
        checkpoint = {'id': step['id'], 'status': status, 'completed': complete, 'attempts': len(attempts),
                      'source': str(directory / ('snapshot' if complete else 'workspace')) if directory else None,
                      'result': str(directory / 'result.json') if directory else None,
                      'stdout': str(directory / 'executor.stdout') if directory else None,
                      'stderr': str(directory / 'executor.stderr') if directory else None,
                      'snapshot_manifest_sha256': digest(directory / 'snapshot.json') if complete and (directory / 'snapshot.json').is_file() else None}
        checkpoint['assessments'] = [assessment for assessment in assessments if assessment['checkpoint'] == step['id']]
        checkpoint['primary_assessment'] = next((assessment for assessment in checkpoint['assessments']
                                                 if assessment['role'] == 'primary'), None)
        checkpoints.append(checkpoint)
        if not complete and next_action['step'] is None and next_action['action'] == 'development-complete':
            next_action = {'action': 'retry' if attempts else 'develop', 'step': step['id'], 'retry': bool(attempts),
                           'explanation': 'Scoped live authorization and reviewed runtime required.'}
            if len(attempts) >= 4:
                next_action.update(action='new-run-required', explanation='Three additional retries exhausted; retain this run.')
    if configuration['run_mode'] == 'qualification' and not assessment_binding:
        next_action = {'action': 'bind-evaluator', 'step': None, 'retry': False,
                       'explanation': 'Freeze the qualified evaluator from #9 before the first development session.'}
    elif assessment_binding:
        pending = next((checkpoint for checkpoint in checkpoints
                        if checkpoint['completed'] and not checkpoint['primary_assessment']), None)
        if pending:
            next_action = {'action': 'evaluate', 'step': pending['id'], 'retry': False,
                           'explanation': 'Explicitly assess the retained snapshot with scoped evaluation authorization.'}
        elif next_action['action'] == 'development-complete':
            next_action['explanation'] = 'All frozen checkpoints and primary assessments retained. Owner acceptance remains separate.'
    if pending_cleanup:
        next_action = {'action': 'cleanup', 'step': pending_cleanup[0]['step'], 'retry': False,
                       'explanation': 'Retained runtime cleanup is unresolved. Run the explicit cleanup command before further development.'}
    if active['active']:
        next_action = {'action': 'wait', 'step': None, 'retry': False,
                       'explanation': 'An operator action is active. Retained measurements may still be partial.'}
    previews = []
    index = root / 'previews/index.json'
    if index.exists():
        for item in json.loads(index.read_text()):
            metadata_path = root / item['artifact']
            if not metadata_path.resolve().is_relative_to(root / 'previews'):
                raise ValueError('preview metadata must remain within controller preview artifacts')
            previews.append(dict(item, evidence=json.loads(metadata_path.read_text()) if metadata_path.is_file() else None))
    return dict(configuration, root=str(root), run_id=run_id, checkpoints=checkpoints,
                next_action=next_action, resources=resources, previews=previews, active_operation=active,
                assessment_binding=assessment_binding, assessments=assessments,
                runtime_cleanup_required=pending_cleanup, runtime_cleanups=cleanups)


def develop(args):
    from .manual import develop as manual_develop
    root, configuration = load_run(args)
    with operation(root, 'development'):
        status = build_status(root, configuration)
        if status['runtime_cleanup_required']:
            raise ValueError('retained runtime requires explicit cleanup before further development')
        step = selected_step(root, args.step)
        if configuration['run_mode'] == 'qualification':
            if not status['assessment_binding']:
                raise ValueError('ten-step qualification requires a qualified evaluator binding before development')
            if any(checkpoint['completed'] and not checkpoint['primary_assessment'] for checkpoint in status['checkpoints']):
                raise ValueError('separately evaluate the previous completed checkpoint before further qualification development')
        approval = Path(args.authorization).resolve()
        text = approval.read_text()
        if not text.strip():
            raise ValueError('nonempty scoped live launch authorization record required')
        # Validate runtime before allocating launch or development records.
        from .development_runtime import load_config
        load_config(root / 'runtime.json')
        launch = {'source': str(approval), 'sha256': digest(approval), 'recorded_text': text,
                  'step': step, 'retry': args.retry}
        manual_develop(SimpleNamespace(sequence=str(root / 'sequence.json'), output=str(root / 'development'),
                                       step=step, executor=None, codex_config=None, runtime_config=str(root / 'runtime.json'),
                                       development_only=True, retry=args.retry, launch_authorization=launch))
    return build_status(root, configuration)


def bind_evaluator(args):
    from .assessment import bind
    root, configuration = load_run(args)
    with operation(root, 'evaluator binding'):
        bind(root, configuration, args.evaluator_manifest)
    return build_status(root, configuration)


def evaluate(args):
    root, configuration = load_run(args)
    with operation(root, 'independent evaluation'):
        if not (root / 'evaluator-binding.json').exists():
            raise ValueError('evaluator is unbound; bind a qualified package from #8 before evaluation')
        from .assessment import evaluate as assess
        step = selected_step(root, args.step)
        approval = Path(args.authorization).resolve()
        text = approval.read_text()
        if not text.strip():
            raise ValueError('nonempty scoped evaluation authorization record required')
        authorization = {'source': str(approval), 'sha256': digest(approval), 'recorded_text': text,
                         'step': step, 'rerun': args.rerun}
        assess(root, configuration, step, rerun=args.rerun, authorization=authorization)
    return build_status(root, configuration)


def cleanup(args):
    from .development_runtime import cleanup_runtime
    root, configuration = load_run(args)
    step = selected_step(root, args.step)
    with operation(root, 'development runtime cleanup'):
        pending = [entry for entry in build_status(root, configuration)['runtime_cleanup_required'] if entry['step'] == step]
        if not pending:
            raise ValueError('no unresolved development runtime allocation for selected checkpoint')
        index_path = root / 'runtime-cleanups/index.json'
        index_path.parent.mkdir(exist_ok=True)
        index = json.loads(index_path.read_text()) if index_path.exists() else []
        for entry in pending:
            relative = f'runtime-cleanups/{uuid.uuid4()}'
            index.append(relative + '/cleanup.json')
            write_json(index_path, index)
            cleanup_runtime(entry['allocation'], root / 'runtime.json', root / relative)
    return build_status(root, configuration)


def preview(args):
    root, configuration = load_run(args)
    with operation(root, 'preview cleanup' if args.stop else 'preview startup'):
        operate_preview(args, root, configuration)
    return build_status(root, configuration)


def operate_preview(args, root, configuration):
    from . import preview as runtime_preview
    step = selected_step(root, args.step)
    index_path = root / 'previews/index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    if args.stop:
        selected = [entry for entry in index if entry['step'] == step]
        if not selected:
            raise ValueError('no retained preview for selected checkpoint')
        for entry in reversed(selected):
            runtime_preview.stop(root / entry['directory'])
    else:
        status = build_status(root, configuration)
        checkpoint = next(c for c in status['checkpoints'] if c['id'] == step)
        if not checkpoint['completed']:
            raise ValueError('completed developer checkpoint required for preview')
        if not args.preview_config:
            raise ValueError('--preview-config required to start a preview')
        runtime_preview.load_config(args.preview_config)
        relative = f'previews/{step}/{uuid.uuid4()}'
        directory = root / relative
        # Record the allocation before launch so startup failures remain discoverable.
        index_path.parent.mkdir(exist_ok=True)
        index.append({'step': step, 'directory': relative, 'artifact': relative + '/preview.json'})
        write_json(index_path, index)
        try:
            runtime_preview.start(checkpoint['source'], args.preview_config, directory)
        except (OSError, ValueError) as error:
            if not (directory / 'preview.json').exists():
                directory.mkdir(parents=True, exist_ok=True)
                write_json(directory / 'preview.json', {'outcome': 'preview_preflight_error', 'error': str(error),
                                                        'resources_removed': True, 'url': None})
            raise


def display(value):
    return 'unknown' if value is None else str(value)


def markdown(report):
    binding = report.get('assessment_binding')
    evaluator = binding['version'] if binding else report['evaluator_binding']
    lines = [f"Run: {report['run_name']} ({report['run_mode']})", '',
             f"Application: {report['application']} @ {report['package_version']}",
             f"Evaluator: {evaluator}" + ('.' if binding else '; primary scores unavailable.'),
             f"Artifacts: {report['root']}", '',
             '| Checkpoint | Status | Attempts | Retained source |', '| --- | --- | --- | --- |']
    for checkpoint in report['checkpoints']:
        lines.append(f"| {checkpoint['id']} | {checkpoint['status']} | {checkpoint['attempts']} | {display(checkpoint['source'])} |")
    for checkpoint in report['checkpoints']:
        if checkpoint['stdout']:
            lines.extend(['', f"{checkpoint['id']} logs: {checkpoint['stdout']} ; {checkpoint['stderr']}"])
    assessments = report.get('assessments', [])
    if assessments:
        lines.extend(['', '| Checkpoint | Assessment | Role | Functional | Security | Outcome | Evidence |',
                      '| --- | --- | --- | --- | --- | --- | --- |'])
        for assessment in assessments:
            lines.append(f"| {assessment['checkpoint']} | {assessment['attempt']} | {assessment['role']} | "
                         f"{assessment['functional']} | {assessment['security']} | {assessment['outcome']} | {assessment['artifact']} |")
    lines.extend(['', resource.markdown(report['resources'])])
    for attempt in report['resources']['attempts']:
        evidence = attempt['stages']['development']
        if not evidence:
            continue
        container_memory = evidence.get('container_memory') or {}
        lines.append(f"{attempt['checkpoint']} attempt {attempt['attempt']} sampled container memory (bytes): "
                     + display(container_memory.get('peak_sampled_bytes')) + '; ' + container_memory.get('scope', 'scope unknown'))
    for entry in report['runtime_cleanup_required']:
        lines.extend(['', f"Runtime cleanup pending for {entry['step']}: {entry['allocation']}",
                      f"Cleanup: python3 -m principiis cleanup --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']}"])
    for entry in report['previews']:
        evidence = entry['evidence'] or {}
        lines.extend(['', f"{entry['step']} preview evidence: {report['root']}/{entry['artifact']}",
                      f"Preview: {evidence.get('outcome', 'unknown')} ; URL: {display(evidence.get('url'))}",
                      f"Cleanup: python3 -m principiis preview --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']} --stop"])
    action = report['next_action']
    lines.extend(['', 'Next action: ' + action['action'] + (' ' + action['step'] if action['step'] else ''), action['explanation']])
    return '\n'.join(lines) + '\n'


CSV_FIELDS = ('run_name', 'run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact',
              'stage', 'role', 'functional', 'security', 'evaluator_version', 'evaluator_manifest_sha256',
              'snapshot_manifest_sha256', 'source', 'stdout', 'stderr', 'development_seconds', 'evaluation_seconds', 'started_at', 'finished_at',
              *resource.CATEGORIES, 'total_tokens', 'local_peak_sampled_rss_bytes', 'local_memory_scope',
              'container_peak_sampled_bytes', 'container_memory_scope', 'actual_spending', 'hosted_model_memory')


def csv_report(report):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for attempt in report['resources']['attempts']:
        stage = 'evaluation' if attempt['stages']['evaluation'] and not attempt['stages']['development'] else 'development'
        evidence = attempt['stages'][stage]
        tokens, memory = evidence.get('tokens') or {}, evidence.get('memory') or {}
        container_memory = evidence.get('container_memory') or {}
        directory = Path(attempt['artifact']).parent
        result = json.loads(Path(attempt['artifact']).read_text()) if Path(attempt['artifact']).is_file() else {}
        row = {key: attempt.get(key) for key in ('run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact')}
        provenance = result.get('provenance') or {}
        row.update(run_name=report['run_name'], stage=stage, role=result.get('role'),
                   functional=result.get('functional'), security=result.get('security'),
                   evaluator_version=provenance.get('version'), evaluator_manifest_sha256=provenance.get('manifest_sha256'),
                   snapshot_manifest_sha256=result.get('snapshot_manifest_sha256'),
                   source=result.get('snapshot') if stage == 'evaluation' else str(directory / ('snapshot' if result.get('completed') else 'workspace')),
                   stdout=str(directory / ('evaluator.stdout' if stage == 'evaluation' else 'executor.stdout')),
                   stderr=str(directory / ('evaluator.stderr' if stage == 'evaluation' else 'executor.stderr')),
                   development_seconds=evidence.get('elapsed_seconds') if stage == 'development' else None,
                   evaluation_seconds=evidence.get('elapsed_seconds') if stage == 'evaluation' else None,
                   started_at=evidence.get('started_at'),
                   finished_at=evidence.get('finished_at'), local_peak_sampled_rss_bytes=memory.get('peak_sampled_rss_bytes'),
                   local_memory_scope=memory.get('scope'), container_peak_sampled_bytes=container_memory.get('peak_sampled_bytes'),
                   container_memory_scope=container_memory.get('scope'), actual_spending=None, hosted_model_memory=None)
        row.update({key: tokens.get(key) for key in (*resource.CATEGORIES, 'total_tokens')})
        writer.writerow({key: display(value) for key, value in row.items()})
    return stream.getvalue()


def save_report(report):
    root = Path(report['root']) / 'reports'
    root.mkdir(exist_ok=True)
    write_json(root / 'development.json', report)
    (root / 'development.csv').write_text(csv_report(report))
    (root / 'development.md').write_text(markdown(report))
    return root


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    commands = {}
    for name in ('init', 'develop', 'bind-evaluator', 'evaluate', 'status', 'preview', 'cleanup', 'report'):
        command = sub.add_parser(name)
        commands[name] = command
        command.add_argument('--run', required=True)
        command.add_argument('--runs-root', default=os.environ.get('PRINCIPIIS_RUNS_ROOT', str(Path.home() / '.local/share/principiis/runs')))
        command.add_argument('--format', choices=('markdown', 'json', 'csv') if name == 'report' else ('markdown', 'json'), default='markdown')
    commands['init'].add_argument('--application', choices=('document-portal',), required=True)
    commands['init'].add_argument('--runtime-config', required=True)
    commands['init'].add_argument('--steps', type=int, choices=(3, 10), default=3)
    commands['develop'].add_argument('--step', required=True)
    commands['develop'].add_argument('--retry', action='store_true')
    commands['develop'].add_argument('--authorization', required=True, help='file recording reviewed runtime and scoped owner launch authorization')
    commands['bind-evaluator'].add_argument('--evaluator-manifest', required=True)
    commands['evaluate'].add_argument('--step', required=True)
    commands['evaluate'].add_argument('--rerun', action='store_true')
    commands['evaluate'].add_argument('--authorization', required=True, help='file recording scoped owner evaluation authorization')
    commands['preview'].add_argument('--step', required=True)
    commands['preview'].add_argument('--preview-config')
    commands['preview'].add_argument('--stop', action='store_true')
    commands['cleanup'].add_argument('--step', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            report = initialize(args)
        elif args.command == 'develop':
            report = develop(args)
        elif args.command == 'bind-evaluator':
            report = bind_evaluator(args)
        elif args.command == 'evaluate':
            report = evaluate(args)
        elif args.command == 'preview':
            report = preview(args)
        elif args.command == 'cleanup':
            report = cleanup(args)
        else:
            report = build_status(*load_run(args))
        if args.command == 'report':
            save_report(report)
        print(json.dumps(report, indent=2) if args.format == 'json' else csv_report(report) if args.format == 'csv' else markdown(report), end='')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
