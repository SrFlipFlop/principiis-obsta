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
import shlex
import signal
import shutil
import time
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
    from .conditions import load as load_condition
    from .development_runtime import load_config
    runtime_path = Path(args.runtime_config).resolve()
    load_config(runtime_path)  # Validate configuration without starting Docker or allocating an attempt.
    condition_path, condition = load_condition(getattr(args, 'condition', 'baseline'))
    root = run_directory(args)
    package = REPOSITORY / 'benchmarks' / args.application
    metadata = json.loads((package / 'package.json').read_text())
    count = getattr(args, 'steps', 3)
    if count == 10:
        from .qualification import load_qualified_package
        metadata = load_qualified_package(package, expected_steps=10)
        if not args.evaluator_manifest:
            raise ValueError('ten-step run requires --evaluator-manifest during init')
    elif (metadata.get('id') != args.application
          or metadata.get('qualification_status') not in ('qualified_first_three', 'qualified')
          or metadata.get('owner_review') not in ('approved_first_three', 'approved')):
        raise ValueError('three-step rehearsal requires a qualified and owner-reviewed application package')
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
                'condition': {'id': condition['id'], 'version': condition['version']}, 'steps': steps}
    root.mkdir(parents=True, exist_ok=False)
    os.chmod(root, 0o700)
    (root / 'requests').mkdir()
    for relative, content in requests.items():
        (root / relative).write_bytes(content)
    (root / 'runtime.json').write_bytes(runtime_path.read_bytes())
    os.chmod(root / 'runtime.json', 0o600)
    (root / 'condition.json').write_bytes(condition_path.read_bytes())
    write_json(root / 'sequence.json', sequence)
    configuration = {
        'schema_version': 1, 'run_name': args.run, 'application': args.application,
        'condition': sequence['condition'],
        'run_mode': 'qualification' if count == 10 else 'development-rehearsal', 'evaluator_binding': 'unbound',
        'investigation': getattr(args, 'investigation', 'final'),
        'package_version': metadata['version'], 'package_sha256': digest(package / 'package.json'),
        'frozen_files': {name: digest(root / name) for name in ('runtime.json', 'condition.json', 'sequence.json', *requests)},
        'qualification': 'pending runtime review and scoped live acceptance; no primary scores',
    }
    write_json(root / 'configuration.json', configuration)
    try:
        if args.evaluator_manifest:
            from .assessment import bind
            bind(root, configuration, args.evaluator_manifest)
        return build_status(root, configuration)
    except Exception:
        shutil.rmtree(root)
        raise


def imported_development_files(root):
    """Inventory only copied development evidence, excluding new evaluations."""
    development = root / 'development'
    paths = [development / 'manual.json']
    for name in ('tasks', 'steps', 'attempts'):
        directory = development / name
        if directory.is_dir() and not directory.is_symlink():
            paths.extend(path for path in directory.rglob('*') if not path.is_dir() or path.is_symlink())
        elif directory.exists() or directory.is_symlink():
            raise ValueError('imported development evidence has an invalid directory')
    inventory = {}
    for path in paths:
        name = str(path.relative_to(root))
        if path.is_symlink():
            inventory[name] = {'symlink': os.readlink(path)}
        elif path.is_file():
            inventory[name] = {'sha256': digest(path)}
        else:
            raise ValueError('imported development evidence is missing: ' + name)
    return inventory


def derive_evaluation(args):
    """Start a new evaluator ledger from attested completed development evidence."""
    from .assessment import bind
    source_args = SimpleNamespace(run=args.source_run, runs_root=args.runs_root)
    source, original = load_run(source_args)
    target = run_directory(args)
    if target.exists():
        raise ValueError('derived run already exists; use a new run name')
    if original.get('run_mode') == 'evaluation-derived':
        raise ValueError('derive from an original development run, not another evaluation import')
    if active_operation(source)['active']:
        raise ValueError('source run has an active operation; wait before importing')
    source_status = build_status(source, original)
    for stage, key in (('development', 'runtime_cleanup_required'),
                       ('evaluation', 'evaluation_cleanup_required'),
                       ('reviewer', 'investigation_cleanup_required')):
        if source_status[key]:
            raise ValueError(f'source {stage} runtime cleanup is unresolved')
    sequence = json.loads((source / 'sequence.json').read_text())
    records, source_run_id = allocations(source, sequence)
    ids = [entry['id'] for entry in sequence['steps']]
    if not source_run_id or [entry['allocation']['id'] for entry in records if entry['result'] and entry['result'].get('completed')] != ids:
        raise ValueError('every source checkpoint must have one completed development result')
    source_files = imported_development_files(source)
    metadata = json.loads((REPOSITORY / 'benchmarks' / original['application'] / 'package.json').read_text())
    if metadata.get('version') != original.get('package_version'):
        raise ValueError('current package version differs from source development; use a compatible release')
    target.mkdir(parents=True, exist_ok=False)
    os.chmod(target, 0o700)
    try:
        for name in original['frozen_files']:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, destination)
        development = target / 'development'
        development.mkdir()
        shutil.copy2(source / 'development/manual.json', development / 'manual.json')
        for name in ('tasks', 'steps', 'attempts'):
            if (source / 'development' / name).is_dir():
                shutil.copytree(source / 'development' / name, development / name, symlinks=True)
        if imported_development_files(source) != source_files or imported_development_files(target) != source_files:
            raise ValueError('source development changed during import; discard this derived run')
        lineage = {'schema_version': 1, 'source_run': original['run_name'], 'source_root': str(source),
                   'source_run_id': source_run_id, 'source_configuration_sha256': digest(source / 'configuration.json'),
                   'source_binding_sha256': digest(source / 'evaluator-binding.json')
                       if (source / 'evaluator-binding.json').is_file() else None,
                   'development_files': source_files}
        write_json(target / 'lineage.json', lineage)
        configuration = dict(original, run_name=args.run, run_mode='evaluation-derived',
                             evaluator_binding='unbound', investigation='none',
                             package_version=metadata['version'],
                             package_sha256=digest(REPOSITORY / 'benchmarks' / original['application'] / 'package.json'),
                             qualification='evaluation-only import of completed retained development; no model launch',
                             source_run={'run_name': original['run_name'], 'root': str(source), 'run_id': source_run_id},
                             lineage_sha256=digest(target / 'lineage.json'))
        write_json(target / 'configuration.json', configuration)
        bind(target, configuration, args.evaluator_manifest)
        return build_status(target, configuration)
    except Exception:
        shutil.rmtree(target)
        raise


def load_run(args):
    root = run_directory(args)
    configuration = json.loads((root / 'configuration.json').read_text())
    if configuration.get('run_name') != args.run:
        raise ValueError('run identity differs from its saved configuration')
    for name, expected in configuration['frozen_files'].items():
        path = root / name
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('saved development configuration changed; use a new run')
    if configuration.get('run_mode') == 'evaluation-derived':
        lineage = root / 'lineage.json'
        if (lineage.is_symlink() or not lineage.is_file()
                or digest(lineage) != configuration.get('lineage_sha256')):
            raise ValueError('evaluation import lineage changed')
        provenance = json.loads(lineage.read_text())
        source = root.parent / provenance['source_run']
        source_binding = source / 'evaluator-binding.json'
        if source_binding.is_symlink() or (source_binding.exists() and not source_binding.is_file()):
            raise ValueError('source development lineage changed')
        binding_digest = digest(source_binding) if source_binding.is_file() else None
        if (source.is_symlink() or str(source.resolve()) != provenance['source_root']
                or provenance['source_run'] != configuration['source_run']['run_name']
                or provenance['source_root'] != configuration['source_run']['root']
                or digest(source / 'configuration.json') != provenance['source_configuration_sha256']
                or binding_digest != provenance['source_binding_sha256']
                or imported_development_files(source) != provenance['development_files']):
            raise ValueError('source development lineage changed')
        if imported_development_files(root) != provenance['development_files']:
            raise ValueError('imported development evidence changed')
    return root, configuration


def step_identity(selection):
    choices = {str(number): f'step-{number:02}' for number in range(1, 11)}
    choices.update({value: value for value in choices.values()})
    if selection not in choices:
        raise ValueError('select request 1 through 10')
    return choices[selection]


def selected_step(root, selection):
    step = step_identity(selection)
    sequence = json.loads((root / 'sequence.json').read_text())
    if step not in [entry['id'] for entry in sequence['steps']]:
        raise ValueError('selected checkpoint is outside the frozen run; use a new run for a longer sequence')
    return step


def final_step(root):
    return json.loads((root / 'sequence.json').read_text())['steps'][-1]['id']


def authentication_failure(stdout_path):
    """Classify a known Codex login failure without exposing agent output."""
    if not stdout_path.is_file() or stdout_path.is_symlink():
        return False
    with stdout_path.open(errors='replace') as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            error = event.get('error') if isinstance(event, dict) and event.get('type') == 'turn.failed' else None
            message = error.get('message', '') if isinstance(error, dict) else ''
            if isinstance(message, str) and ('refresh token was already used' in message
                                             or 'token_expired' in message):
                return True
    return False


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
    evaluation_cleanup_required = assessment_evidence.get('cleanup_required', [])
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
        checkpoint['failure_reason'] = ('codex_authentication' if directory and not complete
                                        and authentication_failure(directory / 'executor.stdout') else None)
        checkpoint['assessments'] = [assessment for assessment in assessments if assessment['checkpoint'] == step['id']]
        checkpoint['primary_assessment'] = next((assessment for assessment in checkpoint['assessments']
                                                 if assessment['role'] == 'primary'), None)
        checkpoints.append(checkpoint)
        if not complete and next_action['step'] is None and next_action['action'] == 'development-complete':
            next_action = {'action': 'retry' if attempts else 'develop', 'step': step['id'], 'retry': bool(attempts),
                           'explanation': 'Run the selected development command with the reviewed runtime.'}
            if len(attempts) >= 4:
                next_action.update(action='new-run-required', explanation='Three additional retries exhausted; retain this run.')
            elif checkpoint['failure_reason'] == 'codex_authentication':
                next_action['explanation'] = ('Codex authentication failed. Refresh the private auth file, then '
                                              'retry this step with --retry; the original attempt stays saved.')
    if configuration['run_mode'] == 'qualification' and not assessment_binding:
        next_action = {'action': 'new-run-required', 'step': None, 'retry': False,
                       'explanation': 'A ten-step run needs its qualified evaluator bound during init; create a new run.'}
    elif assessment_binding:
        pending = next((checkpoint for checkpoint in checkpoints
                        if checkpoint['completed'] and not checkpoint['primary_assessment']), None)
        if pending:
            next_action = {'action': 'evaluate', 'step': pending['id'], 'retry': False,
                           'explanation': 'Run the hidden checks against the retained snapshot.'}
        elif next_action['action'] == 'development-complete':
            next_action['explanation'] = 'All frozen checkpoints and primary assessments retained. Owner acceptance remains separate.'
    if pending_cleanup:
        next_action = {'action': 'cleanup', 'step': pending_cleanup[0]['step'], 'retry': False,
                       'explanation': 'Retained runtime cleanup is unresolved. Run the explicit cleanup command before further development.'}
    if evaluation_cleanup_required:
        next_action = {'action': 'cleanup-evaluation', 'step': evaluation_cleanup_required[0]['checkpoint'], 'retry': False,
                       'explanation': 'Evaluation runtime cleanup is unresolved; explicitly clean it before development or evaluation.'}
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
    investigations = []
    for step in sequence['steps']:
        parent = root / 'investigations' / step['id']
        if parent.is_dir():
            for directory in sorted(parent.iterdir()):
                if not directory.name.isdigit() or directory.is_symlink() or not directory.is_dir():
                    raise ValueError('invalid investigation allocation directory')
                path = directory / 'investigation.json'
                if path.is_symlink() or not path.resolve().is_relative_to(root / 'investigations'):
                    raise ValueError('investigation evidence must stay inside run artifacts')
                record = json.loads(path.read_text()) if path.is_file() else {
                    'status': 'interrupted_allocation', 'claims': [], 'verified_root_causes': [],
                    'resources': {'elapsed_seconds': None, 'reported_tokens': None},
                }
                investigations.append(dict(record, checkpoint=step['id'], artifact=str(path)))
    for checkpoint in checkpoints:
        checkpoint['investigations'] = [entry for entry in investigations if entry['checkpoint'] == checkpoint['id']]
    investigation_cleanups = []
    index = root / 'investigation-cleanups/index.json'
    if index.is_file():
        for relative in json.loads(index.read_text()):
            path = root / relative
            if not path.resolve().is_relative_to(root / 'investigation-cleanups'):
                raise ValueError('investigation cleanup evidence must stay inside controller artifacts')
            investigation_cleanups.append(json.loads(path.read_text()) if path.is_file()
                                          else {'outcome': 'interrupted_cleanup'})
    investigation_cleanup_required = []
    for entry in investigations:
        allocation_path = Path(entry['artifact']).parent / 'runtime.json'
        if allocation_path.is_symlink():
            raise ValueError('investigation runtime allocation cannot be a symlink')
        if allocation_path.is_file():
            allocation = json.loads(allocation_path.read_text())
            reconciled = any(cleanup.get('outcome') == 'removed'
                             and cleanup.get('allocation') == str(allocation_path)
                             and cleanup.get('allocation_sha256') == digest(allocation_path)
                             for cleanup in investigation_cleanups)
            if allocation.get('state') != 'removed' and not reconciled:
                investigation_cleanup_required.append({'step': entry['checkpoint'],
                                                       'allocation': str(allocation_path),
                                                       'container': allocation.get('container')})
    if next_action['action'] not in ('wait', 'cleanup', 'cleanup-evaluation'):
        mode = configuration.get('investigation', 'none')
        if mode == 'each-step':
            pending = next((entry for entry in checkpoints
                            if entry['primary_assessment'] and (not entry['investigations']
                                or entry['investigations'][0]['status'] != 'completed')), None)
            if pending:
                retry = bool(pending['investigations'])
                next_action = {'action': 'evaluate --ai-review', 'step': pending['id'], 'retry': retry,
                               'explanation': 'Run the separate security investigation for this assessed checkpoint.'
                               + (' Use --rerun to retain the failed attempt.' if retry else '')}
        elif (mode == 'final' and checkpoints
              and all(entry['primary_assessment'] for entry in checkpoints)
              and (not checkpoints[-1]['investigations']
                   or checkpoints[-1]['investigations'][0]['status'] != 'completed')):
            retry = bool(checkpoints[-1]['investigations'])
            next_action = {'action': 'evaluate --final --ai-review', 'step': checkpoints[-1]['id'], 'retry': retry,
                           'explanation': 'Run the separate final Codex security investigation.'
                           + (' Use --rerun to retain the failed attempt.' if retry else '')}
    if investigation_cleanup_required:
        next_action = {'action': 'cleanup-investigation', 'step': investigation_cleanup_required[0]['step'],
                       'retry': False, 'explanation': 'Remove the retained reviewer container before further work.'}
    if active['active']:
        next_action = {'action': 'wait', 'step': None, 'retry': False,
                       'explanation': 'An operator action is active. Retained measurements may still be partial.'}
    return dict(configuration, root=str(root), run_id=run_id, checkpoints=checkpoints,
                next_action=next_action, resources=resources, previews=previews, active_operation=active,
                assessment_binding=assessment_binding, assessments=assessments, investigations=investigations,
                evaluation_cleanup_required=evaluation_cleanup_required,
                runtime_cleanup_required=pending_cleanup, runtime_cleanups=cleanups,
                investigation_cleanup_required=investigation_cleanup_required,
                investigation_cleanups=investigation_cleanups)


def develop(args):
    from .manual import develop as manual_develop
    root, configuration = load_run(args)
    if configuration.get('run_mode') == 'evaluation-derived':
        raise ValueError('evaluation-only derived run cannot launch development')
    with operation(root, 'development'):
        status = build_status(root, configuration)
        if status['runtime_cleanup_required']:
            raise ValueError('retained runtime requires explicit cleanup before further development')
        if status['evaluation_cleanup_required']:
            raise ValueError('evaluation runtime requires explicit cleanup before further development')
        if status['investigation_cleanup_required']:
            raise ValueError('reviewer runtime requires explicit cleanup before further development')
        step = selected_step(root, args.step)
        if configuration['run_mode'] == 'qualification':
            if not status['assessment_binding']:
                raise ValueError('ten-step qualification requires a qualified evaluator binding before development')
            if any(checkpoint['completed'] and not checkpoint['primary_assessment'] for checkpoint in status['checkpoints']):
                raise ValueError('separately evaluate the previous completed checkpoint before further qualification development')
        # Validate runtime before allocating launch or development records.
        from .development_runtime import load_config
        load_config(root / 'runtime.json')
        launch = {'kind': 'manual_cli_invocation', 'command': 'develop',
                  'step': step, 'retry': args.retry}
        manual_develop(SimpleNamespace(sequence=str(root / 'sequence.json'), output=str(root / 'development'),
                                       step=step, executor=None, codex_config=None, runtime_config=str(root / 'runtime.json'),
                                       development_only=True, retry=args.retry, launch_authorization=launch))
    return build_status(root, configuration)


def evaluate(args):
    root, configuration = load_run(args)
    with operation(root, 'independent evaluation'):
        status = build_status(root, configuration)
        if status['runtime_cleanup_required'] or status['evaluation_cleanup_required'] or status['investigation_cleanup_required']:
            raise ValueError('retained runtime requires explicit cleanup before further evaluation')
        if not (root / 'evaluator-binding.json').exists():
            raise ValueError('evaluator is unbound; bind a qualified package from #8 before evaluation')
        from .assessment import evaluate as assess
        step = selected_step(root, args.step)
        invocation = {'kind': 'manual_cli_invocation', 'command': 'evaluate',
                      'step': step, 'rerun': args.rerun}
        assess(root, configuration, step, rerun=args.rerun, authorization=invocation)
    return build_status(root, configuration)


def investigate_run(args):
    from .development_runtime import load_config
    from .investigation import investigate
    root, configuration = load_run(args)
    with operation(root, 'security investigation'):
        mode = configuration.get('investigation', 'none')
        if mode == 'none' or (mode == 'final' and not args.final) or (mode == 'each-step' and args.final):
            raise ValueError('investigation is not enabled for this command in the frozen run')
        step = final_step(root) if args.final else selected_step(root, args.step)
        status = build_status(root, configuration)
        if status['runtime_cleanup_required'] or status['evaluation_cleanup_required'] or status['investigation_cleanup_required']:
            raise ValueError('clean retained runtimes before security investigation')
        checkpoint = next(entry for entry in status['checkpoints'] if entry['id'] == step)
        primary = checkpoint['primary_assessment']
        if not checkpoint['completed'] or not primary:
            raise ValueError('completed checkpoint and primary assessment required before investigation')
        config_path, prompt_path = Path(args.config).resolve(), Path(args.prompt).resolve()
        config = json.loads(config_path.read_text())
        if 'runtime_config' not in config or 'agent' in config or 'codex_config' in config or config.get('evidence') != {}:
            raise ValueError('operator investigation requires an isolated Codex runtime and no host proof commands')
        reviewer = load_config(config['runtime_config'])
        developer = load_config(root / 'runtime.json')
        if Path(reviewer['auth_file']).resolve() == Path(developer['auth_file']).resolve():
            raise ValueError('reviewer requires separately provisioned subscription authentication')
        binding = {'config_sha256': digest(config_path), 'prompt_sha256': digest(prompt_path),
                   'runtime_config_sha256': digest(config['runtime_config']),
                   'prompt_version': args.prompt_version, 'mode': mode}
        binding_path = root / 'investigation-binding.json'
        if binding_path.exists():
            if json.loads(binding_path.read_text()) != binding:
                raise ValueError('investigation configuration changed; use a new run')
        else:
            write_json(binding_path, binding)
        parent = root / 'investigations' / step
        allocations = [path for path in parent.iterdir() if path.is_dir() and path.name.isdigit()] if parent.is_dir() else []
        if allocations and not args.rerun:
            raise ValueError('investigation already retained; explicit --rerun required')
        if not allocations and args.rerun:
            raise ValueError('no investigation to rerun')
        output = parent / str(max((int(path.name) for path in allocations), default=0) + 1)
        report = investigate(SimpleNamespace(snapshot=checkpoint['source'], primary=primary['artifact'],
                                             config=str(config_path), prompt=str(prompt_path),
                                             prompt_version=args.prompt_version, output=str(output)))
        if report['status'] == 'evaluator_error' and (output / 'runtime.json').is_file():
            allocation = json.loads((output / 'runtime.json').read_text())
            if allocation.get('state') != 'removed':
                raise ValueError('reviewer container cleanup unresolved; inspect retained runtime allocation')
    return build_status(root, configuration)


def cleanup_evaluation(args):
    from .assessment import inspect
    from .evaluation_cleanup import cleanup
    root, configuration = load_run(args)
    with operation(root, 'evaluation runtime cleanup'):
        evidence = inspect(root, configuration)
        cleanup(root, evidence['assessments'], selected_step(root, args.step))
    return build_status(root, configuration)


def cleanup_investigation(args):
    from .development_runtime import cleanup_runtime
    root, configuration = load_run(args)
    step = selected_step(root, args.step)
    with operation(root, 'investigation runtime cleanup'):
        pending = [entry for entry in build_status(root, configuration)['investigation_cleanup_required']
                   if entry['step'] == step]
        if not pending:
            raise ValueError('no unresolved investigation runtime allocation for selected checkpoint')
        index_path = root / 'investigation-cleanups/index.json'
        index_path.parent.mkdir(exist_ok=True)
        index = json.loads(index_path.read_text()) if index_path.exists() else []
        for entry in pending:
            allocation = Path(entry['allocation'])
            relative = f'investigation-cleanups/{uuid.uuid4()}'
            index.append(relative + '/cleanup.json')
            write_json(index_path, index)
            cleanup_runtime(allocation, allocation.parent / 'reviewer-runtime.json', root / relative)
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
    lines = ['## Run', '', f"Run: {report['run_name']} ({report['run_mode']})", '',
             f"Application: {report['application']} @ {report['package_version']}",
             f"Condition: {(report.get('condition') or {}).get('id', 'unknown')}",
             f"Investigation: {report.get('investigation', 'not configured')}",
             f"Evaluator: {evaluator}" + ('.' if binding else '; primary scores unavailable.'),
             f"Artifacts: {report['root']}", '', '## Checkpoints', '',
             '| Checkpoint | Development | Evaluation | Attempts | Retained source |',
             '| --- | --- | --- | --- | --- |']
    if report.get('source_run'):
        source = report['source_run']
        lines[lines.index('## Checkpoints'):lines.index('## Checkpoints')] = [
            f"Evaluation-only import of development run {source['run_name']} ({source['root']}); "
            'development measurements are copied evidence, not new model usage.', '']
    for checkpoint in report['checkpoints']:
        development = 'finished' if checkpoint['status'] == 'pending_evaluation' else checkpoint['status']
        primary = checkpoint.get('primary_assessment')
        evaluation = primary['outcome'] if primary else 'not run'
        lines.append(f"| {checkpoint['id']} | {development} | {evaluation} | {checkpoint['attempts']} | {display(checkpoint['source'])} |")
    log_lines = []
    for checkpoint in report['checkpoints']:
        if checkpoint['stdout']:
            log_lines.extend([f"{checkpoint['id']} Codex events: {checkpoint['stdout']}",
                              f"{checkpoint['id']} errors: {checkpoint['stderr']}"])
    if log_lines:
        lines.extend(['', '## Logs', '', *log_lines])
    assessments = report.get('assessments', [])
    if assessments:
        lines.extend(['', '## Hidden evaluations', '', '| Checkpoint | Assessment | Role | Functional | Security | Outcome | Evidence |',
                      '| --- | --- | --- | --- | --- | --- | --- |'])
        for assessment in assessments:
            lines.append(f"| {assessment['checkpoint']} | {assessment['attempt']} | {assessment['role']} | "
                         f"{assessment['functional']} | {assessment['security']} | {assessment['outcome']} | {assessment['artifact']} |")
        details = []
        for assessment in assessments:
            if assessment.get('error'):
                details.append(f"- {assessment['checkpoint']} assessment {assessment['attempt']}: "
                               + ' '.join(str(assessment['error']).split()))
            for check in assessment.get('checks', []):
                if check['status'] != 'pass':
                    reason = ' '.join(str(check.get('detail', '')).split())
                    details.append(f"- {assessment['checkpoint']} assessment {assessment['attempt']} "
                                   f"{check['id']}: {check['status']}" + (f' — {reason}' if reason else ''))
        if details:
            lines.extend(['', '### Evaluation details', '', *details])
    if report.get('investigations'):
        lines.extend(['', '## AI reviews', '', '| Checkpoint | Investigation | Claims | Verified root causes | Seconds | Tokens | Evidence |',
                      '| --- | --- | ---: | ---: | ---: | ---: | --- |'])
        for entry in report['investigations']:
            resources = entry.get('resources') or {}
            tokens = resources.get('reported_tokens') or {}
            lines.append(f"| {entry['checkpoint']} | {entry['status']} | {len(entry['claims'])} | "
                         f"{len(entry['verified_root_causes'])} | {display(resources.get('elapsed_seconds'))} | "
                         f"{display(tokens.get('total_tokens'))} | {entry['artifact']} |")
    lines.extend(['', resource.markdown(report['resources']).rstrip()])
    for entry in report['runtime_cleanup_required']:
        lines.extend(['', f"Runtime cleanup pending for {entry['step']}: {entry['allocation']}",
                      f"Cleanup: python3 -m principiis cleanup --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']}"])
    for entry in report.get('evaluation_cleanup_required', []):
        lines.extend(['', f"Evaluation cleanup pending: {entry['artifact']}",
                      f"Cleanup: python3 -m principiis cleanup-evaluation --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['checkpoint']}"])
    for entry in report.get('investigation_cleanup_required', []):
        lines.extend(['', f"Investigation cleanup pending: {entry['allocation']}",
                      f"Cleanup: principiis cleanup-investigation --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']}"])
    for entry in report['previews']:
        evidence = entry['evidence'] or {}
        lines.extend(['', f"{entry['step']} preview evidence: {report['root']}/{entry['artifact']}",
                      f"Preview: {evidence.get('outcome', 'unknown')} ; URL: {display(evidence.get('url'))}",
                      f"Cleanup: python3 -m principiis preview --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']} --stop"])
    action = report['next_action']
    lines.extend(['', '## Next action', '',
                  action['action'] + (' ' + action['step'] if action['step'] else ''), action['explanation']])
    if action['action'] in ('develop', 'retry', 'evaluate') and action['step']:
        number = int(action['step'].split('-')[-1])
        command = 'develop' if action['action'] in ('develop', 'retry') else 'evaluate'
        retry = ' --retry' if action['action'] == 'retry' else ''
        runs_root = shlex.quote(str(Path(report['root']).parent))
        lines.append(f"Command: principiis {command} --runs-root {runs_root} "
                     f"--run {report['run_name']} --step {number}{retry}")
    return '\n'.join(lines) + '\n'


def development_summary(report, step):
    """Show the result of this development action without repeating the full run report."""
    checkpoint = next(entry for entry in report['checkpoints'] if entry['id'] == step)
    completed = checkpoint['completed']
    lines = [f"Development {step}: {'completed' if completed else checkpoint['status']}"]
    if checkpoint['source']:
        lines.append(f"{'Saved snapshot' if completed else 'Retained workspace'}: {checkpoint['source']}")
    lines.append('Evaluation: not run by this command')
    action = report['next_action']
    if action['action'] in ('develop', 'retry', 'evaluate') and action['step']:
        command = 'develop' if action['action'] in ('develop', 'retry') else 'evaluate'
        number = int(action['step'].split('-')[-1])
        retry = ' --retry' if action['action'] == 'retry' else ''
        label = 'Next in the bound evaluator sequence' if command == 'evaluate' else 'Next'
        lines.append(f"{label}: principiis {command} --runs-root "
                     f"{shlex.quote(str(Path(report['root']).parent))} --run {report['run_name']} "
                     f"--step {number}{retry}")
    else:
        lines.append(f"Operator next action: {action['action']} — {action['explanation']}")
    lines.append(f"Full status: principiis status --runs-root "
                 f"{shlex.quote(str(Path(report['root']).parent))} --run {report['run_name']}")
    return '\n'.join(lines) + '\n'


CSV_FIELDS = ('run_name', 'source_run', 'run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact',
              'stage', 'role', 'functional', 'security', 'evaluator_version', 'evaluator_manifest_sha256',
              'snapshot_manifest_sha256', 'source', 'stdout', 'stderr', 'development_seconds', 'evaluation_seconds', 'investigation_seconds', 'started_at', 'finished_at',
              *resource.CATEGORIES, 'total_tokens', 'local_peak_sampled_rss_bytes', 'local_memory_scope',
              'container_peak_sampled_bytes', 'container_memory_scope', 'actual_spending', 'hosted_model_memory')


def csv_report(report):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    assessments = {entry['artifact']: entry for entry in report.get('assessments', [])}
    for attempt in report['resources']['attempts']:
        stage = 'evaluation' if attempt['stages']['evaluation'] and not attempt['stages']['development'] else 'development'
        evidence = attempt['stages'][stage]
        tokens, memory = evidence.get('tokens') or {}, evidence.get('memory') or {}
        container_memory = evidence.get('container_memory') or {}
        directory = Path(attempt['artifact']).parent
        result = assessments.get(attempt['artifact'])
        if result is None:
            result = json.loads(Path(attempt['artifact']).read_text()) if Path(attempt['artifact']).is_file() else {}
        row = {key: attempt.get(key) for key in ('run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact')}
        provenance = result.get('provenance') or {}
        row.update(run_name=report['run_name'], source_run=(report.get('source_run') or {}).get('run_name'),
                   stage=stage, role=result.get('role'),
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
    for investigation in report.get('investigations', []):
        agent = investigation.get('agent') or {}
        tokens = (investigation.get('resources') or {}).get('reported_tokens') or {}
        memory = agent.get('memory') or {}
        directory = Path(investigation['artifact']).parent
        row = dict(run_name=report['run_name'], source_run=(report.get('source_run') or {}).get('run_name'),
                   run_id=report.get('run_id'), checkpoint=investigation['checkpoint'],
                   attempt=directory.name, session_id=None, outcome=investigation['status'],
                   artifact=investigation['artifact'], stage='investigation',
                   role='primary' if directory.name == '1' else 'rerun',
                   source=investigation.get('snapshot'), stdout=str(directory / 'agent.stdout'),
                   stderr=str(directory / 'agent.stderr'),
                   investigation_seconds=(investigation.get('resources') or {}).get('elapsed_seconds'),
                   started_at=agent.get('started_at'), finished_at=agent.get('finished_at'),
                   local_peak_sampled_rss_bytes=memory.get('peak_sampled_rss_bytes'),
                   local_memory_scope=memory.get('scope'), actual_spending=None, hosted_model_memory=None)
        row.update({key: tokens.get(key) for key in (*resource.CATEGORIES, 'total_tokens')})
        writer.writerow({key: display(row.get(key)) for key in CSV_FIELDS})
    return stream.getvalue()


def save_report(report):
    root = Path(report['root']) / 'reports'
    root.mkdir(exist_ok=True)
    write_json(root / 'development.json', report)
    (root / 'development.csv').write_text(csv_report(report))
    (root / 'development.md').write_text(markdown(report))
    return root


def show_logs(args):
    root, _ = load_run(args)
    path = root / 'operator-events.jsonl'
    offset = 0
    inactive_seen = False
    while True:
        if path.is_file():
            with path.open() as stream:
                stream.seek(offset)
                while line := stream.readline():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if args.step and event.get('step') != selected_step(root, args.step):
                        continue
                    if args.stage and event.get('stage') != args.stage:
                        continue
                    if args.format == 'json':
                        print(json.dumps(event, sort_keys=True), flush=True)
                    else:
                        detail = ' '.join(str(event[key]) for key in ('type', 'item_type', 'outcome', 'artifact')
                                          if event.get(key))
                        print(f"{event.get('time', 'unknown')} {event.get('stage', 'stage')} "
                              f"{event.get('step') or ''} {event.get('event', 'event')} {detail}".strip(), flush=True)
                offset = stream.tell()
        if not args.follow:
            break
        if not active_operation(root)['active']:
            if inactive_seen:
                break
            inactive_seen = True
        else:
            inactive_seen = False
        time.sleep(.5)


def outcome_details(report, command, step, *, ai_review=False):
    if command == 'develop':
        checkpoint = next((entry for entry in report['checkpoints'] if entry['id'] == step), None)
        return {'outcome': checkpoint['status'], 'artifact': checkpoint['result']} if checkpoint else {}
    if command == 'evaluate' and not ai_review:
        assessments = [entry for entry in report['assessments'] if entry['checkpoint'] == step]
        return {'outcome': assessments[-1]['outcome'], 'artifact': assessments[-1]['artifact']} if assessments else {}
    if command == 'evaluate' and ai_review:
        investigations = [entry for entry in report['investigations'] if entry['checkpoint'] == step]
        return {'outcome': investigations[-1]['status'], 'artifact': investigations[-1]['artifact']} if investigations else {}
    return {}


def compare(args):
    from .comparison import compare_reports, csv_report as comparison_csv, markdown as comparison_markdown
    reports = [build_status(*load_run(SimpleNamespace(run=run, runs_root=args.runs_root)))
               for run in args.runs]
    result = compare_reports(reports)
    if args.format == 'json':
        print(json.dumps(result, indent=2))
    elif args.format == 'csv':
        print(comparison_csv(result), end='')
    else:
        print(comparison_markdown(result), end='')


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    comparison = sub.add_parser('compare')
    comparison.add_argument('--runs', nargs='+', required=True)
    comparison.add_argument('--runs-root', default=os.environ.get('PRINCIPIIS_RUNS_ROOT', str(Path.home() / '.local/share/principiis/runs')))
    comparison.add_argument('--format', choices=('markdown', 'json', 'csv'), default='markdown')
    commands = {}
    for name in ('init', 'derive-evaluation', 'develop', 'evaluate', 'status', 'preview', 'cleanup', 'cleanup-evaluation', 'cleanup-investigation', 'report', 'logs'):
        command = sub.add_parser(name)
        commands[name] = command
        command.add_argument('--run', required=True)
        command.add_argument('--runs-root', default=os.environ.get('PRINCIPIIS_RUNS_ROOT', str(Path.home() / '.local/share/principiis/runs')))
        command.add_argument('--format', choices=('markdown', 'json', 'csv') if name == 'report' else ('markdown', 'json'), default='markdown')
        command.add_argument('--verbose', action='store_true')
    commands['init'].add_argument('--application', choices=(
        'document-portal', 'customer-support-desk', 'team-expense-manager',
        'workflow-dashboard', 'online-marketplace'), required=True)
    commands['init'].add_argument('--runtime-config', required=True)
    commands['init'].add_argument('--evaluator-manifest', help='qualified hidden evaluator release; required for ten steps')
    commands['init'].add_argument('--condition', default='baseline')
    commands['init'].add_argument('--investigation', choices=('none', 'final', 'each-step'), default='final')
    commands['init'].add_argument('--steps', type=int, choices=(3, 10), default=3)
    commands['derive-evaluation'].add_argument('--source-run', required=True, help='completed original run in the same runs root')
    commands['derive-evaluation'].add_argument('--evaluator-manifest', required=True, help='qualified replacement evaluator release')
    commands['develop'].add_argument('--step', required=True)
    commands['develop'].add_argument('--retry', action='store_true')
    evaluation_target = commands['evaluate'].add_mutually_exclusive_group(required=True)
    evaluation_target.add_argument('--step')
    evaluation_target.add_argument('--final', action='store_true', help='review the final frozen checkpoint')
    commands['evaluate'].add_argument('--ai-review', action='store_true', help='run the separate Codex security review instead of hidden checks')
    commands['evaluate'].add_argument('--rerun', action='store_true')
    commands['evaluate'].add_argument('--config', help='separate reviewer configuration; required with --ai-review')
    commands['evaluate'].add_argument('--prompt', help='reviewer prompt; required with --ai-review')
    commands['evaluate'].add_argument('--prompt-version', help='reviewer prompt version; required with --ai-review')
    commands['preview'].add_argument('--step', required=True)
    commands['preview'].add_argument('--preview-config')
    commands['preview'].add_argument('--stop', action='store_true')
    commands['logs'].add_argument('--follow', action='store_true')
    commands['logs'].add_argument('--step')
    commands['logs'].add_argument('--stage', choices=('develop', 'evaluate', 'ai-review'))
    commands['cleanup'].add_argument('--step', required=True)
    commands['cleanup-evaluation'].add_argument('--step', required=True)
    commands['cleanup-investigation'].add_argument('--step', required=True)
    args = parser.parse_args()
    if args.command == 'evaluate':
        if args.final and not args.ai_review:
            parser.error('--final requires --ai-review')
        if args.ai_review and not all((args.config, args.prompt, args.prompt_version)):
            parser.error('--ai-review requires --config, --prompt and --prompt-version')
        if not args.ai_review and any((args.config, args.prompt, args.prompt_version)):
            parser.error('reviewer options require --ai-review')
    try:
        if args.command == 'compare':
            compare(args)
            return
        if args.command == 'logs':
            show_logs(args)
            return
        progress = None
        if args.command in ('develop', 'evaluate'):
            from .progress import Progress
            root, _ = load_run(args)
            step = final_step(root) if args.command == 'evaluate' and args.final else selected_step(root, args.step)
            stage = 'ai-review' if args.command == 'evaluate' and args.ai_review else args.command
            progress = Progress(root, stage, step, verbose=args.verbose,
                                interval=10 if args.verbose else 30)
        if progress:
            with progress:
                if args.command == 'develop':
                    report = develop(args)
                elif args.command == 'evaluate' and not args.ai_review:
                    report = evaluate(args)
                else:
                    report = investigate_run(args)
                progress.result_details = outcome_details(report, args.command, step,
                                                          ai_review=args.command == 'evaluate' and args.ai_review)
        elif args.command == 'init':
            report = initialize(args)
        elif args.command == 'derive-evaluation':
            report = derive_evaluation(args)
        elif args.command == 'preview':
            report = preview(args)
        elif args.command == 'cleanup':
            report = cleanup(args)
        elif args.command == 'cleanup-evaluation':
            report = cleanup_evaluation(args)
        elif args.command == 'cleanup-investigation':
            report = cleanup_investigation(args)
        else:
            report = build_status(*load_run(args))
        if args.command == 'report':
            save_report(report)
        print(json.dumps(report, indent=2) if args.format == 'json' else csv_report(report) if args.format == 'csv'
              else development_summary(report, step) if args.command == 'develop' and not args.verbose
              else markdown(report), end='')
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
